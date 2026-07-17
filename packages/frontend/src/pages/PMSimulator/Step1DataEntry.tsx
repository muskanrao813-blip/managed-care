import { useState } from 'react';
import { useSimulatorStore } from '../../store/useSimulatorStore';
import { calculateEngagementScore } from '@managed-care/shared';
import type { HraAnswers } from '@managed-care/shared';
import { patientsApi } from '../../lib/api';
import { ChevronRight, Upload, PenLine } from 'lucide-react';

const LAB_FIELDS = [
  { key: 'HbA1c', label: 'HbA1c (%)', group: 'Diabetes' },
  { key: 'TSH', label: 'TSH (uIU/mL)', group: 'Thyroid' },
  { key: 'T3', label: 'T3 (ng/dL)', group: 'Thyroid' },
  { key: 'T4', label: 'T4 (ug/dL)', group: 'Thyroid' },
  { key: 'Albumin', label: 'Albumin (g/dL)', group: 'Liver' },
  { key: 'ALP', label: 'ALP (U/L)', group: 'Liver' },
  { key: 'BilirubinDirect', label: 'Bilirubin Direct (mg/dL)', group: 'Liver' },
  { key: 'BilirubinTotal', label: 'Bilirubin Total (mg/dL)', group: 'Liver' },
  { key: 'GGTP', label: 'GGTP (U/L)', group: 'Liver' },
  { key: 'SGOT', label: 'SGOT (U/L)', group: 'Liver' },
  { key: 'SGPT', label: 'SGPT (U/L)', group: 'Liver' },
  { key: 'BUN', label: 'BUN (mg/dL)', group: 'Kidney' },
  { key: 'Creatinine', label: 'Creatinine (mg/dL)', group: 'Kidney' },
  { key: 'Urea', label: 'Urea (mg/dL)', group: 'Kidney' },
  { key: 'UricAcid', label: 'Uric Acid (mg/dL)', group: 'Kidney' },
  { key: 'BUNCreatRatio', label: 'BUN/Creat Ratio', group: 'Kidney' },
  { key: 'TotalCholesterol', label: 'Total Cholesterol (mg/dL)', group: 'Lipids' },
  { key: 'HDL', label: 'HDL (mg/dL)', group: 'Lipids' },
  { key: 'LDL', label: 'LDL (mg/dL)', group: 'Lipids' },
  { key: 'NonHDL', label: 'Non-HDL (mg/dL)', group: 'Lipids' },
  { key: 'Triglycerides', label: 'Triglycerides (mg/dL)', group: 'Lipids' },
];

const LAB_GROUPS = ['Diabetes', 'Thyroid', 'Liver', 'Kidney', 'Lipids'];

const SAMPLE_LABS: Record<string, number> = {
  HbA1c: 9.2, TSH: 2.1, T3: 120, T4: 8.5,
  Albumin: 4.0, ALP: 85, BilirubinDirect: 0.15, BilirubinTotal: 0.8,
  GGTP: 40, SGOT: 35, SGPT: 42,
  BUN: 16, Creatinine: 1.0, Urea: 30, UricAcid: 5.5, BUNCreatRatio: 16,
  TotalCholesterol: 220, HDL: 42, LDL: 145, NonHDL: 178, Triglycerides: 165,
};

