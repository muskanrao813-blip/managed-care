import type { ActivityDomain, ActivityStatus, PlannedActivity, PatientInput } from '../types';
import { ACTIVITY_META } from '../constants/activities';

export const PERSONA_PREFERENCES: Record<string, { preferred: string[]; avoided: string[] }> = {
  RESILIENT: {
    preferred: ['daily_mood_check', 'water_intake_log', 'gratitude_check_in', 'mindfulness_moment', 'sleep_quality_log'],
    avoided: ['step_burst_challenge', 'gym_session_strength', 'weekly_step_challenge', 'diet_rainbow_challenge'],
  },
  ENCOURAGEMENT_SEEKER: {
    preferred: ['mental_wellness_guided_session', 'gratitude_check_in', 'body_scan_awareness', 'sleep_quality_log', 'circle_of_care_ask_for_support'],
    avoided: ['step_burst_challenge', 'gym_session_strength'],
  },
  CHALLENGE_LOVER: {
    preferred: ['step_burst_challenge', 'stair_challenge', 'active_hour_challenge', 'gym_session_cardio', 'gym_session_strength', 'weekly_step_challenge', 'diet_rainbow_challenge'],
    avoided: ['sleep_quality_log', 'gratitude_check_in'],
  },
  HABIT_FORMER: {
    preferred: ['meal_log_full_day', 'water_intake_log', 'diet_meal_timing_log', 'weekly_weigh_in'],
    avoided: ['step_burst_challenge', 'active_hour_challenge'],
  },
  SOCIAL: {
    preferred: ['circle_of_care_weekly_share', 'circle_of_care_family_meal_challenge', 'circle_of_care_caregiver_guide'],
    avoided: ['hra_vitals_awareness_check'],
  },
  ACHIEVER: {
    preferred: ['weekly_step_challenge', 'step_burst_challenge', 'gym_session_cardio', 'habit_guide_challenge', 'circle_of_care_milestone_share'],
    avoided: ['mental_health_education_bite'],
  },
  DATA_DRIVEN: {
    preferred: ['binah_face_scan', 'glucometer_reading_log', 'diabetes_ai_glucose_pattern_review', 'hra_vitals_awareness_check'],
    avoided: ['mental_wellness_guided_session'],
  },
  SCIENCE_SEEKER: {
    preferred: ['disease_education_module', 'hra_disease_risk_quiz', 'mental_health_education_bite', 'smart_insight_of_the_day'],
    avoided: ['circle_of_care_milestone_share'],
  },
};

function dayOfWeek(day: number): number {
  return ((day - 1) % 7) + 1; // 1=Mon ... 7=Sun
}

function weekNumber(day: number): number {
  return Math.ceil(day / 7);
}

function isWeeklyDay(day: number, target: number): boolean {
  return dayOfWeek(day) === target;
}

function isBiweeklyDays(day: number, targets: number[]): boolean {
  return targets.includes(dayOfWeek(day));
}

function isAltweeklyOdd(day: number, target: number): boolean {
  return dayOfWeek(day) === target && weekNumber(day) % 2 === 1;
}

function isAltweeklyEven(day: number, target: number): boolean {
  return dayOfWeek(day) === target && weekNumber(day) % 2 === 0;
}

function isCadenceDay(day: number, cadenceDays: number[]): boolean {
  return cadenceDays.includes(day);
}

function isMonthly(day: number): boolean {
  // Fires on day 1 of each 28-day block
  return (day - 1) % 28 === 0;
}

function isMonthlyDayN(day: number, targetDow: number): boolean {
  // Fires if it's the target DOW in the first week of each 28-day block
  const blockDay = ((day - 1) % 28) + 1;
  return blockDay <= 7 && dayOfWeek(day) === targetDow;
}

