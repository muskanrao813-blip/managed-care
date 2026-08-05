"""
PatientState — the single source of truth for the LangGraph graph.
Every node reads from and writes to this object.
Persisted in Supabase Postgres between daily runs via LangGraph checkpointing.
"""

from typing import TypedDict, Optional, Literal


class PatientState(TypedDict):

    # ── Identity ───────────────────────────────────────────────────────────────
    phr_id:             str
    mobile_hash:        str
    programme:          Literal["DIABETES"]          # extend when other programmes go live
    product_code:       str                          # VYTAL0126 or VYTAL0626
    cohort:             Literal["MODERATE", "HIGH", "VERY_HIGH"]
    gender:             str
    policy_start_date:  str                          # YYYY-MM-DD
    day_number:         int                          # days since enrolment

    # ── Clinical profile (set by Health Profiler on enrolment + each lab) ──────
    latest_hba1c:       Optional[float]              # e.g. 7.5
    hba1c_target:       float                        # derived from cohort
    hba1c_trend:        list                         # [{date, value, unit}, ...]
    hba1c_band:         Optional[str]                # Normal | Moderate | High | Very High
    hba1c_delta:        Optional[float]              # change vs previous test
    clinical_review_needed: bool                     # True if delta >= 1.0
    all_lab_results:    list                         # full lab history from Trino
    health_profile:     dict                         # full output from Health Profiler agent

    # ── Clinical schedule (set by Care Planner, updated on clinical triggers) ──
    clinical_schedule:  dict                         # {doctor:[dates], diet:[dates], lab:[dates]}
    next_doctor_date:   Optional[str]
    next_diet_date:     Optional[str]
    next_lab_date:      Optional[str]

    # ── Benefit utilisation (from Trino f_claim + Supabase) ───────────────────
    doctor_used:        int
    doctor_max:         int                          # from BENEFIT_CAPS[cohort]
    dietician_used:     int
    dietician_max:      int
    lab_used:           int
    lab_max:            int
    benefit_cap_reached: bool

    # ── Psychology profile (updated weekly by Psychology Profiler) ─────────────
    psych_stage:        str    # Pre-contemplation|Contemplation|Preparation|Action|Maintenance
    motivation_type:    str    # Intrinsic | Extrinsic
    comm_style:         str    # Empathetic | Direct | Achievement | FOMO
    barrier:            str    # Time | Anxiety | Skepticism | Disengagement | None
    fomo_sensitivity:   str    # Low | Medium | High
    smart_send_time:    str    # "18:30" — best contact window from past response data
    distress_flag:      bool
    frustration_stage:  str    # NORMAL | CAUTION | BACKOFF | SOFT_REST
    psych_profile:      dict   # full output from Psychology Profiler agent

    # ── Engagement signals (updated after every interaction) ───────────────────
    meal_logs_last_7d:          int
    step_logs_last_7d:          int
    mood_logs_last_7d:          int
    weight_logs_last_7d:        int
    last_nudge_sent_at:         Optional[str]
    last_nudge_channel:         Optional[str]   # WHATSAPP | VOICE_BOT | APP_NUDGE
    last_nudge_responded:       bool
    consecutive_no_response:    int
    consecutive_missed_appts:   int
    diet_checkin_responses:     list            # last 3 weekly responses ["A","C","B"]

    # ── Rewards & devices (updated by Rewards Agent) ───────────────────────────
    points:                     int
    level:                      str             # BRONZE | SILVER | GOLD | PLATINUM
    device_eligible:            bool
    device_allocated:           bool
    device_type:                str             # CGM | Glucometer (from PROGRAMME_CONTEXT)
    binah_eligible:             bool

    # ── Orchestrator decision (set each run, consumed by tools) ───────────────
    trigger_event:      str     # daily_schedule|lab_received|wa_reply|voice_outcome|enrollment
    trigger_data:       dict    # e.g. {"hba1c": 7.2} for lab_received
    current_action:     Optional[str]   # send_whatsapp|trigger_voice|book_appointment
    current_message:    Optional[dict]  # full message payload from Comm Crafter
    next_agent:         Optional[str]   # routing hint set by orchestrator
    escalate_to_human:  bool
    escalation_reason:  Optional[str]
    run_timestamp:      str


# ── Default state for a newly enrolled patient ─────────────────────────────────
def default_state(phr_id: str, cohort: str, product_code: str) -> PatientState:
    from constants.programme_context import BENEFIT_CAPS, PROGRAMME_CONTEXT

    caps   = BENEFIT_CAPS[cohort]
    prog   = PROGRAMME_CONTEXT["DIABETES"]
    device = prog["devices"][cohort]

    return PatientState(
        phr_id=phr_id,
        mobile_hash="",
        programme="DIABETES",
        product_code=product_code,
        cohort=cohort,
        gender="",
        policy_start_date="",
        day_number=1,

        latest_hba1c=None,
        hba1c_target=7.0,
        hba1c_trend=[],
        hba1c_band=None,
        hba1c_delta=None,
        clinical_review_needed=False,
        all_lab_results=[],
        health_profile={},

        clinical_schedule={},
        next_doctor_date=None,
        next_diet_date=None,
        next_lab_date=None,

        doctor_used=0,
        doctor_max=caps["doctor"],
        dietician_used=0,
        dietician_max=caps["dietician"],
        lab_used=0,
        lab_max=4,
        benefit_cap_reached=False,

        psych_stage="Pre-contemplation",
        motivation_type="Extrinsic",
        comm_style="Empathetic",
        barrier="None",
        fomo_sensitivity="Medium",
        smart_send_time="18:30",
        distress_flag=False,
        frustration_stage="NORMAL",
        psych_profile={},

        meal_logs_last_7d=0,
        step_logs_last_7d=0,
        mood_logs_last_7d=0,
        weight_logs_last_7d=0,
        last_nudge_sent_at=None,
        last_nudge_channel=None,
        last_nudge_responded=False,
        consecutive_no_response=0,
        consecutive_missed_appts=0,
        diet_checkin_responses=[],

        points=0,
        level="BRONZE",
        device_eligible=False,
        device_allocated=False,
        device_type=device,
        binah_eligible=False,

        trigger_event="enrollment",
        trigger_data={},
        current_action=None,
        current_message=None,
        next_agent=None,
        escalate_to_human=False,
        escalation_reason=None,
        run_timestamp="",
    )
