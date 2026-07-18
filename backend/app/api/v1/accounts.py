"""Account routes are exposed under the customer aggregate in customers.py."""

from app.api.v1.customers import customer_accounts

__all__ = ["customer_accounts"]
