from typing import Optional

from pydantic import BaseModel, Field


class Claim(BaseModel):
    travel_type: Optional[str] = Field(
        default=None,
        description="domestic or international"
    )

    expense_category: Optional[str] = Field(
        default=None,
        description="hotel, meal, taxi, flight, visa, internet, conference"
    )

    amount: Optional[float] = Field(
        default=None,
        description="expense amount in INR"
    )

    expense_date: Optional[str] = Field(
        default=None,
        description="date of expense in YYYY-MM-DD format"
    )

    vendor_name: Optional[str] = Field(
        default=None,
        description="name of the vendor or service provider"
    )

    business_purpose: Optional[str] = Field(
        default=None,
        description="reason for the business travel or expense"
    )

    receipt_available: Optional[bool] = Field(
        default=None,
        description="whether a receipt is attached"
    )