import { Router, Request, Response } from 'express';
import prisma from '../db';
import { emitNudgeSent } from '../sockets';
import { processEscalations } from '../jobs/escalations';

const router = Router();

// POST /api/nudges/send — simulate sending a nudge
router.post('/send', async (req: Request, res: Response) => {
  try {
    const { patientId, activityId, channel, tier, messageContent } = req.body as {
      patientId: string;
      activityId: string;
      channel: 'WHATSAPP' | 'APP_NUDGE' | 'VOICE_BOT' | 'AGENT_TASK';
      tier: number;
      messageContent: Record<string, unknown>;
    };

    const nudge = await prisma.nudgeEvent.create({
      data: {
        patientId,
        activityId,
        channel,
        tier,
        scheduledAt: new Date(),
        sentAt: new Date(),
        status: 'SENT',
        messageContent,
      },
    });

    // Simulate delivery log
    console.log(`[MOCK ${channel}] Sent to patient ${patientId}: `, messageContent);
    emitNudgeSent(patientId, channel, messageContent);

    res.status(201).json(nudge);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// GET /api/nudges/patient/:id
router.get('/patient/:id', async (req: Request, res: Response) => {
  try {
    const nudges = await prisma.nudgeEvent.findMany({
      where: { patientId: req.params.id },
      orderBy: { scheduledAt: 'desc' },
      take: 50,
    });
    res.json(nudges);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// POST /api/nudges/:id/respond — simulate patient response
router.post('/:id/respond', async (req: Request, res: Response) => {
  try {
    const { response } = req.body as { response: string };

    const nudge = await prisma.nudgeEvent.update({
      where: { id: req.params.id },
      data: {
        respondedAt: new Date(),
        response,
        status: 'RESPONDED',
      },
    });

    // Cancel subsequent tiers for same activity
    await prisma.nudgeEvent.updateMany({
      where: {
        activityId: nudge.activityId,
        tier: { gt: nudge.tier },
        status: { in: ['PENDING', 'SENT'] },
      },
      data: { status: 'CANCELLED' },
    });

    res.json({ nudge, message: 'Response recorded and subsequent tiers cancelled' });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// POST /api/nudges/process-escalations — cron-triggered
router.post('/process-escalations', async (_req: Request, res: Response) => {
  try {
    await processEscalations();
    res.json({ message: 'Escalations processed' });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

export default router;
