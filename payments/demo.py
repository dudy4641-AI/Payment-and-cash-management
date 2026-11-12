"""Demo state for the screen: a company mid-month with something in every queue."""

from __future__ import annotations

from decimal import Decimal

from .mock_data import BANKS, STATEMENT_DATE, SUPPLIERS, correct_bank, matching_scenario
from .models import DocType, DocumentUpload, Entity, StatementEntry
from .service import PaymentSystem


def build_demo(system: PaymentSystem | None = None) -> PaymentSystem:
    system = system or PaymentSystem(BANKS, SUPPLIERS)

    # Approved and matched against statements: the metric 2 scenario, which
    # leaves missing invoices and three lines for the bookkeeper to review.
    scenario = matching_scenario()
    for upload in scenario.uploads:
        doc = system.upload_document(upload)
        system.approve(doc.id, correct_bank(upload.supplier_name))
    for bank in ("leumi", "chase"):
        system.ingest_statement(bank, [l.entry for l in scenario.lines if l.bank_code == bank])

    # Paid payment demand still waiting for its tax invoice.
    demand = system.upload_document(
        DocumentUpload(DocType.PAYMENT_DEMAND, "Hermon Insurance", Decimal("2210.40"), "D-901"))
    system.approve(demand.id, "leumi")
    system.ingest_statement("leumi", [StatementEntry("Hermon Insurance", Decimal("2210.40"),
                                                     STATEMENT_DATE)])

    # Approved, not yet in the bank.
    for supplier, amount, number in [("Soylent Foods", "1320.10", "A-902"),
                                     ("Tavor Translations", "640.00", "A-903")]:
        doc = system.upload_document(DocumentUpload(DocType.TAX_INVOICE, supplier,
                                                    Decimal(amount), number))
        system.approve(doc.id, correct_bank(supplier))

    # Wrong bank, waiting for the CFO.
    doc = system.upload_document(
        DocumentUpload(DocType.TAX_INVOICE, "Initrode Inc", Decimal("3200.00"), "W-904"))
    system.approve(doc.id, "leumi")

    # Uploaded twice: the copy waits for the bookkeeper.
    dup = DocumentUpload(DocType.TAX_INVOICE, "Cyberdyne Systems", Decimal("9100.00"), "X-905")
    system.approve(system.upload_document(dup).id, "chase")
    system.upload_document(dup)

    # Waiting for approval, including a new supplier with no budget category.
    system.add_supplier("Northwind Design", Entity.US)
    for supplier, amount, number, doc_type in [
        ("Shapira Legal", "2600.00", "P-906", DocType.TAX_INVOICE),
        ("Vandelay Imports", "4875.00", "P-907", DocType.PAYMENT_DEMAND),
        ("Hooli Analytics", "830.00", "P-908", DocType.TAX_INVOICE),
        ("Northwind Design", "5400.00", "P-909", DocType.TAX_INVOICE),
    ]:
        system.upload_document(DocumentUpload(doc_type, supplier, Decimal(amount), number))
    return system
