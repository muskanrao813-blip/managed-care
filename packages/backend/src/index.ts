import 'dotenv/config';
import { createServer } from 'http';
import { Server as SocketIOServer } from 'socket.io';
import app from './app';
import { setupSockets } from './sockets';
import { startCronJobs } from './jobs';

const PORT = process.env.PORT ?? 3001;

const httpServer = createServer(app);
const io = new SocketIOServer(httpServer, {
  cors: { origin: '*', methods: ['GET', 'POST', 'PATCH', 'DELETE'] },
});

setupSockets(io);
startCronJobs();

httpServer.listen(PORT, () => {
  console.log(`🚀 Managed Care API running on http://localhost:${PORT}`);
});
