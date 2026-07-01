import json

from langchain.tools import tool

from utils.llm import llm
from models.claim import Claim
from prompts.prompts import CLAIM_EXTRACTION_PROMPT


_structured_llm = llm.with_structured_output(Claim)

REQUIRED_FIELDS = [
    "travel_type",
    "expense_category",
    "amount",
    "expense_date",
    "vendor_name",
    "business_purpose",
    "receipt_available",
]


def _run_extraction(conversation: str, current_claim: str = "{}") -> dict:
    """Actual extraction logic — called by tool_execution_node with injected state."""
    try:
        existing = json.loads(current_claim) if current_claim else {}
    except json.JSONDecodeError:
        existing = {}

    prompt = CLAIM_EXTRACTION_PROMPT.format(
        conversation=conversation,
        claim=json.dumps(existing, indent=2)
    )

    response = _structured_llm.invoke(prompt)
    updated = response.model_dump(exclude_none=True)
    merged = {**existing, **updated}

    missing = []
    for field in REQUIRED_FIELDS:
        if field not in merged or merged[field] in ["", None]:
            missing.append(field)
            continue
        if field == "amount" and (
            not isinstance(merged[field], (int, float)) or merged[field] <= 0
        ):
            missing.append(field)

    return {
        "extracted_fields": merged,
        "missing_fields": missing,
        "is_complete": len(missing) == 0,
    }


@tool
def claim_extractor() -> dict:
    """
    Extract and validate reimbursement claim fields from the conversation history.
    Returns extracted fields, missing required fields, and whether the claim is complete.
    Always call this first when the user is submitting or updating a reimbursement claim.
    No arguments needed — context is injected automatically from the conversation.
    """
    # This path is never reached — tool_execution_node intercepts and calls _run_extraction directly
    return {"error": "Direct invocation not supported; context injection required"}
