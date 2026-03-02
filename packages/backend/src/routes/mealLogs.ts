import { Router, Request, Response } from 'express';
import prisma from '../db';

const router = Router();

// POST /api/meal-logs
router.post('/', async (req: Request, res: Response) => {
  try {
    const log = await prisma.mealLog.create({
      data: req.body as {
        patientId: string;
        mealType: 'BREAKFAST' | 'LUNCH' | 'DINNER' | 'SNACK';
        description?: string;
        calories?: number;
        photoUrl?: string;
        nutritionData?: Record<string, unknown>;
      },
    });

    // Update meal streak
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const todayMeals = await prisma.mealLog.count({
      where: { patientId: log.patientId, loggedAt: { gte: today, lt: tomorrow } },
    });

    if (todayMeals >= 2) {
      const patient = await prisma.patient.findUniqueOrThrow({ where: { id: log.patientId } });
      const streaks = patient.streaks as { medication: number; steps: number; mealLog: number };
      await prisma.patient.update({
        where: { id: log.patientId },
        data: { streaks: { ...streaks, mealLog: streaks.mealLog + 1 } },
      });
    }

    res.status(201).json(log);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// GET /api/meal-logs/patient/:id/today
router.get('/patient/:id/today', async (req: Request, res: Response) => {
  try {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    const logs = await prisma.mealLog.findMany({
      where: { patientId: req.params.id, loggedAt: { gte: today, lt: tomorrow } },
      orderBy: { loggedAt: 'asc' },
    });
    res.json(logs);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

export default router;