export default function Step1DataEntry() {
  const { patientForm, setPatientForm, labValues, setLabValues, hraAnswers, setHraAnswers, setEngagementScore, setStep, setPatientId, setAllocation } = useSimulatorStore();
  const [labMode, setLabMode] = useState<'manual' | 'upload'>('manual');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const liveEngagement = Object.keys(hraAnswers).length >= 4
    ? calculateEngagementScore({
        gender: hraAnswers.gender ?? 'MALE',
        dob: hraAnswers.dob ?? '1980-01-01',
        weightKg: hraAnswers.weightKg ?? 70,
        heightCm: hraAnswers.heightCm ?? 170,
        alcohol: hraAnswers.alcohol ?? 'Never',
        sleepHours: hraAnswers.sleepHours ?? 7,
        stress: hraAnswers.stress ?? 'Mild',
        anxietyFrequency: hraAnswers.anxietyFrequency,
      })
    : null;

  const handleLabChange = (key: string, value: string) => {
    const num = parseFloat(value);
    if (!isNaN(num)) setLabValues({ ...labValues, [key]: num });
    else {
      const updated = { ...labValues };
      delete updated[key];
      setLabValues(updated);
    }
  };

  const loadSample = () => setLabValues(SAMPLE_LABS);

  const handleSubmit = async () => {
    setError('');
    if (!patientForm.name || !patientForm.department || !patientForm.city) {
      return setError('Please fill in all patient fields');
    }
    if (Object.keys(labValues).length < 5) {
      return setError('Please enter at least 5 lab values');
    }
    if (!hraAnswers.stress) {
      return setError('Please complete the HRA questionnaire');
    }

    setLoading(true);
    try {
      const fullHra: HraAnswers = {
        gender: hraAnswers.gender ?? 'MALE',
        dob: hraAnswers.dob ?? '1980-01-01',
        weightKg: hraAnswers.weightKg ?? 70,
        heightCm: hraAnswers.heightCm ?? 170,
        alcohol: hraAnswers.alcohol ?? 'Never',
        sleepHours: hraAnswers.sleepHours ?? 7,
        stress: hraAnswers.stress ?? 'Mild',
        anxietyFrequency: hraAnswers.anxietyFrequency,
      };

      const res = await patientsApi.create({
        ...patientForm,
        labValues,
        hraAnswers: fullHra,
      });

      setPatientId(res.data.patient.id);
      setAllocation(res.data.allocation);
      setEngagementScore(res.data.engagementScore);
      setStep(2);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } };
      setError(err.response?.data?.error ?? 'Failed to create patient');
    } finally {
      setLoading(false);
    }
  };

  const showAnxiety = hraAnswers.stress === 'Moderate' || hraAnswers.stress === 'High' || hraAnswers.stress === 'ExtHigh';

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Step 1 — Patient Data Entry & HRA</h1>
        <p className="text-gray-500 text-sm mt-1">Enter employee details, upload or manually input lab results, and complete the HRA.</p>
      </div>

      {/* Employee Profile */}
      <div className="card">
        <h2 className="font-semibold text-gray-800 mb-4">Employee Profile</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full Name *</label>
            <input className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={patientForm.name} onChange={(e) => setPatientForm({ name: e.target.value })} placeholder="Rajesh Kumar" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Age *</label>
            <input type="number" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={patientForm.age} onChange={(e) => setPatientForm({ age: parseInt(e.target.value) || 0 })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Gender *</label>
            <select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={patientForm.gender} onChange={(e) => setPatientForm({ gender: e.target.value as 'MALE' | 'FEMALE' | 'OTHER' })}>
              <option value="MALE">Male</option>
              <option value="FEMALE">Female</option>
              <option value="OTHER">Other</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Department *</label>
            <input className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={patientForm.department} onChange={(e) => setPatientForm({ department: e.target.value })} placeholder="Engineering" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">City *</label>
            <input className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={patientForm.city} onChange={(e) => setPatientForm({ city: e.target.value })} placeholder="Mumbai" />
          </div>
        </div>
      </div>

      {/* Lab Report */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-800">Lab Report</h2>
          <div className="flex gap-2">
            <button onClick={() => setLabMode('manual')} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${labMode === 'manual' ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}>
              <PenLine size={14} /> Manual Entry
            </button>
            <button onClick={() => setLabMode('upload')} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${labMode === 'upload' ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}>
              <Upload size={14} /> Upload PDF
            </button>
            <button onClick={loadSample} className="px-3 py-1.5 rounded-lg text-sm font-medium border border-gray-300 text-gray-600 hover:bg-gray-50">
              Load Sample
            </button>
          </div>
        </div>

        {labMode === 'upload' && (
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center mb-4 bg-gray-50">
            <Upload size={32} className="mx-auto text-gray-400 mb-2" />
            <p className="text-gray-500 text-sm">Upload PDF lab report for auto-extraction</p>
            <p className="text-xs text-gray-400 mt-1">(Simulated — click Load Sample to auto-fill)</p>
            <button onClick={loadSample} className="mt-3 btn-primary text-sm">
              Simulate PDF Extraction
            </button>
          </div>
        )}

        <div className="space-y-4">
          {LAB_GROUPS.map((group) => (
            <div key={group}>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">{group}</h3>
              <div className="grid grid-cols-3 gap-3">
                {LAB_FIELDS.filter((f) => f.group === group).map((field) => (
                  <div key={field.key}>
                    <label className="block text-xs text-gray-600 mb-1">{field.label}</label>
                    <input
                      type="number"
                      step="0.01"
                      className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      value={labValues[field.key] ?? ''}
                      onChange={(e) => handleLabChange(field.key, e.target.value)}
                      placeholder="—"
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* HRA */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-800">Health Risk Assessment (HRA)</h2>
          {liveEngagement !== null && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Live Score:</span>
              <span className={`badge text-sm font-bold ${liveEngagement >= 70 ? 'bg-green-100 text-green-800' : liveEngagement >= 40 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'}`}>
                {liveEngagement}/100
              </span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Q2 Date of Birth</label>
            <input type="date" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={hraAnswers.dob ?? ''} onChange={(e) => setHraAnswers({ dob: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Q3 Weight (kg)</label>
            <input type="number" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={hraAnswers.weightKg ?? ''} onChange={(e) => setHraAnswers({ weightKg: parseFloat(e.target.value) || 0 })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Q4 Height (cm)</label>
            <input type="number" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={hraAnswers.heightCm ?? ''} onChange={(e) => setHraAnswers({ heightCm: parseFloat(e.target.value) || 0 })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Q5 Alcohol Consumption</label>
            <select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={hraAnswers.alcohol ?? ''} onChange={(e) => setHraAnswers({ alcohol: e.target.value as HraAnswers['alcohol'] })}>
              <option value="">Select...</option>
              <option value="Never">Never</option>
              <option value="Occasional">Occasional</option>
              <option value="Light">Light (1-2 drinks/week)</option>
              <option value="Moderate">Moderate (3-5 drinks/week)</option>
              <option value="Heavy">Heavy (daily)</option>
              <option value="Binge">Binge drinking</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Q6 Sleep (hours/night)</label>
            <input type="number" step="0.5" min="0" max="12" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={hraAnswers.sleepHours ?? ''} onChange={(e) => setHraAnswers({ sleepHours: parseFloat(e.target.value) || 0 })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Q7 Stress Level</label>
            <select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={hraAnswers.stress ?? ''} onChange={(e) => setHraAnswers({ stress: e.target.value as HraAnswers['stress'] })}>
              <option value="">Select...</option>
              <option value="VeryLow">Very Low</option>
              <option value="Mild">Mild</option>
              <option value="Moderate">Moderate</option>
              <option value="High">High</option>
              <option value="ExtHigh">Extremely High</option>
            </select>
          </div>
          {showAnxiety && (
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Q9 Anxiety / Nervousness Frequency</label>
              <select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={hraAnswers.anxietyFrequency ?? ''} onChange={(e) => setHraAnswers({ anxietyFrequency: e.target.value as HraAnswers['anxietyFrequency'] })}>
                <option value="">Select...</option>
                <option value="Never">Never</option>
                <option value="Rarely">Rarely</option>
                <option value="Sometimes">Sometimes</option>
                <option value="Often">Often</option>
                <option value="AlmostEveryDay">Almost Every Day</option>
              </select>
            </div>
          )}
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>}

      <div className="flex justify-end">
        <button onClick={handleSubmit} disabled={loading} className="btn-primary flex items-center gap-2">
          {loading ? 'Processing...' : 'Submit & Score →'}
          {!loading && <ChevronRight size={16} />}
        </button>
      </div>
    </div>
  );
}
