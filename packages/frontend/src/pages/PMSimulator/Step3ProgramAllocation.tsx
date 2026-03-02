import { useSimulatorStore } from '../../store/useSimulatorStore';
import { ChevronRight } from 'lucide-react';

const PROGRAM_FEATURES: Record<string, Record<string, string[]>> = {
  DIABETES: {
    MODERATE: ['Diet counselling', 'Step tracking', 'Medication reminders', 'Monthly HRA', 'Basic education modules'],
    HIGH: ['All MODERATE features', 'AI glucose pattern review (day 30+)', 'Bi-weekly dietician consults', 'Glucometer benefit (250 pts)', 'Periodic HRA at 60/120/180'],
    VERY_HIGH: ['All HIGH features', 'Daily glucometer logging', 'AI weekly glucose reports', 'Gym sessions (300 pts)', 'Frequent HRA every 30 days', 'Dedicated care coordinator'],
  },
  THYROID: {
    MODERATE: ['Stress management sessions', 'Sleep tracking', 'Medication reminders', 'Education modules'],
    HIGH: ['All MODERATE features', 'Enhanced mental wellness', 'Dietician consult', 'Bi-monthly HRA'],
    VERY_HIGH: ['All HIGH features', 'Intensive stress journal', 'Sleep hygiene program', 'Frequent consults', 'HRA every 30 days'],
  },
  LIVER: {
    MODERATE: ['Diet optimisation', 'Alcohol monitoring', 'Gut health activities', 'Education'],
    HIGH: ['All MODERATE features', 'Food mood journal', 'Enhanced dietician support', 'Bi-monthly HRA'],
    VERY_HIGH: ['All HIGH features', 'Intensive diet tracking', 'Liver-specific education', 'Monthly lab monitoring', 'HRA every 30 days'],
  },
  KIDNEY: {
    MODERATE: ['Hydration tracking', 'Diet monitoring', 'Education', 'Step programme'],
    HIGH: ['All MODERATE features', 'Dietician support', 'Enhanced hydration focus', 'Bi-monthly HRA'],
    VERY_HIGH: ['All HIGH features', 'Daily hydration logs', 'Lab monitoring', 'Frequent dietician', 'HRA every 30 days'],
  },
  DYSLIPIDEMIA: {
    MODERATE: ['Calorie audit', 'Food swap challenges', 'Step programme', 'Education'],
    HIGH: ['All MODERATE features', 'Portion plate training', 'Dietician support', 'Sodium/sugar tracking'],
    VERY_HIGH: ['All HIGH features', 'Intensive diet monitoring', 'Lipid-specific education', 'Gym programme (300 pts)', 'HRA every 30 days'],
  },
};

const COHORT_ORDER = ['MODERATE', 'HIGH', 'VERY_HIGH'];

export default function Step3ProgramAllocation() {
  const { allocation, setStep, engagementScore } = useSimulatorStore();

  if (!allocation) return <div className="p-6 text-gray-500">No allocation data. Please complete Step 1 first.</div>;

  const programFeatures = PROGRAM_FEATURES[allocation.programId] ?? {};

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Step 3 — Program Allocation</h1>
        <p className="text-gray-500 text-sm mt-1">Allocated program details, feature matrix, and secondary domain scores.</p>
      </div>

      {/* Primary allocation card */}
      <div className={`card border-2 ${
        allocation.cohort === 'VERY_HIGH' ? 'border-red-300 bg-red-50' :
        allocation.cohort === 'HIGH' ? 'border-orange-300 bg-orange-50' :
        'border-yellow-300 bg-yellow-50'
      }`}>
        <div className="flex items-center gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase">Primary Program</p>
            <p className="text-3xl font-black text-gray-900 mt-0.5">{allocation.programId}</p>
            <p className="text-sm text-gray-600 mt-1">{allocation.reason}</p>
          </div>
          <div className="ml-auto text-right">
            <span className={`badge text-lg px-4 py-2 font-bold ${
              allocation.cohort === 'VERY_HIGH' ? 'bg-red-200 text-red-900' :
              allocation.cohort === 'HIGH' ? 'bg-orange-200 text-orange-900' :
              'bg-yellow-200 text-yellow-900'
            }`}>
              {allocation.cohort}
            </span>
            <p className="text-xs text-gray-500 mt-2">Engagement Score: <strong>{engagementScore}/100</strong></p>
          </div>
        </div>
      </div>

      {/* Feature matrix */}
      <div className="card">
        <h2 className="font-semibold text-gray-800 mb-4">Feature Matrix — {allocation.programId}</h2>
        <div className="grid grid-cols-3 gap-4">
          {COHORT_ORDER.map((cohort) => (
            <div key={cohort} className={`rounded-lg p-4 border-2 ${
              cohort === allocation.cohort
                ? cohort === 'VERY_HIGH' ? 'border-red-400 bg-red-50' :
                  cohort === 'HIGH' ? 'border-orange-400 bg-orange-50' :
                  'border-yellow-400 bg-yellow-50'
                : 'border-gray-200 bg-gray-50 opacity-60'
            }`}>
              <div className="flex items-center justify-between mb-3">
                <span className={`badge font-semibold ${
                  cohort === 'VERY_HIGH' ? 'bg-red-200 text-red-800' :
                  cohort === 'HIGH' ? 'bg-orange-200 text-orange-800' :
                  'bg-yellow-200 text-yellow-800'
                }`}>{cohort}</span>
                {cohort === allocation.cohort && <span className="text-xs font-semibold text-blue-600">★ Assigned</span>}
              </div>
              <ul className="space-y-1.5">
                {(programFeatures[cohort] ?? []).map((feature) => (
                  <li key={feature} className="flex items-start gap-1.5 text-xs text-gray-700">
                    <span className="text-green-500 mt-0.5 flex-shrink-0">✓</span>
                    {feature}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Secondary domains */}
      <div className="card">
        <h2 className="font-semibold text-gray-800 mb-4">All Domain Scores</h2>
        <div className="space-y-3">
          {allocation.allDomainScores.map((score) => (
            <div key={score.domain} className={`flex items-center gap-4 p-3 rounded-lg border ${
              score.domain === allocation.programId ? 'border-blue-200 bg-blue-50' : 'border-gray-100 bg-white'
            }`}>
              <div className="w-32 font-medium text-sm text-gray-800">{score.domain}</div>
              <div className="flex-1">
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div className={`h-2 rounded-full ${
                    score.normalized >= 8 ? 'bg-red-500' :
                    score.normalized >= 5 ? 'bg-orange-400' :
                    score.normalized > 0 ? 'bg-yellow-400' :
                    'bg-green-300'
                  }`} style={{ width: `${Math.min(100, score.normalized * 10)}%` }} />
                </div>
              </div>
              <div className="w-16 text-right font-mono text-sm">{score.normalized.toFixed(1)}/10</div>
              <div className="w-20">
                {score.cohort ? (
                  <span className={`badge text-xs ${
                    score.cohort === 'VERY_HIGH' ? 'bg-red-100 text-red-800' :
                    score.cohort === 'HIGH' ? 'bg-orange-100 text-orange-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>{score.cohort}</span>
                ) : (
                  <span className="badge bg-green-100 text-green-800 text-xs">Normal</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex justify-end">
        <button onClick={() => setStep(4)} className="btn-primary flex items-center gap-2">
          Next: 180-Day Plan <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
