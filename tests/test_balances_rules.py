"""Balance rules beyond metric 5 (SPEC section 5, balances)."""

from datetime import date
from decimal import Decimal as D

from payments.models import DocType, DocumentUpload, StatementEntry

from .conftest import upload_and_approve

DAY = date(2026, 11, 12)
OPENING_CHASE = D("1200000.00")


def _inv(supplier, amount, number):
    return DocumentUpload(DocType.TAX_INVOICE, supplier, D(amount), number)


def test_line_without_invoice_still_reduces_current_balance(system):
    system.ingest_statement("chase", [StatementEntry("Zoom Video", D("149.90"), DAY)])
    assert system.current_balance("chase") == OPENING_CHASE - D("149.90")
    assert system.expected_balance("chase") == OPENING_CHASE - D("149.90")


def test_held_wrong_bank_payment_is_not_subtracted(system):
    _, payment = upload_and_approve(system, _inv("Tavor Translations", "500.00", "H-1"), "chase")
    assert payment is None
    assert system.expected_balance("chase") == OPENING_CHASE


def test_line_under_review_is_not_counted_twice(system):
    # Two approved payments of the same amount, one bank line: one of them
    # left the bank, the other is still pending.
    upload_and_approve(system, _inv("Initrode Inc", "2450.00", "R-1"), "chase")
    upload_and_approve(system, _inv("Initrode Inc", "2450.00", "R-2"), "chase")
    [line] = system.ingest_statement("chase", [StatementEntry("Initrode Inc", D("2450.00"), DAY)])

    current = OPENING_CHASE - D("2450.00")
    assert system.current_balance("chase") == current
    assert system.expected_balance("chase") == current - D("2450.00")

    # The bookkeeper confirms which one: the numbers do not move.
    docs = {d.doc_number: d for d in system.list_documents()}
    system.confirm_match(line.id, docs["R-1"].id)
    assert system.current_balance("chase") == current
    assert system.expected_balance("chase") == current - D("2450.00")


def test_banks_do_not_affect_each_other(system):
    upload_and_approve(system, _inv("Shapira Legal", "1000.00", "L-1"), "leumi")
    assert system.current_balance("chase") == OPENING_CHASE
    assert system.expected_balance("chase") == OPENING_CHASE
    assert system.expected_balance("leumi") == D("250000.00") - D("1000.00")
