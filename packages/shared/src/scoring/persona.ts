import type { HraAnswers, Persona, MotivationalStyle, EngagementCapacity, ClinicalUrgency, Cohort } from '../types';

export function detectPersona(
  hra: HraAnswers,
  engagementScore: number,
  age: number,
  cohort: Cohort
): Persona {
  const engagementCapacity: EngagementCapacity =
    engagementScore >= 70 ? 'HIGH' : engagementScore >= 40 ? 'MEDIUM' : 'LOW';

  const clinicalUrgency: ClinicalUrgency =
    cohort === 'VERY_HIGH' ? 'CRITICAL' : cohort === 'HIGH' ? 'ELEVATED' : 'MANAGED';

  const isHighStress = hra.stress === 'High' || hra.stress === 'ExtHigh';

  let motivationalStyle: MotivationalStyle;

  if (isHighStress && hra.sleepHours < 6) {
    motivationalStyle = 'RESILIENT';
  } else if (isHighStress) {
    motivationalStyle = 'ENCOURAGEMENT_SEEKER';
  } else if (age <= 35 && engagementScore >= 60) {
    motivationalStyle = 'CHALLENGE_LOVER';
  } else if (age >= 50 && hra.stress === 'VeryLow') {
    motivationalStyle = 'HABIT_FORMER';
  } else if (hra.alcohol !== 'Never' && hra.stress === 'Moderate') {
    motivationalStyle = 'SOCIAL';
  } else if (engagementScore >= 70) {
    motivationalStyle = 'ACHIEVER';
  } else if (hra.stress === 'VeryLow' || hra.stress === 'Mild') {
    motivationalStyle = 'DATA_DRIVEN';
  } else {
    motivationalStyle = 'SCIENCE_SEEKER';
  }

  return { motivationalStyle, engagementCapacity, clinicalUrgency };
}