function getActivitiesForDay(
  day: number,
  patient: PatientInput,
  cohort: string,
  programId: string
): string[] {
  const activities: string[] = [];

  // --- DIET ---
  if (isBiweeklyDays(day, [1, 3])) activities.push('meal_log_full_day');
  if (isBiweeklyDays(day, [1, 4])) activities.push('diet_meal_timing_log');
  if (isAltweeklyOdd(day, 3)) activities.push('diet_food_swap_challenge');
  if (isAltweeklyOdd(day, 2)) activities.push('diet_calorie_audit_day');
  if (isAltweeklyOdd(day, 5)) activities.push('diet_hydration_focus_day');
  if (isAltweeklyEven(day, 2)) activities.push('diet_food_mood_journal');
  if (isAltweeklyEven(day, 4)) activities.push('diet_rainbow_challenge');
  if (isAltweeklyEven(day, 7)) activities.push('diet_gut_health_day');

  // --- STEPS ---
  if (isWeeklyDay(day, 1)) activities.push('weekly_step_challenge');
  if (isAltweeklyOdd(day, 2)) activities.push('step_burst_challenge');
  if (isBiweeklyDays(day, [3, 5])) activities.push('post_meal_walk_prompt');
  if (isWeeklyDay(day, 6)) activities.push('active_hour_challenge');
  if (isAltweeklyOdd(day, 4)) activities.push('stair_challenge');
  if (isAltweeklyEven(day, 2)) activities.push('active_commute_day');
  if (isAltweeklyEven(day, 7)) activities.push('nature_walk_prompt');
  if (isAltweeklyEven(day, 4)) activities.push('move_every_hour_challenge');

  // --- MENTAL ---
  if (isBiweeklyDays(day, [2, 5])) activities.push('mental_wellness_guided_session');
  if (isAltweeklyOdd(day, 3)) activities.push('sleep_quality_log');
  if (isWeeklyDay(day, 4)) activities.push('stress_journal');
  if (isAltweeklyOdd(day, 7)) activities.push('gratitude_check_in');
  if (isWeeklyDay(day, 6)) activities.push('digital_detox_nudge');
  if (isAltweeklyOdd(day, 2)) activities.push('social_wellness_prompt');
  if (isAltweeklyOdd(day, 1)) activities.push('mental_health_education_bite');
  if (isAltweeklyEven(day, 2)) activities.push('emotional_eating_check');
  if (isAltweeklyEven(day, 1)) activities.push('body_scan_awareness');
  if (isAltweeklyEven(day, 3)) activities.push('mindfulness_moment');
  if (isAltweeklyEven(day, 7)) activities.push('joy_activity_prompt');
  if (isCadenceDay(day, [21, 51, 81, 111, 141, 171])) activities.push('sleep_hygiene_audit');

  // --- COC ---
  if (isWeeklyDay(day, 5)) activities.push('circle_of_care_weekly_share');
  if (isCadenceDay(day, [30, 60, 90, 120, 150])) activities.push('circle_of_care_milestone_share');
  if (isMonthly(day)) activities.push('circle_of_care_family_meal_challenge');
  if (isAltweeklyEven(day, 3)) activities.push('circle_of_care_caregiver_guide');
  if (isMonthlyDayN(day, 7)) activities.push('circle_of_care_checkin_call'); // approx monthly day 28
  if (isMonthlyDayN(day, 1)) activities.push('circle_of_care_shared_goal'); // approx monthly day 15
  if (isAltweeklyEven(day, 2)) activities.push('circle_of_care_ask_for_support');
  // circle_of_care_appreciation_note: monthly last Sunday
  if (isMonthlyDayN(day, 7) && ((day - 1) % 28) >= 21) activities.push('circle_of_care_appreciation_note');

  // --- HRA ---
  const hraPeriodicDays: Record<string, number[]> = {
    VERY_HIGH: [30, 60, 90, 120, 150, 180],
    HIGH: [60, 120, 180],
    MODERATE: [90, 180],
  };
  if (isCadenceDay(day, hraPeriodicDays[cohort] ?? [])) activities.push('hra_periodic_checkin');
  if (isWeeklyDay(day, 3)) activities.push('hra_weekly_symptom_check');
  if (isWeeklyDay(day, 1)) activities.push('hra_energy_tracker');
  if (isCadenceDay(day, [15, 45, 75, 105, 135, 165])) activities.push('hra_medication_side_effect_log');
  // hra_lifestyle_self_assessment: day after hra_periodic_checkin
  if (isCadenceDay(day, (hraPeriodicDays[cohort] ?? []).map((d) => d + 1))) activities.push('hra_lifestyle_self_assessment');
  if (isCadenceDay(day, [10, 40, 70, 100, 130, 160])) activities.push('hra_vitals_awareness_check');
  if (isCadenceDay(day, [20, 50, 80, 110, 140, 170])) activities.push('hra_disease_risk_quiz');
  if (isCadenceDay(day, [22, 52, 82, 112, 142, 172])) activities.push('hra_sleep_hygiene_audit'); // day after sleep_hygiene_audit
  if (isMonthlyDayN(day, 7)) activities.push('hra_body_measurement_log');

  // --- WEIGHT ---
  if (isWeeklyDay(day, 1)) activities.push('weekly_weigh_in');
  if (isMonthlyDayN(day, 3)) activities.push('waist_measurement_monthly');
  if (isCadenceDay(day, [14, 28, 42, 56, 70, 84, 98, 112, 126, 140, 154, 168])) activities.push('weight_trend_review');
  if (isAltweeklyOdd(day, 4)) activities.push('portion_plate_challenge');
  if (isCadenceDay(day, [30, 60, 90, 120, 150, 180])) activities.push('bmi_awareness_check');
  if (isAltweeklyEven(day, 2)) activities.push('sodium_sugar_awareness_day');
  if (isMonthlyDayN(day, 3) && ((day - 1) % 28) >= 14) activities.push('no_scale_body_check');
  if (isCadenceDay(day, [25, 55, 85, 115, 145, 175])) activities.push('visceral_fat_awareness');
  if (isAltweeklyOdd(day, 6)) activities.push('mindful_eating_day');

  // --- CLINICAL/DEVICE-BASED ---
  if (isBiweeklyDays(day, [1, 4])) activities.push('binah_face_scan');
  // glucometer/smart_scale/wearable: daily — only if relevant benefits exist (checked at gate)
  activities.push('glucometer_reading_log');
  activities.push('smart_scale_reading_log');
  activities.push('wearable_steps_sync');
  if (isWeeklyDay(day, 1)) activities.push('wearable_hrv_sync');

  // --- GYM (VERY_HIGH only) ---
  if (cohort === 'VERY_HIGH') {
    if (isWeeklyDay(day, 1)) activities.push('gym_session_cardio');
    if (isWeeklyDay(day, 3)) activities.push('gym_session_strength');
    if (isWeeklyDay(day, 5)) activities.push('gym_session_yoga');
  }

  // --- EDUCATION/AI ---
  if (isWeeklyDay(day, 2)) activities.push('disease_education_module');
  if ((cohort === 'HIGH' || cohort === 'VERY_HIGH') && programId === 'DIABETES') {
    if (isWeeklyDay(day, 3)) activities.push('diabetes_ai_glucose_pattern_review');
    if (isWeeklyDay(day, 6)) activities.push('diabetes_ai_weekly_report');
  }

  return [...new Set(activities)]; // deduplicate
}

