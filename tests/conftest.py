import pytest

from payments.mock_data import BANKS, SUPPLIERS
from payments.models import Document, DocumentUpload, Payment
from payments.service import PaymentSystem


@pytest.fixture
def system() -> PaymentSystem:
    return PaymentSystem(BANKS, SUPPLIERS)


def upload_and_approve(
    system: PaymentSystem, upload: DocumentUpload, bank_code: str
) -> tuple[Document, Payment | None]:
    doc = system.upload_document(upload)
    return doc, system.approve(doc.id, bank_code)


def current(system: PaymentSystem, doc_id: str) -> Document:
    """Re-read a document from the system, so tests never rely on a stale copy."""
    return next(d for d in system.list_documents() if d.id == doc_id)
