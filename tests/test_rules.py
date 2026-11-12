"""Rules from SPEC section 5 that are not covered by a single metric."""

import csv
import io
from decimal import Decimal

import pytest

from payments.mock_data import ALIAS_CASE, correct_bank, matching_scenario
from payments.models import AlertType, DocType, DocumentUpload, Entity, Status
from payments.names import NameRelation, clean_name, relation
from payments.service import ApprovalBlocked

from .conftest import current, upload_and_approve


def run_matching(system):
    """Run the metric 2 scenario; return {doc_number: doc} and the lines."""
    scenario = matching_scenario()
    docs = {}
    for upload in scenario.uploads:
        doc, _ = upload_and_approve(system, upload, correct_bank(upload.supplier_name))
        docs[upload.doc_number] = doc
    lines = []
    for bank in ("leumi", "chase"):
        lines += system.ingest_statement(
            bank, [l.entry for l in scenario.lines if l.bank_code == bank])
    return docs, lines


# --- Rule (b): extra supplier name after the bookkeeper confirms ------------


def test_confirmed_bank_name_is_matched_automatically_next_time(system):
    docs, lines = run_matching(system)
    line = next(l for l in lines if l.payee_name == ALIAS_CASE.confirm_payee)
    doc = docs[ALIAS_CASE.confirm_doc_number]
    assert line.status == Status.NEEDS_REVIEW

    system.confirm_match(line.id, doc.id)

    assert current(system, doc.id).status == Status.PAID
    review_alerts = [a for a in system.alerts()
                     if a.statement_line_id == line.id and a.alert_type == AlertType.UNCERTAIN_MATCH]
    assert review_alerts and all(a.resolved for a in review_alerts)

    # Next month: same bank name, new invoice. No review this time.
    new_doc, payment = upload_and_approve(system, ALIAS_CASE.next_upload, "chase")
    alerts_before = len(system.alerts())
    [new_line] = system.ingest_statement("chase", [ALIAS_CASE.next_line])

    assert new_line.matched_payment_id == payment.id
    assert current(system, new_doc.id).status == Status.PAID
    assert len(system.alerts()) == alerts_before


def test_without_confirmation_the_same_name_is_still_reviewed(system):
    run_matching(system)
    _, payment = upload_and_approve(system, ALIAS_CASE.next_upload, "chase")
    [line] = system.ingest_statement("chase", [ALIAS_CASE.next_line])
    assert line.status == Status.NEEDS_REVIEW
    assert line.matched_payment_id is None


def test_confirming_one_of_two_candidates_releases_the_other(system):
    docs, lines = run_matching(system)
    line = next(l for l in lines if l.payee_name == "Initrode Inc")
    system.confirm_match(line.id, docs["M-211"].id)
    assert current(system, docs["M-211"].id).status == Status.PAID
    assert current(system, docs["M-216"].id).status == Status.APPROVED
    # Same name as the supplier: nothing to save as an extra name.
    assert clean_name("Initrode Inc") not in system.aliases


# --- Wrong bank: card platform belongs to the US entity ---------------------


def test_israeli_supplier_paid_by_card_platform_is_alerted(system):
    upload = DocumentUpload(DocType.TAX_INVOICE, "Tavor Translations", Decimal("90.00"), "K-1")
    doc, payment = upload_and_approve(system, upload, "cards")
    assert payment is None
    assert current(system, doc.id).status == Status.NEEDS_REVIEW
    assert [a.alert_type for a in system.alerts()] == [AlertType.WRONG_BANK]


def test_cfo_decision_sends_the_held_payment(system):
    upload = DocumentUpload(DocType.TAX_INVOICE, "Initrode Inc", Decimal("3200.00"), "K-2")
    doc, _ = upload_and_approve(system, upload, "leumi")
    payment = system.decide_wrong_bank(doc.id, "chase")
    assert payment.bank_code == "chase"
    assert current(system, doc.id).status == Status.APPROVED
    assert all(a.resolved for a in system.alerts())


# --- New supplier ------------------------------------------------------------


def test_new_supplier_needs_budget_category_before_approval(system):
    system.add_supplier("Fresh Vendor", Entity.US)
    upload = DocumentUpload(DocType.TAX_INVOICE, "Fresh Vendor", Decimal("100.00"), "N-1")
    doc = system.upload_document(upload)
    with pytest.raises(ApprovalBlocked):
        system.approve(doc.id, "chase")
    assert system.payments() == []

    system.assign_budget_category("Fresh Vendor", "שיווק")
    assert system.approve(doc.id, "chase") is not None


# --- Name cleaning -----------------------------------------------------------


@pytest.mark.parametrize("raw, cleaned", [
    ("GLOBEX, LTD.", "globex"),
    ("Globex Ltd", "globex"),
    ("  Acme   Cloud  Inc. ", "acme cloud"),
    ("STARK HARDWARE SUPPLY CO", "stark hardware supply"),
    ('כרמל שירותים בע"מ', "כרמל שירותים"),
])
def test_clean_name(raw, cleaned):
    assert clean_name(raw) == cleaned


@pytest.mark.parametrize("line, supplier, expected", [
    ("GLOBEX, LTD.", "Globex Ltd", NameRelation.SAME),
    ("STARK HARDWARE SUPPLY CO", "Stark Hardware", NameRelation.STARTS_WITH),
    ("PAYPAL *WAYNE CONSULTING", "Wayne Consulting", NameRelation.AFTER_OTHER_TEXT),
    ("Hooli Analytics", "Hooli", NameRelation.STARTS_WITH),
    ("Hoolix Analytics", "Hooli Analytics", None),
    ("Acme Cloudy", "Acme Cloud", None),  # whole words only
])
def test_name_relation(line, supplier, expected):
    assert relation(line, supplier) == expected


# --- Export for the bookkeeper ----------------------------------------------


def test_export_lists_every_statement_line(system):
    _, lines = run_matching(system)
    rows = list(csv.DictReader(io.StringIO(system.export_transactions_csv())))
    assert len(rows) == len(lines) == 20
    globex = next(r for r in rows if r["payee"] == "GLOBEX, LTD.")
    assert (globex["document_number"], globex["supplier"], globex["status"]) == \
        ("M-215", "Globex Ltd", Status.PAID.value)
    zoom = next(r for r in rows if r["payee"] == "Zoom Video")
    assert (zoom["document_number"], zoom["status"]) == ("", Status.MISSING_INVOICE.value)


def test_removed_name_goes_back_to_review(system):
    docs, lines = run_matching(system)
    line = next(l for l in lines if l.payee_name == ALIAS_CASE.confirm_payee)
    system.confirm_match(line.id, docs[ALIAS_CASE.confirm_doc_number].id)
    alias = clean_name(ALIAS_CASE.confirm_payee)
    assert system.aliases_by_supplier() == {"Wayne Consulting": [alias]}

    system.remove_alias(alias)
    assert system.aliases_by_supplier() == {}
    upload_and_approve(system, ALIAS_CASE.next_upload, "chase")
    [new_line] = system.ingest_statement("chase", [ALIAS_CASE.next_line])
    assert new_line.status == Status.NEEDS_REVIEW
