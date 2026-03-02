import prisma from '../db';
import { emitOutcomeUpdated } from '../sockets';

const BASE_POTENTIAL: Record<string, Record<string, number>> = {
  DIABETES: { MODERATE: 0.8, HIGH: 1.5, VERY_HIGH: 2.5 },
  DYSLIPIDEMIA: { MODERATE: 20, HIGH: 35, VERY_HIGH: 55 },
  LIVER: { MODERATE: 15, HIGH: 30, VERY_HIGH: 50 },
  KIDNEY: { MODERATE: 0.05, HIGH: 0.10, VERY_HIGH: 0.20 },
  THYROID: { MODERATE: 1.0, HIGH: 2.5, VERY_HIGH: 4.0 },
};

const INFLECTION_PARAMS: Record<string, { inflection: number; k: number }> = {
  VERY_HIGH: { inflection: 45, k: 0.08 },
  HIGH: { inflection: 60, k: 0.07 },
  MODERATE: { inflection: 75, k: 0.06 },
};

function sCurve(dayNumber: number, cohort: string): number {
  const { inflection, k } = INFLECTION_PARAMS[cohort] ?? INFLECTION_PARAMS.MODERATE;
  return 1 / (1 + Math.exp(-k * (dayNumber - inflection)));
}

function getPrimaryBiomarker(programId: string, labValues: Record<string, number>): number {
  const biomarkerMap: Record<string, string> = {
    DIABETES: 'HbA1c',
    DYSLIPIDEMIA: 'LDL',
    LIVER: 'SGPT',
    KIDNEY: 'Creatinine',
    THYROID: 'TSH',
  };
  return labValues[biomarkerMap[programId] ?? ''] ?? 0;
}

export async function runDailyOutcomes(): Promise<void> {
  const patients = await prisma.patient.findMany();

  for (const patient of patients) {
    const labValues = patient.currentLabValues as Record<string, number>;
    const baseline = getPrimaryBiomarker(patient.programId, labValues);
    const basePot = BASE_POTENTIAL[patient.programId]?.[patient.cohort] ?? 1;

    const totalActivities = await prisma.activity180Day.count({
      where: { patientId: patient.id, dayNumber: { lte: patient.dayNumber } },
    });
    const completedActivities = await prisma.activity180Day.count({
      where: { patientId: patient.id, dayNumber: { lte: patient.dayNumber }, status: 'COMPLETED' },
    });
    const adherenceRate = totalActivities > 0 ? completedActivities / totalActivities : 0;

    const completedConsults = await prisma.clinicalAppointment.count({
      where: { patientId: patient.id, status: 'COMPLETED', type: 'DOCTOR' },
    });
    const completedDiet = await prisma.clinicalAppointment.count({
      where: { patientId: patient.id, status: 'COMPLETED', type: 'DIETICIAN' },
    });
    const consultMultiplier = 1 + completedConsults * 0.03 + completedDiet * 0.02;

    const timeFactor = sCurve(patient.dayNumber, patient.cohort);

    const calcPrediction = (adhRate: number): number =>
      Math.max(0, baseline - basePot * adhRate * timeFactor * consultMultiplier);

    const myPath = calcPrediction(adherenceRate);
    const fullPotential = calcPrediction(1.0);
    const minimalEffort = calcPrediction(0.3);

    const today = new Date();

    const upsert = async (lineType: string, value: number): Promise<void> => {
      const id = `${patient.id}_${patient.dayNumber}_${lineType}`;
      await prisma.outcomePrediction.upsert({
        where: { id },
        create: {
          id,
          patientId: patient.id,
          date: today,
          predictedValue: value,
          baselineValue: baseline,
          adherenceContribution: adherenceRate,
          consultationContribution: consultMultiplier,
          dayNumber: patient.dayNumber,
          lineType,
        },
        update: { predictedValue: value },
      });
    };

    await upsert('MY_PATH', myPath);
    await upsert('FULL_POTENTIAL', fullPotential);
    await upsert('MINIMAL_EFFORT', minimalEffort);

    emitOutcomeUpdated(patient.id, patient.dayNumber, myPath);
  }
}
