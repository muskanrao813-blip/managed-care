# AI Care Coordinator — Agent Tool Architecture
**What to build, what tools to use, and why**

---

## The one-line answer

Build the care coordinator as a **LangGraph stateful agent graph**, with Trino as the read tool,
Supabase as the write store, WhatsApp/Exotel as output tools, and FastAPI webhooks as the
feedback channel. Every other tool choice flows from this.

---

## Why LangGraph and not something else

Your care coordinator is not a chatbot. It is a **long-running stateful workflow** that:
- Remembers what it decided yesterday
- Branches differently based on patient response
- Runs on a schedule AND on events (lab result in → replan immediately)
- Has human escalation built in
- Must never repeat a message it already sent

This rules out simple LLM chains (no state), AutoGen (too conversational),
and n8n/Zapier (no LLM reasoning in the flow). LangGraph was built exactly for this.

| Requirement | How LangGraph handles it |
|---|---|
| Patient state persists across daily runs | Built-in checkpointing (Postgres or Redis backend) |
| Conditional routing (clinical vs engagement lane) | Conditional edges in the graph |
| 9 specialized agents | Each agent = one node in the graph |
| Human escalation (SG Agent) | `interrupt_before` on escalation node — pauses for human |
| Triggered by schedule AND events | External triggers call `graph.invoke()` |
| Trino, WhatsApp, Voice Bot as actions | Each = a LangGraph Tool with `@tool` decorator |
| Streaming voice scripts | LangGraph supports streaming output per node |

---

## Full System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TRIGGER LAYER                                   │
│  APScheduler (daily 8 AM)  │  Webhook (lab result in)  │  Event bus    │
└────────────────┬────────────────────────┬───────────────────────────────┘
                 │                        │
                 ▼                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH ORCHESTRATOR GRAPH                         │
│                                                                         │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐            │
│   │   Health     │    │  Psychology  │    │    Care      │            │
│   │  Profiler    │───▶│  Profiler    │───▶│   Planner    │            │
│   │  (Node 2)    │    │  (Node 3)    │    │  (Node 4)    │            │
│   └──────┬───────┘    └──────────────┘    └──────┬───────┘            │
│          │                                        │                    │
│          ▼ (if clinical_review_needed)            ▼                    │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐            │
│   │    Care      │    │ Appointment  │    │ Comm Crafter │            │
│   │   Planner    │    │ Coordinator  │    │  (Node 5)    │            │
│   │ Clinical Lane│    │  (Node 7)    │    └──────┬───────┘            │
│   └──────────────┘    └──────────────┘           │                    │
│                                                   ▼                    │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐            │
│   │     Diet     │    │   Rewards    │    │  Progress    │            │
│   │  Adherence   │    │   Agent      │    │  Reporter    │            │
│   │  (Node 6)    │    │  (Node 9)    │    │  (Node 8)    │            │
│   └──────────────┘    └──────────────┘    └──────────────┘            │
│                                                                         │
│   ┌─────────────────────────────────────────────────────┐              │
│   │            ORCHESTRATOR (Node 1)                    │              │
│   │   Reads all node outputs → decides next action      │              │
│   └─────────────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         TOOL LAYER                                      │
│                                                                         │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────────┐   │
│  │  Trino    │  │ WhatsApp  │  │  Exotel   │  │  Supabase Write   │   │
│  │  Reader   │  │  Sender   │  │  Voice    │  │  (care plan, log) │   │
│  │  Tool     │  │  Tool     │  │  Trigger  │  │  Tool             │   │
│  └───────────┘  └───────────┘  └───────────┘  └───────────────────┘   │
│                                                                         │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────────┐   │
│  │  Binah AI │  │  Gym      │  │  Lab      │  │  Benefit Cap      │   │
│  │  Trigger  │  │  Booking  │  │  Booking  │  │  Checker          │   │
│  │  Tool     │  │  Tool     │  │  Tool     │  │  Tool             │   │
│  └───────────┘  └───────────┘  └───────────┘  └───────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      RESPONSE / FEEDBACK LAYER                          │
│                                                                         │
│   FastAPI Webhook Server                                                │
│   POST /webhook/whatsapp   ← incoming WA replies → re-invoke graph     │
│   POST /webhook/voice      ← call outcome → re-invoke graph            │
│   POST /webhook/lab-result ← new lab in system → re-invoke graph       │
│   POST /webhook/binah      ← face scan result → re-invoke graph        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## The LangGraph State Object

