"""SPEC 8.1: upload twenty documents; the list shows exactly twenty."""

from payments.mock_data import completeness_scenario
from payments.models import Status


def test_list_shows_exactly_the_uploaded_documents(system):
    scenario = completeness_scenario()

    uploaded = [system.upload_document(u) for u in scenario.uploads]
    listed = system.list_documents()

    assert len(listed) == scenario.expected_count
    assert {d.id for d in listed} == {d.id for d in uploaded}
    assert sorted(d.doc_number for d in listed) == sorted(u.doc_number for u in scenario.uploads)
    # A freshly uploaded document waits for approval (SPEC section 4, step 2).
    assert all(d.status == Status.PENDING_APPROVAL for d in listed)
