import { Router, Request, Response } from 'express';
import prisma from '../db';

const router = Router();

// GET /api/wellness-sessions/patient/:id/:activityId
router.get('/patient/:id/:activityId', async (req: Request, res: Response) => {
  try {
    const session = await prisma.wellnessSession.findFirst({
      where: { patientId: req.params.id, activityId: req.params.activityId },
      orderBy: { startedAt: 'desc' },
    });
    res.json(session);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// POST /api/wellness-sessions
router.post('/', async (req: Request, res: Response) => {
  try {
    const session = await prisma.wellnessSession.create({
      data: req.body as {
        patientId: string;
        activityId: string;
        sessionType: 'MEDITATION' | 'BOX_BREATHING' | 'CBT' | 'PROGRESSIVE_RELAXATION' | 'GUIDED_IMAGERY' | 'GROUNDING';
      },
    });
    res.status(201).json(session);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// PATCH /api/wellness-sessions/:id
router.patch('/:id', async (req: Request, res: Response) => {
  try {
    const { durationSeconds, completed } = req.body as {
      durationSeconds?: number;
      completed?: boolean;
    };
    const session = await prisma.wellnessSession.update({
      where: { id: req.params.id },
      data: {
        durationSeconds,
        completed,
        completedAt: completed ? new Date() : undefined,
      },
    });
    res.json(session);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

export default router;
