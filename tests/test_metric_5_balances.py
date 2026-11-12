"""SPEC 8.5: in Leumi and in Chase, current balance = opening minus the three
cleared payments, expected balance = current minus the two pending ones,
exact to the cent."""

from decimal import Decimal

import pytest

from payments.mock_data import STATEMENT_DATE, balance_scenario
from payments.models import StatementEntry

from .conftest import upload_and_approve


@pytest.mark.parametrize("case", balance_scenario().cases, ids=lambda c: c.bank_code)
def test_current_and_expected_balance_to_the_cent(system, case):
    assert system.banks[case.bank_code].opening_balance == case.opening_balance

    for upload in case.cleared + case.pending:
        _, payment = upload_and_approve(system, upload, case.bank_code)
        assert payment is not None

    system.ingest_statement(
        case.bank_code,
        [StatementEntry(u.supplier_name, u.amount, STATEMENT_DATE) for u in case.cleared],
    )

    current = system.current_balance(case.bank_code)
    expected = system.expected_balance(case.bank_code)

    assert isinstance(current, Decimal) and isinstance(expected, Decimal)
    assert current == case.expected_current
    assert expected == case.expected_expected