This is the most important design decision. Every node reads from and writes to this state.
It is persisted in Postgres (Supabase) between runs.

```python
from typing import TypedDict, Optional, Literal
from datetime import datetime

class PatientState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────────────
    patient_id:         str
    programme:          Literal["DIABETES", "DYSLIPIDEMIA", "LIVER", "KIDNEY", "THYROID"]
    cohort:             Literal["MODERATE", "HIGH", "VERY_HIGH"]
    day_number:         int
    enrolled_date:      str

    # ── Clinical profile (set by Health Profiler, updated on each lab) ────
    health_profile:     dict          # biomarker bands, delta, clinical_review_needed
    clinical_schedule:  dict          # {doctor: [dates], diet: [dates], lab: [dates]}
    clinical_review_needed: bool

    # ── Psychology profile (updated weekly by Psychology Profiler) ────────
    psych_profile:      dict          # stage, motivation, barrier, comm_style, fomo
    frustration_stage:  str           # NORMAL | CAUTION | BACKOFF | SOFT_REST
    smart_send_time:    str           # "18:30" — best contact window

    # ── Engagement signals (updated after every interaction) ─────────────
    last_nudge_sent_at:     Optional[str]
    last_nudge_channel:     Optional[str]
    last_nudge_responded:   bool
    consecutive_no_response: int
    consecutive_missed_appts: int

    # ── Activity tracking ─────────────────────────────────────────────────
    meal_logs_last_7d:      int
    step_logs_last_7d:      int
    mood_logs_last_7d:      int
    appointments_attended:  int
    appointments_missed:    int
    diet_checkin_responses: list[str]   # ["A", "C", "B"] last 3 weeks

    # ── Benefits ──────────────────────────────────────────────────────────
    doctor_used:        int
    doctor_max:         int
    diet_used:          int
    diet_max:           int
    lab_used:           int
    points:             int
    level:              str
    device_allocated:   bool

    # ── Orchestrator decision (set each run, consumed by tool layer) ──────
    current_action:     Optional[str]   # "send_whatsapp" | "trigger_voice" | "book_appointment"
    current_message:    Optional[dict]  # full message payload
    escalate_to_human:  bool
    escalation_reason:  Optional[str]

    # ── Run metadata ──────────────────────────────────────────────────────
    trigger_event:      str            # "daily_schedule" | "lab_received" | "wa_reply"
    trigger_data:       Optional[dict] # e.g., {"hba1c": 7.2} for lab_received
    run_timestamp:      str
```

---

## The Tools (each is a Python function decorated with @tool)

### Tool 1 — Trino Data Fetcher
```python
from langchain_core.tools import tool
from trino.dbapi import connect

@tool
def fetch_patient_data_from_trino(patient_id: str, query_type: str) -> dict:
    """
    Fetch patient data from Trino data warehouse.
    query_type: lab_results | appointment_history | engagement_logs | hra_answers
    Returns structured dict. Read-only — never writes to Trino.
    """
    conn = connect(
        host="your-trino-host",
        port=443,
        user="care_coordinator_svc",
        catalog="hive",
        schema="managed_care",
        http_scheme="https",
        auth=BasicAuthentication("user", "password"),
    )
    cursor = conn.cursor()

    queries = {
        "lab_results": f"""
            SELECT test_name, value, test_date
            FROM lab_results
            WHERE patient_id = '{patient_id}'
            ORDER BY test_date DESC
            LIMIT 20
        """,
        "appointment_history": f"""
            SELECT appointment_type, scheduled_date, status, notes
            FROM appointments
            WHERE patient_id = '{patient_id}'
            ORDER BY scheduled_date DESC
            LIMIT 10
        """,
        "engagement_logs": f"""
            SELECT event_type, event_date, event_data
            FROM engagement_events
            WHERE patient_id = '{patient_id}'
              AND event_date >= current_date - interval '14' day
        """,
        "hra_answers": f"""
            SELECT question_key, answer_value, response_date
            FROM hra_responses
            WHERE patient_id = '{patient_id}'
            ORDER BY response_date DESC
            LIMIT 50
        """,
    }

    cursor.execute(queries[query_type])
    rows = cursor.fetchall()
    columns = [d[0] for d in cursor.description]
    return {"data": [dict(zip(columns, row)) for row in rows]}
```

