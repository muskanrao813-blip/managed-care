import { Router, Request, Response } from 'express';
import prisma from '../db';
import {
  allocateProgram,
  calculateEngagementScore,
  detectPersona,
  build180DayPlan,
} from '@managed-care/shared';
import type { Gender, HraAnswers, Cohort } from '@managed-care/shared';
import { runDailyOutcomes } from '../jobs/dailyOutcomes';
import { nanoid } from 'nanoid';

const router = Router();

// POST /api/patients — create patient + run scoring + build 180-day plan
router.post('/', async (req: Request, res: Response) => {
  try {
    const { name, age, gender, department, city, labValues, hraAnswers } = req.body as {
      name: string;
      age: number;
      gender: Gender;
      department: string;
      city: string;
      labValues: Record<string, number>;
      hraAnswers: HraAnswers;
    };

    // Score
    const allocation = allocateProgram(labValues, gender);
    const engagementScore = calculateEngagementScore(hraAnswers);
    const persona = detectPersona(hraAnswers, engagementScore, age, allocation.cohort as Cohort);

    const patient = await prisma.patient.create({
      data: {
        name,
        age,
        gender,
        department,
        city,
        programId: allocation.programId,
        cohort: allocation.cohort,
        engagementScore,
        personaStyle: persona.motivationalStyle,
        engagementCapacity: persona.engagementCapacity,
        baselineLabValues: labValues,
        currentLabValues: labValues,
      },
    });

    // Save baseline lab report
    await prisma.labReport.create({
      data: {
        patientId: patient.id,
        values: labValues,
        source: 'MANUAL',
        isBaseline: true,
      },
    });

    // Save HRA
    await prisma.hraResponse.create({
      data: {
        patientId: patient.id,
        dayNumber: 1,
        answers: hraAnswers as Record<string, unknown>,
        engagementScoreResult: engagementScore,
        personaResult: persona.motivationalStyle,
      },
    });

    // Build 180-day plan
    const planActivities = build180DayPlan({
      id: patient.id,
      programId: patient.programId,
      cohort: patient.cohort,
      engagementScore: patient.engagementScore,
      personaStyle: patient.personaStyle,
      engagementCapacity: patient.engagementCapacity,
      points: patient.points,
      gender: patient.gender,
      age: patient.age,
      hra: hraAnswers,
    });

    // Batch insert in chunks to avoid hitting limits
    const chunkSize = 500;
    for (let i = 0; i < planActivities.length; i += chunkSize) {
      const chunk = planActivities.slice(i, i + chunkSize);
      await prisma.activity180Day.createMany({ data: chunk });
    }

    // Create welcome call SFDC task
    const sfdcTaskId = `SFDC-${nanoid(10)}`;
    await prisma.sfdcTask.create({
      data: {
        patientId: patient.id,
        sfdcTaskId,
        type: 'WELCOME_CALL',
        priority: 'HIGH',
        status: 'OPEN',
        subject: `Welcome Call — ${patient.name}`,
        description: `New patient ${patient.name} enrolled in ${patient.programId} program (${patient.cohort} cohort). Please conduct welcome call within 24 hours.`,
        callScript: `Hello ${patient.name}! Welcome to our managed care program. I'm calling to introduce you to your personalized ${patient.programId} management plan. Your HbA1c/lab values indicate you've been enrolled in our ${patient.cohort} care program. Today I'd like to walk you through your 180-day journey and answer any questions.`,
      },
    });

    // Seed initial outcome predictions
    await runDailyOutcomes();

    res.status(201).json({
      patient,
      allocation,
      engagementScore,
      persona,
      sfdcWelcomeTaskId: sfdcTaskId,
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: (err as Error).message });
  }
});

