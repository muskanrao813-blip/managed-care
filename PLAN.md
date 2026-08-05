# AI Care Coordinator — Complete Implementation Plan
**VYTAL Managed Care Programme · Bajaj Finserv Health**
_Grounded in: `C:\Users\muskan.rao\Documents\managed-care-platform`_

---

## Table of Contents

1. [Stack & What's Already Built](#1-stack--whats-already-built)
2. [Programme Clinical Context Configs](#2-programme-clinical-context-configs)
3. [Programme Benefit Caps](#3-programme-benefit-caps)
4. [Complete Agent Architecture](#4-complete-agent-architecture)
5. [Database Schema — Additions to Existing Prisma Schema](#5-database-schema--additions-to-existing-prisma-schema)
6. [Dashboard — Care Coordinator Tab](#6-dashboard--care-coordinator-tab)
7. [File Structure](#7-file-structure)
8. [Build Phases](#8-build-phases)
9. [Guardrails Summary](#9-guardrails-summary)

---

## 1. Stack & What's Already Built

### Tech Stack
| Layer | Technology |
|---|---|
| Backend | Node.js + Express + TypeScript |
| Database | PostgreSQL via Prisma ORM |
| Frontend | React + Vite + TypeScript + Tailwind CSS |
| Shared | `packages/shared` — types, scoring, activity constants |
| AI | `claude-sonnet-4-6` via Anthropic SDK |
| Real-time | Socket.IO (`packages/backend/src/sockets`) |

### Already Built (do not rebuild)

| Component | Location | Notes |
|---|---|---|
| Prisma schema | `packages/backend/prisma/schema.prisma` | Patient, LabReport, HraResponse, Activity180Day, ClinicalAppointment, NudgeEvent, OutcomePrediction, SfdcTask, WellnessSession, StepLog, MoodLog, MealLog |
| Engagement score | `packages/shared/src/scoring/engagementScore.ts` | BMI, alcohol, sleep, stress, anxiety from HRA → 0–100 |
| Persona detection | `packages/shared/src/scoring/persona.ts` | 8 styles: RESILIENT, ENCOURAGEMENT_SEEKER, CHALLENGE_LOVER, HABIT_FORMER, SOCIAL, ACHIEVER, DATA_DRIVEN, SCIENCE_SEEKER |
| Activity catalogue | `packages/shared/src/constants/activities.ts` | 50+ activities across DIET, STEPS, MENTAL, COC, HRA, WEIGHT, CLINICAL, EVERGREEN domains |
| Plan builder | `packages/shared/src/scoring/planBuilder.ts` | Persona-aware 180-day activity scheduler |
| Daily outcomes job | `packages/backend/src/jobs/dailyOutcomes.ts` | S-curve outcome prediction by programme + cohort |
| Escalations job | `packages/backend/src/jobs/escalations.ts` | Tier-based nudge escalation: WA (T1) → App (T2, 6h) → Voice (T3, 12h) → SFDC Task (24h) |
| Lab scoring | `packages/shared/src/scoring/domainScoring.ts` | Lab ranges + domain scores |
| Lab ranges | `packages/shared/src/scoring/labRanges.ts` | Per-programme biomarker thresholds |
| Types | `packages/shared/src/types/index.ts` | All shared TypeScript types |
| Routes | `packages/backend/src/routes/` | patients, activities, appointments, nudges, outcomes, sfdc, wellness, stepLogs, mealLogs, moodLogs |
| Frontend pages | `packages/frontend/src/pages/` | PMSimulator (5-step), PatientApp, AgentView |
| Real-time events | `packages/backend/src/sockets/index.ts` | escalationFired, agentTaskCreated, outcomeUpdated |

### Key Enums Already in Prisma
```
Cohort:            MODERATE | HIGH | VERY_HIGH
FrustrationStage:  NORMAL | CAUTION | BACKOFF | SOFT_REST
ActivityDomain:    DIET | STEPS | MENTAL | COC | HRA | WEIGHT | CLINICAL | EVERGREEN
NudgeChannel:      WHATSAPP | APP_NUDGE | VOICE_BOT | AGENT_TASK
SfdcTaskType:      WELCOME_CALL | MISSED_CONSULT | MISSED_LAB | MISSED_MEDICATION | WORSENING_LAB | EMERGENCY
Level:             BRONZE | SILVER | GOLD | PLATINUM
```

---

## 2. Programme Clinical Context Configs

Add to `packages/shared/src/constants/programmeContext.ts` (new file).

```typescript
export const PROGRAMME_CONTEXT = {
  DIABETES: {
    product_codes: ['VYTAL0126', 'VYTAL0626'],
    specialist: 'Diabetologist / GP',
    primaryBiomarker: 'HbA1c',
    biomarkers: {
      HbA1c: { unit: '%', normal: '<5.7', moderate: '5.7–6.4', high: '6.5–8', very_high: '>8' },
    },
    escalation_thresholds: { HbA1c_delta: 1.0 },
    devices: { MODERATE: 'Glucometer', HIGH: 'Glucometer', VERY_HIGH: 'CGM' },
    dietary_focus: 'Low glycemic index, reduced refined carbs, portion control, 5 small meals',
    lifestyle_priority: ['smoking cessation', 'weight management', 'physical activity'],
    ai_model_unlock: ['HIGH', 'VERY_HIGH'],
    userLanguage: 'sugar levels',
  },
  DYSLIPIDEMIA: {
    product_codes: ['VYTAL0226', 'VYTAL0726'],
    specialist: 'Cardiologist / GP',
    primaryBiomarker: 'LDL',
    biomarkers: {
      Total_Cholesterol: { normal: '<200', high: '200–239', very_high: '≥240' },
      LDL:               { normal: '<100', high: '130–159', very_high: '≥160' },
      HDL:               { normal_male: '>40', normal_female: '>50' },
      Triglycerides:     { normal: '<150', high: '150–199', very_high: '≥200' },
    },
    escalation_thresholds: { LDL_delta: 30, TG_delta: 50 },
    devices: { MODERATE: 'Weighing Scale', HIGH: 'Weighing Scale + BP Monitor', VERY_HIGH: 'Weighing Scale + BP Monitor' },
    dietary_focus: 'Low saturated fat, high fibre, omega-3 rich foods, avoid trans fats',
    lifestyle_priority: ['weight management', 'smoking cessation', 'alcohol reduction'],
    ai_model_unlock: ['HIGH', 'VERY_HIGH'],
    userLanguage: 'cholesterol and lipid levels',
  },
  LIVER: {
    product_codes: ['VYTAL0326', 'VYTAL0826'],
    specialist: 'Gastroenterologist / GP',
    primaryBiomarker: 'SGPT',
    biomarkers: {
      SGOT:            { normal: '<40', high: '40–120', very_high: '>120' },
      SGPT:            { normal: '<40', high: '40–120', very_high: '>120' },
      ALP:             { normal: '<120' },
      GGT:             { normal_male: '<55', normal_female: '<38' },
      Bilirubin_Total: { normal: '<1.2' },
    },
    escalation_thresholds: { SGPT_delta: 30 },
    devices: { MODERATE: 'Weighing Scale', HIGH: 'Weighing Scale', VERY_HIGH: 'Weighing Scale' },
    dietary_focus: 'Avoid alcohol completely, low fat, no processed foods, small frequent meals',
    lifestyle_priority: ['alcohol cessation', 'weight management', 'avoid hepatotoxic drugs'],
    ai_model_unlock: ['HIGH', 'VERY_HIGH'],
    userLanguage: 'liver enzymes',
  },
  KIDNEY: {
    product_codes: ['VYTAL0426', 'VYTAL0926'],
    specialist: 'Nephrologist / GP',
    primaryBiomarker: 'Creatinine',
    biomarkers: {
      Creatinine: { normal: '0.7–1.2', high: '1.3–2.0', very_high: '>2.0' },
      BUN:        { normal: '7–20' },
      Uric_Acid:  { normal_male: '<7.0', normal_female: '<6.0' },
      eGFR:       { normal: '>90', moderate: '60–89', high: '30–59', very_high: '<30' },
    },
    escalation_thresholds: { Creatinine_delta: 0.3, eGFR_delta: -10 },
    devices: { MODERATE: 'Weighing Scale', HIGH: 'Weighing Scale', VERY_HIGH: 'Weighing Scale' },
    dietary_focus: 'Low protein, low sodium, low potassium (if severe), controlled fluid intake',
    lifestyle_priority: ['hydration management', 'avoid nephrotoxic drugs', 'BP control'],
    ai_model_unlock: ['HIGH', 'VERY_HIGH'],
    userLanguage: 'kidney function',
  },
  THYROID: {
    product_codes: ['VYTAL0526', 'VYTAL01026'],
    specialist: 'Endocrinologist / GP',
    primaryBiomarker: 'TSH',
    biomarkers: {
      TSH: { normal: '0.4–4.0', hypothyroid: '>4.0', hyperthyroid: '<0.4' },
      T3:  { normal: '80–200 ng/dL' },
      T4:  { normal: '5–12 µg/dL' },
    },
    escalation_thresholds: { TSH_fold_change: 2.0 },
    devices: { MODERATE: 'Weighing Scale', HIGH: 'Weighing Scale', VERY_HIGH: 'Weighing Scale' },
    dietary_focus: 'Iodine-adequate diet, avoid goitrogenic foods in excess, consistent meal timing',
    lifestyle_priority: ['medication timing adherence', 'stress management', 'weight monitoring'],
    ai_model_unlock: ['HIGH', 'VERY_HIGH'],
    userLanguage: 'thyroid levels',
  },
} as const;
```

---

## 3. Programme Benefit Caps

Add to `packages/shared/src/constants/programmeContext.ts`.

```typescript
export const BENEFIT_CAPS = {
  MODERATE: {
    doctor: 6, dietician: 6,
    lab_discount: 0.10, pharma_discount: 0.10,
    gym: 'Online Fitness only',
    mental_wellness: false, quit_smoking: false,
  },
  HIGH: {
    doctor: 8, dietician: 8,
    lab_discount: 0.15, pharma_discount: 0.15,
    gym: '12 sessions + Online Fitness',
    mental_wellness: true, quit_smoking: true,
  },
  VERY_HIGH: {
    doctor: 99, dietician: 99,  // 99 = unlimited; operationally 1/month
    lab_discount: 0.20, pharma_discount: 0.20,
    gym: '24 sessions + Online Fitness',
    mental_wellness: true, quit_smoking: true,
  },
} as const;

export const DEVICE_CAPS = {
  CGM: 100, Glucometer: 100, BP_Monitor: 100, Weighing_Scale: 100,
};

export const LIFESTYLE_CAPS = {
  Metabolic_Assessment: 200, Stress_Assessment: 100, Alcohol_Assessment: 100,
};

export const FOMO_THRESHOLD = 0.30; // trigger FOMO nudge when slots < 30% remaining
```

---

## 4. Complete Agent Architecture

The existing codebase has partial implementations. Below maps each agent to existing code and what must be added.

---

### Agent 1 — Orchestrator

**Status:** NOT YET BUILT — needs new file `packages/backend/src/agents/orchestrator.ts`

**Role:** Master scheduler. Reads both clinical and engagement lanes. Dispatches to correct agent. Never modifies data — only reads and routes.

#### Trigger Matrix

| Event | Action | Lane |
|---|---|---|
| Patient enrolled | Health Profiler → Psychology Profiler → Care Planner | Both |
| Day 1 | Communication Crafter (Welcome message) | Engagement |
| Day 30/45/60 per cohort | Appointment Coordinator (Doctor booking) | Clinical |
| Day 1 or post-doctor (HIGH/VERY_HIGH) | Appointment Coordinator (Diet booking) | Clinical |
| Day 90/180 per cohort | Appointment Coordinator (Lab booking) | Clinical |
| New lab report | Health Profiler → Care Planner (clinical lane only) | Clinical |
| T+6h no response | Tier 2: App nudge _(already in `escalations.ts`)_ | Engagement |
| T+12h no response | Tier 3: Voice bot _(already in `escalations.ts`)_ | Engagement |
| T+24h clinical miss | SFDC Task _(already in `escalations.ts`)_ | Escalation |
| T+48h no response | Additional SFDC follow-up | Escalation |
| T+96h no response | SFDC follow-up | Escalation |
| T+168h no response | Final SFDC follow-up | Escalation |
| Every 7 days | Psychology Profiler → update engagement_schedule | Engagement |
| Every 30 days | Progress Reporter → adherence score | Both |
| Device slots < 30% | Rewards Agent → FOMO nudge to eligible users | Engagement |
| Benefit cap reached | Flag to SFDC Agent | Escalation |
| 3+ consecutive missed appointments | Flag to SFDC Agent (stop automated comms) | Escalation |

#### System Prompt (injected at runtime)

```
You are the Care Coordinator Orchestrator for BFL VYTAL Managed Care programme.

Inputs: patient's current care plan state, last interaction outcome,
pending_actions list, clinical_schedule, engagement_schedule, programme_context.

Your ONLY job: decide which agent to invoke, on which channel, with what delay.

Rules:
1. Clinical triggers (lab results, prescriptions) → Care Planner (clinical lane)
2. Engagement triggers (no-response, weekly review) → Psychology Profiler + Comm Crafter
3. NEVER route a psychology signal to the clinical lane
4. Benefit cap reached → {action: "flag_sfdc", reason: "benefit_cap_reached"}
5. 3+ consecutive missed appts → {action: "flag_sfdc", reason: "repeated_miss"}
6. Priority: VERY_HIGH > HIGH > MODERATE for device/lifestyle slot actions

Output: JSON { agent, channel, delay_hours, context_payload, priority }
```

---

### Agent 2 — Health Profiler

**Status:** PARTIAL — `labRanges.ts` and `domainScoring.ts` exist. Need wrapper agent that parses HRA + produces structured `health_profile` JSON.

**File:** `packages/backend/src/agents/healthProfiler.ts`

**Runs on:** Enrolment + every new `LabReport` record.

#### System Prompt

```
You are a clinical data analyst for chronic disease management.
Programme context injected: {programme_name}, {biomarker_thresholds}, {escalation_thresholds}.

Inputs: biomarker values (JSON), HRA answers, previous health_profile (if exists).

Tasks:
1. Map each biomarker to its threshold band (Normal/Moderate/High/Very High)
   using ONLY the thresholds in the injected programme context
2. Compute biomarker delta vs last test (if previous profile exists)
3. If delta crosses escalation_threshold → clinical_review_needed = true
4. Parse HRA lifestyle flags: smoking, alcohol_risk, sleep_hours, stress_level, BMI
5. Determine device eligibility per programme device rules
6. Determine lifestyle assessment eligibility (Metabolic/Alcohol/Stress)
7. Write 2-sentence plain-language health summary (internal use only)

GUARDRAIL: No treatment suggestions. No medication recommendations.
Only interpret against programme thresholds.

Output: health_profile JSON + clinical_review_needed boolean
```

---

### Agent 3 — Psychology Profiler

**Status:** PARTIAL — `persona.ts` (detectPersona) + `FrustrationStage` enum exist. Need weekly re-evaluation agent that reads `NudgeEvent` outcomes.

**File:** `packages/backend/src/agents/psychologyProfiler.ts`

**Runs:** Every 7 days per patient.

#### Weekly Input Signals (read from existing DB tables)

```typescript
interface WeeklySignals {
  whatsapp_opens_last_7d:       number;   // NudgeEvent WHATSAPP SENT count
  whatsapp_replies_last_7d:     number;   // NudgeEvent RESPONDED count
  voice_bot_completed_last_7d:  boolean;  // NudgeEvent VOICE_BOT RESPONDED
  appointments_attended_last_30d: number; // ClinicalAppointment COMPLETED
  appointments_missed_last_30d:   number; // ClinicalAppointment MISSED
  diet_logs_last_7d:            number;   // MealLog count
  weight_logs_last_7d:          number;   // StepLog / activity WEIGHT COMPLETED
  vitals_logs_last_7d:          number;   // HRA domain activities COMPLETED
  last_interaction_outcome:     string;   // latest NudgeEvent.status
  consecutive_missed_appts:     number;   // computed from ClinicalAppointment
  hra_completed:                boolean;  // HraResponse exists
  device_response:              boolean;  // responded to FOMO nudge
}
```

#### Stage → Action Mapping

| Signal Pattern | Stage | Communication Action |
|---|---|---|
| Never opens, never responds | Pre-contemplation | Short, high-FOMO, ultra-low-effort ask |
| Opens but no action | Contemplation | Empathetic, address fear/barrier, voice bot |
| Asks questions, objects | Preparation | Informative, answer objection, book while warm |
| Books, attends, logs | Action | Achievement framing, next milestone |
| Logs consistently, improving | Maintenance | Monthly only, celebrate + next goal |
| High stress HRA + no engagement | Distress flag | 2-week pause, one empathetic check-in |

#### System Prompt

```
You are a behavioural psychologist specialising in chronic disease adherence.
Inputs: weekly behavioural signals, previous psychology profile.

Tasks:
1. Assign Transtheoretical Stage of Change
2. Identify primary motivation: Extrinsic (rewards/FOMO) or Intrinsic (health/family)
3. Identify primary barrier: Time / Anxiety / Skepticism / Disengagement / None
4. Assign communication style: Empathetic / Direct / Achievement / FOMO
   → maps to existing personaStyle field on Patient
5. Rate FOMO sensitivity: Low / Medium / High
6. Identify best contact window (morning/evening/weekday)
   → updates smartSendTime field on Patient
7. Set distress_flag if: stress=High/ExtHigh AND opens=0 AND missed_appts >= 2

CONSTRAINTS:
- Output affects ONLY engagement_schedule
- Never recommend clinical frequency changes
- consecutive_missed_appts >= 3 → escalate_to_sfdc = true
- distress_flag = true → FrustrationStage = SOFT_REST (existing enum)

Output: psychology_profile JSON (maps to Patient.psych_profile JSON field)
```

---

### Agent 4 — Care Planner

**Status:** PARTIAL — `planBuilder.ts` schedules engagement activities. Need clinical scheduling layer on top.

**File:** `packages/backend/src/agents/carePlanner.ts`

#### Clinical Lane System Prompt

```
You manage the CLINICAL SCHEDULING LANE for a VYTAL programme patient.
Programme context injected: {programme_name}, {specialist_type}, {benefit_caps}.

Inputs: health_profile, clinical_review_needed, consultations_used,
        consultations_max (from BENEFIT_CAPS), current clinical_schedule.

Rules:
1. Initial schedule:
   - Doctor:   Day 30 (HIGH/VERY_HIGH), Day 45 (MODERATE)
   - Dietician: Day 1 (HIGH/VERY_HIGH), post-doctor (MODERATE)
   - Lab:      Day 90 (HIGH/VERY_HIGH), Day 180 (MODERATE)
2. Shorten interval ONLY when: clinical_review_needed = true OR prescription says so
3. Lengthen interval ONLY when: 2 consecutive labs show improvement
4. Always check: consultations_used < consultations_max before scheduling
5. If cap reached → {action: "flag_sfdc", reason: "benefit_cap_reached"}
6. Log every change with reason: lab_result_trigger / prescription_trigger / improvement_trigger

HARD GUARDRAILS:
- Never exceed benefit cap
- Never change clinical schedule based on engagement/psychology signals
- Never add appointment types not in the programme benefits grid

Output: clinical_schedule JSON + change_log entry → stored in ClinicalAppointment table
```

#### Engagement Lane System Prompt

```
You manage the ENGAGEMENT SCHEDULING LANE.
Inputs: psychology_profile (weekly), last 7d interaction outcomes,
        next_clinical_date (read-only), diet_log_compliance.

Rules:
1. Set send time = smartSendTime from Patient (updated by Psychology Profiler)
2. Select script_variant based on personaStyle
3. Nudge frequency:
   - Diet check-in: 7 days (Action stage) / 14 days (others)
   - HRA reminder: every 7 days until hra_completed = true
   - Weight/vitals: every 3 days (Action/Maintenance) / every 7 days (others)
4. FrustrationStage = SOFT_REST → 1 WhatsApp only for next 14 days
5. escalate_to_sfdc = true → stop all automated comms, create SfdcTask

READ-ONLY: next_clinical_date, benefit_remaining

Output: engagement_schedule JSON → drives NudgeEvent creation
```

---

### Agent 5 — Communication Crafter

**Status:** NOT YET BUILT — need new file `packages/backend/src/agents/communicationCrafter.ts`

**Role:** Writes all WhatsApp messages and voice bot scripts. All 10 message types. Personalised per psychology profile + programme context.

#### Script Library — All 10 Message Types

**1. Welcome (Day 1)**
> "Hi [Name]! Welcome to your [Programme Name] through VYTAL by Bajaj Finserv Health.
> Your profile shows [cohort] risk — we'll work closely with you over 12 months
> to help you [programme-specific outcome goal]. First step: [first_action].
> Reply YES and we'll take care of the rest."

**2. Consultation Booking Reminder**
> "Hi [Name], your [specialist_type] consultation is scheduled for [Date] at [Time].
> This is one of your [benefit_remaining] consultations this year — video/phone call,
> no travel needed. Reply CONFIRM to lock it in | RESCHEDULE if needed."

**3. Lab Result Share (direction only — no raw values)**
> _Improving:_ "Great news [Name]! Your [userLanguage] results are heading in the right
> direction. Your [specialist_type] will review details on [Date]. Keep it up!"
>
> _Needs attention:_ "Hi [Name], your recent [userLanguage] check shows something
> your doctor will want to discuss. Next consultation moved to [new_date]. This is
> exactly what the programme is here for."

**4. Diet Check-in**
> "Hi [Name], quick check-in! How's [dietary_focus_summary] going this week?
> Reply: A) Going well  B) Mostly following  C) Struggling a bit
> Dietician session in [X] days — we'll note your reply."

**5. FOMO — Device Nudge (uses actual `DEVICE_CAPS` inventory count)**
> _High FOMO:_ "[Name], your VYTAL programme includes a FREE [device_type]!
> [actual_slots_remaining] units left this month — first-come, first-served.
> Complete [prerequisite_action] first. Reply CLAIM to reserve yours today."
>
> _Low FOMO:_ "Hi [Name], your programme includes a [device_type] to track your
> [userLanguage] at home. Complete [prerequisite_action] to secure yours."

**6. Adherence Praise (streak-based)**
> "[Name], you've logged [streak_days] days in a row! Small consistent actions
> drive real health improvement. Your adherence score this month: [score]/100.
> Next milestone: [next_milestone]. You're [X]% there."

**7. Missed Appointment Recovery**
> _Anxiety barrier (Empathetic):_ "Hi [Name], we noticed you missed [appointment_type]
> on [Date] — no worries at all. Your slot is still available.
> Would [option_1] or [option_2] work? Reply 1 or 2."
>
> _Disengaged barrier (Direct):_ "[Name], your [appointment_type] slot wasn't used.
> You have [benefit_remaining] consultations remaining this year.
> Reply REBOOK and we'll set a new time in 2 days."

**8. HRA Push**
> "[Name], your Health Risk Assessment takes just 8 minutes and unlocks
> [what_it_unlocks]. Complete it here: [link]. Best done in the morning."

**9. User Log Prompt**
> "Good morning [Name]! Time for your daily health log.
> Reply: Weight [Xkg] | BP [X/X] | Steps [X] | Mood [1-5]
> Example: Weight 78kg | BP 130/85 | Steps 6200 | Mood 4. Takes 30 seconds."

**10. Monthly Progress Report**
> "[Name], your VYTAL Health Summary — [Month]:
> [userLanguage] outcome: [Improved/Stable/Needs Attention]
> Consultations this month: [X] | This year: [X] of [max]
> Adherence score: [score]/100 ([+/- delta] from last month)
> Next focus: [next_milestone]
> Full report in your VYTAL app."

#### System Prompt

```
You are a patient engagement specialist for BFL VYTAL Managed Care.
Programme context: {programme_name}, {specialist_type}, {userLanguage}, {device_type}.
Psychology profile: {personaStyle}, {barrier}, {fomo_sensitivity}, {smartSendTime}.

Rules:
1. WhatsApp: max 3 short paragraphs, 1 CTA only, no jargon
2. Voice: natural spoken language, 60–90 seconds, handle 2 objections
3. NEVER mention specific biomarker values — direction only (improving/worsening/stable)
4. NEVER recommend medications or clinical activities not in the plan
5. ONE ask per message. No stacked CTAs
6. Anxiety barrier: open with emotional acknowledgment first
7. FOMO high: lead with scarcity. FOMO low: lead with personal benefit
8. Programme language: use userLanguage field from PROGRAMME_CONTEXT
9. Device FOMO: always use actual slot count from DB — never fabricated

Output: { channel, script, fallback_script, cta, personalization_vars_used }
→ stored in NudgeEvent.messageContent (JSON field)
```

---

### Agent 6 — Diet Adherence Agent

**Status:** NOT YET BUILT — `packages/backend/src/agents/dietAdherence.ts`

**Runs:** After each diet check-in response (weekly cadence via engagement lane).

#### High-Risk Deviations by Programme

| Programme | High-Risk Foods |
|---|---|
| DIABETES | Refined sugar, white rice, fruit juices, sweets |
| DYSLIPIDEMIA | Fried foods, red meat, full-fat dairy, trans fats |
| LIVER | Alcohol (any amount), processed meats, high-fat foods |
| KIDNEY | High-potassium (banana, potato), high-sodium (pickles, papad), high-protein if eGFR < 30 |
| THYROID | Excess raw cruciferous veg (goitrogens), inconsistent meal timing |

#### System Prompt

```
You are a clinical dietitian's assistant for VYTAL chronic disease management.
Programme context: {dietary_focus}, {high_risk_foods}.

Per check-in:
1. Validate: does reported eating align with prescribed plan?
2. If deviation: is it a high-risk deviation for this programme?
3. Provide 1 positive reinforcement + 1 gentle correction (never both)
4. Suggest 1 easy substitute (never a new diet plan)
5. 3+ consecutive deviations → dietician_followup_needed = true

GUARDRAIL: Never prescribe a new diet plan. Reference only what the dietician
already recommended. Compliance tracking and motivation only.

Output: { compliance_flag, deviation_detected, high_risk_flag,
          response_message, dietician_followup_needed }
→ updates MealLog and triggers ClinicalAppointment if flag set
```

---

### Agent 7 — Appointment Coordinator

**Status:** PARTIAL — `packages/backend/src/routes/appointments.ts` exists. Need agent wrapper with benefit cap enforcement and escalation logic.

**File:** `packages/backend/src/agents/appointmentCoordinator.ts`

#### System Prompt

```
You are a healthcare appointment coordinator for VYTAL programme.

Inputs: clinical_schedule, consultations_used, consultations_max,
        ClinicalAppointment history, programme_context.

Tasks:
1. Determine next required consultation from clinical_schedule
2. Hard check: consultations_used < consultations_max
3. Generate booking confirmation via Communication Crafter
4. Surface doctor notes from completed appointments to next diet/HRA prompt
5. Pre-appointment reminders: T-24h WhatsApp + T-1h voice bot
6. Missed appointment: rechurn sequence (T+12 WA → T+24 voice)
   [Note: Tier 1→2→3 escalation already built in escalations.ts]
7. After 3 consecutive misses: escalate_to_sfdc = true, stop automated rescheduling

Benefit tracking:
- doctor consultations_used: X of Y
- dietician consultations_used: X of Y
- Alert when remaining <= 2 (nudge to use before expiry)

GUARDRAIL: Only schedule within approved provider network.
Never add appointment types not in programme benefits grid.
```

---

### Agent 8 — Progress Reporter

**Status:** NOT YET BUILT — `packages/backend/src/agents/progressReporter.ts`

**Runs:** Monthly per patient. Reads `OutcomePrediction` + `Activity180Day` + `ClinicalAppointment`.

#### Adherence Score Formula

```
Total (0–100) =
  Clinical Risk Score    × 0.30   ← biomarker band from Health Profiler
+ Engagement Score       × 0.25   ← app opens + consultations attended
+ Adherence Intent Score × 0.25   ← diet/activity/sleep logs
+ Lifestyle Risk Score   × 0.20   ← smoking, alcohol, sleep, stress from HRA
```

**Bands:** > 75 = High · 50–75 = Moderate · 30–50 = Low · < 30 = Very Low

```typescript
const ENGAGEMENT_SCORE = {    // max 25
  app_opens_4_5_per_week:        10,
  app_opens_2_3_per_week:         5,
  app_opens_0_1_per_week:         0,
  consultations_as_recommended:  15,
  consultations_not_adhered:      0,
};

const INTENT_SCORE = {        // max 25
  diet_log:      9,
  activity_log:  8,
  sleep_log:     4,
  stress_log:    4,
};

const LIFESTYLE_PENALTY = {   // max 20, deducted
  smoking:          10,
  alcohol_high_risk: 5,
  high_stress:       3,
  poor_sleep:        2,
};
```

#### System Prompt

```
You are a health outcomes analyst generating monthly summaries for VYTAL patients.
Programme context: {programme_name}, {userLanguage}.
Psychology profile: {personaStyle}, {motivation_type}.

Monthly report structure:
1. Opening: 1 sentence specific to this patient's effort (not generic)
2. Clinical direction: [userLanguage] — Improving / Stable / Needs Attention
   (NEVER raw biomarker values)
3. Engagement: consultations X/Y, logs X days, HRA: done/pending
4. Adherence score: [score]/100, delta [+/- X], driving factor
5. Next focus: 1 specific action for next 30 days + why it matters
6. Close — tied to motivation:
   Intrinsic: "You're building a healthier future for yourself and your family"
   Extrinsic:  "You're [X] points away from unlocking [next_reward]"

WhatsApp version: <= 150 words → stored in NudgeEvent.messageContent
Dashboard version: full detail → stored as OutcomePrediction.lineType = "MONTHLY_REPORT"

GUARDRAIL: Direction only in user-facing messages. No raw values.
```

---

### Agent 9 — Rewards Agent

**Status:** PARTIAL — `Patient.points`, `Patient.level`, `Patient.streaks` exist. Need device allocation logic and FOMO mechanic.

**File:** `packages/backend/src/agents/rewardsAgent.ts`

#### Allocation Priority Logic

```typescript
function getAllocationPriority(patient: Patient) {
  const cohortRank = { VERY_HIGH: 1, HIGH: 2, MODERATE: 3 };
  // Within same cohort: adherence score DESC, then enrollmentDate ASC
  return [cohortRank[patient.cohort], -patient.engagementScore, patient.enrollmentDate];
}
```

#### Lifestyle Assessment Eligibility

| Assessment | Eligibility Criteria |
|---|---|
| Metabolic | HRA obese/overweight + abnormal HbA1c + abnormal Lipid + High BP (any 3) |
| Alcohol | HRA alcohol >= 5 drinks/month + abnormal LFT (SGPT/SGOT elevated) |
| Stress | HRA stress = High/ExtHigh + High BP |

#### System Prompt

```
You manage reward allocation for VYTAL programme.

Inputs: device_inventory (actual counts from DB), patient eligibility,
        engagementScores, psychology profiles, allocation history.

Tasks:
1. Check eligibility: patient's programme + cohort matches device rules
2. Check inventory: slots_remaining > 0
3. Rank eligible unallocated patients by (cohort_priority, engagementScore DESC, enrollmentDate ASC)
4. Allocate next patient in queue when slot opens
5. FOMO nudge: when slots_remaining < 30% of DEVICE_CAPS
   → trigger Communication Crafter for all eligible-but-unallocated patients
   → calibrate intensity using fomo_sensitivity from psychology profile
6. "Unlocked" message: fire immediately when patient completes prerequisite milestone
7. Lifestyle assessment: check eligibility from HRA + latest LabReport values

GUARDRAIL: Never fabricate slot counts. Always use actual DB inventory.
"X slots left" = real number. Never promise a device the patient's cohort
doesn't qualify for.
```

---

## 5. Database Schema — Additions to Existing Prisma Schema

The existing `schema.prisma` covers most needs. Add these to `packages/backend/prisma/schema.prisma`:

```prisma
// Programme config snapshot stored per patient (from PROGRAMME_CONTEXT)
model ProgrammeConfig {
  id                String   @id @default(cuid())
  patientId         String   @unique
  programmeKey      String   // "DIABETES" | "DYSLIPIDEMIA" | etc.
  cohort            Cohort
  specialistType    String
  primaryBiomarker  String
  deviceEligible    String   // device name from PROGRAMME_CONTEXT.devices
  benefitCaps       Json     // snapshot of BENEFIT_CAPS at enrolment
  userLanguage      String   // e.g., "sugar levels"
  createdAt         DateTime @default(now())

  patient Patient @relation(fields: [patientId], references: [id], onDelete: Cascade)
}

// Monthly adherence scores
model AdherenceScore {
  id               String   @id @default(cuid())
  patientId        String
  scoreMonth       String   // "YYYY-MM"
  clinicalScore    Float    // 0–30
  engagementScore  Float    // 0–25
  intentScore      Float    // 0–25
  lifestyleScore   Float    // 0–20
  totalScore       Float    // 0–100
  scoreBand        String   // "Very Low" | "Low" | "Moderate" | "High"
  deltaFromLast    Float?
  createdAt        DateTime @default(now())

  patient Patient @relation(fields: [patientId], references: [id], onDelete: Cascade)
}

// Device and lifestyle reward inventory + allocation
model RewardAllocation {
  id              String   @id @default(cuid())
  patientId       String
  rewardType      String   // "CGM" | "Glucometer" | "BP_Monitor" | "Weighing_Scale" | "Metabolic" | "Stress" | "Alcohol"
  eligibilityDate DateTime
  fomoNudgeSent   Boolean  @default(false)
  allocated       Boolean  @default(false)
  allocationDate  DateTime?
  dispatchDate    DateTime?
  deliveryDate    DateTime?
  status          String   @default("eligible") // eligible/allocated/dispatched/delivered

  patient Patient @relation(fields: [patientId], references: [id], onDelete: Cascade)
}

// Care plan versions (both lanes, with audit trail)
model CarePlanVersion {
  id                  String   @id @default(cuid())
  patientId           String
  planVersion         Int
  revisionReason      String?
  revisionTrigger     String?  // lab_result_trigger | prescription_trigger | improvement_trigger | weekly_psych | enrollment
  revisionLane        String?  // clinical | engagement
  status              String   @default("active") // active | completed | paused
  clinicalSchedule    Json     // { doctor: Date[], dietician: Date[], lab: Date[] }
  engagementSchedule  Json     // { channel, script_variant, cadence, send_time }
  dietaryGuidelines   String?
  lifestyleGoals      Json?
  createdAt           DateTime @default(now())
  revisedAt           DateTime @updatedAt

  patient Patient @relation(fields: [patientId], references: [id], onDelete: Cascade)
}

// All orchestrator decisions for audit + replay
model OrchestratorLog {
  id              String   @id @default(cuid())
  patientId       String
  runDate         DateTime @default(now())
  triggerEvent    String   // enrolled | lab_received | weekly_review | no_response_12h | etc.
  agentInvoked    String
  channel         String?
  delayHours      Float?
  contextSnapshot Json
  decisionOutput  Json     // raw orchestrator JSON output
  createdAt       DateTime @default(now())

  patient Patient @relation(fields: [patientId], references: [id], onDelete: Cascade)
}
```

**Also add to `Patient` model** (extend existing):
```prisma
// Add these fields to the existing Patient model:
healthProfile    Json?    // output from Health Profiler agent
psychProfile     Json?    // output from Psychology Profiler (weekly)
mobileHash       String?  @unique  // PHI protection — use this in comms, not name+phone
```

---

## 6. Dashboard — Care Coordinator Tab

Add a new tab to the existing `packages/frontend/src/pages/AgentView/index.tsx`.

**Backend data endpoint:** `GET /api/coordinator/stats` powered by a new summary job.

| Section | Metrics | Filter |
|---|---|---|
| Engagement Funnel | % patients by stage: Pre-contemplation → Maintenance | Programme, cohort |
| Adherence Score Distribution | Histogram 0–100 + monthly trend | Programme, cohort |
| Communication Effectiveness | WA open rate, reply rate, voice completion %, avg response time | By script_variant |
| Milestone Tracker | % patients: welcome done / first consult / first lab / HRA done / device allocated | Programme |
| Clinical Activity | Consultations used vs cap (doctor + dietician) | Programme, month |
| Benefit Utilisation Alerts | Patients at ≥80% cap (at risk of wasting benefits) | Live list |
| Device & Lifestyle Allocation | Slots used/remaining per device, allocation pace, FOMO nudge count | Live inventory |
| Escalation Queue | Open SfdcTask records: reason, days open, assignee | Live list |
| Patient Timeline Drill-down | Select patient → full CarePlanVersion history, OrchestratorLog, AdherenceScore trend | Per-patient |
| Plan Revision Log | When/why plans changed, lane, outcome | Audit trail |

---

## 7. File Structure

```
packages/
├── shared/
│   └── src/
│       ├── types/index.ts                ✅ exists
│       ├── scoring/
│       │   ├── engagementScore.ts        ✅ exists
│       │   ├── persona.ts                ✅ exists
│       │   ├── domainScoring.ts          ✅ exists
│       │   ├── labRanges.ts              ✅ exists
│       │   └── planBuilder.ts            ✅ exists
│       └── constants/
│           ├── activities.ts             ✅ exists
│           └── programmeContext.ts       🔲 NEW — PROGRAMME_CONTEXT + BENEFIT_CAPS + DEVICE_CAPS
│
├── backend/
│   ├── prisma/
│   │   ├── schema.prisma                 ✅ exists (extend with 5 new models above)
│   │   └── seed.ts                       ✅ exists
│   └── src/
│       ├── agents/                       🔲 NEW DIRECTORY
│       │   ├── llmClient.ts              🔲 NEW — Claude API wrapper (claude-sonnet-4-6)
│       │   ├── orchestrator.ts           🔲 NEW — Agent 1
│       │   ├── healthProfiler.ts         🔲 NEW — Agent 2
│       │   ├── psychologyProfiler.ts     🔲 NEW — Agent 3
│       │   ├── carePlanner.ts            🔲 NEW — Agent 4 (two lanes)
│       │   ├── communicationCrafter.ts   🔲 NEW — Agent 5 (all 10 scripts)
│       │   ├── dietAdherence.ts          🔲 NEW — Agent 6
│       │   ├── appointmentCoordinator.ts 🔲 NEW — Agent 7
│       │   ├── progressReporter.ts       🔲 NEW — Agent 8
│       │   └── rewardsAgent.ts           🔲 NEW — Agent 9
│       ├── jobs/
│       │   ├── dailyOutcomes.ts          ✅ exists
│       │   ├── escalations.ts            ✅ exists
│       │   ├── index.ts                  ✅ exists (add orchestrator cron here)
│       │   ├── weeklyPsychology.ts       🔲 NEW — fires Psychology Profiler every 7 days
│       │   ├── monthlyProgress.ts        🔲 NEW — fires Progress Reporter every 30 days
│       │   └── rewardsAllocation.ts      🔲 NEW — checks FOMO threshold daily
│       ├── routes/
│       │   ├── patients.ts               ✅ exists
│       │   ├── activities.ts             ✅ exists
│       │   ├── appointments.ts           ✅ exists
│       │   ├── nudges.ts                 ✅ exists
│       │   ├── outcomes.ts               ✅ exists
│       │   ├── sfdc.ts                   ✅ exists
│       │   ├── wellness.ts               ✅ exists
│       │   ├── stepLogs.ts               ✅ exists
│       │   ├── mealLogs.ts               ✅ exists
│       │   ├── moodLogs.ts               ✅ exists
│       │   └── coordinator.ts            🔲 NEW — dashboard stats endpoint
│       ├── sockets/index.ts              ✅ exists
│       ├── db.ts                         ✅ exists
│       ├── app.ts                        ✅ exists
│       └── index.ts                      ✅ exists
│
└── frontend/
    └── src/
        └── pages/
            ├── PMSimulator/              ✅ exists (5 steps)
            ├── PatientApp/               ✅ exists
            └── AgentView/
                ├── index.tsx             ✅ exists (add new tab here)
                └── CareCoordinatorTab.tsx 🔲 NEW — all 10 dashboard sections
```

---

## 8. Build Phases

| Phase | What to Build | Key Files | Depends On |
|---|---|---|---|
| **1 — Config Layer** | `programmeContext.ts`, Prisma schema extensions, `llmClient.ts` | `shared/constants/programmeContext.ts`, 5 new Prisma models, `agents/llmClient.ts` | Existing schema |
| **2 — Health Profiler** | Agent 2 wrapper around existing `labRanges.ts` + `domainScoring.ts`. Populates `Patient.healthProfile` | `agents/healthProfiler.ts` | Phase 1 + existing lab scoring |
| **3 — Psychology Profiler** | Agent 3 weekly job. Reads `NudgeEvent` outcomes. Updates `Patient.psychProfile`, `Patient.smartSendTime`, `Patient.frustrationStage` | `agents/psychologyProfiler.ts`, `jobs/weeklyPsychology.ts` | Phase 2 |
| **4 — Care Planner** | Agent 4 — clinical lane on top of existing `planBuilder.ts`. Generates `CarePlanVersion` records | `agents/carePlanner.ts` | Phase 3 |
| **5 — Communication Crafter + Appointment Coordinator** | Agents 5 + 7. All 10 script types. Booking with benefit cap enforcement | `agents/communicationCrafter.ts`, `agents/appointmentCoordinator.ts` | Phase 4 |
| **6 — Orchestrator** | Agent 1 — master cron job. Reads plan state → dispatches to agents | `agents/orchestrator.ts`, extend `jobs/index.ts` | Phase 5 |
| **7 — Diet Adherence + Rewards** | Agents 6 + 9. Diet compliance tracking + device allocation with FOMO | `agents/dietAdherence.ts`, `agents/rewardsAgent.ts`, `jobs/rewardsAllocation.ts` | Phase 6 |
| **8 — Progress Reporter** | Agent 8. Monthly score calculation + WhatsApp + dashboard version | `agents/progressReporter.ts`, `jobs/monthlyProgress.ts` | Phase 7 |
| **9 — Dashboard Tab** | New Care Coordinator tab in `AgentView`. Stats endpoint + frontend component | `routes/coordinator.ts`, `pages/AgentView/CareCoordinatorTab.tsx` | Phase 8 |

---

## 9. Guardrails Summary

| Guardrail | Enforcement |
|---|---|
| No medical advice | All 9 agent system prompts explicitly prohibit it |
| Clinical frequency only from clinical outputs | Care Planner enforces lane separation — engagement signals cannot change `clinicalSchedule` |
| Benefit cap never exceeded | Agent 7 checks `consultations_used < consultations_max` before every `ClinicalAppointment` creation |
| No raw biomarker values in user comms | Communication Crafter system prompt rule + Progress Reporter maps to direction-only language |
| FOMO must be factual | Rewards Agent reads actual `RewardAllocation` inventory count — never a hardcoded number |
| 3+ consecutive misses → human only | Orchestrator creates `SfdcTask`, stops all automated `NudgeEvent` creation for that patient |
| Distress flag → communication pause | Psychology Profiler sets `FrustrationStage = SOFT_REST`; Engagement Lane reads this before every nudge |
| PHI protection | `Patient.mobileHash` used in all external comms; `Patient.id` (cuid) only in DB |
| Escalation audit trail | Every `OrchestratorLog` record captures trigger, decision, and context snapshot for replay |

---

_Last updated: 2026-06-06 · Stack: TypeScript + PostgreSQL (Prisma) + React + claude-sonnet-4-6_
_Codebase: `C:\Users\muskan.rao\Documents\managed-care-platform`_
