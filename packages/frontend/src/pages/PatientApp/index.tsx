import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { patientsApi, activitiesApi, outcomesApi, logsApi } from '../../lib/api';
import { Activity, Heart, Droplets, Footprints, Star, Trophy, Flame, ChevronDown } from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';

type Patient = {
  id: string; name: string; age: number; programId: string; cohort: string;
  dayNumber: number; points: number; level: string; engagementScore: number;
  personaStyle: string; frustrationStage: string; streaks: { medication: number; steps: number; mealLog: number };
  currentLabValues: Record<string, number>;
};

type ActivityItem = {
  id: string; activityType: string; domain: string; status: string;
  intent: string; completionLogic: string; pointsEarned: number; isClinical: boolean;
  isEvergreen: boolean; benefitGatePoints: number;
};

type Prediction = { dayNumber: number; predictedValue: number; lineType: string };

const DOMAIN_ICONS: Record<string, React.ReactNode> = {
  DIET: <Heart size={16} />,
  STEPS: <Footprints size={16} />,
  MENTAL: <Star size={16} />,
  WEIGHT: <Activity size={16} />,
  HRA: <Activity size={16} />,
  CLINICAL: <Heart size={16} />,
  EVERGREEN: <Droplets size={16} />,
  COC: <Star size={16} />,
};

const LEVEL_THRESHOLD = { BRONZE: 0, SILVER: 100, GOLD: 300, PLATINUM: 600 };
const LEVEL_MAX = { BRONZE: 99, SILVER: 299, GOLD: 599, PLATINUM: 1200 };

