import { CLASSIFY_RANGES } from './labRanges';
import type { DomainScore, TestBreakdown, AllocationResult, Cohort, Gender, ProgramId } from '../types';

export const DOMAIN_TESTS: Record<ProgramId, { testCode: string; coeff: number }[]> = {
  DIABETES: [
    { testCode: 'HbA1c', coeff: 3 },
  ],
  THYROID: [
    { testCode: 'TSH', coeff: 3 },
    { testCode: 'T3', coeff: 2 },
    { testCode: 'T4', coeff: 2 },
  ],
  LIVER: [
    { testCode: 'Albumin', coeff: 2 },
    { testCode: 'ALP', coeff: 2 },
    { testCode: 'BilirubinDirect', coeff: 2 },
    { testCode: 'BilirubinTotal', coeff: 3 },
    { testCode: 'GGTP', coeff: 2 },
    { testCode: 'SGOT', coeff: 3 },
    { testCode: 'SGPT', coeff: 3 },
  ],
  KIDNEY: [
    { testCode: 'BUN', coeff: 2 },
    { testCode: 'Creatinine', coeff: 3 },
    { testCode: 'Urea', coeff: 2 },
    { testCode: 'UricAcid', coeff: 2 },
    { testCode: 'BUNCreatRatio', coeff: 2 },
  ],
  DYSLIPIDEMIA: [
    { testCode: 'TotalCholesterol', coeff: 3 },
    { testCode: 'HDL', coeff: 3 },
    { testCode: 'LDL', coeff: 3 },
    { testCode: 'NonHDL', coeff: 2 },
    { testCode: 'Triglycerides', coeff: 2 },
  ],
};

export const DOMAIN_MAX: Record<ProgramId, number> = {
  DIABETES: 9,
  THYROID: 21,
  LIVER: 51,
  KIDNEY: 33,
  DYSLIPIDEMIA: 39,
};

export function classifyBiomarker(
  testCode: string,
  value: number,
  gender: Gender
): { label: string; outcomeValue: 0 | 1 | 2 | 3 } {
  const key = `${testCode}_${gender}`;
  const buckets = CLASSIFY_RANGES[key];
  if (!buckets) return { label: 'Unknown', outcomeValue: 0 };
  for (const bucket of buckets) {
    if (value >= bucket.low && value <= bucket.high) {
      return { label: bucket.label, outcomeValue: bucket.outcomeValue };
    }
  }
  return { label: 'Unknown', outcomeValue: 0 };
}

export function calculateDomainScore(
  biomarkers: Record<string, number>,
  domain: ProgramId,
  gender: Gender
): DomainScore {
  const tests = DOMAIN_TESTS[domain];
  const maxPossible = DOMAIN_MAX[domain];
  let raw = 0;
  const testBreakdown: TestBreakdown[] = [];

  for (const { testCode, coeff } of tests) {
    const value = biomarkers[testCode];
    if (value === undefined || value === null) continue;
    const { label, outcomeValue } = classifyBiomarker(testCode, value, gender);
    const contribution = outcomeValue * coeff;
    raw += contribution;
    testBreakdown.push({ testCode, value, label, outcomeValue, coefficient: coeff, contribution });
  }

  const normalized = maxPossible > 0 ? (raw / maxPossible) * 10 : 0;
  const cohort: Cohort | null =
    normalized === 0 ? null : normalized < 5 ? 'MODERATE' : normalized < 8 ? 'HIGH' : 'VERY_HIGH';

  return { domain, raw, normalized, cohort, testBreakdown };
}

export function hasSeverelyHighInDomain(
  biomarkers: Record<string, number>,
  domain: ProgramId,
  gender: Gender
): boolean {
  const tests = DOMAIN_TESTS[domain];
  for (const { testCode } of tests) {
    const value = biomarkers[testCode];
    if (value === undefined || value === null) continue;
    const { outcomeValue } = classifyBiomarker(testCode, value, gender);
    if (outcomeValue === 3) return true;
  }
  return false;
}

const DOMAIN_PRIORITY: ProgramId[] = ['DIABETES', 'DYSLIPIDEMIA', 'LIVER', 'KIDNEY', 'THYROID'];

export function allocateProgram(
  biomarkers: Record<string, number>,
  gender: Gender
): AllocationResult {
  const allDomainScores = (Object.keys(DOMAIN_TESTS) as ProgramId[]).map((domain) =>
    calculateDomainScore(biomarkers, domain, gender)
  );

  // Rule 1: severely high wins, priority order
  const severelyHighDomains = DOMAIN_PRIORITY.filter((d) =>
    hasSeverelyHighInDomain(biomarkers, d, gender)
  );

  if (severelyHighDomains.length > 0) {
    const programId = severelyHighDomains[0];
    const score = allDomainScores.find((s) => s.domain === programId)!;
    const cohort: Cohort = score.cohort ?? 'VERY_HIGH';
    const triggerTest = score.testBreakdown.find((t) => t.outcomeValue === 3);
    return {
      programId,
      cohort,
      reason: `${triggerTest?.testCode ?? 'Lab value'} Severely High → ${programId} ${cohort}`,
      allDomainScores,
    };
  }

  // Rule 2: highest normalized score wins, tie-break by priority
  let bestScore: DomainScore | null = null;
  let bestDomain: ProgramId = 'DIABETES';

  for (const domain of DOMAIN_PRIORITY) {
    const score = allDomainScores.find((s) => s.domain === domain)!;
    if (!bestScore || score.normalized > bestScore.normalized) {
      bestScore = score;
      bestDomain = domain;
    }
  }

  const cohort: Cohort = bestScore?.cohort ?? 'MODERATE';
  return {
    programId: bestDomain,
    cohort,
    reason: `Highest normalized score (${bestScore?.normalized.toFixed(1)}/10) → ${bestDomain} ${cohort}`,
    allDomainScores,
  };
}
