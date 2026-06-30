from langchain.tools import tool


LIMITS = {
    ("hotel", "domestic"):         5000,
    ("hotel", "international"):    12000,
    ("meal", "domestic"):          1500,
    ("meal", "international"):     1500,
    ("taxi", "domestic"):          2000,
    ("taxi", "international"):     2000,
    ("internet", "domestic"):      500,
    ("internet", "international"): 500,
}


@tool
def limit_checker(expense_category: str, travel_type: str, amount: float) -> dict:
    """
    Check if the claimed amount is within the policy limit for the given
    expense category and travel type. Returns the approved amount and deduction.
    Use this for hotel, meal, taxi, and internet expense categories.
    """
    key = (expense_category.lower(), travel_type.lower())
    limit = LIMITS.get(key)

    if limit is None:
        return {
            "status": "no_limit_defined",
            "message": f"No fixed limit defined for {expense_category} ({travel_type}). Refer to policy document.",
            "approved": amount,
            "deducted": 0,
        }

    if amount <= limit:
        return {
            "status": "within_limit",
            "limit": limit,
            "approved": amount,
            "deducted": 0,
        }

    return {
        "status": "exceeds_limit",
        "limit": limit,
        "approved": limit,
        "deducted": round(amount - limit, 2),
    }
