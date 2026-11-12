"""The demo company used by the screen has something in every queue."""

from collections import Counter

from payments.demo import build_demo
from payments.models import AlertType, Status


def test_demo_has_every_queue_filled():
    system = build_demo()
    statuses = Counter(d.status for d in system.list_documents())
    assert set(statuses) == {Status.PENDING_APPROVAL, Status.APPROVED, Status.PAID,
                             Status.MISSING_INVOICE, Status.NEEDS_REVIEW}
    open_alerts = Counter(a.alert_type for a in system.alerts(include_resolved=False))
    assert open_alerts == {AlertType.UNCERTAIN_MATCH: 3, AlertType.WRONG_BANK: 1,
                           AlertType.DUPLICATE: 1}
