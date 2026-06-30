import json
import logging
from datetime import date, timedelta

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from utils.llm import llm
from models.claim import Claim
from prompts.prompts import (
    CLAIM_EXTRACTION_PROMPT,
    ASK_MISSING_FIELDS_PROMPT,
    AGENT_SYSTEM_PROMPT,
)
from tools.policy_lookup import policy_lookup
from tools.limit_checker import limit_checker
from tools.receipt_validator import receipt_validator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("travel_agent")


structured_llm = llm.with_structured_output(Claim)

TOOLS = [policy_lookup, limit_checker, receipt_validator]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
llm_with_tools = llm.bind_tools(TOOLS)


def strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()


REQUIRED_FIELDS = [
    "travel_type",
    "expense_category",
    "amount",
    "expense_date",
    "vendor_name",
    "business_purpose",
    "receipt_available",
]


# ----------------------------------------------------------
# Extract Claim
# ----------------------------------------------------------

def extract_claim_node(state):

    current_claim = state.get("claim", {})

    conversation = "\n".join(
        f"{m['role']}: {m['content']}"
        for m in state["messages"]
    )

    prompt = CLAIM_EXTRACTION_PROMPT.format(
        conversation=conversation,
        claim=json.dumps(current_claim, indent=2)
    )

    response = structured_llm.invoke(prompt)
    updated_claim = response.model_dump(exclude_none=True)
    merged_claim = {**current_claim, **updated_claim}

    newly_extracted = {
        k: v for k, v in updated_claim.items()
        if k not in current_claim or current_claim[k] != v
    }

    log.info("[extract_claim] Newly extracted: %s", newly_extracted)
    log.info("[extract_claim] Full claim: %s", merged_claim)

    audit_entry = {
        "step": "extract_claim",
        "label": "Claim Extraction",
        "newly_extracted_fields": newly_extracted,
        "full_claim": merged_claim,
    }

    return {
        "claim": merged_claim,
        "agent_messages": [],           # reset ReAct loop for this turn
        "audit_trail": state.get("audit_trail", []) + [audit_entry],
    }


# ----------------------------------------------------------
# Validate Claim
# ----------------------------------------------------------

def validate_claim_node(state):

    claim = state["claim"]
    missing = []

    for field in REQUIRED_FIELDS:

        if field not in claim or claim[field] in ["", None]:
            missing.append(field)
            continue

        if field == "amount" and (
            not isinstance(claim[field], (int, float)) or claim[field] <= 0
        ):
            missing.append(field)

    if missing:
        log.warning("[validate_claim] Status: incomplete | Missing: %s", missing)
    else:
        log.info("[validate_claim] Status: complete — all required fields present")

    audit_entry = {
        "step": "validate_claim",
        "label": "Claim Validation",
        "status": "incomplete" if missing else "complete",
        "missing_fields": missing,
    }

    return {
        "missing_fields": missing,
        "audit_trail": state.get("audit_trail", []) + [audit_entry],
    }


# ----------------------------------------------------------
# Ask Missing Fields
# ----------------------------------------------------------

def ask_missing_fields_node(state):

    prompt = ASK_MISSING_FIELDS_PROMPT.format(
        missing_fields="\n".join(state["missing_fields"])
    )

    response = llm.invoke(prompt)
    reply = response.content

    updated_messages = state["messages"] + [
        {"role": "assistant", "content": reply}
    ]

    log.info("[ask_missing_fields] Requesting fields: %s", state["missing_fields"])

    audit_entry = {
        "step": "ask_missing_fields",
        "label": "Requested Missing Information",
        "fields_requested": state["missing_fields"],
        "routed_to": "END (awaiting user response)",
    }

    return {
        "final_answer": reply,
        "messages": updated_messages,
        "audit_trail": state.get("audit_trail", []) + [audit_entry],
    }


# ----------------------------------------------------------
# Agent Node (ReAct)
# ----------------------------------------------------------

def agent_node(state):

    current = state.get("agent_messages", [])

    if not current:
        today = date.today()
        cutoff = today - timedelta(days=90)

        system_msg = SystemMessage(content=AGENT_SYSTEM_PROMPT.format(
            today=today.isoformat(),
            cutoff_date=cutoff.isoformat(),
        ))
        human_msg = HumanMessage(
            content=f"Evaluate this reimbursement claim:\n{json.dumps(state['claim'], indent=2)}"
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
        log.info("[agent] Final decision reached — no more tool calls")
        audit_entry = {
            "step": "agent_final",
            "label": "Agent Reached Final Decision",
        }

    return {
        "agent_messages": new_messages,
        "audit_trail": state.get("audit_trail", []) + [audit_entry],
    }


# ----------------------------------------------------------
# Tool Execution Node
# ----------------------------------------------------------

def tool_execution_node(state):

    last_message = state["agent_messages"][-1]
    tool_results = []
    audit_results = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        log.info("[tool_execution] Running: %s | Args: %s", tool_name, tool_args)

        result = TOOLS_BY_NAME[tool_name].invoke(tool_args)
        result_str = json.dumps(result)

        log.info("[tool_execution] Result: %s", result_str)

        tool_results.append(
            ToolMessage(content=result_str, tool_call_id=tool_call["id"])
        )
        audit_results.append({
            "tool": tool_name,
            "args": tool_args,
            "result": result,
        })

    audit_entry = {
        "step": "tool_execution",
        "label": "Tool Execution",
        "results": audit_results,
    }

    return {
        "agent_messages": state["agent_messages"] + tool_results,
        "audit_trail": state.get("audit_trail", []) + [audit_entry],
    }


# ----------------------------------------------------------
# Finalize Node
# ----------------------------------------------------------

def finalize_node(state):

    last_message = state["agent_messages"][-1]

    content = last_message.content
    if isinstance(content, list):
        content = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )

    reply = strip_json_fences(content)

    try:
        parsed = json.loads(reply)
        audit_decision = parsed.get("decision", "unknown")
        audit_reason = parsed.get("reason", "")
        audit_confidence = parsed.get("confidence", "")
    except (json.JSONDecodeError, TypeError):
        audit_decision = "unparseable"
        audit_reason = reply[:200]
        audit_confidence = ""

    log.info("[finalize] Decision: %s | Confidence: %s", audit_decision, audit_confidence)
    log.info("[finalize] Reason: %s", audit_reason)

    audit_entry = {
        "step": "decision",
        "label": "Final Decision",
        "tool_called": "LLM (Gemini)",
        "decision": audit_decision,
        "reason": audit_reason,
        "confidence": audit_confidence,
        "claim_evaluated": state["claim"],
    }

    updated_messages = state["messages"] + [
        {"role": "assistant", "content": reply}
    ]

    return {
        "final_answer": reply,
        "messages": updated_messages,
        "agent_messages": [],           # reset for next turn
        "audit_trail": state.get("audit_trail", []) + [audit_entry],
    }
