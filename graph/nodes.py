import json
import logging
import re
from datetime import date, timedelta

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from utils.llm import llm
from prompts.prompts import ORCHESTRATOR_PROMPT
from tools.policy_lookup import policy_lookup
from tools.limit_checker import limit_checker
from tools.receipt_validator import receipt_validator
from tools.claim_extractor import claim_extractor, _run_extraction


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("travel_agent")


TOOLS = [claim_extractor, limit_checker, receipt_validator, policy_lookup]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
llm_with_tools = llm.bind_tools(TOOLS)


def strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()


def extract_json(text: str) -> str:
    """Extract the first JSON object from text that may contain prose around it."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return text

# Agent Node (Orchestrator + ReAct)

def agent_node(state):

    current = state.get("agent_messages", [])

    if not current:
        today = date.today()
        cutoff = today - timedelta(days=90)
        print("Today and cutoff date")
        print(today, cutoff)
        system_msg = SystemMessage(content=ORCHESTRATOR_PROMPT.format(
            today=today.isoformat(),
            cutoff_date=cutoff.isoformat(),
        ))

        conversation = "\n".join(
            f"{m['role']}: {m['content']}"
            for m in state["messages"]
        )
        human_msg = HumanMessage(
            content=f"Conversation so far:\n{conversation}"
        )
        current = [system_msg, human_msg]

    response = llm_with_tools.invoke(current)
    new_messages = current + [response]

    if response.tool_calls:
        tool_names = [tc["name"] for tc in response.tool_calls]
        tool_inputs = [{tc["name"]: tc["args"]} for tc in response.tool_calls]
        log.info("[agent] Calling tools: %s", tool_names)
        audit_entry = {
            "step": "agent_tool_call",
            "label": "Agent Calling Tools",
            "tools_called": tool_names,
            "tool_inputs": tool_inputs,
        }
    else:
        log.info("[agent] Final answer reached — no more tool calls")
        audit_entry = {
            "step": "agent_final",
            "label": "Agent Reached Final Answer",
        }

    return {
        "agent_messages": new_messages,
        "audit_trail": state.get("audit_trail", []) + [audit_entry],
    }


# Tool Execution Node

def tool_execution_node(state):

    last_message = state["agent_messages"][-1]
    tool_results = []
    audit_results = []
    updated_claim = state.get("claim", {})

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        # claim_extractor: call implementation directly with injected state (bypasses schema validation)
        if tool_name == "claim_extractor":
            conversation = "\n".join(
                f"{m['role']}: {m['content']}"
                for m in state["messages"]
            )
            log.info("[tool_execution] claim_extractor — injecting conversation (%d messages) and current claim", len(state["messages"]))
            result = _run_extraction(
                conversation=conversation,
                current_claim=json.dumps(updated_claim),
            )
        else:
            log.info("[tool_execution] Running: %s | Args: %s", tool_name, tool_args)
            result = TOOLS_BY_NAME[tool_name].invoke(tool_args)

        result_str = json.dumps(result)

        log.info("[tool_execution] %s result: %s", tool_name, result_str)

        # Update claim state when claim_extractor runs
        if tool_name == "claim_extractor" and isinstance(result, dict):
            extracted = result.get("extracted_fields", {})
            updated_claim = {**updated_claim, **extracted}
            log.info("[tool_execution] Updated claim: %s", updated_claim)

        tool_results.append(
            ToolMessage(content=result_str, tool_call_id=tool_call["id"])
        )
        audit_results.append({
            "tool": tool_name,
            "args": {"note": "injected from state"} if tool_name == "claim_extractor" else tool_args,
            "result": result,
        })

    audit_entry = {
        "step": "tool_execution",
        "label": "Tool Execution",
        "results": audit_results,
    }

    return {
        "agent_messages": state["agent_messages"] + tool_results,
        "claim": updated_claim,
        "audit_trail": state.get("audit_trail", []) + [audit_entry],
    }



# Finalize Node

def finalize_node(state):

    last_message = state["agent_messages"][-1]

    content = last_message.content
    if isinstance(content, list):
        content = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )

    reply = extract_json(strip_json_fences(content))

    try:
        parsed = json.loads(reply)
        audit_decision = parsed.get("decision", "unknown")
        audit_reason = parsed.get("reason", "")
        audit_confidence = parsed.get("confidence", "")
        log.info("[finalize] Decision: %s | Confidence: %s", audit_decision, audit_confidence)
        log.info("[finalize] Reason: %s", audit_reason)
    except (json.JSONDecodeError, TypeError):
        audit_decision = "text_response"
        audit_reason = reply[:200]
        audit_confidence = ""
        log.info("[finalize] Plain text response: %s", audit_reason)

    audit_entry = {
        "step": "decision",
        "label": "Final Answer",
        "decision": audit_decision,
        "reason": audit_reason,
        "confidence": audit_confidence,
        "claim_evaluated": state.get("claim", {}),
    }

    updated_messages = state["messages"] + [
        {"role": "assistant", "content": reply}
    ]

    return {
        "final_answer": reply,
        "messages": updated_messages,
        "agent_messages": [],
        "audit_trail": state.get("audit_trail", []) + [audit_entry],
    }
