import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { sfdcApi, outcomesApi } from '../../lib/api';
import { RefreshCw, Clock, AlertTriangle, Phone, CheckCircle, XCircle, AlertOctagon } from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';

type SfdcTask = {
  id: string; sfdcTaskId: string; type: string; priority: string; status: string;
  subject: string; description: string; callScript: string; outcome?: string;
  agentNotes?: string; createdAt: string;
  patient: {
    id: string; name: string; age: number; programId: string; cohort: string;
    dayNumber: number; engagementScore: number; personaStyle: string;
    currentLabValues: Record<string, number>;
  };
};

type OutcomeData = {
  grouped: { MY_PATH: { dayNumber: number; predictedValue: number }[] };
};

const PRIORITY_COLORS: Record<string, string> = {
  URGENT: 'bg-red-100 text-red-800 border-red-300',
  HIGH: 'bg-orange-100 text-orange-800 border-orange-300',
  MEDIUM: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  LOW: 'bg-gray-100 text-gray-700 border-gray-200',
};

const TYPE_ICONS: Record<string, React.ReactNode> = {
  WELCOME_CALL: <Phone size={14} className="text-blue-600" />,
  MISSED_CONSULT: <AlertTriangle size={14} className="text-orange-600" />,
  MISSED_LAB: <AlertTriangle size={14} className="text-orange-600" />,
  MISSED_MEDICATION: <AlertOctagon size={14} className="text-red-600" />,
  WORSENING_LAB: <AlertOctagon size={14} className="text-red-600" />,
  EMERGENCY: <AlertOctagon size={14} className="text-red-600" />,
};

const OUTCOME_OPTIONS = [
  { value: 'CONTACTED_RESCHEDULED', label: 'Contacted — Rescheduled', icon: <CheckCircle size={14} />, color: 'text-green-600' },
  { value: 'CONTACTED_REFUSED', label: 'Contacted — Refused', icon: <XCircle size={14} />, color: 'text-red-600' },
  { value: 'NO_ANSWER_RETRY', label: 'No Answer — Retry in 2h', icon: <Clock size={14} />, color: 'text-yellow-600' },
  { value: 'ESCALATED', label: 'Escalated to Clinical Manager', icon: <AlertTriangle size={14} />, color: 'text-orange-600' },
];

const PRIMARY_BIOMARKERS: Record<string, string> = {
  DIABETES: 'HbA1c', DYSLIPIDEMIA: 'LDL', LIVER: 'SGPT', KIDNEY: 'Creatinine', THYROID: 'TSH',
};