### Tool 2 — WhatsApp Sender
```python
@tool
def send_whatsapp_message(patient_id: str, message: str, quick_replies: list[str]) -> dict:
    """
    Send a WhatsApp message to the patient via WATI/Twilio/Gupshup.
    Returns: {sent: bool, message_id: str, sent_at: str}
    Logs the nudge to Supabase nudge_events table.
    """
    # Call WhatsApp Business API
    response = requests.post(
        f"{WATI_BASE_URL}/api/v1/sendSessionMessage/{patient_mobile}",
        headers={"Authorization": f"Bearer {WATI_TOKEN}"},
        json={"messageText": message}
    )
    # Log to Supabase
    supabase.table("nudge_events").insert({
        "patient_id": patient_id,
        "channel": "WHATSAPP",
        "message": message,
        "sent_at": datetime.now().isoformat(),
        "status": "SENT"
    }).execute()
    return {"sent": True, "message_id": response.json().get("id")}
```

### Tool 3 — Voice Bot Script Trigger
```python
@tool
def trigger_voice_call(patient_id: str, script: dict) -> dict:
    """
    Trigger an outbound IVR call via Exotel with a generated script.
    script: {opening, questions, action_ask, branches: {yes, no, escalation}}
    Returns: {call_initiated: bool, call_sid: str}
    """
    # Exotel outbound call API
    response = requests.post(
        f"https://api.exotel.com/v1/Accounts/{EXOTEL_SID}/Calls/connect",
        auth=(EXOTEL_KEY, EXOTEL_TOKEN),
        data={
            "From": patient_phone,
            "To": EXOTEL_AGENT_NUMBER,
            "CallerId": EXOTEL_CALLER_ID,
            "Url": f"{WEBHOOK_BASE}/voice-xml/{patient_id}",  # TwiML/Exotel XML
            "StatusCallback": f"{WEBHOOK_BASE}/webhook/voice",
        }
    )
    return {"call_initiated": True, "call_sid": response.json().get("Sid")}
```

### Tool 4 — Appointment Booker
```python
@tool
def book_appointment(patient_id: str, appointment_type: str, preferred_date: str) -> dict:
    """
    Book a doctor/dietician/lab appointment.
    Checks benefit cap before booking. Writes to Supabase.
    appointment_type: DOCTOR | DIETICIAN | LAB_TEST
    Returns: {booked: bool, appointment_id: str, date: str} or {blocked: true, reason: "cap_reached"}
    """
    # Check cap first
    cap_check = supabase.table("benefit_utilisation")\
        .select("*")\
        .eq("patient_id", patient_id)\
        .eq("benefit_type", appointment_type)\
        .single().execute()

    if cap_check.data["used_count"] >= cap_check.data["max_count"]:
        return {"booked": False, "blocked": True, "reason": "cap_reached"}

    # Create appointment
    appt = supabase.table("clinical_appointments").insert({
        "patient_id": patient_id,
        "type": appointment_type,
        "scheduled_date": preferred_date,
        "status": "SCHEDULED"
    }).execute()

    # Increment used count
    supabase.table("benefit_utilisation")\
        .update({"used_count": cap_check.data["used_count"] + 1})\
        .eq("id", cap_check.data["id"]).execute()

    return {"booked": True, "appointment_id": appt.data[0]["id"]}
```

### Tool 5 — Binah AI Trigger
```python
@tool
def trigger_binah_scan(patient_id: str) -> dict:
    """
    Send a deep link to the patient to open the Binah AI face scan in the app.
    Only fires if patient has binah benefit (benefitGatePoints threshold crossed).
    Returns: {triggered: bool, deep_link: str}
    """
    deep_link = f"vytal://binah-scan?patient={patient_id}&session={uuid.uuid4()}"
    send_whatsapp_message.invoke({
        "patient_id": patient_id,
        "message": f"Time for your Binah health scan! It takes 60 seconds and gives you your heart rate, SpO2, and stress levels. Tap here: {deep_link}",
        "quick_replies": ["Open Scan", "Later"]
    })
    return {"triggered": True, "deep_link": deep_link}
```

