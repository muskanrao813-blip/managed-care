export type Gender = 'MALE' | 'FEMALE' | 'OTHER';
export type Cohort = 'MODERATE' | 'HIGH' | 'VERY_HIGH';
export type EngagementCapacity = 'LOW' | 'MEDIUM' | 'HIGH';
export type Level = 'BRONZE' | 'SILVER' | 'GOLD' | 'PLATINUM';
export type FrustrationStage = 'NORMAL' | 'CAUTION' | 'BACKOFF' | 'SOFT_REST';
export type ActivityStatus = 'PENDING' | 'COMPLETED' | 'MISSED' | 'ATTEMPTED' | 'LOCKED';
export type ActivityDomain = 'DIET' | 'STEPS' | 'MENTAL' | 'COC' | 'HRA' | 'WEIGHT' | 'CLINICAL' | 'EVERGREEN';
export type NudgeChannel = 'WHATSAPP' | 'APP_NUDGE' | 'VOICE_BOT' | 'AGENT_TASK';
export type NudgeStatus = 'PENDING' | 'SENT' | 'RESPONDED' | 'IGNORED' | 'CANCELLED';
export type AppointmentType = 'DOCTOR' | 'DIETICIAN' | 'LAB_TEST';
export type AppointmentStatus = 'SCHEDULED' | 'CONFIRMED' | 'COMPLETED' | 'RESCHEDULED' | 'MISSED';
export type SfdcTaskType = 'WELCOME_CALL' | 'MISSED_CONSULT' | 'MISSED_LAB' | 'MISSED_MEDICATION' | 'WORSENING_LAB' | 'EMERGENCY';
export type SfdcTaskPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
export type SfdcTaskStatus = 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'ESCALATED';
export type WellnessSessionType = 'MEDITATION' | 'BOX_BREATHING' | 'CBT' | 'PROGRESSIVE_RELAXATION' | 'GUIDED_IMAGERY' | 'GROUNDING';
export type MealType = 'BREAKFAST' | 'LUNCH' | 'DINNER' | 'SNACK';
export type StepSource = 'MANUAL' | 'WEARABLE' | 'PEDOMETER';
export type LabSource = 'UPLOAD' | 'MANUAL' | 'CHECK_IN';
export type ProgramId = 'DIABETES' | 'THYROID' | 'LIVER' | 'KIDNEY' | 'DYSLIPIDEMIA';
export type MotivationalStyle =
  | 'RESILIENT'
  | 'ENCOURAGEMENT_SEEKER'
  | 'CHALLENGE_LOVER'
  | 'HABIT_FORMER'
  | 'SOCIAL'
  | 'ACHIEVER'
  | 'DATA_DRIVEN'
  | 'SCIENCE_SEEKER';
export type ClinicalUrgency = 'CRITICAL' | 'ELEVATED' | 'MANAGED';

export interface Persona {
  motivationalStyle: MotivationalStyle;
  engagementCapacity: EngagementCapacity;
  clinicalUrgency: ClinicalUrgency;
}

export interface TestBreakdown {
  testCode: string;
  value: number;
  label: string;
  outcomeValue: number;
  coefficient: number;
  contribution: number;
}

export interface DomainScore {
  domain: ProgramId;
  raw: number;
  normalized: number;
  cohort: Cohort | null;
  testBreakdown: TestBreakdown[];
}

export interface AllocationResult {
  programId: ProgramId;
  cohort: Cohort;
  reason: string;
  allDomainScores: DomainScore[];
}

export interface HraAnswers {
  gender: Gender;
  dob: string;
  weightKg: number;
  heightCm: number;
  alcohol: 'Never' | 'Occasional' | 'Light' | 'Moderate' | 'Heavy' | 'Binge';
  sleepHours: number;
  stress: 'VeryLow' | 'Mild' | 'Moderate' | 'High' | 'ExtHigh';
  sleepImpact?: string;
  anxietyFrequency?: 'Never' | 'Rarely' | 'Sometimes' | 'Often' | 'AlmostEveryDay';
}

export interface ActivityMeta {
  activityType: string;
  domain: ActivityDomain;
  isClinical: boolean;
  isEvergreen: boolean;
  defaultPoints: number;
  benefitGatePoints: number;
  intent: string;
  completionLogic: string;
  minDurationSeconds?: number;
  requiresBenefit?: string;
}

export interface PlannedActivity {
  patientId: string;
  dayNumber: number;
  activityType: string;
  domain: ActivityDomain;
  isClinical: boolean;
  isEvergreen: boolean;
  status: ActivityStatus;
  scheduledDate: Date;
  completedAt?: Date;
  pointsEarned: number;
  completionData?: Record<string, unknown>;
  intent: string;
  completionLogic: string;
  benefitGatePoints: number;
}

export interface PatientInput {
  id: string;
  programId: string;
  cohort: string;
  engagementScore: number;
  personaStyle: string;
  engagementCapacity: string;
  points: number;
  gender: string;
  age: number;
  hra?: HraAnswers;
}
