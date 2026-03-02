import type { HraAnswers } from '../types';

export function calculateEngagementScore(hra: HraAnswers): number {
  const bmi = hra.weightKg / Math.pow(hra.heightCm / 100, 2);
  let score = 50;

  // BMI adjustment
  if (bmi < 25) score += 5;
  else if (bmi <= 27) score += 0;
  else if (bmi <= 30) score -= 5;
  else score -= 10;

  // Alcohol
  const alcoholMap: Record<string, number> = {
    Never: 5,
    Occasional: 2,
    Light: 0,
    Moderate: -8,
    Heavy: -12,
    Binge: -15,
  };
  score += alcoholMap[hra.alcohol] ?? 0;

  // Sleep
  if (hra.sleepHours < 6) score -= 10;
  else if (hra.sleepHours <= 7) score -= 3;
  else if (hra.sleepHours <= 8) score += 10;
  else score -= 2;

  // Stress
  const stressMap: Record<string, number> = {
    VeryLow: 10,
    Mild: 5,
    Moderate: -8,
    High: -12,
    ExtHigh: -18,
  };
  score += stressMap[hra.stress] ?? 0;

  // Compound: sleep < 6h AND stress >= High → additional -10
  if (hra.sleepHours < 6 && (hra.stress === 'High' || hra.stress === 'ExtHigh')) {
    score -= 10;
  }

  // Anxiety Q9 (conditional on stress >= Moderate)
  if (hra.anxietyFrequency) {
    const anxietyMap: Record<string, number> = {
      Never: 5,
      Rarely: 0,
      Sometimes: -5,
      Often: -10,
      AlmostEveryDay: -15,
    };
    score += anxietyMap[hra.anxietyFrequency] ?? 0;
  }

  return Math.max(0, Math.min(100, score));
}