### Tool 6 — Gym Session Dispatcher
```python
@tool
def dispatch_gym_session(patient_id: str, session_type: str, day_number: int) -> dict:
    """
    Schedule a gym session activity for the patient in the activity planner.
    session_type: cardio | strength | yoga
    Only fires if patient has gym benefit allocated.
    """
    activity = supabase.table("activity_180_day").insert({
        "patient_id": patient_id,
        "day_number": day_number,
        "activity_type": f"gym_session_{session_type}",
        "domain": "STEPS",
        "is_clinical": False,
        "status": "PENDING",
        "scheduled_date": compute_date_from_day(patient_id, day_number),
        "points_earned": 0,
        "benefit_gate_points": 300,
    }).execute()
    return {"scheduled": True, "activity_id": activity.data[0]["id"]}
```

### Tool 7 — Supabase Care Plan Writer
```python
@tool
def update_care_plan(patient_id: str, lane: str, updates: dict, reason: str) -> dict:
    """
    Write a new care plan version to Supabase.
    lane: "clinical" | "engagement"
    reason: why the plan changed (lab_result_trigger | weekly_psych | enrollment)
    NEVER called for clinical lane based on engagement signals.
    """
    # Get current version
    current = supabase.table("care_plan_versions")\
        .select("plan_version")\
        .eq("patient_id", patient_id)\
        .order("plan_version", desc=True)\
        .limit(1).execute()

    new_version = (current.data[0]["plan_version"] + 1) if current.data else 1

    supabase.table("care_plan_versions").insert({
        "patient_id": patient_id,
        "plan_version": new_version,
        "revision_lane": lane,
        "revision_reason": reason,
        "revision_trigger": reason,
        "status": "active",
        **updates
    }).execute()

    return {"updated": True, "version": new_version}
```

### Tool 8 — Benefit Cap Checker
```python
@tool
def check_benefit_cap(patient_id: str, benefit_type: str) -> dict:
    """
    Check if a patient has remaining benefit slots.
    benefit_type: DOCTOR | DIETICIAN | LAB_TEST | GYM | BINAH
    Returns: {remaining: int, used: int, max: int, cap_reached: bool}
    """
    result = supabase.table("benefit_utilisation")\
        .select("*")\
        .eq("patient_id", patient_id)\
        .eq("benefit_type", benefit_type)\
        .single().execute()

    used = result.data["used_count"]
    max_count = result.data["max_count"]
    return {
        "remaining": max_count - used,
        "used": used,
        "max": max_count,
        "cap_reached": used >= max_count
    }
```

### Tool 9 — Human Escalation (SG Agent)
```python
@tool
def escalate_to_human_agent(patient_id: str, reason: str, priority: str, call_script: str) -> dict:
    """
    Create a task for the human SG Agent. Stops all automated comms for this patient.
    reason: repeated_miss | benefit_cap | distress | worsening_lab | emergency
    priority: LOW | MEDIUM | HIGH | URGENT
    """
    task_id = f"SFDC-{nanoid(10)}"
    supabase.table("sfdc_tasks").insert({
        "patient_id": patient_id,
        "sfdc_task_id": task_id,
        "type": map_reason_to_sfdc_type(reason),
        "priority": priority,
        "status": "OPEN",
        "subject": f"Escalation: {reason} — {patient_id}",
        "description": f"AI coordinator has flagged this patient for human review. Reason: {reason}",
        "call_script": call_script,
    }).execute()

    # Stop automated comms — set frustration stage to SOFT_REST
    supabase.table("patients")\
        .update({"frustration_stage": "SOFT_REST"})\
        .eq("id", patient_id).execute()

    return {"escalated": True, "task_id": task_id}
```

---

## The LangGraph Graph Definition

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver

