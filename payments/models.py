"""Data model for the supplier payments system.

Mirrors the Supabase schema in supabase/migrations/0001_init.sql.
Amounts are always Decimal (USD, two decimal places), never float.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum


class Status(str, Enum):
    """Closed list of statuses (SPEC section 5). No other value is allowed."""

    UPLOADED = "הועלתה"
    PENDING_APPROVAL = "ממתינה לאישור"
    APPROVED = "אושרה"
    PAID = "שולמה"
    MISSING_INVOICE = "חסרה חשבונית"
    NEEDS_REVIEW = "דורשת בירור"


class DocType(str, Enum):
    PAYMENT_DEMAND = "דרישת תשלום"
    TAX_INVOICE = "חשבונית מס"


class Entity(str, Enum):
    IL = "ישראל"
    US = 'ארה"ב'


class BankKind(str, Enum):
    BANK = "bank"
    CARD_PLATFORM = "card_platform"


class AlertType(str, Enum):
    DUPLICATE = "כפל תשלום"
    WRONG_BANK = "בנק לא נכון"
    UNCERTAIN_MATCH = "מקרה ספק"


class Recipient(str, Enum):
    CFO = "סמנכ\"ל כספים"
    BOOKKEEPER = "מנהלת חשבונות"


# Who handles each alert (SPEC section 5).
ALERT_RECIPIENT = {
    AlertType.DUPLICATE: Recipient.BOOKKEEPER,
    AlertType.WRONG_BANK: Recipient.CFO,
    AlertType.UNCERTAIN_MATCH: Recipient.BOOKKEEPER,
}


@dataclass(frozen=True)
class Bank:
    code: str
    name: str
    entity: Entity
    kind: BankKind
    opening_balance: Decimal


@dataclass(frozen=True)
class Supplier:
    name: str
    entity: Entity
    budget_category: str | None  # None means a new supplier


# --- Inputs: what a user uploads -------------------------------------------


@dataclass(frozen=True)
class DocumentUpload:
    doc_type: DocType
    supplier_name: str
    amount: Decimal
    doc_number: str


@dataclass(frozen=True)
class StatementEntry:
    """One line of an uploaded (mock) bank statement: a debit to a payee."""

    payee_name: str
    amount: Decimal
    value_date: date


# --- Records the system keeps ----------------------------------------------


@dataclass
class Document:
    id: str
    doc_type: DocType
    supplier_name: str
    amount: Decimal
    doc_number: str
    status: Status
    linked_payment_id: str | None = None


@dataclass
class Payment:
    id: str
    document_id: str
    bank_code: str
    supplier_name: str
    amount: Decimal
    statement_line_id: str | None = None  # set once it appears in a statement


@dataclass
class StatementLine:
    id: str
    bank_code: str
    payee_name: str
    amount: Decimal
    value_date: date
    status: Status | None = None
    matched_payment_id: str | None = None


@dataclass
class Alert:
    id: str
    alert_type: AlertType
    recipient: Recipient
    document_id: str | None = None
    statement_line_id: str | None = None
    message: str = ""
