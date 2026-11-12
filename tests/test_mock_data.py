"""Checks that the mock data itself matches the counts in SPEC section 8.
These test the fixtures, not the system, so they pass already in stage 1."""

from collections import Counter
from decimal import Decimal

from payments import mock_data as md
from payments.models import BankKind, DocType, Entity, Status


def test_status_list_is_closed_and_has_six_values():
    assert [s.value for s in Status] == [
        "הועלתה", "ממתינה לאישור", "אושרה", "שולמה", "חסרה חשבונית", "דורשת בירור",
    ]


def test_company_setup():
    banks = {b.code: b for b in md.BANKS}
    assert banks["leumi"].entity == Entity.IL
    assert banks["chase"].entity == Entity.US
    assert banks["cards"].entity == Entity.US
    assert banks["cards"].kind == BankKind.CARD_PLATFORM
    assert all(s.budget_category for s in md.SUPPLIERS)


def test_completeness_has_twenty_distinct_documents():
    s = md.completeness_scenario()
    assert len(s.uploads) == s.expected_count == 20
    assert len({u.doc_number for u in s.uploads}) == 20


def test_matching_has_12_5_3():
    s = md.matching_scenario()
    labels = Counter(l.expected for l in s.lines)
    assert len(s.lines) == 20
    assert labels == {md.MATCHED: 12, md.MISSING: 5, md.REVIEW: 3}
    # Every matched line has exactly one document with that exact name and amount.
    for line in s.lines:
        if line.expected == md.MATCHED:
            same = [u for u in s.uploads
                    if u.supplier_name == line.entry.payee_name and u.amount == line.entry.amount]
            assert [u.doc_number for u in same] == list(line.doc_numbers)


def test_duplicates_has_12_4_4():
    s = md.duplicate_scenario()
    assert (len(s.regular), len(s.demand_pairs), len(s.duplicates)) == (12, 4, 4)
    for demand, invoice in s.demand_pairs:
        assert demand.doc_type == DocType.PAYMENT_DEMAND
        assert invoice.doc_type == DocType.TAX_INVOICE
        assert (demand.supplier_name, demand.amount) == (invoice.supplier_name, invoice.amount)
    first_round = s.regular + [d for d, _ in s.demand_pairs] + s.duplicates
    assert len(first_round) == s.expected_total_payments
    # No two first-round documents share supplier and amount, so matching is unambiguous.
    assert len({(u.supplier_name, u.amount) for u in first_round}) == len(first_round)


def test_wrong_bank_cases():
    s = md.wrong_bank_scenario()
    assert len(s.wrong) == 2
    for upload, bank in s.wrong:
        assert md.SUPPLIER_BY_NAME[upload.supplier_name].entity == Entity.US
        assert bank == "leumi"
    for upload, bank in s.control:
        entity = md.SUPPLIER_BY_NAME[upload.supplier_name].entity
        assert not (entity == Entity.US and bank == "leumi")


def test_balance_expectations_add_up_to_the_cent():
    s = md.balance_scenario()
    assert [c.bank_code for c in s.cases] == ["leumi", "chase"]
    banks = {b.code: b for b in md.BANKS}
    for c in s.cases:
        assert (len(c.cleared), len(c.pending)) == (3, 2)
        assert c.opening_balance == banks[c.bank_code].opening_balance
        current = c.opening_balance - sum((u.amount for u in c.cleared), Decimal("0"))
        assert current == c.expected_current
        assert current - sum((u.amount for u in c.pending), Decimal("0")) == c.expected_expected
        for u in c.cleared + c.pending:
            assert md.correct_bank(u.supplier_name) == c.bank_code
