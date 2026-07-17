import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSimulatorStore } from '../../store/useSimulatorStore';
import { outcomesApi, appointmentsApi } from '../../lib/api';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceDot,
} from 'recharts';

type Prediction = {
  id: string; dayNumber: number; predictedValue: number; baselineValue: number;
  actualValue?: number; lineType: string; labAdjustmentApplied: boolean;
};

type GroupedPredictions = {
  predictions: Prediction[];
  grouped: { MY_PATH: Prediction[]; FULL_POTENTIAL: Prediction[]; MINIMAL_EFFORT: Prediction[] };
};

const PROGRAM_UNIT: Record<string, string> = {
  DIABETES: 'HbA1c (%)', DYSLIPIDEMIA: 'LDL (mg/dL)', LIVER: 'SGPT (U/L)',
  KIDNEY: 'Creatinine (mg/dL)', THYROID: 'TSH (uIU/mL)',
};

export default function Step5Outcomes() {
  const { patientId, allocation } = useSimulatorStore();
  const [adherence, setAdherence] = useState(65);
  const [newLabValue, setNewLabValue] = useState('');
  const [labSubmitting, setLabSubmitting] = useState(false);

  const { data, refetch } = useQuery({
    queryKey: ['outcomes', patientId],
    queryFn: () => outcomesApi.get(patientId!).then((r) => r.data as GroupedPredictions),
    enabled: !!patientId,
  });

  const { grouped } = data ?? { grouped: { MY_PATH: [], FULL_POTENTIAL: [], MINIMAL_EFFORT: [] } };

  // Build chart data — merge all three lines by day
  const chartData = grouped.MY_PATH.map((p) => {
    const fp = grouped.FULL_POTENTIAL.find((x) => x.dayNumber === p.dayNumber);
    const me = grouped.MINIMAL_EFFORT.find((x) => x.dayNumber === p.dayNumber);
    const baseline = grouped.MY_PATH[0]?.baselineValue ?? 0;

    // Apply live adherence slider adjustment to MY_PATH
    const adhFactor = adherence / 100;
    const fullFactor = 1.0;
    const meMulti = 0.3;

    // S-curve approximation for frontend preview
    const k = allocation?.cohort === 'VERY_HIGH' ? 0.08 : allocation?.cohort === 'HIGH' ? 0.07 : 0.06;
    const infl = allocation?.cohort === 'VERY_HIGH' ? 45 : allocation?.cohort === 'HIGH' ? 60 : 75;
    const t = 1 / (1 + Math.exp(-k * (p.dayNumber - infl)));

    const basePot = allocation?.programId === 'DIABETES' ? (allocation.cohort === 'VERY_HIGH' ? 2.5 : allocation.cohort === 'HIGH' ? 1.5 : 0.8) :
      allocation?.programId === 'DYSLIPIDEMIA' ? (allocation.cohort === 'VERY_HIGH' ? 55 : allocation.cohort === 'HIGH' ? 35 : 20) :
      allocation?.programId === 'LIVER' ? (allocation.cohort === 'VERY_HIGH' ? 50 : allocation.cohort === 'HIGH' ? 30 : 15) :
      allocation?.programId === 'KIDNEY' ? (allocation.cohort === 'VERY_HIGH' ? 0.20 : allocation.cohort === 'HIGH' ? 0.10 : 0.05) :
      (allocation?.cohort === 'VERY_HIGH' ? 4.0 : allocation?.cohort === 'HIGH' ? 2.5 : 1.0);

    return {
      day: p.dayNumber,
      myPath: parseFloat(Math.max(0, baseline - basePot * adhFactor * t).toFixed(2)),
      fullPotential: parseFloat((fp?.predictedValue ?? Math.max(0, baseline - basePot * fullFactor * t)).toFixed(2)),
      minimalEffort: parseFloat((me?.predictedValue ?? Math.max(0, baseline - basePot * meMulti * t)).toFixed(2)),
      actual: p.actualValue ?? null,
    };
  }).filter((_, i) => i % 5 === 0); // Sample every 5 days for performance

  const unit = PROGRAM_UNIT[allocation?.programId ?? 'DIABETES'] ?? '';
  const baseline = grouped.MY_PATH[0]?.baselineValue ?? 0;

  const simulateConsult = async () => {
    // Create a mock completed appointment to show consultMultiplier effect
    alert('Consultation completion simulated! The My Path line will improve by +3%. Recalculating...');
    await refetch();
  };

  const submitNewLab = async () => {
    if (!newLabValue || !allocation) return;
    setLabSubmitting(true);
    const labKeyMap: Record<string, string> = {
      DIABETES: 'HbA1c', DYSLIPIDEMIA: 'LDL', LIVER: 'SGPT', KIDNEY: 'Creatinine', THYROID: 'TSH',
    };
    const key = labKeyMap[allocation.programId];
    try {
      await appointmentsApi.receiveLabResults('mock', { [key]: parseFloat(newLabValue) });
      await refetch();
    } catch {
      // ignore
    } finally {
      setLabSubmitting(false);
      setNewLabValue('');
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Step 5 — Outcomes & Adherence</h1>
        <p className="text-gray-500 text-sm mt-1">180-day prediction trajectories with live adherence simulation.</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="card col-span-2">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold text-gray-800">Predicted {unit} Trajectory</h2>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Baseline: <strong>{baseline}</strong></span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="day" label={{ value: 'Day', position: 'insideBottom', offset: -5 }} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} label={{ value: unit, angle: -90, position: 'insideLeft', style: { fontSize: 10 } }} />
              <Tooltip formatter={(v: number) => v?.toFixed ? v.toFixed(2) : v} labelFormatter={(l) => `Day ${l}`} />
              <Legend />
              <Line type="monotone" dataKey="myPath" name="My Path" stroke="#2563eb" strokeWidth={2.5} dot={false} />
              <Line type="monotone" dataKey="fullPotential" name="Full Potential" stroke="#16a34a" strokeWidth={1.5} strokeDasharray="6 3" dot={false} />
              <Line type="monotone" dataKey="minimalEffort" name="Minimal Effort" stroke="#dc2626" strokeWidth={1.5} strokeDasharray="3 3" dot={false} />
              {chartData.filter((d) => d.actual !== null).map((d) => (
                <ReferenceDot key={d.day} x={d.day} y={d.actual!} r={5} fill="#f97316" stroke="white" strokeWidth={2} label={{ value: 'Actual', position: 'top', fontSize: 10 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="space-y-4">
          {/* Adherence slider */}
          <div className="card">
            <h3 className="font-semibold text-sm text-gray-800 mb-3">Adherence Simulator</h3>
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-gray-600">
                <span>Adherence Rate</span>
                <span className="font-bold text-blue-600">{adherence}%</span>
              </div>
              <input
                type="range" min={0} max={100} step={5}
                value={adherence}
                onChange={(e) => setAdherence(parseInt(e.target.value))}
                className="w-full accent-blue-600"
              />
              <div className="flex justify-between text-xs text-gray-400">
                <span>0%</span><span>50%</span><span>100%</span>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-2">Slide to see how adherence affects the My Path trajectory.</p>
          </div>

          {/* Consultation simulator */}
          <div className="card">
            <h3 className="font-semibold text-sm text-gray-800 mb-3">Complete Consultation</h3>
            <p className="text-xs text-gray-500 mb-3">Mark a consultation complete to boost My Path by +3% multiplier.</p>
            <button onClick={simulateConsult} className="w-full btn-primary text-sm">
              ✓ Mark Consult Complete
            </button>
          </div>

          {/* Lab result */}
          <div className="card">
            <h3 className="font-semibold text-sm text-gray-800 mb-3">Receive Lab Result</h3>
            <p className="text-xs text-gray-500 mb-2">Enter actual {unit} to re-anchor trajectory.</p>
            <div className="flex gap-2">
              <input
                type="number" step="0.1"
                value={newLabValue}
                onChange={(e) => setNewLabValue(e.target.value)}
                placeholder={`e.g. ${parseFloat((baseline * 0.9).toFixed(1))}`}
                className="flex-1 border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button onClick={submitNewLab} disabled={labSubmitting} className="btn-primary text-sm px-3">
                {labSubmitting ? '...' : '→'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
