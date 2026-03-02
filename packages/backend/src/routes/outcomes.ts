import { Router, Request, Response } from 'express';
import prisma from '../db';
import { runDailyOutcomes } from '../jobs/dailyOutcomes';

const router = Router();

// GET /api/outcomes/patient/:id — all 180 days grouped by line type
router.get('/patient/:id', async (req: Request, res: Response) => {
  try {
    const predictions = await prisma.outcomePrediction.findMany({
      where: { patientId: req.params.id },
      orderBy: [{ lineType: 'asc' }, { dayNumber: 'asc' }],
    });

    // Group by line type for frontend
    const grouped: Record<string, typeof predictions> = {
      MY_PATH: [],
      FULL_POTENTIAL: [],
      MINIMAL_EFFORT: [],
    };
    for (const p of predictions) {
      if (grouped[p.lineType]) grouped[p.lineType].push(p);
    }

    res.json({ predictions, grouped });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// POST /api/outcomes/recalculate/:id — force recalculation
router.post('/recalculate/:id', async (req: Request, res: Response) => {
  try {
    await runDailyOutcomes();
    res.json({ message: 'Outcomes recalculated' });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

export default router;
