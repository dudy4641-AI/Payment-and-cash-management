"""SPEC 8.2: twenty statement lines. 12 matched correctly, 5 flagged as
missing an invoice, 3 sent for review, 0 wrong matches."""

from collections import defaultdict

from payments.mock_data import MATCHED, MISSING, REVIEW, correct_bank, matching_scenario
from payments.models import AlertType, Recipient, Status

from .conftest import current, upload_and_approve


def test_statement_lines_are_matched_flagged_or_sent_for_review(system):
    scenario = matching_scenario()

    doc_by_number = {}
    payment_by_doc_number = {}
    for upload in scenario.uploads:
        doc, payment = upload_and_approve(system, upload, correct_bank(upload.supplier_name))
        assert payment is not None
        doc_by_number[upload.doc_number] = doc
        payment_by_doc_number[upload.doc_number] = payment

    # Upload one statement per bank, keeping each line next to its label.
    by_bank = defaultdict(list)
    for labelled in scenario.lines:
        by_bank[labelled.bank_code].append(labelled)
    results = []
    for bank_code, labelled_lines in by_bank.items():
        lines = system.ingest_statement(bank_code, [l.entry for l in labelled_lines])
        assert len(lines) == len(labelled_lines)
        results += zip(labelled_lines, lines)

    review_alerts = {
        a.statement_line_id: a
        for a in system.alerts()
        if a.alert_type == AlertType.UNCERTAIN_MATCH
    }

    matched = missing = review = wrong = 0
    for labelled, line in results:
        if line.matched_payment_id is not None:
            expected_ids = {payment_by_doc_number[n].id for n in labelled.doc_numbers}
            if labelled.expected != MATCHED or line.matched_payment_id not in expected_ids:
                wrong += 1
                continue

        if labelled.expected == MATCHED:
            matched += line.matched_payment_id is not None
            for n in labelled.doc_numbers:
                assert current(system, doc_by_number[n].id).status == Status.PAID
        elif labelled.expected == MISSING:
            missing += line.status == Status.MISSING_INVOICE
        elif labelled.expected == REVIEW:
            alert = review_alerts.get(line.id)
            if line.status == Status.NEEDS_REVIEW and alert is not None:
                review += 1
                assert alert.recipient == Recipient.BOOKKEEPER

    assert wrong == 0
    # A payment is never matched to two lines (the two identical Acme lines
    # must each get a different document).
    matched_ids = [line.matched_payment_id for _, line in results if line.matched_payment_id]
    assert len(matched_ids) == len(set(matched_ids))
    assert matched == scenario.expected_matched
    assert missing == scenario.expected_missing
    assert review == scenario.expected_review

    # Documents behind a doubtful line are not marked paid.
    for labelled in scenario.lines:
        if labelled.expected == REVIEW:
            for n in labelled.doc_numbers:
                assert current(system, doc_by_number[n].id).status == Status.NEEDS_REVIEW
