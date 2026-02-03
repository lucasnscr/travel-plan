"""LangGraph state machine for the travel planning workflow.

Defines the full DAG of nodes — from requirements gathering through
booking and document generation — with conditional edges for budget
re-optimization and human-in-the-loop approval.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from travel_orchestrator.graph.edges import (
    determine_revision_target,
    process_approval_decision,
    should_optimize_costs,
)
from travel_orchestrator.graph.nodes.analyze_destination import analyze_destination_node
from travel_orchestrator.graph.nodes.calculate_budget import calculate_budget_node
from travel_orchestrator.graph.nodes.gather_requirements import gather_requirements_node
from travel_orchestrator.graph.nodes.optimize_itinerary import optimize_itinerary_node
from travel_orchestrator.graph.nodes.present_for_approval import present_for_approval_node
from travel_orchestrator.graph.nodes.risk_check import risk_and_policy_check_node
from travel_orchestrator.graph.nodes.search_activities import search_activities_node
from travel_orchestrator.graph.nodes.search_hotels import search_hotels_node
from travel_orchestrator.state.models import TravelPlannerCore
from travel_orchestrator.utils.logging import get_logger, log_node_execution

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Node stubs — each decorated with structured logging that auto-binds
# plan_id from state.
# ---------------------------------------------------------------------------


@log_node_execution("search_flights")
async def search_flights_node(state: TravelPlannerCore) -> TravelPlannerCore:
    """Query flight sources and score options."""
    # TODO: Implementar busca de voos
    return state


@log_node_execution("process_feedback")
async def process_feedback_node(state: TravelPlannerCore) -> TravelPlannerCore:
    """Incorporate reviewer feedback and decide which node to revisit."""
    # TODO: Implementar processamento de feedback
    return {**state, "revision_count": state["revision_count"] + 1}


@log_node_execution("book_services")
async def book_services_node(state: TravelPlannerCore) -> TravelPlannerCore:
    """Execute bookings for flight, hotel, and activities that require it."""
    # TODO: Implementar reservas
    return state


@log_node_execution("generate_documents")
async def generate_documents_node(state: TravelPlannerCore) -> TravelPlannerCore:
    """Generate final itinerary PDF, confirmation emails, calendar events."""
    # TODO: Implementar geração de documentos
    return state


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def create_travel_planner_graph() -> StateGraph:
    """Build and return the (uncompiled) LangGraph StateGraph.

    The graph encodes the full travel-planning workflow::

        START
          → gather_requirements
          → analyze_destination
          → search_flights
          → search_hotels
          → search_activities
          → optimize_itinerary
          → calculate_budget
          →  ┬─ over budget ──→ search_flights  (loop)
             └─ within budget → risk_and_policy_check
          → present_for_approval   (HITL interrupt)
          →  ┬─ approved ──→ book_services → generate_documents → END
             └─ rejected ──→ process_feedback → (re-route to relevant node)
    """
    graph = StateGraph(TravelPlannerCore)

    # -- Register nodes -------------------------------------------------------
    graph.add_node("gather_requirements", gather_requirements_node)
    graph.add_node("analyze_destination", analyze_destination_node)
    graph.add_node("search_flights", search_flights_node)
    graph.add_node("search_hotels", search_hotels_node)
    graph.add_node("search_activities", search_activities_node)
    graph.add_node("optimize_itinerary", optimize_itinerary_node)
    graph.add_node("calculate_budget", calculate_budget_node)
    graph.add_node("risk_and_policy_check", risk_and_policy_check_node)
    graph.add_node("present_for_approval", present_for_approval_node)
    graph.add_node("process_feedback", process_feedback_node)
    graph.add_node("book_services", book_services_node)
    graph.add_node("generate_documents", generate_documents_node)

    # -- Linear edges ---------------------------------------------------------
    graph.add_edge(START, "gather_requirements")
    graph.add_edge("gather_requirements", "analyze_destination")
    graph.add_edge("analyze_destination", "search_flights")
    graph.add_edge("search_flights", "search_hotels")
    graph.add_edge("search_hotels", "search_activities")
    graph.add_edge("search_activities", "optimize_itinerary")
    graph.add_edge("optimize_itinerary", "calculate_budget")

    # -- Conditional: budget check (edges.should_optimize_costs) ---------------
    graph.add_conditional_edges(
        "calculate_budget",
        should_optimize_costs,
        path_map={
            "optimize_costs": "search_flights",
            "proceed": "risk_and_policy_check",
        },
    )

    graph.add_edge("risk_and_policy_check", "present_for_approval")

    # -- Conditional: approval (edges.process_approval_decision) ---------------
    graph.add_conditional_edges(
        "present_for_approval",
        process_approval_decision,
        path_map={
            "approved": "book_services",
            "rejected": "process_feedback",
        },
    )

    # -- Conditional: feedback re-route (edges.determine_revision_target) ------
    graph.add_conditional_edges(
        "process_feedback",
        determine_revision_target,
        path_map={
            "search_flights": "search_flights",
            "search_hotels": "search_hotels",
            "search_activities": "search_activities",
        },
    )

    # -- Final linear path ----------------------------------------------------
    graph.add_edge("book_services", "generate_documents")
    graph.add_edge("generate_documents", END)

    return graph


def compile_graph() -> CompiledStateGraph:
    """Compile the travel planner graph with in-memory checkpointing.

    The compiled graph is ready to be invoked or streamed.  The
    ``present_for_approval`` node uses ``interrupt()`` internally to
    pause for human review, so no ``interrupt_before`` is needed.
    """
    graph = create_travel_planner_graph()
    return graph.compile(
        checkpointer=MemorySaver(),
    )
