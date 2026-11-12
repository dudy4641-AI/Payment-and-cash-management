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
    uploads = {u.doc_number: u for u in s.uploads}
    for line in s.lines:
        # Every candidate document exists and has the line's amount.
        for n in line.doc_numbers:
            assert uploads[n].amount == line.entry.amount
        if line.expected == md.MISSING:
            assert line.doc_numbers == ()
    # Lines that share candidates: as many lines as documents means automatic
    # matching; a different count means review.
    groups = Counter(l.doc_numbers for l in s.lines if len(l.doc_numbers) > 1)
    for docs, n_lines in groups.items():
        expected = {l.expected for l in s.lines if l.doc_numbers == docs}
        assert expected == {md.MATCHED if n_lines == len(docs) else md.REVIEW}


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
    banks = {b.code: b for b in md.BANKS}
    pairs = [(md.SUPPLIER_BY_NAME[u.supplier_name].entity, bank) for u, bank in s.wrong]
    assert len(s.wrong) == s.expected_alerts == 4
    assert Counter(pairs) == {(Entity.US, "leumi"): 2, (Entity.IL, "chase"): 2}
    for upload, bank in s.control:
        assert md.SUPPLIER_BY_NAME[upload.supplier_name].entity == banks[bank].entity


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
