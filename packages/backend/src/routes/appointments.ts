import { Router, Request, Response } from 'express';
import prisma from '../db';
import { nanoid } from 'nanoid';
import { emitAgentTaskCreated } from '../sockets';

const router = Router();

// GET /api/appointments/patient/:id
router.get('/patient/:id', async (req: Request, res: Response) => {
  try {
    const appointments = await prisma.clinicalAppointment.findMany({
      where: { patientId: req.params.id },
      orderBy: { scheduledDate: 'asc' },
    });
    res.json(appointments);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// POST /api/appointments
router.post('/', async (req: Request, res: Response) => {
  try {
    const appointment = await prisma.clinicalAppointment.create({
      data: req.body as {
        patientId: string;
        type: 'DOCTOR' | 'DIETICIAN' | 'LAB_TEST';
        scheduledDate: string;
        providerName: string;
      },
    });
    res.status(201).json(appointment);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// PATCH /api/appointments/:id — confirm / update status
router.patch('/:id', async (req: Request, res: Response) => {
  try {
    const { status, confirmationChannel } = req.body as {
      status: string;
      confirmationChannel?: string;
    };

    const appt = await prisma.clinicalAppointment.findUniqueOrThrow({ where: { id: req.params.id } });
    const patient = await prisma.patient.findUniqueOrThrow({ where: { id: appt.patientId } });

    const updateData: Record<string, unknown> = { status };
    if (status === 'CONFIRMED') {
      updateData.confirmedAt = new Date();
      if (confirmationChannel) updateData.confirmationChannel = confirmationChannel;
    }
    if (status === 'MISSED') {
      // Create SFDC task for missed appointment
      const sfdcTaskId = `SFDC-${nanoid(10)}`;
      await prisma.sfdcTask.create({
        data: {
          patientId: appt.patientId,
          sfdcTaskId,
          type: appt.type === 'LAB_TEST' ? 'MISSED_LAB' : 'MISSED_CONSULT',
          priority: 'HIGH',
          status: 'OPEN',
          subject: `Missed ${appt.type} — ${patient.name}`,
          description: `Patient ${patient.name} missed ${appt.type} appointment with ${appt.providerName} scheduled for ${appt.scheduledDate.toISOString()}.`,
          callScript: `Hello ${patient.name}, I'm calling about your missed ${appt.type} appointment with ${appt.providerName}. We'd like to reschedule at your earliest convenience.`,
        },
      });
      emitAgentTaskCreated(sfdcTaskId, appt.patientId, 'MISSED_CONSULT', 'HIGH');
    }

    const updated = await prisma.clinicalAppointment.update({
      where: { id: req.params.id },
      data: updateData,
    });

    // Compose confirmation message (NEVER says "points credited" at this stage)
    let confirmationMessage: string | null = null;
    if (status === 'CONFIRMED') {
      const dateStr = new Date(appt.scheduledDate).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
      if (appt.type === 'DOCTOR') {
        confirmationMessage = `Your appointment is confirmed with ${appt.providerName} on ${dateStr}. Video link will be sent 30 minutes before. Reply 'HELP' if you need support.`;
      } else if (appt.type === 'LAB_TEST') {
        confirmationMessage = `Your lab test is confirmed at ${appt.providerName} on ${dateStr}. Fasting required from midnight. Bring your HealthCare+ ID.`;
      } else if (appt.type === 'DIETICIAN') {
        confirmationMessage = `Your session is confirmed with ${appt.providerName} on ${dateStr}. She has reviewed your last 14 days of meal logs.`;
      }
    }

    res.json({ appointment: updated, confirmationMessage });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// POST /api/appointments/:id/submit-prescription — doctor submits notes → completion + points
router.post('/:id/submit-prescription', async (req: Request, res: Response) => {
  try {
    const { notes } = req.body as { notes: string };

    const appt = await prisma.clinicalAppointment.update({
      where: { id: req.params.id },
      data: {
        status: 'COMPLETED',
        completedAt: new Date(),
        prescriptionSubmittedAt: new Date(),
        notes,
        pointsAwarded: true,
      },
    });

    // Award 50 points for doctor consultation completion
    const patient = await prisma.patient.findUniqueOrThrow({ where: { id: appt.patientId } });
    const newPoints = patient.points + 50;
    await prisma.patient.update({
      where: { id: appt.patientId },
      data: { points: newPoints, level: getLevel(newPoints) },
    });

    res.json({
      appointment: appt,
      pointsMessage: '✓ Appointment completed. 50 points credited to your account.',
    });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// POST /api/appointments/:id/receive-lab-results
router.post('/:id/receive-lab-results', async (req: Request, res: Response) => {
  try {
    const { labValues } = req.body as { labValues?: Record<string, number> };

    const appt = await prisma.clinicalAppointment.update({
      where: { id: req.params.id },
      data: {
        status: 'COMPLETED',
        completedAt: new Date(),
        labResultsReceivedAt: new Date(),
        pointsAwarded: true,
      },
    });

    if (labValues) {
      await prisma.labReport.create({
        data: {
          patientId: appt.patientId,
          values: labValues,
          source: 'CHECK_IN',
        },
      });
      await prisma.patient.update({
        where: { id: appt.patientId },
        data: { currentLabValues: labValues },
      });
    }

    const patient = await prisma.patient.findUniqueOrThrow({ where: { id: appt.patientId } });
    const newPoints = patient.points + 30;
    await prisma.patient.update({
      where: { id: appt.patientId },
      data: { points: newPoints, level: getLevel(newPoints) },
    });

    res.json({
      appointment: appt,
      pointsMessage: '✓ Lab test completed. 30 points credited to your account.',
    });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// POST /api/appointments/:id/generate-diet-plan
router.post('/:id/generate-diet-plan', async (req: Request, res: Response) => {
  try {
    const { planNotes } = req.body as { planNotes?: string };

    const appt = await prisma.clinicalAppointment.update({
      where: { id: req.params.id },
      data: {
        status: 'COMPLETED',
        completedAt: new Date(),
        dietPlanGeneratedAt: new Date(),
        notes: planNotes,
        pointsAwarded: true,
      },
    });

    const patient = await prisma.patient.findUniqueOrThrow({ where: { id: appt.patientId } });
    const newPoints = patient.points + 40;
    await prisma.patient.update({
      where: { id: appt.patientId },
      data: { points: newPoints, level: getLevel(newPoints) },
    });

    res.json({
      appointment: appt,
      pointsMessage: '✓ Dietician session completed. 40 points credited to your account.',
    });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

function getLevel(points: number): 'BRONZE' | 'SILVER' | 'GOLD' | 'PLATINUM' {
  if (points >= 600) return 'PLATINUM';
  if (points >= 300) return 'GOLD';
  if (points >= 100) return 'SILVER';
  return 'BRONZE';
}

export default router;
