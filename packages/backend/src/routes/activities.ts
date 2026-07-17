import { Router, Request, Response } from 'express';
import prisma from '../db';
import { emitActivityCompleted } from '../sockets';

const router = Router();

// POST /api/activities/:id/complete
router.post('/:id/complete', async (req: Request, res: Response) => {
  try {
    const { completionData } = req.body as { completionData?: Record<string, unknown> };

    const activity = await prisma.activity180Day.findUniqueOrThrow({ where: { id: req.params.id } });

    const meta = await prisma.activity180Day.findUnique({ where: { id: req.params.id } });
    if (!meta) return res.status(404).json({ error: 'Activity not found' });

    const pointsEarned = meta.benefitGatePoints === 0 ? getDefaultPoints(meta.activityType) : 0;

    const updated = await prisma.activity180Day.update({
      where: { id: req.params.id },
      data: {
        status: 'COMPLETED',
        completedAt: new Date(),
        pointsEarned,
        completionData: completionData ?? null,
      },
    });

    // Update patient points and check level
    const patient = await prisma.patient.findUniqueOrThrow({ where: { id: activity.patientId } });
    const newPoints = patient.points + pointsEarned;
    const newLevel = getLevel(newPoints);

    await prisma.patient.update({
      where: { id: activity.patientId },
      data: { points: newPoints, level: newLevel },
    });

    emitActivityCompleted(activity.patientId, req.params.id, pointsEarned);

    res.json({ activity: updated, pointsEarned, totalPoints: newPoints, level: newLevel });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// POST /api/activities/:id/attempt
router.post('/:id/attempt', async (req: Request, res: Response) => {
  try {
    const { completionData } = req.body as { completionData?: Record<string, unknown> };

    const updated = await prisma.activity180Day.update({
      where: { id: req.params.id },
      data: {
        status: 'ATTEMPTED',
        completionData: completionData ?? null,
      },
    });

    res.json(updated);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// GET /api/activities/patient/:id/today
router.get('/patient/:id/today', async (req: Request, res: Response) => {
  try {
    const patient = await prisma.patient.findUniqueOrThrow({ where: { id: req.params.id } });

    const activities = await prisma.activity180Day.findMany({
      where: { patientId: req.params.id, dayNumber: patient.dayNumber },
      orderBy: [{ isClinical: 'desc' }, { isEvergreen: 'desc' }, { activityType: 'asc' }],
    });

    res.json(activities);
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

function getDefaultPoints(activityType: string): number {
  const pointsMap: Record<string, number> = {
    daily_mood_check: 1,
    water_intake_log: 1,
    habit_guide_challenge: 1,
    meal_log_full_day: 6,
    diet_food_swap_challenge: 3,
    diet_meal_timing_log: 1,
    diet_hydration_focus_day: 2,
    diet_food_mood_journal: 2,
    diet_rainbow_challenge: 2,
    diet_gut_health_day: 2,
    diet_calorie_audit_day: 2,
    diet_dietician_challenge: 3,
    diet_weekly_dietician_review: 2,
    weekly_step_challenge: 10,
    step_burst_challenge: 3,
    post_meal_walk_prompt: 2,
    active_hour_challenge: 5,
    stair_challenge: 2,
    active_commute_day: 2,
    nature_walk_prompt: 2,
    move_every_hour_challenge: 3,
    mental_wellness_guided_session: 2,
    stress_journal: 2,
    gratitude_check_in: 1,
    sleep_quality_log: 1,
    sleep_hygiene_audit: 2,
    digital_detox_nudge: 1,
    social_wellness_prompt: 1,
    mental_health_education_bite: 2,
    emotional_eating_check: 1,
    body_scan_awareness: 2,
    mindfulness_moment: 2,
    joy_activity_prompt: 1,
    hra_energy_tracker: 1,
    hra_periodic_checkin: 2,
    hra_weekly_symptom_check: 1,
    hra_lifestyle_self_assessment: 2,
    hra_vitals_awareness_check: 2,
    hra_disease_risk_quiz: 2,
    hra_sleep_hygiene_audit: 2,
    hra_body_measurement_log: 1,
    hra_medication_side_effect_log: 1,
    circle_of_care_weekly_share: 3,
    circle_of_care_milestone_share: 5,
    circle_of_care_family_meal_challenge: 3,
    circle_of_care_caregiver_guide: 2,
    circle_of_care_checkin_call: 3,
    circle_of_care_shared_goal: 2,
    circle_of_care_ask_for_support: 2,
    circle_of_care_appreciation_note: 2,
    weekly_weigh_in: 2,
    waist_measurement_monthly: 2,
    weight_trend_review: 1,
    portion_plate_challenge: 2,
    bmi_awareness_check: 1,
    sodium_sugar_awareness_day: 2,
    no_scale_body_check: 1,
    visceral_fat_awareness: 2,
    mindful_eating_day: 2,
    binah_face_scan: 2,
    glucometer_reading_log: 1,
    smart_scale_reading_log: 1,
    wearable_hrv_sync: 1,
    gym_session_cardio: 3,
    gym_session_strength: 3,
    gym_session_yoga: 3,
    disease_education_module: 2,
    diabetes_ai_glucose_pattern_review: 2,
    diabetes_ai_weekly_report: 2,
  };
  return pointsMap[activityType] ?? 1;
}

function getLevel(points: number): 'BRONZE' | 'SILVER' | 'GOLD' | 'PLATINUM' {
  if (points >= 600) return 'PLATINUM';
  if (points >= 300) return 'GOLD';
  if (points >= 100) return 'SILVER';
  return 'BRONZE';
}

export default router;