def build_care_coordinator_graph():
    graph = StateGraph(PatientState)

    # ── Add all 9 agent nodes ─────────────────────────────────────────────
    graph.add_node("orchestrator",            orchestrator_node)
    graph.add_node("health_profiler",         health_profiler_node)
    graph.add_node("psychology_profiler",     psychology_profiler_node)
    graph.add_node("care_planner_clinical",   care_planner_clinical_node)
    graph.add_node("care_planner_engagement", care_planner_engagement_node)
    graph.add_node("communication_crafter",   communication_crafter_node)
    graph.add_node("diet_adherence",          diet_adherence_node)
    graph.add_node("appointment_coordinator", appointment_coordinator_node)
    graph.add_node("progress_reporter",       progress_reporter_node)
    graph.add_node("rewards_agent",           rewards_agent_node)
    graph.add_node("human_escalation",        human_escalation_node)   # interrupt point

    # ── Entry point ────────────────────────────────────────────────────────
    graph.set_entry_point("orchestrator")

    # ── Orchestrator routing ───────────────────────────────────────────────
    graph.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {
            "health_profiler":         "health_profiler",
            "psychology_profiler":     "psychology_profiler",
            "appointment_coordinator": "appointment_coordinator",
            "communication_crafter":   "communication_crafter",
            "progress_reporter":       "progress_reporter",
            "rewards_agent":           "rewards_agent",
            "human_escalation":        "human_escalation",
            "end":                     END,
        }
    )

    # ── Health Profiler → clinical vs engagement branch ────────────────────
    graph.add_conditional_edges(
        "health_profiler",
        lambda s: "care_planner_clinical" if s["clinical_review_needed"] else "psychology_profiler",
        {
            "care_planner_clinical": "care_planner_clinical",
            "psychology_profiler":   "psychology_profiler",
        }
    )

    # ── All agents return to orchestrator for next decision ────────────────
    for node in ["psychology_profiler", "care_planner_clinical",
                 "care_planner_engagement", "diet_adherence",
                 "appointment_coordinator", "progress_reporter", "rewards_agent"]:
        graph.add_edge(node, "communication_crafter")

    graph.add_edge("communication_crafter", END)
    graph.add_edge("human_escalation", END)

    # ── Persistence: patient state survives between daily runs ─────────────
    checkpointer = PostgresSaver.from_conn_string(SUPABASE_POSTGRES_URL)

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_escalation"]  # pause for human review
    )
```

---

## The Routing Function (heart of the orchestrator)

```python
def route_from_orchestrator(state: PatientState) -> str:
    """
    This function is the Orchestrator Agent's decision.
    It reads state and returns which node to invoke next.
    """
    trigger = state["trigger_event"]

    # ── Immediate escalation checks (always first) ────────────────────────
    if state["escalate_to_human"]:
        return "human_escalation"
    if state["frustration_stage"] == "SOFT_REST":
        return "end"  # stop all automated comms

    # ── Event-driven routing ───────────────────────────────────────────────
    if trigger == "lab_received":
        return "health_profiler"        # new lab → re-profile → clinical replan
    if trigger == "wa_reply":
        return "diet_adherence"         # incoming reply → check diet compliance
    if trigger == "voice_outcome":
        return "psychology_profiler"    # call outcome → update psychology stage
    if trigger == "binah_result":
        return "health_profiler"        # new vitals scan → update health profile

    # ── Schedule-driven routing ────────────────────────────────────────────
    if trigger == "enrollment":
        return "health_profiler"        # day 0: profile → plan → communicate
    if trigger == "weekly_psych_review":
        return "psychology_profiler"    # every 7 days
    if trigger == "monthly_progress":
        return "progress_reporter"      # every 30 days

    # ── Daily orchestrator logic ───────────────────────────────────────────
    if is_clinical_schedule_date(state):
        return "appointment_coordinator"

    if state["consecutive_no_response"] >= 2:
        # Escalate channel: if last was WA, try voice next
        if state["last_nudge_channel"] == "WHATSAPP":
            state["current_action"] = "trigger_voice"
        return "communication_crafter"

    if state["consecutive_missed_appts"] >= 3:
        state["escalate_to_human"] = True
        state["escalation_reason"] = "repeated_miss"
        return "human_escalation"

    if should_check_rewards(state):
        return "rewards_agent"

    # Default: check if we should send today's engagement nudge
    return "communication_crafter"
