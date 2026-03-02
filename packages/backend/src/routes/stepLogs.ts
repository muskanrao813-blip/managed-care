import { Router, Request, Response } from 'express';
import prisma from '../db';

const router = Router();

// POST /api/step-logs
router.post('/', async (req: Request, res: Response) => {
  try {
    const { patientId, stepsLogged, targetSteps, source = 'MANUAL' } = req.body as {
      patientId: string;
      stepsLogged: number;
      targetSteps: number;
      source?: 'MANUAL' | 'WEARABLE' | 'PEDOMETER';
    };

    const log = await prisma.stepLog.create({
      data: {
        patientId,
        date: new Date(),
        stepsLogged,
        targetSteps,
        source,
        targetMet: stepsLogged >= targetSteps,
      },
    });

    // Update streak
    if (log.targetMet) {
      const patient = await prisma.patient.findUniqueOrThrow({ where: { id: patientId } });
      const streaks = patient.streaks as { medication: number; steps: number; mealLog: number };
      await prisma.patient.update({
        where: { id: patientId },
        data: { streaks: { ...streaks, steps: streaks.steps + 1 } },
      });
    }

    res.status(201).json(log);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// GET /api/step-logs/patient/:id/today
router.get('/patient/:id/today', async (req: Request, res: Response) => {
  try {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    const log = await prisma.stepLog.findFirst({
      where: { patientId: req.params.id, date: { gte: today, lt: tomorrow } },
      orderBy: { createdAt: 'desc' },
    });
    res.json(log);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

export default router;
