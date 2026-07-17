import { PrismaClient } from '@prisma/client';
import { allocateProgram, calculateEngagementScore, detectPersona, build180DayPlan } from '@managed-care/shared';
import type { HraAnswers, Gender, Cohort } from '@managed-care/shared';
import { nanoid } from 'nanoid';

const prisma = new PrismaClient();

const PATIENTS: Array<{
  name: string; age: number; gender: Gender; department: string; city: string;
  labValues: Record<string, number>; hra: HraAnswers;
}> = [
  {
    name: 'Rajesh Kumar',
    age: 52,
    gender: 'MALE',
    department: 'Engineering',
    city: 'Mumbai',
    labValues: {
      HbA1c: 9.2,
      TSH: 2.1, T3: 120, T4: 8.5,
      Albumin: 4.0, ALP: 85, BilirubinDirect: 0.15, BilirubinTotal: 0.8,
      GGTP: 40, SGOT: 35, SGPT: 42,
      BUN: 16, Creatinine: 1.0, Urea: 30, UricAcid: 5.5, BUNCreatRatio: 16,
      TotalCholesterol: 220, HDL: 42, LDL: 145, NonHDL: 178, Triglycerides: 165,
    },
    hra: { gender: 'MALE', dob: '1972-03-15', weightKg: 88, heightCm: 172, alcohol: 'Occasional', sleepHours: 6.5, stress: 'Moderate' },
  },
  {
    name: 'Priya Sharma',
    age: 38,
    gender: 'FEMALE',
    department: 'Finance',
    city: 'Delhi',
    labValues: {
      HbA1c: 6.8,
      TSH: 8.5, T3: 72, T4: 4.2,
      Albumin: 4.2, ALP: 90, BilirubinDirect: 0.12, BilirubinTotal: 0.7,
      GGTP: 28, SGOT: 25, SGPT: 28,
      BUN: 14, Creatinine: 0.85, Urea: 28, UricAcid: 4.2, BUNCreatRatio: 16.5,
      TotalCholesterol: 195, HDL: 55, LDL: 118, NonHDL: 140, Triglycerides: 145,
    },
    hra: { gender: 'FEMALE', dob: '1986-07-22', weightKg: 72, heightCm: 162, alcohol: 'Never', sleepHours: 5.5, stress: 'High', anxietyFrequency: 'Often' },
  },
  {
    name: 'Mohammed Ali',
    age: 45,
    gender: 'MALE',
    department: 'Operations',
    city: 'Hyderabad',
    labValues: {
      HbA1c: 7.5,
      TSH: 2.8, T3: 135, T4: 9.2,
      Albumin: 2.8, ALP: 145, BilirubinDirect: 0.65, BilirubinTotal: 1.8,
      GGTP: 78, SGOT: 95, SGPT: 165,
      BUN: 18, Creatinine: 1.05, Urea: 35, UricAcid: 6.2, BUNCreatRatio: 17.1,
      TotalCholesterol: 185, HDL: 38, LDL: 122, NonHDL: 147, Triglycerides: 185,
    },
    hra: { gender: 'MALE', dob: '1979-11-08', weightKg: 92, heightCm: 175, alcohol: 'Light', sleepHours: 7.0, stress: 'High' },
  },
  {
    name: 'Sunita Patel',
    age: 58,
    gender: 'FEMALE',
    department: 'HR',
    city: 'Ahmedabad',
    labValues: {
      HbA1c: 5.8,
      TSH: 3.2, T3: 145, T4: 10.1,
      Albumin: 4.1, ALP: 75, BilirubinDirect: 0.10, BilirubinTotal: 0.6,
      GGTP: 22, SGOT: 20, SGPT: 24,
      BUN: 21, Creatinine: 1.25, Urea: 38, UricAcid: 7.5, BUNCreatRatio: 16.8,
      TotalCholesterol: 175, HDL: 45, LDL: 95, NonHDL: 130, Triglycerides: 130,
    },
    hra: { gender: 'FEMALE', dob: '1966-04-12', weightKg: 68, heightCm: 158, alcohol: 'Never', sleepHours: 7.5, stress: 'VeryLow' },
  },
  {
    name: 'Arjun Nair',
    age: 29,
    gender: 'MALE',
    department: 'IT',
    city: 'Bangalore',
    labValues: {
      HbA1c: 5.4,
      TSH: 2.5, T3: 152, T4: 9.8,
      Albumin: 4.3, ALP: 65, BilirubinDirect: 0.08, BilirubinTotal: 0.5,
      GGTP: 32, SGOT: 28, SGPT: 30,
      BUN: 12, Creatinine: 0.90, Urea: 22, UricAcid: 5.8, BUNCreatRatio: 13.3,
      TotalCholesterol: 245, HDL: 35, LDL: 172, NonHDL: 210, Triglycerides: 210,
    },
    hra: { gender: 'MALE', dob: '1995-09-18', weightKg: 78, heightCm: 178, alcohol: 'Moderate', sleepHours: 7.5, stress: 'Moderate', anxietyFrequency: 'Sometimes' },
  },
  {
    name: 'Kavitha Reddy',
    age: 43,
    gender: 'FEMALE',
    department: 'Marketing',
    city: 'Chennai',
    labValues: {
      HbA1c: 13.5,
      TSH: 2.9, T3: 130, T4: 8.8,
      Albumin: 3.8, ALP: 88, BilirubinDirect: 0.14, BilirubinTotal: 0.9,
      GGTP: 35, SGOT: 30, SGPT: 38,
      BUN: 15, Creatinine: 0.88, Urea: 28, UricAcid: 4.9, BUNCreatRatio: 17.0,
      TotalCholesterol: 235, HDL: 42, LDL: 162, NonHDL: 193, Triglycerides: 198,
    },
    hra: { gender: 'FEMALE', dob: '1981-06-30', weightKg: 82, heightCm: 160, alcohol: 'Never', sleepHours: 8.0, stress: 'ExtHigh', anxietyFrequency: 'AlmostEveryDay' },
  },
];

