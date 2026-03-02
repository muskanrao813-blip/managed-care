import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSimulatorStore } from '../../store/useSimulatorStore';
import { patientsApi, nudgesApi } from '../../lib/api';
import { ChevronRight, X, MessageSquare, Bell, Phone, UserCheck } from 'lucide-react';

type Activity = {
  id: string; dayNumber: number; activityType: string; domain: string;
  isClinical: boolean; isEvergreen: boolean; status: string;
  intent: string; completionLogic: string; benefitGatePoints: number;
};

const DOMAIN_COLORS: Record<string, string> = {
  DIET: 'bg-green-100 text-green-800',
  STEPS: 'bg-blue-100 text-blue-800',
  MENTAL: 'bg-purple-100 text-purple-800',
  COC: 'bg-pink-100 text-pink-800',
  HRA: 'bg-yellow-100 text-yellow-800',
  WEIGHT: 'bg-orange-100 text-orange-800',
  CLINICAL: 'bg-red-100 text-red-800',
  EVERGREEN: 'bg-gray-100 text-gray-700',
};

const CHANNEL_ICONS = {
  WHATSAPP: <MessageSquare size={14} className="text-green-600" />,
  APP_NUDGE: <Bell size={14} className="text-blue-600" />,
  VOICE_BOT: <Phone size={14} className="text-purple-600" />,
  AGENT_TASK: <UserCheck size={14} className="text-red-600" />,
};

