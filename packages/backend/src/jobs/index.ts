import cron from 'node-cron';
import { runDailyOutcomes } from './dailyOutcomes';
import { processEscalations } from './escalations';

export function startCronJobs(): void {
  cron.schedule('59 23 * * *', async () => {
    console.log('[CRON] Running daily outcome predictions...');
    await runDailyOutcomes();
  });

  cron.schedule('*/30 * * * *', async () => {
    console.log('[CRON] Processing escalations...');
    await processEscalations();
  });

  console.log('Cron jobs started');
}
