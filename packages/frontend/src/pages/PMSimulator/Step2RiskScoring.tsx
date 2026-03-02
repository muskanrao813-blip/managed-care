import { useSimulatorStore } from '../../store/useSimulatorStore';
import { calculateDomainScore, classifyBiomarker } from '@managed-care/shared';
import type { ProgramId } from '@managed-care/shared';
import { ChevronRight } from 'lucide-react';

const DOMAINS: ProgramId[] = ['DIABETES', 'DYSLIPIDEMIA', 'LIVER', 'KIDNEY', 'THYROID'];

const OUTCOME_COLORS = ['text-gray-500', 'text-yellow-600', 'text-orange-600', 'text-red-600'];
const OUTCOME_BG = ['bg-white', 'bg-yellow-50', 'bg-orange-50', 'bg-red-50'];
const OUTCOME_LABELS = ['Normal', 'Borderline', 'High', 'Severely High'];

export default function Step2RiskScoring() {
  const { labValues, patientForm, allocation, setStep } = useSimulatorStore();
  const gender = patientForm.gender;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Step 2 — Risk Scoring</h1>
        <p className="text-gray-500 text-sm mt-1">Domain-by-domain breakdown of lab values and their clinical risk contribution.</p>
      </div>

      {DOMAINS.map((domain) => {
        const score = calculateDomainScore(labValues, domain, gender);
        return (
          <div key={domain} className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-gray-800">{domain}</h2>
              <div className="flex items-center gap-3">
                {score.cohort && (
                  <span className={`badge ${
                    score.cohort === 'VERY_HIGH' ? 'bg-red-100 text-red-800' :
                    score.cohort === 'HIGH' ? 'bg-orange-100 text-orange-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>
                    {score.cohort}
                  </span>
                )}
                {!score.cohort && <span className="badge bg-green-100 text-green-800">Normal</span>}
                <span className="text-sm font-mono text-gray-600">
                  {score.normalized.toFixed(1)}/10
                </span>
              </div>
            </div>

            {/* Score bar */}
            <div className="w-full bg-gray-100 rounded-full h-2 mb-4">
              <div
                className={`h-2 rounded-full transition-all ${
                  score.normalized >= 8 ? 'bg-red-500' :
                  score.normalized >= 5 ? 'bg-orange-400' :
                  score.normalized > 0 ? 'bg-yellow-400' :
                  'bg-green-400'
                }`}
                style={{ width: `${Math.min(100, score.normalized * 10)}%` }}
              />
            </div>

            {/* Test breakdown table */}
            {score.testBreakdown.length > 0 ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-100">
                    <th className="text-left pb-1.5">Test</th>
                    <th className="text-right pb-1.5">Value</th>
                    <th className="text-left pb-1.5 pl-3">Classification</th>
                    <th className="text-right pb-1.5">Outcome Value</th>
                    <th className="text-right pb-1.5">Coeff</th>
                    <th className="text-right pb-1.5">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {score.testBreakdown.map((t) => {
                    const { label } = classifyBiomarker(t.testCode, t.value, gender);
                    return (
                      <tr key={t.testCode} className={`border-b border-gray-50 ${OUTCOME_BG[t.outcomeValue]}`}>
                        <td className="py-1.5 font-medium">{t.testCode}</td>
                        <td className="text-right font-mono">{t.value}</td>
                        <td className={`pl-3 ${OUTCOME_COLORS[t.outcomeValue]}`}>{label}</td>
                        <td className={`text-right font-bold ${OUTCOME_COLORS[t.outcomeValue]}`}>{t.outcomeValue}</td>
                        <td className="text-right text-gray-500">×{t.coefficient}</td>
                        <td className="text-right font-semibold">{t.contribution}</td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr className="border-t border-gray-200">
                    <td colSpan={5} className="pt-1.5 text-gray-500 font-medium">Domain Score</td>
                    <td className="text-right font-bold">{score.raw}</td>
                  </tr>
                </tfoot>
              </table>
            ) : (
              <p className="text-xs text-gray-400 italic">No lab values provided for this domain.</p>
            )}
          </div>
        );
      })}

      <div className="card bg-blue-50 border-blue-200">
        <h3 className="font-semibold text-blue-900">Color Legend</h3>
        <div className="flex gap-4 mt-2">
          {OUTCOME_LABELS.map((label, i) => (
            <div key={i} className="flex items-center gap-1.5">
              <div className={`w-3 h-3 rounded-sm ${['bg-white border border-gray-300', 'bg-yellow-100', 'bg-orange-100', 'bg-red-100'][i]}`} />
              <span className={`text-xs ${OUTCOME_COLORS[i]}`}>{label}</span>
            </div>
          ))}
        </div>
      </div>

      {allocation && (
        <div className="card bg-blue-900 text-white">
          <p className="text-blue-300 text-sm">Allocation Result</p>
          <p className="text-2xl font-bold mt-1">{allocation.programId} — {allocation.cohort}</p>
          <p className="text-blue-200 text-sm mt-1">{allocation.reason}</p>
        </div>
      )}

      <div className="flex justify-end">
        <button onClick={() => setStep(3)} className="btn-primary flex items-center gap-2">
          Next: Program Allocation <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