export function build180DayPlan(patient: PatientInput): PlannedActivity[] {
  const baseDate = new Date();
  baseDate.setHours(0, 0, 0, 0);

  const pref = PERSONA_PREFERENCES[patient.personaStyle] ?? { preferred: [], avoided: [] };
  const isResilient = patient.personaStyle === 'RESILIENT';

  const evergreenTypes = [
    'water_intake_log',
    'daily_mood_check',
    'smart_insight_of_the_day',
    'diet_plan_reminder',
    'daily_step_count',
    'habit_guide_challenge',
  ];

  const results: PlannedActivity[] = [];

  const getDensityCap = (phase: string): number => {
    if (isResilient) return 1;
    if (patient.engagementCapacity === 'LOW') return phase === 'FOUNDATION' ? 2 : 3;
    if (patient.engagementCapacity === 'MEDIUM') return phase === 'FOUNDATION' ? 3 : 5;
    return phase === 'FOUNDATION' ? 4 : 7;
  };

  for (let day = 1; day <= 180; day++) {
    const scheduledDate = new Date(baseDate);
    scheduledDate.setDate(baseDate.getDate() + day - 1);

    const phase = day <= 30 ? 'FOUNDATION' : day <= 90 ? 'BUILDING' : 'MASTERY';
    const densityCap = getDensityCap(phase);

    // Always add evergreen activities
    for (const actType of evergreenTypes) {
      const meta = ACTIVITY_META[actType];
      if (!meta) continue;
      results.push({
        patientId: patient.id,
        dayNumber: day,
        activityType: actType,
        domain: meta.domain,
        isClinical: meta.isClinical,
        isEvergreen: true,
        status: 'PENDING' as ActivityStatus,
        scheduledDate: new Date(scheduledDate),
        pointsEarned: 0,
        intent: meta.intent,
        completionLogic: meta.completionLogic,
        benefitGatePoints: meta.benefitGatePoints,
      });
    }

    // Get non-evergreen candidates for this day
    let candidates = getActivitiesForDay(day, patient, patient.cohort, patient.programId);

    // FOUNDATION phase restrictions
    if (phase === 'FOUNDATION') {
      candidates = candidates.filter(
        (a) => !['gym_session_cardio', 'gym_session_strength', 'gym_session_yoga',
          'step_burst_challenge', 'diabetes_ai_glucose_pattern_review', 'diabetes_ai_weekly_report'].includes(a)
      );
    }

    // LOW engagement: no high-intensity in first 30 days
    if (patient.engagementScore < 40 && day <= 30) {
      candidates = candidates.filter(
        (a) => !['step_burst_challenge', 'active_hour_challenge', 'gym_session_cardio',
          'gym_session_strength', 'gym_session_yoga'].includes(a)
      );
    }

    // Apply persona avoid list
    candidates = candidates.filter((a) => !pref.avoided.includes(a));

    // Sort: preferred first, then alphabetical
    candidates.sort((a, b) => {
      const aPreferred = pref.preferred.includes(a) ? 0 : 1;
      const bPreferred = pref.preferred.includes(b) ? 0 : 1;
      return aPreferred - bPreferred || a.localeCompare(b);
    });

    // Apply density cap
    const capped = candidates.slice(0, densityCap);

    for (const actType of capped) {
      const meta = ACTIVITY_META[actType];
      if (!meta) continue;

      // Determine status based on benefit gate
      const status: ActivityStatus =
        meta.benefitGatePoints > 0 && patient.points < meta.benefitGatePoints
          ? 'LOCKED'
          : 'PENDING';

      results.push({
        patientId: patient.id,
        dayNumber: day,
        activityType: actType,
        domain: meta.domain,
        isClinical: meta.isClinical,
        isEvergreen: false,
        status,
        scheduledDate: new Date(scheduledDate),
        pointsEarned: 0,
        intent: meta.intent,
        completionLogic: meta.completionLogic,
        benefitGatePoints: meta.benefitGatePoints,
      });
    }
  }

  return results;
}
