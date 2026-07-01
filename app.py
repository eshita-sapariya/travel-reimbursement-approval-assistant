import json
import uuid
import streamlit as st
from graph.workflow import graph

st.set_page_config(
    page_title="Travel Reimbursement Approval Assistant",
    page_icon="✈️"
)

st.title("✈️ Travel Reimbursement Approval Assistant")


# Initialize Session State

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "agent_state" not in st.session_state:
    st.session_state.agent_state = {
        "messages": [],
        "agent_messages": [],
        "claim": {},
        "final_answer": "",
        "audit_trail": [],
    }


# Render a decision JSON as a formatted card

STEP_ICONS = {
    "agent_tool_call":  "🤖",
    "tool_execution":   "🔧",
    "agent_final":      "💡",
    "decision":         "⚖️",
}


def render_audit_trail(trail: list):
    if not trail:
        return
    with st.expander("🔎 Audit Trail — steps taken this turn", expanded=False):
        for i, entry in enumerate(trail):
            step = entry.get("step", "")
            icon = STEP_ICONS.get(step, "•")
            st.markdown(f"**{icon} Step {i+1}: {entry.get('label', step)}**")

            if step == "agent_tool_call":
                tools_called = entry.get("tools_called", [])
                st.markdown(f"**Tools decided to call:** `{'`, `'.join(tools_called)}`")
                for item in entry.get("tool_inputs", []):
                    for tname, targs in item.items():
                        st.markdown(f"- `{tname}` ← `{targs}`")

            elif step == "tool_execution":
                for res in entry.get("results", []):
                    st.markdown(f"**`{res['tool']}`** called with `{res['args']}`")
                    if isinstance(res["result"], (dict, list)):
                        st.json(res["result"])
                    else:
                        st.text(str(res["result"]))

            elif step == "agent_final":
                st.success("Agent has enough information — producing final decision")

            elif step == "decision":
                st.markdown(f"**Tool called:** `{entry.get('tool_called', '')}`")
                st.markdown(f"**Decision:** `{entry.get('decision', '')}`")
                st.markdown(f"**Confidence:** `{entry.get('confidence', '')}`")
                st.markdown(f"**Reason:** {sanitize(entry.get('reason', ''))}")
                with st.popover("Full claim evaluated"):
                    st.json(entry.get("claim_evaluated", {}))

            if i < len(trail) - 1:
                st.divider()


def sanitize(text: str) -> str:
    return text.replace("â‚¹", "INR").replace("â€™", "'").replace("â€œ", '"').replace("â€\x9d", '"')


def strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()


def render_decision(text: str):
    try:
        data = json.loads(strip_json_fences(text))
    except (json.JSONDecodeError, TypeError):
        st.markdown(text)
        return

    decision = data.get("decision", "")
    color_map = {
        "APPROVE": "🟢",
        "PARTIALLY_APPROVE": "🟡",
        "REJECT": "🔴",
        "MANUAL_REVIEW": "🔵",
    }
    icon = color_map.get(decision, "⚪")

    st.markdown(f"### {icon} {decision}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Approved Amount", f"₹{data.get('approved_amount', 0):,}")
    col2.metric("Deducted Amount", f"₹{data.get('deducted_amount', 0):,}")
    col3.metric("Confidence", data.get("confidence", "—"))

    st.markdown(f"**Reason:** {sanitize(data.get('reason', ''))}")
    st.markdown(f"**Policy Reference:** {sanitize(data.get('policy_reference', ''))}")

    missing_docs = data.get("missing_documents", [])
    if missing_docs:
        st.warning("**Missing Documents:** " + ", ".join(missing_docs))


# Display Chat History

for message in st.session_state.agent_state["messages"]:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            render_decision(message["content"])
        else:
            st.markdown(message["content"])


# User Input

user_input = st.chat_input("Describe your travel expense claim...")

if user_input:

    # Append user message to state before invoking graph
    st.session_state.agent_state["messages"].append(
        {"role": "user", "content": user_input}
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    # Invoke graph — nodes handle appending the assistant reply to messages
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    result = graph.invoke(st.session_state.agent_state, config=config)

    # Update full state
    st.session_state.agent_state.update(result)

    assistant_reply = result["final_answer"]

    with st.chat_message("assistant"):
        render_decision(assistant_reply)

    render_audit_trail(result.get("audit_trail", []))