// GET /api/patients
router.get('/', async (_req: Request, res: Response) => {
  try {
    const patients = await prisma.patient.findMany({
      orderBy: { createdAt: 'desc' },
    });
    res.json(patients);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// GET /api/patients/:id
router.get('/:id', async (req: Request, res: Response) => {
  try {
    const patient = await prisma.patient.findUnique({
      where: { id: req.params.id },
      include: {
        appointments: { orderBy: { scheduledDate: 'asc' } },
        sfdcTasks: { orderBy: { createdAt: 'desc' }, take: 10 },
      },
    });
    if (!patient) return res.status(404).json({ error: 'Patient not found' });
    res.json(patient);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// PATCH /api/patients/:id
router.patch('/:id', async (req: Request, res: Response) => {
  try {
    const patient = await prisma.patient.update({
      where: { id: req.params.id },
      data: req.body as Record<string, unknown>,
    });
    res.json(patient);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// POST /api/patients/:id/lab-report — submit new lab report
router.post('/:id/lab-report', async (req: Request, res: Response) => {
  try {
    const { labValues, source = 'CHECK_IN' } = req.body as {
      labValues: Record<string, number>;
      source?: 'UPLOAD' | 'MANUAL' | 'CHECK_IN';
    };

    const patient = await prisma.patient.findUniqueOrThrow({ where: { id: req.params.id } });
    const currentLab = patient.currentLabValues as Record<string, number>;

    const labReport = await prisma.labReport.create({
      data: {
        patientId: patient.id,
        values: labValues,
        source,
        isBaseline: false,
      },
    });

    // Check for worsening values (SGPT, HbA1c, LDL, Creatinine, TSH)
    const primaryMap: Record<string, string> = {
      DIABETES: 'HbA1c', DYSLIPIDEMIA: 'LDL', LIVER: 'SGPT', KIDNEY: 'Creatinine', THYROID: 'TSH',
    };
    const primaryKey = primaryMap[patient.programId];
    const oldVal = currentLab[primaryKey];
    const newVal = labValues[primaryKey];

    if (primaryKey && oldVal !== undefined && newVal !== undefined && newVal > oldVal) {
      const sfdcTaskId = `SFDC-${nanoid(10)}`;
      await prisma.sfdcTask.create({
        data: {
          patientId: patient.id,
          sfdcTaskId,
          type: 'WORSENING_LAB',
          priority: 'URGENT',
          status: 'OPEN',
          subject: `Worsening ${primaryKey} — ${patient.name}`,
          description: `${primaryKey} worsened from ${oldVal} to ${newVal}. Immediate review required.`,
          callScript: `Hello ${patient.name}, we received your latest lab results. Your ${primaryKey} has increased from ${oldVal} to ${newVal}. This is concerning and I'd like to discuss next steps with you immediately.`,
        },
      });
    }

    // Update current lab values
    await prisma.patient.update({
      where: { id: patient.id },
      data: { currentLabValues: labValues },
    });

    // Recalculate outcome predictions
    await runDailyOutcomes();

    res.json({ labReport, message: 'Lab report submitted and predictions recalculated' });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// GET /api/patients/:id/lab-reports
router.get('/:id/lab-reports', async (req: Request, res: Response) => {
  try {
    const reports = await prisma.labReport.findMany({
      where: { patientId: req.params.id },
      orderBy: { reportDate: 'desc' },
    });
    res.json(reports);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// POST /api/patients/:id/hra — submit HRA
router.post('/:id/hra', async (req: Request, res: Response) => {
  try {
    const { hraAnswers } = req.body as { hraAnswers: HraAnswers };
    const patient = await prisma.patient.findUniqueOrThrow({ where: { id: req.params.id } });

    const engagementScore = calculateEngagementScore(hraAnswers);
    const persona = detectPersona(
      hraAnswers,
      engagementScore,
      patient.age,
      patient.cohort as Cohort
    );

    const hraResponse = await prisma.hraResponse.create({
      data: {
        patientId: patient.id,
        dayNumber: patient.dayNumber,
        answers: hraAnswers as Record<string, unknown>,
        engagementScoreResult: engagementScore,
        personaResult: persona.motivationalStyle,
      },
    });

    await prisma.patient.update({
      where: { id: patient.id },
      data: {
        engagementScore,
        personaStyle: persona.motivationalStyle,
        engagementCapacity: persona.engagementCapacity,
      },
    });

    res.json({ hraResponse, engagementScore, persona });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// GET /api/patients/:id/hra
router.get('/:id/hra', async (req: Request, res: Response) => {
  try {
    const responses = await prisma.hraResponse.findMany({
      where: { patientId: req.params.id },
      orderBy: { responseDate: 'desc' },
    });
    res.json(responses);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// GET /api/patients/:id/plan
router.get('/:id/plan', async (req: Request, res: Response) => {
  try {
    const activities = await prisma.activity180Day.findMany({
      where: { patientId: req.params.id },
      orderBy: [{ dayNumber: 'asc' }, { isEvergreen: 'asc' }],
    });
    res.json(activities);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// GET /api/patients/:id/plan/:day
router.get('/:id/plan/:day', async (req: Request, res: Response) => {
  try {
    const activities = await prisma.activity180Day.findMany({
      where: { patientId: req.params.id, dayNumber: parseInt(req.params.day) },
      orderBy: [{ isClinical: 'desc' }, { isEvergreen: 'asc' }],
    });
    res.json(activities);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// POST /api/patients/:id/plan/rebuild
router.post('/:id/plan/rebuild', async (req: Request, res: Response) => {
  try {
    const patient = await prisma.patient.findUniqueOrThrow({ where: { id: req.params.id } });

    await prisma.activity180Day.deleteMany({ where: { patientId: patient.id } });

    const planActivities = build180DayPlan({
      id: patient.id,
      programId: patient.programId,
      cohort: patient.cohort,
      engagementScore: patient.engagementScore,
      personaStyle: patient.personaStyle,
      engagementCapacity: patient.engagementCapacity,
      points: patient.points,
      gender: patient.gender,
      age: patient.age,
    });

    const chunkSize = 500;
    for (let i = 0; i < planActivities.length; i += chunkSize) {
      await prisma.activity180Day.createMany({ data: planActivities.slice(i, i + chunkSize) });
    }

    res.json({ message: 'Plan rebuilt', totalActivities: planActivities.length });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

export default router;
