"""Business logic for documents, approvals, matching and alerts (SPEC 4-5).

Balances (current and expected) belong to stage 3 and are not built yet.
"""

from __future__ import annotations

import copy
import csv
import io
import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from .models import (
    ALERT_RECIPIENT,
    Alert,
    AlertType,
    Bank,
    DocType,
    Document,
    DocumentUpload,
    Entity,
    Payment,
    StatementEntry,
    StatementLine,
    Status,
    Supplier,
)
from .names import NameRelation, clean_name, relation
from .store import InMemoryStore, Store


class ApprovalBlocked(Exception):
    """Approval cannot happen until something is fixed (e.g. budget category)."""


def _new_id() -> str:
    return str(uuid.uuid4())


class PaymentSystem:
    def __init__(
        self,
        banks: Iterable[Bank],
        suppliers: Iterable[Supplier],
        store: Store | None = None,
    ):
        self.store: Store = store or InMemoryStore()
        snap = self.store.load()
        self.banks = {b.code: b for b in snap.banks}
        self.suppliers = {s.name: s for s in snap.suppliers}
        self.aliases: dict[str, str] = dict(snap.aliases)  # cleaned name -> supplier
        self._docs = {d.id: d for d in snap.documents}
        self._payments = {p.id: p for p in snap.payments}
        self._lines = {l.id: l for l in snap.lines}
        self._alerts = {a.id: a for a in snap.alerts}
        # Seed the company setup on first run; stored values win afterwards.
        for b in banks:
            if b.code not in self.banks:
                self.banks[b.code] = b
                self.store.save(b)
        for s in suppliers:
            if s.name not in self.suppliers:
                self.suppliers[s.name] = s
                self.store.save(s)

    # --- Read access (copies, so callers cannot change state by accident) ---

    def list_documents(self) -> list[Document]:
        return [copy.deepcopy(d) for d in self._docs.values()]

    def payments(self) -> list[Payment]:
        return [copy.deepcopy(p) for p in self._payments.values()]

    def statement_lines(self) -> list[StatementLine]:
        return [copy.deepcopy(l) for l in self._lines.values()]

    def alerts(self, include_resolved: bool = True) -> list[Alert]:
        return [copy.deepcopy(a) for a in self._alerts.values()
                if include_resolved or not a.resolved]

    # --- Suppliers ---------------------------------------------------------

    def add_supplier(self, name: str, entity: Entity, budget_category: str | None = None) -> None:
        if name in self.suppliers:
            raise ValueError(f"supplier already exists: {name}")
        supplier = Supplier(name, entity, budget_category)
        self.suppliers[name] = supplier
        self.store.save(supplier)

    def assign_budget_category(self, supplier_name: str, category: str) -> None:
        old = self.suppliers[supplier_name]
        supplier = Supplier(old.name, old.entity, category)
        self.suppliers[supplier_name] = supplier
        self.store.save(supplier)

    # --- Documents ---------------------------------------------------------

    def upload_document(self, upload: DocumentUpload) -> Document:
        if upload.supplier_name not in self.suppliers:
            raise ValueError(f"unknown supplier, add it first: {upload.supplier_name}")
        doc = Document(
            id=_new_id(),
            doc_type=upload.doc_type,
            supplier_name=upload.supplier_name,
            amount=upload.amount,
            doc_number=upload.doc_number,
            status=Status.PENDING_APPROVAL,
        )

        if self._is_duplicate_upload(doc):
            doc.status = Status.NEEDS_REVIEW
            self._save(doc)
            self._alert(AlertType.DUPLICATE, document_id=doc.id,
                        message=f"המסמך {doc.doc_number} של {doc.supplier_name} כבר הועלה")
            return copy.deepcopy(doc)

        if doc.doc_type == DocType.TAX_INVOICE:
            demand = self._open_demand_for(doc)
            if demand is not None:
                self._close_demand(demand, doc)
                return copy.deepcopy(doc)

        self._save(doc)
        return copy.deepcopy(doc)

    def _is_duplicate_upload(self, doc: Document) -> bool:
        key = (doc.supplier_name, doc.doc_type, doc.doc_number)
        return any((d.supplier_name, d.doc_type, d.doc_number) == key for d in self._docs.values())

    def _open_demand_for(self, invoice: Document) -> Document | None:
        """A paid or approved payment demand, same supplier and amount, with no
        tax invoice yet. A tax invoice for it closes it instead of paying again."""
        linked = {d.linked_payment_id for d in self._docs.values() if d.linked_payment_id}
        for d in self._docs.values():
            if (d.doc_type == DocType.PAYMENT_DEMAND
                    and d.supplier_name == invoice.supplier_name
                    and d.amount == invoice.amount):
                payment = self._payment_for(d.id)
                if payment is not None and payment.id not in linked:
                    return d
        return None

    def _close_demand(self, demand: Document, invoice: Document) -> None:
        payment = self._payment_for(demand.id)
        assert payment is not None
        invoice.linked_payment_id = payment.id
        if payment.statement_line_id is not None:  # already left the bank
            invoice.status = Status.PAID
            demand.status = Status.PAID
            self._save(demand)
        else:
            invoice.status = Status.APPROVED
        self._save(invoice)

    def _payment_for(self, document_id: str) -> Payment | None:
        return next((p for p in self._payments.values() if p.document_id == document_id), None)

    # --- Approval ----------------------------------------------------------

    def approve(self, document_id: str, bank_code: str) -> Payment | None:
        """CFO approval. Returns the payment sent to the mock bank, or None if
        nothing was sent: the document is not waiting for approval (duplicate,
        already covered) or a wrong-bank alert now waits for the CFO.
        Raises ApprovalBlocked for a new supplier with no budget category."""
        doc = self._docs[document_id]
        if doc.status != Status.PENDING_APPROVAL:
            return None
        supplier = self.suppliers[doc.supplier_name]
        if not supplier.budget_category:
            raise ApprovalBlocked(f"ספק חדש: חובה לשייך סעיף תקציבי ל-{supplier.name} לפני האישור")
        bank = self.banks[bank_code]
        if bank.entity != supplier.entity:
            doc.status = Status.NEEDS_REVIEW
            doc.requested_bank_code = bank_code
            self._save(doc)
            self._alert(AlertType.WRONG_BANK, document_id=doc.id,
                        message=f"{supplier.name} שייך לישות {supplier.entity.value}, "
                                f"והבנק שנבחר, {bank.name}, שייך לישות {bank.entity.value}")
            return None
        return self._send_payment(doc, bank_code)

    def decide_wrong_bank(self, document_id: str, bank_code: str) -> Payment:
        """The CFO's decision on a wrong-bank alert: pay from `bank_code`, which
        may be the bank first chosen or another one."""
        doc = self._docs[document_id]
        alert = next(a for a in self._alerts.values()
                     if a.document_id == document_id and a.alert_type == AlertType.WRONG_BANK
                     and not a.resolved)
        alert.resolved = True
        self.store.save(alert)
        doc.requested_bank_code = None
        return self._send_payment(doc, bank_code)

    def _send_payment(self, doc: Document, bank_code: str) -> Payment:
        payment = Payment(_new_id(), doc.id, bank_code, doc.supplier_name, doc.amount)
        self._payments[payment.id] = payment
        self.store.save(payment)
        doc.status = Status.APPROVED
        self._save(doc)
        return copy.deepcopy(payment)

    # --- Bank statements and matching -------------------------------------

    def ingest_statement(
        self, bank_code: str, entries: Iterable[StatementEntry]
    ) -> list[StatementLine]:
        """Upload a mock statement. Each line is matched to an open payment,
        sent for review, or flagged as missing an invoice (SPEC section 5)."""
        lines = [StatementLine(_new_id(), bank_code, e.payee_name, e.amount, e.value_date)
                 for e in entries]

        # Work out each line's candidate payments before matching anything, so
        # lines in the same statement are judged together.
        plans = [self._candidates(line) for line in lines]
        groups: dict[frozenset[str], list[int]] = defaultdict(list)
        for i, (_, cands) in enumerate(plans):
            if cands:
                groups[frozenset(p.id for p in cands)].append(i)

        for i, line in enumerate(lines):
            rel, cands = plans[i]
            if not cands:
                line.status = Status.MISSING_INVOICE
                self._save_line(line)
                continue
            group = groups[frozenset(p.id for p in cands)]
            if rel == NameRelation.SAME and len(group) == len(cands):
                # Same supplier and amount, as many payments as lines: pair in order.
                self._match(line, cands[group.index(i)])
            elif rel == NameRelation.STARTS_WITH and len(cands) == 1 and len(group) == 1:
                self._match(line, cands[0])
            else:
                self._send_for_review(line, cands, rel)
        return [copy.deepcopy(l) for l in lines]

    def _candidates(self, line: StatementLine) -> tuple[NameRelation | None, list[Payment]]:
        """Open payments from this bank with the same amount, whose supplier
        name relates to the line's payee. Only the strongest relation counts."""
        alias_of = self.aliases.get(clean_name(line.payee_name))
        found: dict[NameRelation, list[Payment]] = defaultdict(list)
        for p in self._payments.values():
            if (p.statement_line_id is not None or p.bank_code != line.bank_code
                    or p.amount != line.amount):
                continue
            rel = NameRelation.SAME if alias_of == p.supplier_name \
                else relation(line.payee_name, p.supplier_name)
            if rel is not None:
                found[rel].append(p)
        for rel in (NameRelation.SAME, NameRelation.STARTS_WITH, NameRelation.AFTER_OTHER_TEXT):
            if found[rel]:
                return rel, found[rel]
        return None, []

    def _match(self, line: StatementLine, payment: Payment) -> None:
        payment = self._payments[payment.id]
        line.matched_payment_id = payment.id
        doc = self._docs[payment.document_id]
        if doc.doc_type == DocType.PAYMENT_DEMAND and not self._has_tax_invoice(payment.id):
            doc.status = Status.MISSING_INVOICE  # paid, but the tax invoice is missing
        else:
            doc.status = Status.PAID
            for inv in self._docs.values():
                if inv.linked_payment_id == payment.id:
                    inv.status = Status.PAID
                    self._save(inv)
        line.status = doc.status
        self._save_line(line)
        payment.statement_line_id = line.id
        self.store.save(payment)
        self._save(doc)

    def _has_tax_invoice(self, payment_id: str) -> bool:
        return any(d.linked_payment_id == payment_id for d in self._docs.values())

    def _send_for_review(self, line: StatementLine, cands: list[Payment],
                         rel: NameRelation | None) -> None:
        line.status = Status.NEEDS_REVIEW
        line.candidate_document_ids = [p.document_id for p in cands]
        self._save_line(line)
        for p in cands:
            doc = self._docs[p.document_id]
            doc.status = Status.NEEDS_REVIEW
            self._save(doc)
        reason = {
            NameRelation.SAME: "יותר מתשלום מאושר אחד או יותר מתנועה אחת לאותו ספק ולאותו סכום",
            NameRelation.STARTS_WITH: "השם מתחיל בשם הספק, אבל יש יותר מתשלום מאושר אחד שמתאים",
            NameRelation.AFTER_OTHER_TEXT: "שם הספק מופיע אחרי טקסט אחר בתנועה",
        }[rel]
        self._alert(AlertType.UNCERTAIN_MATCH, statement_line_id=line.id,
                    message=f"{line.payee_name} {line.amount}: {reason}")

    def confirm_match(self, statement_line_id: str, document_id: str) -> None:
        """The bookkeeper confirms which document a doubtful line belongs to.
        If the bank name differs from the supplier name after cleaning, it is
        saved as an extra name of the supplier and matched automatically later."""
        line = self._lines[statement_line_id]
        if line.status != Status.NEEDS_REVIEW or document_id not in line.candidate_document_ids:
            raise ValueError("this document is not a candidate of a line under review")
        payment = self._payment_for(document_id)
        assert payment is not None and payment.statement_line_id is None

        others = [d for d in line.candidate_document_ids if d != document_id]
        line.candidate_document_ids = []
        self._match(line, payment)
        for doc_id in others:  # back to waiting for their own bank line
            doc = self._docs[doc_id]
            if doc.status == Status.NEEDS_REVIEW:
                doc.status = Status.APPROVED
                self._save(doc)

        supplier = payment.supplier_name
        alias = clean_name(line.payee_name)
        if alias != clean_name(supplier) and alias not in self.aliases:
            self.aliases[alias] = supplier
            self.store.save_alias(alias, supplier)

        for a in self._alerts.values():
            if a.statement_line_id == line.id and not a.resolved:
                a.resolved = True
                self.store.save(a)

    # --- Export ------------------------------------------------------------

    def export_transactions_csv(self) -> str:
        """All bank statement lines, with what they were matched to, for the
        bookkeeper to check against the books."""
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["bank", "date", "payee", "amount", "status",
                         "document_number", "document_type", "supplier", "budget_category"])
        for line in self._lines.values():
            doc = supplier = None
            if line.matched_payment_id:
                doc = self._docs[self._payments[line.matched_payment_id].document_id]
                supplier = self.suppliers[doc.supplier_name]
            writer.writerow([
                self.banks[line.bank_code].name,
                line.value_date.isoformat(),
                line.payee_name,
                f"{line.amount:.2f}",
                line.status.value if line.status else "",
                doc.doc_number if doc else "",
                doc.doc_type.value if doc else "",
                supplier.name if supplier else "",
                supplier.budget_category or "" if supplier else "",
            ])
        return out.getvalue()

    # --- Balances (stage 3) ------------------------------------------------

    def current_balance(self, bank_code: str) -> Decimal:
        raise NotImplementedError("stage 3: current_balance")

    def expected_balance(self, bank_code: str) -> Decimal:
        raise NotImplementedError("stage 3: expected_balance")

    # --- Helpers -----------------------------------------------------------

    def _save(self, doc: Document) -> None:
        self._docs[doc.id] = doc
        self.store.save(doc)

    def _save_line(self, line: StatementLine) -> None:
        self._lines[line.id] = line
        self.store.save(line)

    def _alert(self, alert_type: AlertType, *, document_id: str | None = None,
               statement_line_id: str | None = None, message: str = "") -> None:
        alert = Alert(_new_id(), alert_type, ALERT_RECIPIENT[alert_type],
                      document_id=document_id, statement_line_id=statement_line_id,
                      message=message)
        self._alerts[alert.id] = alert
        self.store.save(alert)
