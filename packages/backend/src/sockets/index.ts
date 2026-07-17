import { Server as SocketIOServer, Socket } from 'socket.io';

let ioInstance: SocketIOServer | null = null;

export function setupSockets(io: SocketIOServer): void {
  ioInstance = io;
  io.on('connection', (socket: Socket) => {
    console.log(`Client connected: ${socket.id}`);

    socket.on('subscribe:patient', (patientId: string) => {
      void socket.join(`patient:${patientId}`);
    });

    socket.on('subscribe:agent', () => {
      void socket.join('agent:all');
    });

    socket.on('disconnect', () => {
      console.log(`Client disconnected: ${socket.id}`);
    });
  });
}

export function getIO(): SocketIOServer {
  if (!ioInstance) throw new Error('Socket.IO not initialized');
  return ioInstance;
}

export function emitNudgeSent(patientId: string, channel: string, content: unknown): void {
  try {
    const io = getIO();
    io.to(`patient:${patientId}`).to('agent:all').emit('patient:nudge-sent', { patientId, channel, content });
  } catch (_) { /* socket not ready */ }
}

export function emitActivityCompleted(patientId: string, activityId: string, points: number): void {
  try {
    getIO().to(`patient:${patientId}`).emit('patient:activity-completed', { patientId, activityId, points });
  } catch (_) { /* socket not ready */ }
}

export function emitEscalationFired(patientId: string, tier: number, channel: string): void {
  try {
    getIO().to(`patient:${patientId}`).to('agent:all').emit('patient:escalation-fired', { patientId, tier, channel });
  } catch (_) { /* socket not ready */ }
}

export function emitOutcomeUpdated(patientId: string, day: number, predictedValue: number): void {
  try {
    getIO().to(`patient:${patientId}`).emit('patient:outcome-updated', { patientId, day, predictedValue });
  } catch (_) { /* socket not ready */ }
}

export function emitAgentTaskCreated(sfdcTaskId: string, patientId: string, type: string, priority: string): void {
  try {
    getIO().to('agent:all').emit('agent:task-created', { sfdcTaskId, patientId, type, priority });
  } catch (_) { /* socket not ready */ }
}