```

---

## Each Agent Node — What it does in code

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0)

# ── Node 2: Health Profiler ───────────────────────────────────────────────
def health_profiler_node(state: PatientState) -> dict:
    # Step 1: Fetch latest data from Trino
    lab_data        = fetch_patient_data_from_trino.invoke({"patient_id": state["patient_id"], "query_type": "lab_results"})
    hra_data        = fetch_patient_data_from_trino.invoke({"patient_id": state["patient_id"], "query_type": "hra_answers"})

    # Step 2: Call Claude with Health Profiler system prompt
    programme_ctx   = PROGRAMME_CONTEXT[state["programme"]]
    response = llm.invoke([
        SystemMessage(content=HEALTH_PROFILER_SYSTEM_PROMPT.format(
            programme_name=state["programme"],
            biomarker_thresholds=programme_ctx["biomarkers"],
            escalation_thresholds=programme_ctx["escalation_thresholds"],
        )),
        HumanMessage(content=f"""
Lab data: {json.dumps(lab_data)}
HRA data: {json.dumps(hra_data)}
Previous health profile: {json.dumps(state.get("health_profile", {}))}

Return health_profile JSON and clinical_review_needed boolean.
        """)
    ])

    result = parse_json_response(response.content)

    # Step 3: Write to Supabase
    update_care_plan.invoke({
        "patient_id": state["patient_id"],
        "lane": "clinical",
        "updates": {"health_profile": result["health_profile"]},
        "reason": "health_profiler_run"
    })

    return {
        "health_profile": result["health_profile"],
        "clinical_review_needed": result["clinical_review_needed"],
    }


# ── Node 3: Psychology Profiler ────────────────────────────────────────────
def psychology_profiler_node(state: PatientState) -> dict:
    weekly_signals = {
        "meal_logs_last_7d":           state["meal_logs_last_7d"],
        "consecutive_no_response":     state["consecutive_no_response"],
        "appointments_attended":       state["appointments_attended"],
        "appointments_missed":         state["appointments_missed"],
        "last_nudge_responded":        state["last_nudge_responded"],
        "consecutive_missed_appts":    state["consecutive_missed_appts"],
    }

    response = llm.invoke([
        SystemMessage(content=PSYCHOLOGY_PROFILER_SYSTEM_PROMPT),
        HumanMessage(content=f"""
Weekly signals: {json.dumps(weekly_signals)}
Previous psych profile: {json.dumps(state.get("psych_profile", {}))}

Return psychology_profile JSON.
        """)
    ])

    result = parse_json_response(response.content)

    # Update patient smart_send_time and frustration_stage
    supabase.table("patients").update({
        "psych_profile":    result,
        "smart_send_time":  result.get("contact_window", state["smart_send_time"]),
        "frustration_stage": "SOFT_REST" if result.get("distress_flag") else state["frustration_stage"],
    }).eq("id", state["patient_id"]).execute()

    return {
        "psych_profile":     result,
        "smart_send_time":   result.get("contact_window", state["smart_send_time"]),
        "escalate_to_human": result.get("escalate_to_sfdc", False),
        "escalation_reason": "repeated_miss" if result.get("escalate_to_sfdc") else None,
    }


# ── Node 5: Communication Crafter ─────────────────────────────────────────
def communication_crafter_node(state: PatientState) -> dict:
    action      = state.get("current_action", "send_whatsapp")
    programme   = PROGRAMME_CONTEXT[state["programme"]]
    psych       = state.get("psych_profile", {})

    # Determine message type from state context
    message_type = determine_message_type(state)

    response = llm.invoke([
        SystemMessage(content=COMM_CRAFTER_SYSTEM_PROMPT.format(
            programme_name=state["programme"],
            specialist_type=programme["specialist"],
            user_language=programme["userLanguage"],
            device_type=programme["devices"][state["cohort"]],
            comm_style=psych.get("comm_style", "Empathetic"),
            barrier=psych.get("barrier", "None"),
            fomo_sensitivity=psych.get("fomo_sensitivity", "Medium"),
            smart_send_time=state["smart_send_time"],
        )),
        HumanMessage(content=f"""
Message type: {message_type}
Patient context: {summarize_patient_context(state)}
Benefits remaining: Doctor {state['doctor_max'] - state['doctor_used']}, Diet {state['diet_max'] - state['diet_used']}

Generate the message. Return JSON with channel, script, cta, personalization_vars_used.
        """)
    ])

    message_payload = parse_json_response(response.content)

    # Validate: no raw biomarker values in output
    message_payload = validate_no_raw_values(message_payload, state)

    # Execute the message
    if action == "send_whatsapp" or message_payload["channel"] == "WHATSAPP":
        send_whatsapp_message.invoke({
            "patient_id": state["patient_id"],
            "message": message_payload["script"],
            "quick_replies": message_payload.get("quick_replies", [])
        })
    elif action == "trigger_voice":
        trigger_voice_call.invoke({
            "patient_id": state["patient_id"],
            "script": message_payload
        })

    return {
        "current_message":          message_payload,
        "last_nudge_channel":       message_payload["channel"],
        "last_nudge_sent_at":       datetime.now().isoformat(),
        "last_nudge_responded":     False,
        "consecutive_no_response":  state["consecutive_no_response"] + 1,
    }
```

