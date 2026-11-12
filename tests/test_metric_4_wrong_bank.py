"""SPEC 8.4: two invoices of a US supplier paid from Leumi and two of an
Israeli supplier paid from Chase. 4/4 alerted, 0 alerts on payments from the
right bank."""

from payments.mock_data import wrong_bank_scenario
from payments.models import AlertType, Recipient, Status

from .conftest import current, upload_and_approve


def test_supplier_entity_different_from_bank_entity_is_alerted(system):
    scenario = wrong_bank_scenario()

    wrong_docs = []
    for upload, bank_code in scenario.wrong:
        doc, payment = upload_and_approve(system, upload, bank_code)
        # The CFO decides; nothing is sent to the bank before that.
        assert payment is None
        wrong_docs.append(doc)

    control_docs = []
    for upload, bank_code in scenario.control:
        doc, payment = upload_and_approve(system, upload, bank_code)
        assert payment is not None
        control_docs.append(doc)

    alerts = system.alerts()
    wrong_bank_alerts = [a for a in alerts if a.alert_type == AlertType.WRONG_BANK]

    assert {a.document_id for a in wrong_bank_alerts} == {d.id for d in wrong_docs}
    assert len(wrong_bank_alerts) == scenario.expected_alerts
    assert all(a.recipient == Recipient.CFO for a in wrong_bank_alerts)
    assert all(current(system, d.id).status == Status.NEEDS_REVIEW for d in wrong_docs)

    control_ids = {d.id for d in control_docs}
    assert not [a for a in alerts if a.document_id in control_ids]
    assert all(current(system, d.id).status == Status.APPROVED for d in control_docs)