async function main(): Promise<void> {
  console.log('Seeding database...');

  // Clear existing data
  await prisma.nudgeEvent.deleteMany();
  await prisma.sfdcTask.deleteMany();
  await prisma.outcomePrediction.deleteMany();
  await prisma.activity180Day.deleteMany();
  await prisma.clinicalAppointment.deleteMany();
  await prisma.wellnessSession.deleteMany();
  await prisma.stepLog.deleteMany();
  await prisma.mealLog.deleteMany();
  await prisma.moodLog.deleteMany();
  await prisma.labReport.deleteMany();
  await prisma.hraResponse.deleteMany();
  await prisma.patient.deleteMany();

  for (const p of PATIENTS) {
    const allocation = allocateProgram(p.labValues, p.gender);
    const engagementScore = calculateEngagementScore(p.hra);
    const persona = detectPersona(p.hra, engagementScore, p.age, allocation.cohort as Cohort);

    const patient = await prisma.patient.create({
      data: {
        name: p.name,
        age: p.age,
        gender: p.gender,
        department: p.department,
        city: p.city,
        programId: allocation.programId,
        cohort: allocation.cohort,
        engagementScore,
        personaStyle: persona.motivationalStyle,
        engagementCapacity: persona.engagementCapacity,
        baselineLabValues: p.labValues,
        currentLabValues: p.labValues,
        dayNumber: 15, // Seed at day 15 so there's history
        points: Math.floor(Math.random() * 80) + 10,
      },
    });

    console.log(`Created patient: ${patient.name} → ${allocation.programId} ${allocation.cohort} (${persona.motivationalStyle})`);

    // Lab report
    await prisma.labReport.create({
      data: { patientId: patient.id, values: p.labValues, source: 'MANUAL', isBaseline: true },
    });

    // HRA response
    await prisma.hraResponse.create({
      data: {
        patientId: patient.id,
        dayNumber: 1,
        answers: p.hra as Record<string, unknown>,
        engagementScoreResult: engagementScore,
        personaResult: persona.motivationalStyle,
      },
    });

    // 180-day plan
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
      hra: p.hra,
    });

    const chunkSize = 500;
    for (let i = 0; i < planActivities.length; i += chunkSize) {
      await prisma.activity180Day.createMany({ data: planActivities.slice(i, i + chunkSize) });
    }

    // Simulate some completed activities for days 1-14
    const earlyActivities = await prisma.activity180Day.findMany({
      where: { patientId: patient.id, dayNumber: { lte: 14 } },
      take: 100,
    });

    for (const activity of earlyActivities) {
      if (Math.random() > 0.35) {
        await prisma.activity180Day.update({
          where: { id: activity.id },
          data: {
            status: 'COMPLETED',
            completedAt: new Date(Date.now() - Math.random() * 14 * 24 * 60 * 60 * 1000),
            pointsEarned: activity.isEvergreen ? 1 : 2,
          },
        });
      }
    }

    // Upcoming appointments
    const futureDate = (daysFromNow: number): Date => {
      const d = new Date();
      d.setDate(d.getDate() + daysFromNow);
      return d;
    };

    await prisma.clinicalAppointment.create({
      data: {
        patientId: patient.id,
        type: 'DOCTOR',
        scheduledDate: futureDate(3),
        providerName: 'Dr. Anand Rao',
        status: 'SCHEDULED',
      },
    });

    await prisma.clinicalAppointment.create({
      data: {
        patientId: patient.id,
        type: 'LAB_TEST',
        scheduledDate: futureDate(7),
        providerName: 'Apollo Diagnostics',
        status: 'SCHEDULED',
      },
    });

    await prisma.clinicalAppointment.create({
      data: {
        patientId: patient.id,
        type: 'DIETICIAN',
        scheduledDate: futureDate(10),
        providerName: 'Ms. Meera Iyer',
        status: 'SCHEDULED',
      },
    });

    // Welcome SFDC task
    await prisma.sfdcTask.create({
      data: {
        patientId: patient.id,
        sfdcTaskId: `SFDC-${nanoid(10)}`,
        type: 'WELCOME_CALL',
        priority: 'HIGH',
        status: 'OPEN',
        subject: `Welcome Call — ${patient.name}`,
        description: `New patient ${patient.name} enrolled in ${allocation.programId} (${allocation.cohort}). Engagement score: ${engagementScore}. Persona: ${persona.motivationalStyle}.`,
        callScript: `Hello ${patient.name}! Welcome to the Managed Care Program. I'm your dedicated care coordinator. You've been enrolled in our ${allocation.programId} management program at the ${allocation.cohort} care level. I'd love to walk you through your personalized 180-day plan and answer any questions. Do you have 10 minutes?`,
      },
    });

    // Mood logs for last 7 days
    for (let d = 1; d <= 7; d++) {
      const date = new Date();
      date.setDate(date.getDate() - d);
      await prisma.moodLog.create({
        data: { patientId: patient.id, date, score: Math.floor(Math.random() * 3) + 2 },
      });
    }

    // Seed initial outcome predictions (simplified)
    const primaryBiomarkerMap: Record<string, string> = {
      DIABETES: 'HbA1c', DYSLIPIDEMIA: 'LDL', LIVER: 'SGPT', KIDNEY: 'Creatinine', THYROID: 'TSH',
    };
    const basePotMap: Record<string, Record<string, number>> = {
      DIABETES: { MODERATE: 0.8, HIGH: 1.5, VERY_HIGH: 2.5 },
      DYSLIPIDEMIA: { MODERATE: 20, HIGH: 35, VERY_HIGH: 55 },
      LIVER: { MODERATE: 15, HIGH: 30, VERY_HIGH: 50 },
      KIDNEY: { MODERATE: 0.05, HIGH: 0.10, VERY_HIGH: 0.20 },
      THYROID: { MODERATE: 1.0, HIGH: 2.5, VERY_HIGH: 4.0 },
    };

    const baselineKey = primaryBiomarkerMap[allocation.programId] ?? 'HbA1c';
    const baseline = (p.labValues[baselineKey] as number) ?? 0;
    const basePot = basePotMap[allocation.programId]?.[allocation.cohort] ?? 1;

    const sCurve = (day: number): number => {
      const params: Record<string, { i: number; k: number }> = {
        VERY_HIGH: { i: 45, k: 0.08 }, HIGH: { i: 60, k: 0.07 }, MODERATE: { i: 75, k: 0.06 },
      };
      const { i, k } = params[allocation.cohort] ?? params.MODERATE;
      return 1 / (1 + Math.exp(-k * (day - i)));
    };

    const predictionData: {
      id: string; patientId: string; date: Date; predictedValue: number; baselineValue: number;
      dayNumber: number; lineType: string; adherenceContribution: number; consultationContribution: number;
    }[] = [];

    for (let day = 1; day <= 180; day++) {
      const t = sCurve(day);
      const date = new Date();
      date.setDate(date.getDate() - 15 + day);

      predictionData.push(
        { id: `${patient.id}_${day}_MY_PATH`, patientId: patient.id, date, predictedValue: Math.max(0, baseline - basePot * 0.65 * t), baselineValue: baseline, dayNumber: day, lineType: 'MY_PATH', adherenceContribution: 0.65, consultationContribution: 1.0 },
        { id: `${patient.id}_${day}_FULL_POTENTIAL`, patientId: patient.id, date, predictedValue: Math.max(0, baseline - basePot * 1.0 * t), baselineValue: baseline, dayNumber: day, lineType: 'FULL_POTENTIAL', adherenceContribution: 1.0, consultationContribution: 1.0 },
        { id: `${patient.id}_${day}_MINIMAL_EFFORT`, patientId: patient.id, date, predictedValue: Math.max(0, baseline - basePot * 0.3 * t), baselineValue: baseline, dayNumber: day, lineType: 'MINIMAL_EFFORT', adherenceContribution: 0.3, consultationContribution: 1.0 },
      );
    }

    for (let i = 0; i < predictionData.length; i += 500) {
      await prisma.outcomePrediction.createMany({ data: predictionData.slice(i, i + 500) });
    }

    console.log(`  → ${planActivities.length} activities, 3 appointments, predictions seeded`);
  }

  console.log('\n✅ Database seeded successfully with 6 patients!');
  console.log('\nPatient programs:');
  for (const p of PATIENTS) {
    const alloc = allocateProgram(p.labValues, p.gender);
    console.log(`  ${p.name}: ${alloc.programId} ${alloc.cohort}`);
  }
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