function greetingByTime(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

export default function PatientApp() {
  const urlParams = new URLSearchParams(window.location.search);
  const [selectedPatientId, setSelectedPatientId] = useState<string>(urlParams.get('patientId') ?? '');
  const [completingId, setCompletingId] = useState<string | null>(null);
  const [moodScore, setMoodScore] = useState<number | null>(null);
  const [waterCount, setWaterCount] = useState(0);
  const [activityModal, setActivityModal] = useState<ActivityItem | null>(null);

  const { data: patients } = useQuery({
    queryKey: ['patients'],
    queryFn: () => patientsApi.list().then((r) => r.data as Patient[]),
  });

  const { data: patient } = useQuery({
    queryKey: ['patient', selectedPatientId],
    queryFn: () => patientsApi.get(selectedPatientId).then((r) => r.data as Patient),
    enabled: !!selectedPatientId,
  });

  const { data: todayActivities = [], refetch: refetchActivities } = useQuery({
    queryKey: ['today-activities', selectedPatientId],
    queryFn: () => activitiesApi.getToday(selectedPatientId).then((r) => r.data as ActivityItem[]),
    enabled: !!selectedPatientId,
  });

  const { data: outcomeData } = useQuery({
    queryKey: ['outcomes', selectedPatientId],
    queryFn: () => outcomesApi.get(selectedPatientId).then((r) => r.data as { grouped: { MY_PATH: Prediction[]; FULL_POTENTIAL: Prediction[]; MINIMAL_EFFORT: Prediction[] } }),
    enabled: !!selectedPatientId,
  });

  const handleComplete = async (activity: ActivityItem) => {
    setCompletingId(activity.id);
    try {
      await activitiesApi.complete(activity.id);
      await refetchActivities();
    } finally {
      setCompletingId(null);
      setActivityModal(null);
    }
  };

  const handleMoodLog = async (score: number) => {
    if (!selectedPatientId) return;
    setMoodScore(score);
    await logsApi.logMood({ patientId: selectedPatientId, score });
    const moodActivity = todayActivities.find((a) => a.activityType === 'daily_mood_check' && a.status === 'PENDING');
    if (moodActivity) await activitiesApi.complete(moodActivity.id, { score });
    await refetchActivities();
  };

  const handleWater = async () => {
    const next = waterCount + 1;
    setWaterCount(next);
    const waterActivity = todayActivities.find((a) => a.activityType === 'water_intake_log' && a.status === 'PENDING');
    if (waterActivity && next >= 1) {
      await activitiesApi.complete(waterActivity.id, { glasses: next });
      await refetchActivities();
    }
  };

  const completedToday = todayActivities.filter((a) => a.status === 'COMPLETED').length;
  const totalToday = todayActivities.length;

  const chartData = (outcomeData?.grouped?.MY_PATH ?? []).filter((_, i) => i % 10 === 0).map((p) => ({
    day: p.dayNumber,
    value: parseFloat(p.predictedValue.toFixed(2)),
  }));

  const levelMin = LEVEL_THRESHOLD[patient?.level as keyof typeof LEVEL_THRESHOLD] ?? 0;
  const levelMax = LEVEL_MAX[patient?.level as keyof typeof LEVEL_MAX] ?? 99;
  const levelPct = patient ? Math.min(100, ((patient.points - levelMin) / (levelMax - levelMin)) * 100) : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Patient selector for demo */}
      <div className="bg-white border-b border-gray-200 px-4 py-2 flex items-center gap-3">
        <span className="text-xs text-gray-500">Demo Patient:</span>
        <select
          className="text-sm border border-gray-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={selectedPatientId}
          onChange={(e) => setSelectedPatientId(e.target.value)}
        >
          <option value="">-- Select Patient --</option>
          {(patients ?? []).map((p) => (
            <option key={p.id} value={p.id}>{p.name} ({p.programId} {p.cohort})</option>
          ))}
        </select>
      </div>

      {!selectedPatientId && (
        <div className="flex items-center justify-center h-80 text-gray-400">
          <div className="text-center">
            <Activity size={48} className="mx-auto mb-3 opacity-30" />
            <p>Select a patient to view their app</p>
          </div>
        </div>
      )}

      {patient && (
        <div className="max-w-[430px] mx-auto">
          {/* Hero Header */}
          <div className="bg-gradient-to-br from-blue-600 to-blue-800 text-white px-5 pt-5 pb-6 sticky top-0 z-10 shadow-lg">
            <p className="text-blue-200 text-sm">{greetingByTime()},</p>
            <h1 className="text-xl font-bold">{patient.name}</h1>
            <div className="flex items-center gap-2 mt-1">
              <span className="bg-white/20 text-white text-xs px-2 py-0.5 rounded-full">{patient.programId}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                patient.cohort === 'VERY_HIGH' ? 'bg-red-400/80' :
                patient.cohort === 'HIGH' ? 'bg-orange-400/80' :
                'bg-yellow-400/80 text-yellow-900'
              }`}>{patient.cohort}</span>
            </div>
            <div className="flex items-center justify-between mt-3">
              <div className="text-center">
                <p className="text-2xl font-black">Day {patient.dayNumber}</p>
                <p className="text-xs text-blue-200">of 180</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-black">{patient.points}</p>
                <p className="text-xs text-blue-200">pts • {patient.level}</p>
              </div>
              <div className="text-center">
                <div className="flex items-center gap-1">
                  <Flame size={16} className="text-orange-300" />
                  <p className="text-2xl font-black">{patient.streaks.steps}</p>
                </div>
                <p className="text-xs text-blue-200">day streak</p>
              </div>
            </div>
          </div>

          <div className="p-4 space-y-4">
            {/* Today's progress */}
            <div className="card">
              <div className="flex items-center justify-between mb-2">
                <h2 className="font-semibold text-gray-800">Today's Activities</h2>
                <span className="text-sm font-medium text-blue-600">{completedToday}/{totalToday}</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2">
                <div className="bg-blue-500 h-2 rounded-full transition-all" style={{ width: `${totalToday ? (completedToday / totalToday) * 100 : 0}%` }} />
              </div>
            </div>

            {/* Mood check */}
            <div className="card">
              <h2 className="font-semibold text-gray-800 mb-3">How are you feeling?</h2>
              <div className="flex gap-2 justify-center">
                {[
                  { score: 1, emoji: '😞' },
                  { score: 2, emoji: '😕' },
                  { score: 3, emoji: '😐' },
                  { score: 4, emoji: '🙂' },
                  { score: 5, emoji: '😊' },
                ].map(({ score, emoji }) => (
                  <button
                    key={score}
                    onClick={() => handleMoodLog(score)}
                    className={`text-3xl p-2 rounded-xl transition-all ${
                      moodScore === score ? 'bg-blue-100 scale-110 ring-2 ring-blue-400' : 'hover:bg-gray-100'
                    }`}
                  >
                    {emoji}
                  </button>
                ))}
              </div>
              {moodScore && <p className="text-xs text-center text-green-600 mt-2">✓ Mood logged! +1 pt</p>}
            </div>

            {/* Water tracker */}
            <div className="card">
              <div className="flex items-center justify-between mb-2">
                <h2 className="font-semibold text-gray-800">Water Intake</h2>
                <span className="text-sm text-blue-600">{waterCount} / 8 glasses</span>
              </div>
              <div className="flex gap-1.5 flex-wrap mb-2">
                {Array.from({ length: 8 }, (_, i) => (
                  <div key={i} className={`w-8 h-10 rounded-b-full border-2 transition-colors ${
                    i < waterCount ? 'bg-blue-400 border-blue-500' : 'bg-gray-100 border-gray-200'
                  }`}>
                    <Droplets size={12} className={`mx-auto mt-1.5 ${i < waterCount ? 'text-white' : 'text-gray-300'}`} />
                  </div>
                ))}
              </div>
              <button onClick={handleWater} className="btn-secondary w-full text-sm">
                + Add Glass
              </button>
            </div>

            {/* Activities */}
            <div>
              <h2 className="font-semibold text-gray-800 mb-3">Activities</h2>
              <div className="space-y-2">
                {todayActivities.map((activity) => (
                  <button
                    key={activity.id}
                    onClick={() => setActivityModal(activity)}
                    className={`w-full text-left p-3 rounded-xl border transition-all ${
                      activity.status === 'COMPLETED'
                        ? 'bg-green-50 border-green-200'
                        : activity.status === 'LOCKED'
                        ? 'bg-gray-50 border-gray-100 opacity-60'
                        : activity.isClinical
                        ? 'bg-blue-50 border-blue-200'
                        : 'bg-white border-gray-200 hover:border-blue-300 hover:shadow-sm'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                        activity.status === 'COMPLETED' ? 'bg-green-500 text-white' :
                        activity.isClinical ? 'bg-blue-500 text-white' :
                        'bg-gray-100 text-gray-500'
                      }`}>
                        {activity.status === 'COMPLETED' ? '✓' : DOMAIN_ICONS[activity.domain] ?? <Activity size={16} />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-medium truncate ${activity.status === 'COMPLETED' ? 'line-through text-gray-400' : 'text-gray-900'}`}>
                          {activity.activityType.replace(/_/g, ' ')}
                        </p>
                        <p className="text-xs text-gray-500 truncate">{activity.intent.substring(0, 60)}</p>
                      </div>
                      {activity.status !== 'COMPLETED' && activity.status !== 'LOCKED' && (
                        <span className="text-xs font-semibold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full flex-shrink-0">
                          +{activity.pointsEarned || 2}pt
                        </span>
                      )}
                      {activity.status === 'LOCKED' && (
                        <span className="text-xs text-gray-400">🔒</span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Outcome chart */}
            {chartData.length > 0 && (
              <div className="card">
                <h2 className="font-semibold text-gray-800 mb-3">Your Health Journey</h2>
                <p className="text-xs text-gray-500 mb-2">Predicted improvement over 180 days</p>
                <ResponsiveContainer width="100%" height={150}>
                  <LineChart data={chartData}>
                    <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} width={35} />
                    <Tooltip formatter={(v: number) => v?.toFixed ? v.toFixed(2) : v} labelFormatter={(l) => `Day ${l}`} />
                    <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2.5} dot={false} name="My Path" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Points & Level */}
            <div className="card">
              <div className="flex items-center gap-3 mb-3">
                <Trophy size={20} className="text-yellow-500" />
                <div>
                  <p className="font-semibold text-gray-800">{patient.level}</p>
                  <p className="text-xs text-gray-500">{patient.points} points total</p>
                </div>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-3">
                <div className="bg-gradient-to-r from-yellow-400 to-orange-400 h-3 rounded-full transition-all" style={{ width: `${levelPct}%` }} />
              </div>
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>{levelMin} pts</span>
                <span>{levelMax} pts</span>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-3">
                {[
                  { label: 'Med streak', value: patient.streaks.medication, icon: '💊' },
                  { label: 'Step streak', value: patient.streaks.steps, icon: '👟' },
                  { label: 'Meal streak', value: patient.streaks.mealLog, icon: '🍽️' },
                ].map((s) => (
                  <div key={s.label} className="bg-gray-50 rounded-lg p-2 text-center">
                    <p className="text-lg">{s.icon}</p>
                    <p className="text-lg font-bold">{s.value}</p>
                    <p className="text-xs text-gray-500">{s.label}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Activity modal */}
      {activityModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-end">
          <div className="bg-white w-full max-w-[430px] mx-auto rounded-t-2xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-gray-900">{activityModal.activityType.replace(/_/g, ' ')}</h2>
              <button onClick={() => setActivityModal(null)} className="text-gray-400">✕</button>
            </div>
            <div className="space-y-2">
              <div className="bg-blue-50 rounded-lg p-3">
                <p className="text-xs font-semibold text-blue-800 mb-1">What you need to do</p>
                <p className="text-sm text-gray-800">{activityModal.intent}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs font-semibold text-gray-600 mb-1">How it's completed</p>
                <p className="text-xs text-gray-600 leading-relaxed">{activityModal.completionLogic}</p>
              </div>
            </div>
            {activityModal.status !== 'COMPLETED' && activityModal.status !== 'LOCKED' && (
              <button
                onClick={() => handleComplete(activityModal)}
                disabled={completingId === activityModal.id}
                className="btn-primary w-full"
              >
                {completingId === activityModal.id ? 'Completing...' : 'Mark Complete ✓'}
              </button>
            )}
            {activityModal.status === 'COMPLETED' && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                <p className="text-green-700 font-semibold">✓ Completed!</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
