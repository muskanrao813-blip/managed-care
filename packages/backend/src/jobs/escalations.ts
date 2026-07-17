import { nanoid } from 'nanoid';
import prisma from '../db';
import { emitEscalationFired, emitAgentTaskCreated } from '../sockets';

export async function processEscalations(): Promise<void> {
  const now = new Date();
  const sixHoursAgo = new Date(now.getTime() - 6 * 60 * 60 * 1000);
  const twelveHoursAgo = new Date(now.getTime() - 12 * 60 * 60 * 1000);
  const twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);

  const sentNudges = await prisma.nudgeEvent.findMany({
    where: { status: 'SENT' },
    include: { patient: true, activity: true },
  });

  for (const nudge of sentNudges) {
    if (!nudge.sentAt) continue;

    if (nudge.tier === 1 && nudge.sentAt <= sixHoursAgo) {
      await prisma.nudgeEvent.create({
        data: {
          patientId: nudge.patientId,
          activityId: nudge.activityId,
          channel: 'APP_NUDGE',
          tier: 2,
          scheduledAt: now,
          sentAt: now,
          status: 'SENT',
          messageContent: {
            message: `Reminder: complete your ${nudge.activity.activityType} activity`,
            activityId: nudge.activityId,
          },
        },
      });
      emitEscalationFired(nudge.patientId, 2, 'APP_NUDGE');
      await prisma.nudgeEvent.update({ where: { id: nudge.id }, data: { status: 'IGNORED' } });
    } else if (nudge.tier === 2 && nudge.sentAt <= twelveHoursAgo) {
      const hourNow = now.getHours();
      const inWindow = hourNow >= 9 && hourNow < 22;
      const callTime = inWindow ? now : new Date(now.setHours(9, 0, 0, 0));

      await prisma.nudgeEvent.create({
        data: {
          patientId: nudge.patientId,
          activityId: nudge.activityId,
          channel: 'VOICE_BOT',
          tier: 3,
          scheduledAt: callTime,
          sentAt: inWindow ? now : undefined,
          status: inWindow ? 'SENT' : 'PENDING',
          messageContent: {
            script: `Hello! This is your managed care voice assistant calling about your ${nudge.activity.activityType}. We noticed it hasn't been completed. Can we help you get started?`,
            isClinical: nudge.activity.isClinical,
          },
        },
      });
      if (inWindow) emitEscalationFired(nudge.patientId, 3, 'VOICE_BOT');
      await prisma.nudgeEvent.update({ where: { id: nudge.id }, data: { status: 'IGNORED' } });
    } else if (nudge.tier === 3 && nudge.activity.isClinical && nudge.sentAt <= twentyFourHoursAgo) {
      const sfdcTaskId = `SFDC-${nanoid(10)}`;
      await prisma.sfdcTask.create({
        data: {
          patientId: nudge.patientId,
          nudgeEventId: nudge.id,
          sfdcTaskId,
          type: 'MISSED_CONSULT',
          priority: 'HIGH',
          status: 'OPEN',
          subject: `Missed ${nudge.activity.activityType} — ${nudge.patient.name}`,
          description: `Patient ${nudge.patient.name} (Day ${nudge.patient.dayNumber}) did not respond to WhatsApp, App, and Voice Bot nudges for ${nudge.activity.activityType}. Escalating to care coordinator.`,
          callScript: `Hello, I'm calling from your managed care team regarding a missed ${nudge.activity.activityType} appointment. We want to make sure you receive the best care possible. How can we help?`,
        },
      });
      emitAgentTaskCreated(sfdcTaskId, nudge.patientId, 'MISSED_CONSULT', 'HIGH');
      await prisma.nudgeEvent.update({ where: { id: nudge.id }, data: { status: 'IGNORED' } });
    }
  }

  // Check for 3+ consecutive missed medication reminders
  const patients = await prisma.patient.findMany({ select: { id: true, name: true, dayNumber: true } });
  for (const patient of patients) {
    const recentMedLogs = await prisma.activity180Day.findMany({
      where: {
        patientId: patient.id,
        activityType: { in: ['medication_reminder_morning', 'medication_reminder_evening'] },
        dayNumber: { gte: patient.dayNumber - 3 },
      },
      orderBy: { dayNumber: 'desc' },
    });

    const allMissed = recentMedLogs.length >= 3 && recentMedLogs.every((a) => a.status === 'MISSED');
    if (allMissed) {
      const existing = await prisma.sfdcTask.findFirst({
        where: { patientId: patient.id, type: 'MISSED_MEDICATION', status: { in: ['OPEN', 'IN_PROGRESS'] } },
      });
      if (!existing) {
        const sfdcTaskId = `SFDC-${nanoid(10)}`;
        await prisma.sfdcTask.create({
          data: {
            patientId: patient.id,
            sfdcTaskId,
            type: 'MISSED_MEDICATION',
            priority: 'URGENT',
            status: 'OPEN',
            subject: `3+ Consecutive Missed Medications — ${patient.name}`,
            description: `Patient has missed medication reminders for 3 or more consecutive days.`,
            callScript: `Hello, we noticed you've missed your medication for the past few days. Missing medication can significantly impact your health outcomes. Are there any barriers to taking your medication? We're here to help.`,
          },
        });
        emitAgentTaskCreated(sfdcTaskId, patient.id, 'MISSED_MEDICATION', 'URGENT');
      }
    }
  }
}
