"""Storage for PaymentSystem.

The system keeps its state in memory and writes every change through to a
store. InMemoryStore keeps nothing (tests). SupabaseStore persists to the
Supabase tables and loads them back on start.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol

import requests

from .models import (
    Alert,
    AlertType,
    Bank,
    BankKind,
    DocType,
    Document,
    Entity,
    Payment,
    Recipient,
    StatementLine,
    Status,
    Supplier,
)


@dataclass
class Snapshot:
    banks: list[Bank] = field(default_factory=list)
    suppliers: list[Supplier] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)  # cleaned name -> supplier
    documents: list[Document] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)
    lines: list[StatementLine] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)


class Store(Protocol):
    def load(self) -> Snapshot: ...
    def save(self, record: Any) -> None: ...
    def save_alias(self, alias: str, supplier_name: str) -> None: ...
    def delete_alias(self, alias: str) -> None: ...


class InMemoryStore:
    def load(self) -> Snapshot:
        return Snapshot()

    def save(self, record: Any) -> None:
        pass

    def save_alias(self, alias: str, supplier_name: str) -> None:
        pass

    def delete_alias(self, alias: str) -> None:
        pass


# --- Supabase ----------------------------------------------------------------

TABLES: dict[type, tuple[str, str]] = {  # model -> (table, order column)
    Bank: ("banks", "code"),
    Supplier: ("suppliers", "name"),
    Document: ("documents", "uploaded_at"),
    Payment: ("payments", "approved_at"),
    StatementLine: ("statement_lines", "uploaded_at"),
    Alert: ("alerts", "created_at"),
}

# Column types that need converting when loading a row back into a model.
_ENUMS = {
    "entity": Entity, "kind": BankKind, "doc_type": DocType, "status": Status,
    "alert_type": AlertType, "recipient": Recipient,
}
_DECIMALS = {"amount", "opening_balance"}


def _to_json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def to_row(record: Any) -> dict[str, Any]:
    return {k: _to_json(v) for k, v in dataclasses.asdict(record).items()}


def from_row(model: type, row: dict[str, Any]) -> Any:
    values = {}
    for f in dataclasses.fields(model):
        if f.name not in row:
            continue
        v = row[f.name]
        if v is not None:
            if f.name in _ENUMS:
                v = _ENUMS[f.name](v)
            elif f.name in _DECIMALS:
                v = Decimal(str(v)).quantize(Decimal("0.01"))
            elif f.name == "value_date":
                v = date.fromisoformat(v)
        values[f.name] = v
    return model(**values)


class SupabaseStore:
    """Talks to Supabase's REST API (PostgREST) with the project's secret key."""

    def __init__(self, url: str, key: str):
        self.base = url.rstrip("/") + "/rest/v1"
        self.session = requests.Session()
        self.session.headers.update({"apikey": key, "Content-Type": "application/json"})

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        resp = self.session.request(method, f"{self.base}/{path}", timeout=30, **kwargs)
        if not resp.ok:
            raise RuntimeError(f"Supabase {method} {path}: HTTP {resp.status_code} {resp.text}")
        return resp

    def _upsert(self, table: str, row: dict[str, Any]) -> None:
        self._request(
            "POST", table, json=row,
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )

    def save(self, record: Any) -> None:
        table, _ = TABLES[type(record)]
        self._upsert(table, to_row(record))

    def save_alias(self, alias: str, supplier_name: str) -> None:
        self._upsert("supplier_aliases", {"alias": alias, "supplier_name": supplier_name})

    def delete_alias(self, alias: str) -> None:
        self._request("DELETE", "supplier_aliases", params={"alias": f"eq.{alias}"})

    def load(self) -> Snapshot:
        def rows(table: str, order: str) -> list[dict[str, Any]]:
            return self._request("GET", f"{table}?select=*&order={order}").json()

        snap = Snapshot()
        for model, (table, order) in TABLES.items():
            records = [from_row(model, r) for r in rows(table, order)]
            attr = {Bank: "banks", Supplier: "suppliers", Document: "documents",
                    Payment: "payments", StatementLine: "lines", Alert: "alerts"}[model]
            setattr(snap, attr, records)
        snap.aliases = {r["alias"]: r["supplier_name"]
                        for r in rows("supplier_aliases", "created_at")}
        return snap

    def wipe(self) -> None:
        """Delete every row. For the test project only."""
        self._request("PATCH", "payments?id=not.is.null", json={"statement_line_id": None})
        self._request("PATCH", "documents?id=not.is.null", json={"linked_payment_id": None})
        for table, key in [
            ("alerts", "id"), ("statement_lines", "id"), ("payments", "id"),
            ("documents", "id"), ("supplier_aliases", "alias"),
            ("suppliers", "name"), ("banks", "code"),
        ]:
            self._request("DELETE", f"{table}?{key}=not.is.null")
