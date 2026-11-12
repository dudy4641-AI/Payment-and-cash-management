"""Apply supabase/migrations/*.sql to a Supabase project via the Management API.

Usage:  python3 scripts/apply_schema.py <project-ref>

The access token is read from SUPABASE_ACCESS_TOKEN. In the cloud sandbox the
network proxy injects the real token, so a placeholder value is enough there.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


def main(ref: str) -> None:
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "sbp_placeholder")
    url = f"https://api.supabase.com/v1/projects/{ref}/database/query"
    for path in sorted((ROOT / "supabase" / "migrations").glob("*.sql")):
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"query": path.read_text(encoding="utf-8")},
            timeout=60,
        )
        print(f"{path.name}: HTTP {resp.status_code}")
        if not resp.ok:
            print(resp.text)
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