---

## The Feedback Webhook Server (FastAPI)

This is how responses from WhatsApp, voice calls, and labs re-enter the graph.

```python
from fastapi import FastAPI
from langgraph.types import Command

app   = FastAPI()
graph = build_care_coordinator_graph()

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(payload: dict):
    """WATI/Twilio sends incoming patient replies here."""
    patient_id = resolve_patient_from_phone(payload["from"])
    reply_text = payload["text"]

    # Update nudge as responded
    supabase.table("nudge_events")\
        .update({"status": "RESPONDED", "response": reply_text, "responded_at": datetime.now().isoformat()})\
        .eq("patient_id", patient_id)\
        .eq("status", "SENT")\
        .order("sent_at", desc=True)\
        .limit(1).execute()

    # Re-invoke the graph with the wa_reply trigger
    config = {"configurable": {"thread_id": patient_id}}
    graph.invoke(
        {"trigger_event": "wa_reply", "trigger_data": {"reply": reply_text}, "last_nudge_responded": True, "consecutive_no_response": 0},
        config=config
    )
    return {"status": "processed"}


@app.post("/webhook/voice")
async def voice_webhook(payload: dict):
    """Exotel sends call outcome here."""
    patient_id  = resolve_patient_from_call(payload["CallSid"])
    call_status = payload["Status"]       # "completed" | "busy" | "no-answer"
    dtmf_input  = payload.get("Digits")  # patient pressed 1 or 2 during call

    graph.invoke(
        {"trigger_event": "voice_outcome", "trigger_data": {"status": call_status, "input": dtmf_input}},
        config={"configurable": {"thread_id": patient_id}}
    )
    return {"status": "processed"}


@app.post("/webhook/lab-result")
async def lab_result_webhook(payload: dict):
    """Called when a new lab report is uploaded to the system."""
    patient_id = payload["patient_id"]
    lab_values = payload["values"]       # {"HbA1c": 7.2, "Fasting_Glucose": 118}

    # Write to Supabase lab table
    supabase.table("lab_reports").insert({
        "patient_id": patient_id,
        "values": lab_values,
        "report_date": datetime.now().isoformat(),
        "source": "UPLOAD"
    }).execute()

    # Immediately re-invoke the graph — lab_received is a high-priority trigger
    graph.invoke(
        {"trigger_event": "lab_received", "trigger_data": lab_values},
        config={"configurable": {"thread_id": patient_id}}
    )
    return {"status": "replanning_triggered"}


@app.post("/webhook/binah")
async def binah_webhook(payload: dict):
    """Binah AI sends face scan results here."""
    patient_id  = payload["patient_id"]
    scan_result = payload["result"]      # {"hr": 78, "spo2": 98, "stress": "moderate"}

    graph.invoke(
        {"trigger_event": "binah_result", "trigger_data": scan_result},
        config={"configurable": {"thread_id": patient_id}}
    )
    return {"status": "processed"}
```

---

## The Daily Scheduler

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=8, minute=0)
async def daily_orchestrator_run():
    """Runs every morning at 8 AM for all active patients."""
    patients = supabase.table("patients")\
        .select("id, frustration_stage")\
        .eq("programme", "DIABETES")\
        .execute()

    for patient in patients.data:
        if patient["frustration_stage"] == "SOFT_REST":
            continue  # do not disturb

        config = {"configurable": {"thread_id": patient["id"]}}
        await graph.ainvoke(
            {"trigger_event": "daily_schedule"},
            config=config
        )

