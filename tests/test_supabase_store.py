"""Integration test: the logic writes through to Supabase and loads back.

Skipped unless SUPABASE_URL is set. WIPES ALL DATA in the target project,
so point it only at the test project. Needs migrations 0001 and 0002.
"""

import os
from decimal import Decimal

import pytest

from payments.mock_data import BANKS, STATEMENT_DATE, SUPPLIERS
from payments.models import DocType, DocumentUpload, StatementEntry, Status
from payments.service import PaymentSystem
from payments.store import SupabaseStore

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "placeholder")

pytestmark = pytest.mark.skipif(not SUPABASE_URL, reason="SUPABASE_URL not set")


def _inv(supplier, amount, number, doc_type=DocType.TAX_INVOICE):
    return DocumentUpload(doc_type, supplier, Decimal(amount), number)


def _state(system):
    def key(objs, *fields):
        return sorted(tuple(str(getattr(o, f)) for f in fields) for o in objs)

    return {
        "documents": key(system.list_documents(), "id", "status", "linked_payment_id",
                         "requested_bank_code"),
        "payments": key(system.payments(), "id", "document_id", "bank_code", "amount",
                        "statement_line_id"),
        "lines": key(system.statement_lines(), "id", "status", "matched_payment_id",
                     "candidate_document_ids"),
        "alerts": key(system.alerts(), "id", "alert_type", "recipient", "resolved"),
        "aliases": sorted(system.aliases.items()),
    }


def test_state_survives_a_reload():
    store = SupabaseStore(SUPABASE_URL, SUPABASE_KEY)
    store.wipe()
    system = PaymentSystem(BANKS, SUPPLIERS, store=store)

    # A plain invoice, a payment demand, a duplicate upload, a wrong bank.
    plain = system.upload_document(_inv("Hooli Analytics", "100.10", "S-1"))
    system.approve(plain.id, "chase")
    demand = system.upload_document(_inv("Acme Cloud", "200.20", "S-2", DocType.PAYMENT_DEMAND))
    system.approve(demand.id, "chase")
    system.upload_document(_inv("Hooli Analytics", "100.10", "S-1"))
    wrong = system.upload_document(_inv("Tavor Translations", "300.30", "S-3"))
    assert system.approve(wrong.id, "chase") is None
    via_paypal = system.upload_document(_inv("Wayne Consulting", "400.40", "S-4"))
    system.approve(via_paypal.id, "chase")

    lines = system.ingest_statement("chase", [
        StatementEntry("Hooli Analytics", Decimal("100.10"), STATEMENT_DATE),
        StatementEntry("Acme Cloud", Decimal("200.20"), STATEMENT_DATE),
        StatementEntry("PAYPAL *WAYNE CONSULTING", Decimal("400.40"), STATEMENT_DATE),
        StatementEntry("Zoom Video", Decimal("149.90"), STATEMENT_DATE),
    ])
    assert [l.status for l in lines] == [
        Status.PAID, Status.MISSING_INVOICE, Status.NEEDS_REVIEW, Status.MISSING_INVOICE]

    # The bookkeeper confirms the PayPal line, the tax invoice for the demand
    # arrives, and the CFO decides on the wrong bank.
    system.confirm_match(lines[2].id, via_paypal.id)
    system.upload_document(_inv("Acme Cloud", "200.20", "S-5"))
    system.decide_wrong_bank(wrong.id, "leumi")

    reloaded = PaymentSystem(BANKS, SUPPLIERS, store=SupabaseStore(SUPABASE_URL, SUPABASE_KEY))
    assert _state(reloaded) == _state(system)
    assert [d.doc_number for d in reloaded.list_documents()] == \
        [d.doc_number for d in system.list_documents()]
