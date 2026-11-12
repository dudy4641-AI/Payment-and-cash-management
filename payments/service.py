"""Business-logic interface that the five metric tests call.

Stage 1 defines the interface only. Every method raises NotImplementedError;
the logic is built in stage 2a (documents, matching, alerts) and stage 3
(balances). See PLAN.md.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from .models import (
    Alert,
    Bank,
    Document,
    DocumentUpload,
    Payment,
    StatementEntry,
    StatementLine,
    Supplier,
)


class PaymentSystem:
    def __init__(self, banks: Iterable[Bank], suppliers: Iterable[Supplier]):
        self.banks = {b.code: b for b in banks}
        self.suppliers = {s.name: s for s in suppliers}

    # --- Documents ---------------------------------------------------------

    def upload_document(self, upload: DocumentUpload) -> Document:
        """Store an uploaded document and return it with its status."""
        raise NotImplementedError("stage 2a: upload_document")

    def list_documents(self) -> list[Document]:
        raise NotImplementedError("stage 2a: list_documents")

    def assign_budget_category(self, supplier_name: str, category: str) -> None:
        raise NotImplementedError("stage 2a: assign_budget_category")

    def approve(self, document_id: str, bank_code: str) -> Payment | None:
        """CFO approval. Returns the payment sent to the mock bank, or None if
        no payment was sent (blocked, alerted, or already covered)."""
        raise NotImplementedError("stage 2a: approve")

    # --- Bank statements and matching -------------------------------------

    def ingest_statement(
        self, bank_code: str, entries: Iterable[StatementEntry]
    ) -> list[StatementLine]:
        """Upload a mock statement; match each line to a payment or flag it."""
        raise NotImplementedError("stage 2a: ingest_statement")

    def payments(self) -> list[Payment]:
        raise NotImplementedError("stage 2a: payments")

    def alerts(self) -> list[Alert]:
        raise NotImplementedError("stage 2a: alerts")

    # --- Balances ----------------------------------------------------------

    def current_balance(self, bank_code: str) -> Decimal:
        raise NotImplementedError("stage 3: current_balance")

    def expected_balance(self, bank_code: str) -> Decimal:
        raise NotImplementedError("stage 3: expected_balance")
