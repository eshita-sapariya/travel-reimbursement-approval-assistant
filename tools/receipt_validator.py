from langchain.tools import tool


RECEIPT_REQUIRED = {
    "hotel", "meal", "taxi", "flight",
    "train", "bus", "visa", "conference",
}

REQUIRED_DOCUMENT_NAMES = {
    "hotel":      "Hotel receipt",
    "meal":       "Meal receipt",
    "taxi":       "Ride receipt",
    "flight":     "Flight invoice and booking confirmation",
    "train":      "Train ticket",
    "bus":        "Bus ticket",
    "visa":       "Visa payment receipt",
    "conference": "Conference invoice",
}


@tool
def receipt_validator(expense_category: str, receipt_available: bool) -> dict:
    """
    Check whether the receipt requirement is satisfied for the given expense category.
    Returns whether the claim can proceed or must be routed to MANUAL_REVIEW.
    Always call this before making a final decision.
    """
    category = expense_category.lower()
    required = category in RECEIPT_REQUIRED

    if not required:
        return {
            "status": "not_required",
            "can_proceed": True,
            "required_document": None,
        }

    if receipt_available:
        return {
            "status": "receipt_present",
            "can_proceed": True,
            "required_document": REQUIRED_DOCUMENT_NAMES.get(category, "Receipt"),
        }

    return {
        "status": "receipt_missing",
        "can_proceed": False,
        "required_document": REQUIRED_DOCUMENT_NAMES.get(category, "Receipt"),
        "action": "Route to MANUAL_REVIEW — receipt is mandatory for this category.",
    }
