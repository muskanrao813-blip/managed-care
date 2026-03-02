import { useSimulatorStore } from '../../store/useSimulatorStore';
import Step1DataEntry from './Step1DataEntry';
import Step2RiskScoring from './Step2RiskScoring';
import Step3ProgramAllocation from './Step3ProgramAllocation';
import Step4PlanBuilder from './Step4PlanBuilder';
import Step5Outcomes from './Step5Outcomes';

const STEPS = [
  { n: 1, label: 'Data Entry & HRA' },
  { n: 2, label: 'Risk Scoring' },
  { n: 3, label: 'Program Allocation' },
  { n: 4, label: '180-Day Plan' },
  { n: 5, label: 'Outcomes' },
];

export default function PMSimulator() {
  const { currentStep, setStep, patientId, allocation, engagementScore } = useSimulatorStore();

  return (
    <div className="flex h-[calc(100vh-52px)]">
      {/* Left sidebar */}
      <aside className="w-56 bg-white border-r border-gray-200 flex flex-col py-6 px-3 gap-1">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-3 mb-2">Simulator Steps</p>
        {STEPS.map((s) => (
          <button
            key={s.n}
            onClick={() => s.n <= (patientId ? 5 : 1) && setStep(s.n)}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all text-left ${
              currentStep === s.n
                ? 'bg-blue-600 text-white shadow'
                : s.n <= (patientId ? 5 : 1)
                ? 'text-gray-700 hover:bg-gray-100'
                : 'text-gray-300 cursor-not-allowed'
            }`}
          >
            <span className={`w-6 h-6 rounded-full text-xs flex items-center justify-center font-bold border-2 ${
              currentStep === s.n ? 'border-white text-white' : 'border-current'
            }`}>
              {s.n}
            </span>
            {s.label}
          </button>
        ))}
      </aside>

      {/* Main content */}
      <div className="flex-1 overflow-auto">
        <div className="flex h-full">
          <div className="flex-1 overflow-auto p-6">
            {currentStep === 1 && <Step1DataEntry />}
            {currentStep === 2 && <Step2RiskScoring />}
            {currentStep === 3 && <Step3ProgramAllocation />}
            {currentStep === 4 && <Step4PlanBuilder />}
            {currentStep === 5 && <Step5Outcomes />}
          </div>

          {/* Right sticky panel */}
          {patientId && allocation && (
            <aside className="w-64 bg-blue-50 border-l border-blue-100 p-4 flex flex-col gap-3 overflow-auto">
              <h3 className="font-semibold text-blue-900 text-sm">Patient Summary</h3>
              <div className="space-y-2 text-xs">
                <div className="bg-white rounded-lg p-3 border border-blue-100">
                  <p className="text-gray-500">Program</p>
                  <p className="font-bold text-blue-800">{allocation.programId}</p>
                </div>
                <div className="bg-white rounded-lg p-3 border border-blue-100">
                  <p className="text-gray-500">Cohort</p>
                  <span className={`badge font-semibold ${
                    allocation.cohort === 'VERY_HIGH'
                      ? 'bg-red-100 text-red-800'
                      : allocation.cohort === 'HIGH'
                      ? 'bg-orange-100 text-orange-800'
                      : 'bg-yellow-100 text-yellow-800'
                  }`}>
                    {allocation.cohort}
                  </span>
                </div>
                <div className="bg-white rounded-lg p-3 border border-blue-100">
                  <p className="text-gray-500">Engagement Score</p>
                  <p className="font-bold text-green-700">{engagementScore}/100</p>
                </div>
                <div className="bg-white rounded-lg p-3 border border-blue-100">
                  <p className="text-gray-500">Reason</p>
                  <p className="text-gray-700 leading-snug">{allocation.reason}</p>
                </div>
              </div>
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}
