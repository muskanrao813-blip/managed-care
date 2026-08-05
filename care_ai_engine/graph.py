"""
LangGraph orchestrator — routes patient state through all 9 agent nodes.
Stateful execution with PostgreSQL checkpointing (not yet — using in-memory for v1).
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from state import PatientState, default_state
from nodes.orchestrator import orchestrator_node
from nodes.health_profiler import health_profiler_node
from nodes.psychology_profiler import psychology_profiler_node
from nodes.care_planner import care_planner_node
from nodes.communication_crafter import communication_crafter_node
from nodes.diet_adherence import diet_adherence_node
from nodes.appointment_coordinator import appointment_coordinator_node
from nodes.progress_reporter import progress_reporter_node
from nodes.rewards_agent import rewards_agent_node
import db
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# ROUTING LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def _route_from_orchestrator(state: PatientState) -> str:
    """Route to next agent based on orchestrator decision."""
    action = state.get("next_agent", "communication_crafter")
    return action


def _route_from_health_profiler(state: PatientState) -> str:
    """After health profiling, go to care planner or next handler."""
    if state.get("trigger_event") == "enrollment":
        return "care_planner"
    return "communication_crafter"


def _route_from_psychology_profiler(state: PatientState) -> str:
    """After psychology profiling, go to care planner."""
    return "care_planner"


def _route_from_care_planner(state: PatientState) -> str:
    """After care planning, go to next action."""
    trigger = state.get("trigger_event")
    if trigger == "enrollment":
        return "rewards_agent"
    return state.get("next_agent", "end")


# ─────────────────────────────────────────────────────────────────────────────
# NODE EXECUTORS (wrap each agent node, merge outputs into state)
# ─────────────────────────────────────────────────────────────────────────────

def _node_orchestrator(state: PatientState) -> PatientState:
    result = orchestrator_node(state)
    return {**state, **result}


def _node_health_profiler(state: PatientState) -> PatientState:
    result = health_profiler_node(state)
    return {**state, **result}


def _node_psychology_profiler(state: PatientState) -> PatientState:
    result = psychology_profiler_node(state)
    return {**state, **result}


def _node_care_planner(state: PatientState) -> PatientState:
    result = care_planner_node(state)
    return {**state, **result}


def _node_communication_crafter(state: PatientState) -> PatientState:
    result = communication_crafter_node(state)
    return {**state, **result}


def _node_diet_adherence(state: PatientState) -> PatientState:
    result = diet_adherence_node(state)
    return {**state, **result}


def _node_appointment_coordinator(state: PatientState) -> PatientState:
    result = appointment_coordinator_node(state)
    return {**state, **result}


def _node_progress_reporter(state: PatientState) -> PatientState:
    result = progress_reporter_node(state)
    return {**state, **result}


def _node_rewards_agent(state: PatientState) -> PatientState:
    result = rewards_agent_node(state)
    return {**state, **result}


def _node_escalate(state: PatientState) -> PatientState:
    """Create escalation and stop."""
    if state.get("escalate_to_human"):
        reason = state.get("escalation_reason", "manual_escalation")
        db.create_escalation(
            state["mobile_hash"], reason, "HIGH",
            f"Escalation from orchestrator: {reason}",
            f"Trigger: {state.get('trigger_event')}",
            "Calling patient for intervention..."
        )
    return state


def _node_end(state: PatientState) -> PatientState:
    """Final state — log and return."""
    print(f"\n[GRAPH] Execution complete for {state['mobile_hash']}")
    print(f"  Final state: {state.get('current_action', 'end')}")
    print(f"  Points: {state.get('points', 0)} | Level: {state.get('level', 'BRONZE')}")
    return state


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH EXECUTOR (simple version, no LangGraph framework yet)
# ─────────────────────────────────────────────────────────────────────────────

class PatientCareGraph:
    """Simple state machine graph for patient care orchestration."""

    NODE_MAP = {
        "orchestrator":          _node_orchestrator,
        "health_profiler":       _node_health_profiler,
        "psychology_profiler":   _node_psychology_profiler,
        "care_planner":          _node_care_planner,
        "communication_crafter": _node_communication_crafter,
        "diet_adherence":        _node_diet_adherence,
        "appointment_coordinator": _node_appointment_coordinator,
        "progress_reporter":     _node_progress_reporter,
        "rewards_agent":         _node_rewards_agent,
        "escalate":              _node_escalate,
        "end":                   _node_end,
    }

    ROUTER_MAP = {
        "orchestrator":          _route_from_orchestrator,
        "health_profiler":       _route_from_health_profiler,
        "psychology_profiler":   _route_from_psychology_profiler,
        "care_planner":          _route_from_care_planner,
        "communication_crafter": lambda s: s.get("next_agent", "end"),
        "diet_adherence":        lambda s: "end",
        "appointment_coordinator": lambda s: "end",
        "progress_reporter":     lambda s: "end",
        "rewards_agent":         lambda s: "end",
        "escalate":              lambda s: "end",
        "end":                   lambda s: "end",
    }

    def execute(self, state: PatientState, max_steps: int = 15) -> PatientState:
        """Execute the graph, routing between nodes until 'end' is reached."""
        current_node = "orchestrator"
        step = 0

        while current_node != "end" and step < max_steps:
            print(f"\n[GRAPH] Step {step + 1}: {current_node}")
            if current_node not in self.NODE_MAP:
                print(f"  [WARN] Unknown node '{current_node}' — ending")
                break

            node_func = self.NODE_MAP[current_node]
            state = node_func(state)

            router = self.ROUTER_MAP.get(current_node, lambda s: "end")
            current_node = router(state)
            step += 1

        if step >= max_steps:
            print(f"\n[GRAPH] Max steps ({max_steps}) reached — ending")

        return state


def run_patient_care(mobile_hash: str, trigger: str = "daily_schedule",
                     trigger_data: dict = None) -> PatientState:
    """
    Main entry point: fetch patient from DB, run through care graph.
    """
    # Fetch patient state from DB
    patient = db.get_patient(mobile_hash)
    if not patient:
        print(f"[GRAPH] Patient not found: {mobile_hash}")
        return {}

    state = PatientState(patient)
    state["trigger_event"] = trigger
    state["trigger_data"]   = trigger_data or {}
    state["run_timestamp"]  = datetime.now().isoformat()

    # Compute day_number
    policy_start = datetime.strptime(state["policy_start_date"], "%Y-%m-%d")
    state["day_number"] = (datetime.now() - policy_start).days

    # Run graph
    graph = PatientCareGraph()
    final_state = graph.execute(state)

    # Sync final state back to DB (selective fields)
    final_updates = {
        "points":                  final_state.get("points", state.get("points", 0)),
        "level":                   final_state.get("level", state.get("level", "BRONZE")),
        "device_allocated":        1 if final_state.get("device_allocated") else 0,
        "consecutive_no_resp":     final_state.get("consecutive_no_resp", 0),
        "consecutive_missed":      final_state.get("consecutive_missed", 0),
        "last_nudge_channel":      final_state.get("last_nudge_channel", state.get("last_nudge_channel")),
        "last_nudge_at":           final_state.get("last_nudge_at", state.get("last_nudge_at")),
        "last_nudge_responded":    1 if final_state.get("last_nudge_responded") else 0,
    }
    db.update_patient(mobile_hash, final_updates)

    return final_state


if __name__ == "__main__":
    # Test with seeded patient
    print("Testing graph with test patient...")
    result = run_patient_care("TEST_HASH_001", trigger="enrollment")
    print(f"\nFinal state: {result}")
