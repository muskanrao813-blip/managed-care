import { Router, Request, Response } from 'express';
import prisma from '../db';

const router = Router();

// GET /api/sfdc/tasks — all open tasks (agent view)
router.get('/tasks', async (req: Request, res: Response) => {
  try {
    const { status, priority } = req.query as { status?: string; priority?: string };
    const tasks = await prisma.sfdcTask.findMany({
      where: {
        ...(status ? { status: status as 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'ESCALATED' } : {}),
        ...(priority ? { priority: priority as 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT' } : {}),
      },
      include: {
        patient: {
          select: {
            id: true, name: true, age: true, programId: true, cohort: true,
            dayNumber: true, engagementScore: true, personaStyle: true,
            currentLabValues: true,
          },
        },
      },
      orderBy: [{ priority: 'desc' }, { createdAt: 'asc' }],
    });
    res.json(tasks);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// GET /api/sfdc/tasks/patient/:id
router.get('/tasks/patient/:id', async (req: Request, res: Response) => {
  try {
    const tasks = await prisma.sfdcTask.findMany({
      where: { patientId: req.params.id },
      orderBy: { createdAt: 'desc' },
    });
    res.json(tasks);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// PATCH /api/sfdc/tasks/:id — update status/outcome
router.patch('/tasks/:id', async (req: Request, res: Response) => {
  try {
    const { status, outcome, agentNotes } = req.body as {
      status?: string;
      outcome?: string;
      agentNotes?: string;
    };

    const updateData: Record<string, unknown> = {};
    if (status) updateData.status = status;
    if (outcome) updateData.outcome = outcome;
    if (agentNotes) updateData.agentNotes = agentNotes;
    if (status === 'RESOLVED') updateData.resolvedAt = new Date();

    const task = await prisma.sfdcTask.update({
      where: { id: req.params.id },
      data: updateData,
    });

    res.json(task);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

export default router;
