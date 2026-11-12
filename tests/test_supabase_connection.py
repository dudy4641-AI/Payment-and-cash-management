"""Connection test against the Supabase test project.

Skipped unless SUPABASE_URL is set (e.g. https://<ref>.supabase.co).
The key is read from SUPABASE_KEY and sent in the `apikey` header; in the
cloud sandbox the network proxy injects the real key.
"""

import os

import pytest
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "placeholder")

pytestmark = pytest.mark.skipif(not SUPABASE_URL, reason="SUPABASE_URL not set")

TABLES = ["banks", "suppliers", "documents", "payments", "statement_lines", "alerts"]


def rest(method: str, path: str, **kwargs) -> requests.Response:
    return requests.request(
        method,
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
        timeout=30,
        **kwargs,
    )


@pytest.mark.parametrize("table", TABLES)
def test_table_exists_and_is_readable(table):
    resp = rest("GET", f"{table}?select=*&limit=1")
    assert resp.status_code == 200, resp.text


def test_database_rejects_a_status_outside_the_closed_list():
    resp = rest(
        "POST",
        "documents",
        json={
            "doc_type": "חשבונית מס",
            "supplier_name": "connection-test",
            "amount": "1.00",
            "doc_number": "connection-test",
            "status": "בוטלה",  # not one of the six statuses
        },
    )
    assert resp.status_code == 400, resp.text
    assert resp.json().get("code") == "22P02"  # invalid input value for enum
