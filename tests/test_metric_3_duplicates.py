"""SPEC 8.3: 12 regular cases, 4 tax invoices after a payment demand,
4 documents uploaded twice. 4/4 double uploads alerted; the 4 tax invoices
close the original demand with no new payment; 0 alerts on the regular
cases; 0 duplicate payments."""

from collections import Counter

from payments.mock_data import STATEMENT_DATE, correct_bank, duplicate_scenario
from payments.models import AlertType, Recipient, StatementEntry, Status

from .conftest import current, upload_and_approve


def test_duplicates_alerted_and_tax_invoices_close_demands(system):
    scenario = duplicate_scenario()
    demands = [d for d, _ in scenario.demand_pairs]
    tax_invoices = [t for _, t in scenario.demand_pairs]

    # 1. Upload and approve the regular invoices, the demands and the originals.
    first_round = scenario.regular + demands + scenario.duplicates
    docs, payments = {}, {}
    for upload in first_round:
        doc, payment = upload_and_approve(system, upload, correct_bank(upload.supplier_name))
        assert payment is not None
        docs[upload.doc_number] = doc
        payments[upload.doc_number] = payment

    # 2. All of those payments appear in the bank statements.
    for bank_code in ("leumi", "chase"):
        entries = [
            StatementEntry(u.supplier_name, u.amount, STATEMENT_DATE)
            for u in first_round
            if correct_bank(u.supplier_name) == bank_code
        ]
        system.ingest_statement(bank_code, entries)

    for upload in scenario.regular + scenario.duplicates:
        assert current(system, docs[upload.doc_number].id).status == Status.PAID
    # A paid demand stays "missing invoice" until its tax invoice arrives.
    for demand in demands:
        assert current(system, docs[demand.doc_number].id).status == Status.MISSING_INVOICE

    # 3. The tax invoices arrive, and the four documents are uploaded again.
    invoice_docs = [system.upload_document(t) for t in tax_invoices]
    copy_docs = [system.upload_document(u) for u in scenario.duplicates]

    # 4. Trying to approve any of them must not create a payment.
    for doc in invoice_docs + copy_docs:
        assert system.approve(doc.id, correct_bank(doc.supplier_name)) is None

    # Double uploads: 4 of 4 alerted, on the copies, sent to the bookkeeper for review.
    duplicate_alerts = [a for a in system.alerts() if a.alert_type == AlertType.DUPLICATE]
    assert len(duplicate_alerts) == scenario.expected_duplicate_alerts
    assert {a.document_id for a in duplicate_alerts} == {d.id for d in copy_docs}
    assert all(a.recipient == Recipient.BOOKKEEPER for a in duplicate_alerts)
    assert all(current(system, d.id).status == Status.NEEDS_REVIEW for d in copy_docs)

    # Tax invoices: linked to the original payment, demand closed as paid.
    for demand, invoice_doc in zip(demands, invoice_docs):
        invoice_now = current(system, invoice_doc.id)
        assert invoice_now.linked_payment_id == payments[demand.doc_number].id
        assert invoice_now.status == Status.PAID
        assert current(system, docs[demand.doc_number].id).status == Status.PAID

    # No false alarms: the only alerts in the system are the 4 double uploads.
    assert len(system.alerts()) == scenario.expected_duplicate_alerts

    # No duplicate payments at all.
    all_payments = system.payments()
    assert len(all_payments) == scenario.expected_total_payments
    assert max(Counter(p.document_id for p in all_payments).values()) == 1
    number_by_id = {d.id: n for n, d in docs.items()}
    by_charge = Counter((p.supplier_name, number_by_id[p.document_id]) for p in all_payments)
    assert max(by_charge.values()) == 1