export default function Step4PlanBuilder() {
  const { patientId, allocation, setStep } = useSimulatorStore();
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [nudgeSimulator, setNudgeSimulator] = useState<Activity | null>(null);
  const [nudgeState, setNudgeState] = useState({ tier: 1, response: '', sent: false });

  const { data: planData, isLoading } = useQuery({
    queryKey: ['plan', patientId],
    queryFn: () => patientsApi.getPlan(patientId!).then((r) => r.data as Activity[]),
    enabled: !!patientId,
  });

  const { data: dayActivities } = useQuery({
    queryKey: ['plan-day', patientId, selectedDay],
    queryFn: () => patientsApi.getPlanDay(patientId!, selectedDay!).then((r) => r.data as Activity[]),
    enabled: !!patientId && !!selectedDay,
  });

  if (!patientId) return <div className="p-6 text-gray-500">No patient. Complete Step 1 first.</div>;

  // Group activities by day
  const byDay = new Map<number, Activity[]>();
  (planData ?? []).forEach((a) => {
    if (!byDay.has(a.dayNumber)) byDay.set(a.dayNumber, []);
    byDay.get(a.dayNumber)!.push(a);
  });

  // Compute adherence stats
  const totalCompleted = planData?.filter((a) => a.status === 'COMPLETED').length ?? 0;
  const totalActivities = planData?.length ?? 0;

  const sendNudge = async (channel: string) => {
    if (!nudgeSimulator) return;
    const tier = channel === 'WHATSAPP' ? 1 : channel === 'APP_NUDGE' ? 2 : channel === 'VOICE_BOT' ? 3 : 4;
    const messages: Record<string, string> = {
      WHATSAPP: `📱 *Managed Care Reminder*\nHello! Your activity *${nudgeSimulator.activityType.replace(/_/g, ' ')}* is pending today.\n${nudgeSimulator.intent}\n\nReply:\n1 - Done ✓\n2 - Will do later\n3 - Need help\n4 - Pause for 7 days`,
      APP_NUDGE: `Don't forget: ${nudgeSimulator.activityType.replace(/_/g, ' ')} is waiting for you!`,
      VOICE_BOT: `Voice bot calling: "${nudgeSimulator.intent}. Please complete it today to earn ${nudgeSimulator.benefitGatePoints || 2} points."`,
      AGENT_TASK: `SFDC Task created: Follow up with patient about missed ${nudgeSimulator.activityType}`,
    };

    await nudgesApi.send({
      patientId,
      activityId: nudgeSimulator.id,
      channel,
      tier,
      messageContent: { message: messages[channel], activityType: nudgeSimulator.activityType },
    });

    setNudgeState((s) => ({ ...s, tier, sent: true }));
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Step 4 — 180-Day Plan Builder</h1>
        <p className="text-gray-500 text-sm mt-1">
          {isLoading ? 'Building personalised plan...' : `${totalActivities} activities across 180 days. ${totalCompleted} completed.`}
        </p>
      </div>

      {allocation && (
        <div className="card bg-gradient-to-r from-blue-50 to-purple-50 border-blue-200">
          <div className="grid grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-xs text-gray-500">Program</p>
              <p className="font-bold">{allocation.programId}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Cohort</p>
              <p className="font-bold">{allocation.cohort}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Total Days</p>
              <p className="font-bold">180</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Plan Activities</p>
              <p className="font-bold">{totalActivities}</p>
            </div>
          </div>
        </div>
      )}

      {/* Calendar grid */}
      {isLoading ? (
        <div className="card text-center py-12 text-gray-400">Building 180-day plan...</div>
      ) : (
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-3">Plan Calendar</h2>
          <div className="grid gap-1" style={{ gridTemplateColumns: 'repeat(30, 1fr)' }}>
            {Array.from({ length: 180 }, (_, i) => i + 1).map((day) => {
              const dayActs = byDay.get(day) ?? [];
              const hasClinical = dayActs.some((a) => a.isClinical);
              const count = dayActs.filter((a) => !a.isEvergreen).length;
              return (
                <button
                  key={day}
                  onClick={() => setSelectedDay(day === selectedDay ? null : day)}
                  title={`Day ${day}: ${count} activities`}
                  className={`aspect-square rounded text-xs flex flex-col items-center justify-center transition-all border ${
                    selectedDay === day
                      ? 'border-blue-500 bg-blue-600 text-white'
                      : count === 0
                      ? 'bg-gray-50 border-gray-100 text-gray-300'
                      : count <= 2
                      ? 'bg-green-50 border-green-200 text-green-700'
                      : count <= 4
                      ? 'bg-yellow-50 border-yellow-200 text-yellow-700'
                      : 'bg-orange-50 border-orange-200 text-orange-700'
                  }`}
                >
                  <span className="font-medium">{day}</span>
                  {hasClinical && <span className="w-1.5 h-1.5 bg-red-500 rounded-full mt-0.5" />}
                </button>
              );
            })}
          </div>
          <div className="flex gap-4 mt-3 text-xs text-gray-500">
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-100 rounded border border-green-200" /> 1-2 activities</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-yellow-100 rounded border border-yellow-200" /> 3-4 activities</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-orange-100 rounded border border-orange-200" /> 5+ activities</span>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 bg-red-500 rounded-full" /> Clinical appointment</span>
          </div>
        </div>
      )}

      {/* Day detail modal */}
      {selectedDay && (
        <div className="card border-blue-200">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-800">Day {selectedDay} Activities</h2>
            <button onClick={() => setSelectedDay(null)} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
          </div>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {(dayActivities ?? []).map((activity) => (
              <div key={activity.id} className={`flex items-start gap-3 p-3 rounded-lg border ${
                activity.isClinical ? 'border-red-200 bg-red-50' :
                activity.isEvergreen ? 'border-gray-100 bg-gray-50' :
                'border-blue-100 bg-blue-50'
              }`}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-medium text-gray-900 truncate">{activity.activityType.replace(/_/g, ' ')}</p>
                    <span className={`badge text-xs ${DOMAIN_COLORS[activity.domain] ?? 'bg-gray-100 text-gray-700'}`}>{activity.domain}</span>
                    {activity.isEvergreen && <span className="badge bg-gray-100 text-gray-500 text-xs">evergreen</span>}
                    {activity.isClinical && <span className="badge bg-red-100 text-red-700 text-xs">clinical</span>}
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{activity.intent}</p>
                </div>
                <button
                  onClick={() => { setNudgeSimulator(activity); setNudgeState({ tier: 1, response: '', sent: false }); }}
                  className="flex-shrink-0 text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded hover:bg-blue-200 transition-colors"
                >
                  Nudge Sim
                </button>
              </div>
            ))}
            {(dayActivities ?? []).length === 0 && (
              <p className="text-gray-400 text-sm text-center py-4">No activities scheduled for Day {selectedDay}.</p>
            )}
          </div>
        </div>
      )}

      {/* Nudge Simulator */}
      {nudgeSimulator && (
        <div className="card border-purple-200 bg-purple-50">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-purple-900">Nudge Simulator — {nudgeSimulator.activityType.replace(/_/g, ' ')}</h2>
            <button onClick={() => setNudgeSimulator(null)} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
          </div>
          <div className="grid grid-cols-3 gap-4">
            {/* Context */}
            <div className="bg-white rounded-lg p-3 border border-purple-100">
              <h3 className="font-medium text-sm text-gray-800 mb-2">Activity Context</h3>
              <p className="text-xs text-gray-600 mb-1"><strong>Intent:</strong> {nudgeSimulator.intent}</p>
              <p className="text-xs text-gray-600 mb-1"><strong>Domain:</strong> {nudgeSimulator.domain}</p>
              <p className="text-xs text-gray-600"><strong>Completion:</strong> {nudgeSimulator.completionLogic.substring(0, 100)}...</p>
            </div>

            {/* WhatsApp mockup */}
            <div className="bg-[#075E54] rounded-xl p-3 text-white">
              <div className="flex items-center gap-2 mb-3 pb-2 border-b border-white/20">
                <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center text-xs font-bold">MC</div>
                <div>
                  <p className="text-xs font-semibold">Managed Care</p>
                  <p className="text-xs opacity-70">08:30</p>
                </div>
              </div>
              <div className="bg-[#DCF8C6] text-gray-800 rounded-lg p-2 text-xs">
                <p className="font-medium mb-1">📱 Daily Digest</p>
                <p>Your activity: <strong>{nudgeSimulator.activityType.replace(/_/g, ' ')}</strong></p>
                <p className="mt-1">{nudgeSimulator.intent}</p>
                <p className="mt-2 text-gray-500 text-right text-xs">✓✓ {new Date().toLocaleTimeString()}</p>
              </div>
            </div>

            {/* Outcome controls */}
            <div className="bg-white rounded-lg p-3 border border-purple-100">
              <h3 className="font-medium text-sm text-gray-800 mb-2">Simulate Outcome</h3>
              <div className="space-y-1.5">
                {['WHATSAPP', 'APP_NUDGE', 'VOICE_BOT', 'AGENT_TASK'].map((ch) => (
                  <button key={ch} onClick={() => sendNudge(ch)}
                    className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg border border-gray-200 text-xs hover:bg-gray-50 transition-colors">
                    {CHANNEL_ICONS[ch as keyof typeof CHANNEL_ICONS]}
                    <span>Send via {ch.replace(/_/g, ' ')}</span>
                  </button>
                ))}
              </div>
              {nudgeState.sent && (
                <div className="mt-2 p-2 bg-green-50 border border-green-200 rounded text-xs text-green-700">
                  ✓ Nudge sent (Tier {nudgeState.tier})
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <button onClick={() => setStep(5)} className="btn-primary flex items-center gap-2">
          Next: Outcomes <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
