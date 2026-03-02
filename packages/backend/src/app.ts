import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';

import patientsRouter from './routes/patients';
import activitiesRouter from './routes/activities';
import appointmentsRouter from './routes/appointments';
import nudgesRouter from './routes/nudges';
import outcomesRouter from './routes/outcomes';
import sfdcRouter from './routes/sfdc';
import wellnessRouter from './routes/wellness';
import stepLogsRouter from './routes/stepLogs';
import mealLogsRouter from './routes/mealLogs';
import moodLogsRouter from './routes/moodLogs';

const app = express();

app.use(cors({ origin: '*' }));
app.use(express.json({ limit: '10mb' }));

app.use('/api/patients', patientsRouter);
app.use('/api/activities', activitiesRouter);
app.use('/api/appointments', appointmentsRouter);
app.use('/api/nudges', nudgesRouter);
app.use('/api/outcomes', outcomesRouter);
app.use('/api/sfdc', sfdcRouter);
app.use('/api/wellness-sessions', wellnessRouter);
app.use('/api/step-logs', stepLogsRouter);
app.use('/api/meal-logs', mealLogsRouter);
app.use('/api/mood-logs', moodLogsRouter);

app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error(err.stack);
  res.status(500).json({ error: err.message });
});

export default app;