export default function AgentView() {
  const [selectedTask, setSelectedTask] = useState<SfdcTask | null>(null);
  const [filter, setFilter] = useState<string>('ALL');
  const [agentNotes, setAgentNotes] = useState('');
  const queryClient = useQueryClient();

  const { data: tasks = [], refetch } = useQuery({
    queryKey: ['sfdc-tasks', filter],
    queryFn: () => sfdcApi.getTasks(filter !== 'ALL' ? { priority: filter } : {}).then((r) => r.data as SfdcTask[]),
    refetchInterval: 30_000,
  });

  const { data: outcomeData } = useQuery({
    queryKey: ['outcomes', selectedTask?.patient.id],
    queryFn: () => outcomesApi.get(selectedTask!.patient.id).then((r) => r.data as OutcomeData),
    enabled: !!selectedTask?.patient.id,
  });

  const updateTaskMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { status?: string; outcome?: string; agentNotes?: string } }) =>
      sfdcApi.updateTask(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['sfdc-tasks'] });
      void refetch();
    },
  });

  const resolveTask = (outcome: string) => {
    if (!selectedTask) return;
    updateTaskMutation.mutate({
      id: selectedTask.id,
      data: {
        status: outcome === 'ESCALATED' ? 'ESCALATED' : outcome.startsWith('CONTACTED') ? 'RESOLVED' : 'IN_PROGRESS',
        outcome,
        agentNotes,
      },
    });
  };

  const chartData = (outcomeData?.grouped?.MY_PATH ?? []).filter((_, i) => i % 15 === 0).map((p) => ({
    day: p.dayNumber, value: parseFloat(p.predictedValue.toFixed(2)),
  }));

  const openTasks = tasks.filter((t) => t.status === 'OPEN' || t.status === 'IN_PROGRESS');
  const urgentCount = tasks.filter((t) => t.priority === 'URGENT' && t.status !== 'RESOLVED').length;

  return (
    <div className="flex h-[calc(100vh-52px)] bg-gray-50">
      {/* LEFT COLUMN — Task Queue */}
      <aside className="w-72 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <h1 className="font-bold text-gray-900">Agent Dashboard</h1>
            <button onClick={() => void refetch()} className="text-gray-400 hover:text-gray-600">
              <RefreshCw size={16} />
            </button>
          </div>
          {urgentCount > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs text-red-700 font-medium">
              ⚠ {urgentCount} urgent task{urgentCount > 1 ? 's' : ''} need attention
            </div>
          )}
          <div className="flex flex-wrap gap-1 mt-2">
            {['ALL', 'URGENT', 'HIGH', 'MEDIUM', 'LOW'].map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={`text-xs px-2 py-1 rounded-full border transition-colors ${
                  filter === f ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}>
                {f}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {openTasks.length === 0 && (
            <div className="p-4 text-center text-gray-400 text-sm mt-8">No open tasks</div>
          )}
          {openTasks.map((task) => {
            const bioKey = PRIMARY_BIOMARKERS[task.patient.programId];
            const bioVal = bioKey ? task.patient.currentLabValues[bioKey] : null;
            return (
              <button key={task.id} onClick={() => { setSelectedTask(task); setAgentNotes(''); }}
                className={`w-full text-left p-3 border-b border-gray-100 transition-all hover:bg-blue-50 ${
                  selectedTask?.id === task.id ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''
                }`}>
                <div className="flex items-center gap-2 mb-1">
                  {TYPE_ICONS[task.type]}
                  <span className={`badge text-xs ${PRIORITY_COLORS[task.priority]}`}>{task.priority}</span>
                  {task.status === 'IN_PROGRESS' && <span className="badge bg-blue-100 text-blue-700 text-xs">Active</span>}
                </div>
                <p className="font-medium text-sm text-gray-900 truncate">{task.patient.name}</p>
                <p className="text-xs text-gray-500">{task.patient.programId} • Day {task.patient.dayNumber}</p>
                {bioVal && <p className="text-xs text-orange-600 mt-0.5 font-medium">{bioKey}: {bioVal}</p>}
                <p className="text-xs text-gray-400 mt-1 truncate">{task.subject}</p>
                <div className="flex items-center gap-2 mt-1.5">
                  <Clock size={10} className="text-gray-300" />
                  <span className="text-xs text-gray-400">
                    {new Date(task.createdAt).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </aside>

      {/* CENTRE COLUMN — Task Detail */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selectedTask ? (
          <div className="flex items-center justify-center h-full text-gray-400">
            <div className="text-center">
              <Phone size={48} className="mx-auto mb-3 opacity-30" />
              <p>Select a task from the queue</p>
            </div>
          </div>
        ) : (
          <div className="max-w-xl space-y-4">
            {/* Patient summary */}
            <div className="card border-blue-200 bg-blue-50">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-bold text-gray-900 text-lg">{selectedTask.patient.name}</h2>
                  <p className="text-sm text-gray-600">Age {selectedTask.patient.age} • {selectedTask.patient.programId} • Day {selectedTask.patient.dayNumber}</p>
                </div>
                <span className={`badge border ${PRIORITY_COLORS[selectedTask.priority]}`}>{selectedTask.priority}</span>
              </div>
              <div className="grid grid-cols-3 gap-3 mt-3 text-sm">
                <div className="bg-white rounded-lg p-2 text-center border border-blue-100">
                  <p className="text-xs text-gray-500">Cohort</p>
                  <p className="font-bold">{selectedTask.patient.cohort}</p>
                </div>
                <div className="bg-white rounded-lg p-2 text-center border border-blue-100">
                  <p className="text-xs text-gray-500">Engagement</p>
                  <p className="font-bold">{selectedTask.patient.engagementScore}/100</p>
                </div>
                <div className="bg-white rounded-lg p-2 text-center border border-blue-100">
                  <p className="text-xs text-gray-500">Persona</p>
                  <p className="font-bold text-xs">{selectedTask.patient.personaStyle}</p>
                </div>
              </div>
            </div>

            {/* Primary biomarker */}
            {PRIMARY_BIOMARKERS[selectedTask.patient.programId] && (
              <div className="card">
                <h3 className="font-semibold text-sm text-gray-800 mb-2">Clinical Context</h3>
                <div className="flex items-center gap-4">
                  <div>
                    <p className="text-xs text-gray-500">{PRIMARY_BIOMARKERS[selectedTask.patient.programId]}</p>
                    <p className="text-2xl font-black text-red-600">
                      {selectedTask.patient.currentLabValues[PRIMARY_BIOMARKERS[selectedTask.patient.programId]] ?? 'N/A'}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Task description */}
            <div className="card">
              <h3 className="font-semibold text-sm text-gray-800 mb-2">Task: {selectedTask.subject}</h3>
              <p className="text-sm text-gray-600">{selectedTask.description}</p>
            </div>

            {/* Call script */}
            <div className="card bg-green-50 border-green-200">
              <div className="flex items-center gap-2 mb-2">
                <Phone size={14} className="text-green-600" />
                <h3 className="font-semibold text-sm text-green-900">Auto-Generated Call Script</h3>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed italic">"{selectedTask.callScript}"</p>
            </div>

            {/* Agent notes */}
            <div className="card">
              <h3 className="font-semibold text-sm text-gray-800 mb-2">Agent Notes</h3>
              <textarea
                rows={3}
                value={agentNotes}
                onChange={(e) => setAgentNotes(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                placeholder="Add notes about this interaction..."
              />
            </div>

            {/* Outcome buttons */}
            <div className="card">
              <h3 className="font-semibold text-sm text-gray-800 mb-3">Log Outcome</h3>
              <div className="grid grid-cols-2 gap-2">
                {OUTCOME_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => resolveTask(opt.value)}
                    disabled={updateTaskMutation.isPending}
                    className={`flex items-center gap-2 p-2.5 rounded-lg border border-gray-200 text-xs font-medium hover:bg-gray-50 transition-colors ${opt.color}`}
                  >
                    {opt.icon}
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {selectedTask.outcome && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-700">
                ✓ Outcome logged: <strong>{selectedTask.outcome}</strong>
              </div>
            )}
          </div>
        )}
      </div>

      {/* RIGHT COLUMN — Patient Panel */}
      {selectedTask && (
        <aside className="w-72 border-l border-gray-200 bg-white overflow-y-auto p-4 space-y-4">
          <h2 className="font-semibold text-gray-800 text-sm">Outcome Prediction</h2>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={150}>
              <LineChart data={chartData}>
                <XAxis dataKey="day" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 9 }} width={30} />
                <Tooltip formatter={(v: number) => v?.toFixed ? v.toFixed(2) : v} />
                <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-32 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400 text-xs">No prediction data</div>
          )}

          <div>
            <h3 className="font-semibold text-sm text-gray-800 mb-2">Lab Values</h3>
            <div className="space-y-1.5">
              {Object.entries(selectedTask.patient.currentLabValues).map(([key, val]) => (
                <div key={key} className="flex justify-between text-xs">
                  <span className="text-gray-500">{key}</span>
                  <span className="font-medium">{val}</span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="font-semibold text-sm text-gray-800 mb-2">Escalation History</h3>
            <div className="space-y-2">
              {['WhatsApp', 'App Nudge', 'Voice Bot', 'Agent Task'].map((ch, i) => (
                <div key={ch} className="flex items-center gap-2 text-xs">
                  <div className={`w-2 h-2 rounded-full ${i < 3 ? 'bg-red-400' : 'bg-yellow-400'}`} />
                  <span className="text-gray-500">{ch}</span>
                  <span className="ml-auto text-gray-400">{i < 3 ? '✗ No response' : '⏳ Pending'}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>
      )}
    </div>
  );
}
