"""Write docs/MOCK_DATA.md: every mock case with its expected outcome.

Generated from payments/mock_data.py, so the file always matches what the
tests use. Run from the repo root:  python3 scripts/render_mock_data.py
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from payments import mock_data as md  # noqa: E402
from payments.models import ALERT_RECIPIENT, AlertType, Status  # noqa: E402

BANK_NAME = {b.code: b.name for b in md.BANKS}


def usd(x: Decimal) -> str:
    return f"${x:,.2f}"


def entity(supplier: str) -> str:
    return md.SUPPLIER_BY_NAME[supplier].entity.value if supplier in md.SUPPLIER_BY_NAME else "—"


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out + [""]


def company() -> list[str]:
    out = ["## החברה", ""]
    out += table(
        ["בנק", "ישות", "סוג", "יתרת פתיחה"],
        [[b.name, b.entity.value, "בנק" if b.kind.value == "bank" else "פלטפורמת כרטיסים",
          usd(b.opening_balance)] for b in md.BANKS],
    )
    out += ["הבנק הנכון לפי ישות: ישראל → לאומי, ארה\"ב → צ'ייס.", ""]
    out += table(
        ["ספק", "ישות", "סעיף תקציבי"],
        [[s.name, s.entity.value, s.budget_category or "— (ספק חדש)"] for s in md.SUPPLIERS],
    )
    return out


def metric1() -> list[str]:
    s = md.completeness_scenario()
    out = ["## מדד 1: שלמות הרשימה", "",
           "מעלים את 20 המסמכים. **צפוי:** הרשימה מציגה בדיוק 20, כולם בסטטוס "
           f"{Status.PENDING_APPROVAL.value}.", ""]
    out += table(
        ["#", "מספר מסמך", "סוג", "ספק", "ישות", "סכום"],
        [[str(i), u.doc_number, u.doc_type.value, u.supplier_name, entity(u.supplier_name),
          usd(u.amount)] for i, u in enumerate(s.uploads, 1)],
    )
    return out


def metric2() -> list[str]:
    s = md.matching_scenario()
    out = ["## מדד 2: שיוך", "",
           f"שלב א: מעלים את {len(s.uploads)} המסמכים ומאשרים כל אחד מהבנק הנכון לישות של הספק.", ""]
    out += table(
        ["מספר מסמך", "סוג", "ספק", "ישות", "סכום", "בנק לתשלום"],
        [[u.doc_number, u.doc_type.value, u.supplier_name, entity(u.supplier_name),
          usd(u.amount), BANK_NAME[md.correct_bank(u.supplier_name)]] for u in s.uploads],
    )
    out += ["שלב ב: מעלים דפי פירוט עם 20 תנועות.", ""]
    rows = []
    for i, l in enumerate(s.lines, 1):
        if l.expected == md.MATCHED:
            if len(l.doc_numbers) == 1:
                result = f"משויכת ל-{l.doc_numbers[0]}, המסמך עובר ל{Status.PAID.value}"
            else:
                result = (f"משויכת לאחד מ-{', '.join(l.doc_numbers)} (כל תנועה למסמך אחר), "
                          f"המסמך עובר ל{Status.PAID.value}")
        elif l.expected == md.MISSING:
            result = f"{Status.MISSING_INVOICE.value}"
        else:
            docs = (f"המסמך {l.doc_numbers[0]} לא משויך ועובר" if len(l.doc_numbers) == 1
                    else f"המסמכים {', '.join(l.doc_numbers)} לא משויכים ועוברים")
            result = (f"{Status.NEEDS_REVIEW.value}, פנייה למנהלת החשבונות; "
                      f"{docs} ל{Status.NEEDS_REVIEW.value}")
        rows.append([str(i), BANK_NAME[l.bank_code], l.entry.payee_name, usd(l.entry.amount),
                     result, l.note or "—"])
    out += table(["#", "בנק", "שם בתנועה", "סכום", "תוצאה צפויה", "הערה"], rows)
    out += [f"**צפוי:** {s.expected_matched} משויכות נכון, {s.expected_missing} חסרות חשבונית, "
            f"{s.expected_review} לבירור, 0 שיוכים שגויים.", ""]
    a = md.ALIAS_CASE
    out += ["### בדיקה נפרדת: שם נוסף לספק", "",
            f"אחרי שלב ב, מנהלת החשבונות מאשרת שהתנועה \"{a.confirm_payee}\" שייכת ל-"
            f"{a.confirm_doc_number}. השם נשמר כשם נוסף של {a.next_upload.supplier_name}. "
            f"אחר כך מעלים ומאשרים את {a.next_upload.doc_number} על {usd(a.next_upload.amount)}, "
            f"ובדף פירוט חדש מופיעה תנועה \"{a.next_line.payee_name}\" על {usd(a.next_line.amount)}. "
            f"**צפוי:** שיוך אוטומטי ל-{a.next_upload.doc_number}, בלי פנייה חדשה.", ""]
    return out


def metric3() -> list[str]:
    s = md.duplicate_scenario()
    dup_to = ALERT_RECIPIENT[AlertType.DUPLICATE].value
    out = ["## מדד 3: כפל תשלום", "",
           "סדר הפעולות: (1) מעלים ומאשרים את המקרים הרגילים, את דרישות התשלום ואת המקור של "
           "כל מסמך כפול; (2) כל 20 התשלומים מופיעים בדף הפירוט; (3) מגיעות חשבוניות המס, "
           "ומעלים שוב את ארבעת המסמכים הכפולים; (4) מנסים לאשר את חשבוניות המס ואת העותקים.", ""]
    rows = []
    for u in s.regular:
        rows.append(["רגיל", u.doc_number, u.doc_type.value, u.supplier_name, usd(u.amount),
                     BANK_NAME[md.correct_bank(u.supplier_name)],
                     f"תשלום אחד, {Status.PAID.value}, אין התראה"])
    for d, t in s.demand_pairs:
        bank = BANK_NAME[md.correct_bank(d.supplier_name)]
        rows.append(["דרישה ואחריה חשבונית", d.doc_number, d.doc_type.value, d.supplier_name,
                     usd(d.amount), bank,
                     f"תשלום אחד; אחרי דף הפירוט: {Status.MISSING_INVOICE.value}"])
        rows.append(["", t.doc_number, t.doc_type.value, t.supplier_name, usd(t.amount), "—",
                     f"משויכת לתשלום של {d.doc_number}; שניהם {Status.PAID.value}; "
                     "אין תשלום חדש, אין התראה"])
    for u in s.duplicates:
        rows.append(["מועלה פעמיים", u.doc_number, u.doc_type.value, u.supplier_name,
                     usd(u.amount), BANK_NAME[md.correct_bank(u.supplier_name)],
                     f"מקור: תשלום אחד, {Status.PAID.value}. עותק: התראת כפל ל{dup_to}, "
                     f"{Status.NEEDS_REVIEW.value}, אין תשלום"])
    out += table(["קבוצה", "מספר מסמך", "סוג", "ספק", "סכום", "בנק", "תוצאה צפויה"], rows)
    out += [f"**צפוי:** 4 מתוך 4 עותקים מקבלים התראה, 0 התראות אחרות, "
            f"{s.expected_total_payments} תשלומים בסך הכול, אף מסמך לא משולם פעמיים.", ""]
    return out


def metric4() -> list[str]:
    s = md.wrong_bank_scenario()
    to = ALERT_RECIPIENT[AlertType.WRONG_BANK].value
    out = ["## מדד 4: בנק לא נכון", ""]
    rows = []
    for u, bank in s.wrong:
        rows.append([u.doc_number, u.supplier_name, entity(u.supplier_name), usd(u.amount),
                     BANK_NAME[bank], f"התראה ל{to}, {Status.NEEDS_REVIEW.value}, "
                     "לא נשלח תשלום עד שהסמנכ\"ל מחליט"])
    for u, bank in s.control:
        rows.append([u.doc_number, u.supplier_name, entity(u.supplier_name), usd(u.amount),
                     BANK_NAME[bank], f"אין התראה, {Status.APPROVED.value}, תשלום נשלח"])
    out += table(["מספר מסמך", "ספק", "ישות", "סכום", "בנק שנבחר", "תוצאה צפויה"], rows)
    out += [f"**צפוי:** {s.expected_alerts} מתוך {len(s.wrong)} מקבלות התראה, "
            f"0 התראות על {len(s.control)} הביקורות.", ""]
    return out


def metric5() -> list[str]:
    out = ["## מדד 5: יתרות", "",
           "חל על לאומי וצ'ייס בלבד. פלטפורמת הכרטיסים לא נכללת במדד: יתרת הפתיחה שלה "
           f"{usd(next(b.opening_balance for b in md.BANKS if b.code == 'cards'))}, והתנועה היחידה "
           "שלה בנתונים המדומים היא W-405 במדד 4 (אושרה, לא מופיעה בדף פירוט).", ""]
    for c in md.balance_scenario().cases:
        name = BANK_NAME[c.bank_code]
        out += [f"### {name}", "", f"יתרת פתיחה: **{usd(c.opening_balance)}**", ""]
        rows = [[u.doc_number, u.supplier_name, usd(u.amount), "אושר ומופיע בדף הפירוט"]
                for u in c.cleared]
        rows += [[u.doc_number, u.supplier_name, usd(u.amount), "אושר ולא מופיע בדף הפירוט"]
                 for u in c.pending]
        out += table(["מספר מסמך", "ספק", "סכום", "מצב"], rows)
        cleared_sum = sum((u.amount for u in c.cleared), Decimal("0"))
        pending_sum = sum((u.amount for u in c.pending), Decimal("0"))
        out += [
            "**יתרה נוכחית** = יתרת פתיחה פחות התשלומים שמופיעים בדף הפירוט:",
            "",
            f"{usd(c.opening_balance)} − ({' + '.join(usd(u.amount) for u in c.cleared)}) "
            f"= {usd(c.opening_balance)} − {usd(cleared_sum)} = **{usd(c.expected_current)}**",
            "",
            "**יתרה צפויה** = יתרה נוכחית פחות התשלומים שאושרו ולא מופיעים:",
            "",
            f"{usd(c.expected_current)} − ({' + '.join(usd(u.amount) for u in c.pending)}) "
            f"= {usd(c.expected_current)} − {usd(pending_sum)} = **{usd(c.expected_expected)}**",
            "",
        ]
    return out


def render() -> str:
    lines = [
        "# הנתונים המדומים והתוצאות הצפויות",
        "",
        "הקובץ נוצר אוטומטית מ-`payments/mock_data.py` על ידי `scripts/render_mock_data.py`. "
        "אל תערוך אותו ידנית.",
        "",
        "כל מדד רץ על מערכת נקייה משלו, כך שמקרים ממדד אחד לא משפיעים על מדד אחר. "
        "כל הסכומים בדולר.",
        "",
    ]
    for part in (company, metric1, metric2, metric3, metric4, metric5):
        lines += part()
    return "\n".join(lines)


if __name__ == "__main__":
    target = ROOT / "docs" / "MOCK_DATA.md"
    target.parent.mkdir(exist_ok=True)
    target.write_text(render(), encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)}")
