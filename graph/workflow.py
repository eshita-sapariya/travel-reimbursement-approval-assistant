from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import AgentState
from graph.nodes import (
    agent_node,
    tool_execution_node,
    finalize_node,
)


builder = StateGraph(AgentState)

builder.add_node("agent",    agent_node)
builder.add_node("tools",    tool_execution_node)
builder.add_node("finalize", finalize_node)

builder.add_edge(START, "agent")


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
