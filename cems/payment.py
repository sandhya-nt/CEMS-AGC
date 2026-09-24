"""Payment provider abstraction for CEMS event payments.

This module defines a provider interface that separates payment processing
logic from the application. A real payment gateway (Razorpay, Stripe, etc.)
can be integrated by implementing the :class:`PaymentProvider` interface.

Key design principles:

- **No fake successes**: A provider must never report a successful payment
  unless it actually processed one through the gateway. The mock provider
  is explicitly marked as ``provider="mock"`` and is intended only for
  development and testing.
- **Unavailable state**: When no payment provider is configured, the
  :class:`UnavailablePaymentProvider` returns a clear ``unavailable``
  status instead of pretending payment succeeded.
- **Consistent interface**: All providers share the same interface so
  routes and services interact with payments uniformly regardless of
  the underlying gateway.
"""

import os
import secrets
from abc import ABC, abstractmethod
from datetime import datetime

from .extensions import db


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def get_payment_provider():
    """Return the active :class:`PaymentProvider` based on configuration.

    Reads ``PAYMENT_PROVIDER`` from the environment:
      - ``"razorpay"`` → :class:`RazorpayProvider` (stub, raises until configured)
      - ``"mock"`` → :class:`MockPaymentProvider` (development only)
      - Any other / unset value → :class:`UnavailablePaymentProvider`
    """
    provider_name = os.getenv("PAYMENT_PROVIDER", "none").lower()
    if provider_name == "razorpay":
        return RazorpayProvider()
    if provider_name == "mock":
        return MockPaymentProvider()
    return UnavailablePaymentProvider()


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------

class PaymentProvider(ABC):
    """Abstract base for all payment providers.

    Subclasses must implement :meth:`initiate_payment` and :meth:`verify_payment`.
    The :meth:`is_available` method controls whether the UI presents payment
    as an actionable option.
    """

    @abstractmethod
    def initiate_payment(self, registration, payment_method: str):
        """Initiate a payment for the given registration.

        Returns a dict with at minimum ``{"status": "ok", "reference": "..."}``.
        For providers that redirect externally (e.g. Razorpay), the dict may
        also include ``{"redirect_url": "..."}``.

        Raises :class:`PaymentError` on failure.
        """
        ...

    @abstractmethod
    def verify_payment(self, transaction_id: str):
        """Verify / confirm a payment by its transaction reference.

        Returns a dict with ``{"status": "ok", "reference": "..."}`` on success.

        Raises :class:`PaymentError` on failure.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` when this provider can process real payments."""
        ...

    @abstractmethod
    def display_name(self) -> str:
        """Human-readable provider name shown in the UI."""
        ...


class PaymentError(Exception):
    """Raised when a payment operation cannot be completed."""
    pass


# ---------------------------------------------------------------------------
# Unavailable provider — clearly signals that payment is not possible
# ---------------------------------------------------------------------------

class UnavailablePaymentProvider(PaymentProvider):
    """Used when no real payment provider is configured.

    This provider never processes payments. It returns a clear
    ``unavailable`` status so the application can display an appropriate
    message instead of pretending payment succeeded.
    """

    def is_available(self) -> bool:
        return False

    def display_name(self) -> str:
        return "Not Configured"

    def initiate_payment(self, registration, payment_method: str):
        raise PaymentError(
            "Payment is currently unavailable. No payment provider is configured. "
            "Contact the event organizer for alternative arrangements."
        )

    def verify_payment(self, transaction_id: str):
        raise PaymentError(
            "Payment is currently unavailable. No payment provider is configured."
        )


# ---------------------------------------------------------------------------
# Mock provider — development/testing only
# ---------------------------------------------------------------------------

class MockPaymentProvider(PaymentProvider):
    """Development-only provider that records a simulated transaction.

    This provider MUST NOT be used in production. Every payment it records
    is tagged with ``provider="mock"`` so it is clearly distinguishable
    from real payment records.
    """

    def is_available(self) -> bool:
        return True

    def display_name(self) -> str:
        return "Demo (Mock)"

    def initiate_payment(self, registration, payment_method: str):
        if not registration or not registration.event:
            raise PaymentError("Invalid registration.")
        if registration.event.fee <= 0:
            raise PaymentError("This event is free.")

        reference = "MOCK-" + secrets.token_urlsafe(16).upper()
        transaction_id = "TXN-MOCK-" + secrets.token_hex(8).upper()

        return {
            "status": "ok",
            "reference": reference,
            "transaction_id": transaction_id,
            "payment_method": payment_method,
            "amount": float(registration.event.fee),
            "provider": "mock",
            "demo_mode": True,
        }

    def verify_payment(self, transaction_id: str):
        raise PaymentError(
            "Mock payments are one-step. The payment record is created directly. "
            "Use the payment status shown on the ticket/registration page."
        )


# ---------------------------------------------------------------------------
# Razorpay provider — real gateway stub (raises until configured)
# ---------------------------------------------------------------------------

class RazorpayProvider(PaymentProvider):
    """Real Razorpay gateway integration (skeleton).

    To activate: set ``PAYMENT_PROVIDER=razorpay`` and provide
    ``RAZERPAY_KEY_ID`` and ``RAZERPAY_SECRET`` environment variables.

    Until properly configured, every method raises :class:`PaymentError`
    so the application never pretends a real payment succeeded.
    """

    def __init__(self):
        self._key_id = os.getenv("RAZERPAY_KEY_ID", "")
        self._secret = os.getenv("RAZERPAY_SECRET", "")
        self._enabled = bool(self._key_id and self._secret)

    def _require_config(self):
        if not self._enabled:
            raise PaymentError(
                "Razorpay is not configured. Set RAZERPAY_KEY_ID and "
                "RAZERPAY_SECRET environment variables to enable payments."
            )

    def is_available(self) -> bool:
        return self._enabled

    def display_name(self) -> str:
        return "Razorpay"

    def initiate_payment(self, registration, payment_method: str):
        self._require_config()
        # ---- Real integration would go here ----
        # from razorpay import Client
        # client = Client((self._key_id, self._secret))
        # order = client.order.create({...})
        # return {"status": "ok", "reference": order["id"], "redirect_url": ...}
        raise PaymentError("Razorpay integration is not yet implemented.")

    def verify_payment(self, transaction_id: str):
        self._require_config()
        # ---- Real integration would go here ----
        # from razorpay import Client
        # client = Client((self._key_id, self._secret))
        # payment = client.payment.fetch(transaction_id)
        # return {"status": "ok" if payment["status"] == "captured" else "failed", ...}
        raise PaymentError("Razorpay integration is not yet implemented.")
