from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import AgentState
from graph.nodes import (
    extract_claim_node,
    validate_claim_node,
    ask_missing_fields_node,
    agent_node,
    tool_execution_node,
    finalize_node,
)


builder = StateGraph(AgentState)

builder.add_node("extract_claim",      extract_claim_node)
builder.add_node("validate_claim",     validate_claim_node)
builder.add_node("ask_missing_fields", ask_missing_fields_node)
builder.add_node("agent",              agent_node)
builder.add_node("tools",              tool_execution_node)
builder.add_node("finalize",           finalize_node)


builder.add_edge(START, "extract_claim")
builder.add_edge("extract_claim", "validate_claim")


def route_after_validation(state):
    if state["missing_fields"]:
        return "missing"
    return "complete"


builder.add_conditional_edges(
    "validate_claim",
    route_after_validation,
    {
        "missing":  "ask_missing_fields",
        "complete": "agent",
    }
)

# builder.add_edge("ask_missing_fields", END)
builder.add_edge("ask_missing_fields", "extract_claim")


def route_agent(state):
    last = state["agent_messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "finalize"


builder.add_conditional_edges(
    "agent",
    route_agent,
    {
        "tools":    "tools",
        "finalize": "finalize",
    }
)

builder.add_edge("tools",    "agent")
builder.add_edge("finalize", END)


memory = MemorySaver()
graph = builder.compile(checkpointer=memory)