@scheduler.scheduled_job("cron", day_of_week="mon", hour=9)
async def weekly_psychology_run():
    """Every Monday — re-evaluate psychology profile for all patients."""
    patients = supabase.table("patients").select("id").execute()
    for p in patients.data:
        await graph.ainvoke(
            {"trigger_event": "weekly_psych_review"},
            config={"configurable": {"thread_id": p["id"]}}
        )

@scheduler.scheduled_job("cron", day=1, hour=10)
async def monthly_progress_run():
    """First day of each month — progress report for all patients."""
    patients = supabase.table("patients").select("id").execute()
    for p in patients.data:
        await graph.ainvoke(
            {"trigger_event": "monthly_progress"},
            config={"configurable": {"thread_id": p["id"]}}
        )
```

---

## Complete File Structure for This Tool

```
care_ai_engine/
├── main.py                        ← FastAPI app + scheduler startup
├── graph.py                       ← LangGraph graph definition + routing
├── state.py                       ← PatientState TypedDict
│
├── nodes/                         ← One file per agent node
│   ├── orchestrator.py            ← route_from_orchestrator()
│   ├── health_profiler.py         ← health_profiler_node()
│   ├── psychology_profiler.py     ← psychology_profiler_node()
│   ├── care_planner_clinical.py   ← care_planner_clinical_node()
│   ├── care_planner_engagement.py ← care_planner_engagement_node()
│   ├── communication_crafter.py   ← communication_crafter_node()
│   ├── diet_adherence.py          ← diet_adherence_node()
│   ├── appointment_coordinator.py ← appointment_coordinator_node()
│   ├── progress_reporter.py       ← progress_reporter_node()
│   ├── rewards_agent.py           ← rewards_agent_node()
│   └── human_escalation.py        ← human_escalation_node()
│
├── tools/                         ← One file per integration
│   ├── trino_reader.py            ← fetch_patient_data_from_trino()
│   ├── whatsapp_sender.py         ← send_whatsapp_message()
│   ├── voice_trigger.py           ← trigger_voice_call()
│   ├── appointment_booker.py      ← book_appointment()
│   ├── binah_trigger.py           ← trigger_binah_scan()
│   ├── gym_dispatcher.py          ← dispatch_gym_session()
│   ├── supabase_writer.py         ← update_care_plan()
│   ├── benefit_checker.py         ← check_benefit_cap()
│   └── human_escalation_tool.py   ← escalate_to_human_agent()
│
├── prompts/                       ← System prompts for each agent
│   ├── health_profiler.py
│   ├── psychology_profiler.py
│   ├── care_planner.py
│   ├── communication_crafter.py
│   ├── diet_adherence.py
│   ├── appointment_coordinator.py
│   ├── progress_reporter.py
│   └── rewards_agent.py
│
├── constants/
│   ├── programme_context.py       ← PROGRAMME_CONTEXT + BENEFIT_CAPS + DEVICE_CAPS
│   └── activities.py              ← ACTIVITY_META (50+ activities)
│
├── webhooks/                      ← FastAPI routers
│   ├── whatsapp.py
│   ├── voice.py
│   ├── lab_result.py
│   └── binah.py
│
├── scheduler.py                   ← APScheduler daily/weekly/monthly jobs
├── db.py                          ← Supabase client singleton
└── requirements.txt
```

---

## Requirements

```
langgraph>=0.2.0
langchain-anthropic>=0.1.0
langchain-core>=0.2.0
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
apscheduler>=3.10.0
trino>=0.328.0
supabase>=2.3.0
anthropic>=0.25.0
python-dotenv>=1.0.0
nanoid>=2.0.0
httpx>=0.27.0
```

---

## The one-page summary of what you've built

```
Trino (read) ──→ LangGraph State ──→ Claude (reason) ──→ Tools (act)
                      ↑                                        │
                      └────────── Webhook (patient response) ──┘
```

- **Trino** is where all historical patient data lives. Read-only. Never write to it.
- **LangGraph state** is the patient's brain — what we know, what we decided, what happened.
- **Claude** is the reasoning engine inside each node — it reads state, reasons, returns a decision.
- **Tools** are the hands — send message, book appointment, trigger call, write to Supabase.
- **Webhooks** are the ears — when a patient replies, a call ends, or a lab comes in, the graph wakes up and re-runs.

This loop — read → reason → act → listen → repeat — is the entire care coordinator.
