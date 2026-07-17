import { Router, Request, Response } from 'express';
import prisma from '../db';

const router = Router();

// POST /api/mood-logs
router.post('/', async (req: Request, res: Response) => {
  try {
    const { patientId, score, note } = req.body as {
      patientId: string;
      score: number;
      note?: string;
    };

    const log = await prisma.moodLog.create({
      data: { patientId, date: new Date(), score, note },
    });
    res.status(201).json(log);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// GET /api/mood-logs/patient/:id/recent
router.get('/patient/:id/recent', async (req: Request, res: Response) => {
  try {
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

    const logs = await prisma.moodLog.findMany({
      where: { patientId: req.params.id, date: { gte: sevenDaysAgo } },
      orderBy: { date: 'desc' },
    });
    res.json(logs);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

export default router;
