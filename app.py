"""Streamlit screen: documents, approvals, statements, review queue, learned names.

Run:  streamlit run app.py

Storage: with SUPABASE_URL and SUPABASE_KEY (env or .streamlit/secrets.toml)
the data lives in Supabase. Without them, each browser session gets its own
in-memory demo company.
"""

from __future__ import annotations

import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from payments.demo import build_demo
from payments.mock_data import BANKS, SUPPLIERS
from payments.models import AlertType, DocType, DocumentUpload, Entity, StatementEntry, Status
from payments.service import ApprovalBlocked, PaymentSystem
from payments.store import SupabaseStore

st.set_page_config(page_title="תשלומי ספקים", page_icon="💳", layout="wide")
st.markdown(
    """<style>
    .stApp, .stMarkdown, .stTextInput, .stSelectbox, .stNumberInput, .stRadio,
    .stTabs, [data-testid="stSidebar"], .stAlert, .stButton, .stForm { direction: rtl; text-align: right; }
    </style>""",
    unsafe_allow_html=True,
)


def _setting(name: str) -> str:
    try:
        return st.secrets.get(name, "") or os.environ.get(name, "")
    except Exception:  # no secrets file
        return os.environ.get(name, "")


SUPABASE_URL, SUPABASE_KEY = _setting("SUPABASE_URL"), _setting("SUPABASE_KEY")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)


def get_system() -> PaymentSystem:
    if "system" not in st.session_state:
        if USE_SUPABASE:
            st.session_state.system = PaymentSystem(
                BANKS, SUPPLIERS, store=SupabaseStore(SUPABASE_URL, SUPABASE_KEY))
        else:
            st.session_state.system = build_demo()
    return st.session_state.system


def flash(message: str, kind: str = "success") -> None:
    st.session_state.flash = (kind, message)


def esc(text: str) -> str:
    """Escape Markdown so bank names like 'PAYPAL *WAYNE' show as written."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>~])", r"\\\1", text)


def usd(x: Decimal) -> str:
    return f"${x:,.2f}"


def parse_amount(text: str) -> Decimal | None:
    try:
        value = Decimal(str(text).replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        return None
    return value.quantize(Decimal("0.01")) if value > 0 else None


system = get_system()
docs = {d.id: d for d in system.list_documents()}
payments_by_doc = {p.document_id: p for p in system.payments()}
lines = system.statement_lines()
open_alerts = system.alerts(include_resolved=False)
bank_names = {b.code: b.name for b in system.banks.values()}
doc_label = {d.id: f"{d.doc_number} · {d.supplier_name} · {usd(d.amount)}" for d in docs.values()}

# --- Sidebar ---------------------------------------------------------------

with st.sidebar:
    st.header("תשלומי ספקים")
    open_counts = {t: sum(1 for a in open_alerts if a.alert_type == t) for t in AlertType}
    page = st.radio("מסך", [
        "מסמכים ותשלומים",
        'החלטות סמנכ"ל',
        "דף פירוט בנק",
        "פניות למנהלת החשבונות",
        "שמות שהמערכת למדה",
    ], key="page", format_func=lambda n: {
        'החלטות סמנכ"ל': f'{n} ({open_counts[AlertType.WRONG_BANK]})',
        "פניות למנהלת החשבונות":
            f"{n} ({open_counts[AlertType.UNCERTAIN_MATCH] + open_counts[AlertType.DUPLICATE]})",
    }.get(n, n))
    st.caption("מקור נתונים: " + ("סופאבייס" if USE_SUPABASE else "הדגמה בזיכרון, לכל דפדפן בנפרד"))
    if not USE_SUPABASE and st.button("איפוס נתוני ההדגמה"):
        st.session_state.system = build_demo()
        flash("נתוני ההדגמה אופסו")
        st.rerun()
    counts = pd.Series([d.status.value for d in docs.values()]).value_counts()
    st.subheader("מסמכים לפי סטטוס")
    for status in Status:
        st.write(f"{status.value}: **{counts.get(status.value, 0)}**")

if "flash" in st.session_state:
    kind, message = st.session_state.pop("flash")
    getattr(st, kind)(message)



# --- Documents and payments ------------------------------------------------

if page == 'מסמכים ותשלומים':
    st.subheader("רשימת מסמכים ותשלומים")
    status_filter = st.multiselect("סינון לפי סטטוס", [s.value for s in Status],
                                   placeholder="כל הסטטוסים")
    rows = [{
        "מספר מסמך": d.doc_number,
        "סוג": d.doc_type.value,
        "ספק": d.supplier_name,
        "ישות": system.suppliers[d.supplier_name].entity.value,
        "סכום": usd(d.amount),
        "סטטוס": d.status.value,
        "בנק לתשלום": bank_names.get(payments_by_doc[d.id].bank_code, "") if d.id in payments_by_doc
        else (bank_names[d.requested_bank_code] + " (ממתין להחלטה)" if d.requested_bank_code else ""),
    } for d in docs.values()]
    table = pd.DataFrame(rows)
    if status_filter and not table.empty:
        table = table[table["סטטוס"].isin(status_filter)]
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption(f"{len(table)} מסמכים מוצגים מתוך {len(docs)}")

    col_upload, col_approve = st.columns(2)

    with col_upload:
        st.subheader("העלאת מסמך")
        with st.form("upload", clear_on_submit=True):
            doc_type = st.radio("סוג המסמך", [t.value for t in DocType], horizontal=True)
            supplier = st.selectbox("ספק", sorted(system.suppliers) + ["+ ספק חדש"])
            new_name = st.text_input("שם ספק חדש")
            new_entity = st.radio("ישות של ספק חדש", [e.value for e in Entity], horizontal=True)
            amount_text = st.text_input("סכום בדולר")
            doc_number = st.text_input("מספר מסמך")
            st.file_uploader("קובץ המסמך (לתצוגה בלבד, לא נשמר בגרסה הזו)", type=["pdf", "png", "jpg"])
            if st.form_submit_button("העלאה"):
                amount = parse_amount(amount_text)
                name = new_name.strip() if supplier == "+ ספק חדש" else supplier
                if not name or amount is None or not doc_number.strip():
                    st.error("צריך ספק, סכום חיובי ומספר מסמך")
                else:
                    if name not in system.suppliers:
                        system.add_supplier(name, Entity(new_entity))
                    doc = system.upload_document(DocumentUpload(
                        DocType(doc_type), name, amount, doc_number.strip()))
                    flash(f"המסמך {doc.doc_number} הועלה. סטטוס: {doc.status.value}",
                          "warning" if doc.status == Status.NEEDS_REVIEW else "success")
                    st.rerun()

    with col_approve:
        st.subheader("אישור לתשלום")
        pending = [d for d in docs.values() if d.status == Status.PENDING_APPROVAL]
        if not pending:
            st.info("אין מסמכים שממתינים לאישור")
        else:
            doc_id = st.selectbox("מסמך", [d.id for d in pending], format_func=doc_label.get)
            doc = docs[doc_id]
            supplier = system.suppliers[doc.supplier_name]
            st.write(f"ישות הספק: **{supplier.entity.value}** · "
                     f"סעיף תקציבי: **{supplier.budget_category or 'אין (ספק חדש)'}**")
            if not supplier.budget_category:
                category = st.text_input("סעיף תקציבי לספק החדש")
                if st.button("שיוך סעיף תקציבי") and category.strip():
                    system.assign_budget_category(supplier.name, category.strip())
                    flash(f"הסעיף {category.strip()} שויך ל-{supplier.name}")
                    st.rerun()
            codes = list(system.banks)
            bank = st.radio("לשלם מ", codes, format_func=bank_names.get, horizontal=True)
            if st.button("אישור ושליחה לבנק", type="primary"):
                try:
                    payment = system.approve(doc_id, bank)
                except ApprovalBlocked as e:
                    flash(str(e), "error")
                else:
                    if payment:
                        flash(f"אושר. התשלום נשלח ל{bank_names[bank]} (בנק מדומה)")
                    else:
                        flash("התראת בנק לא נכון: התשלום לא נשלח, ההחלטה אצל הסמנכ\"ל", "warning")
                st.rerun()

# --- CFO decisions ---------------------------------------------------------

if page == 'החלטות סמנכ"ל':
    st.subheader("תשלומים שממתינים להחלטה")
    wrong = [a for a in open_alerts if a.alert_type == AlertType.WRONG_BANK]
    if not wrong:
        st.info("אין התראות פתוחות")
    for alert in wrong:
        doc = docs[alert.document_id]
        with st.container(border=True):
            st.write(f"**{esc(doc_label[doc.id])}**")
            st.warning(esc(alert.message))
            options = list(system.banks)
            choice = st.radio("לשלם מ", options, key=f"cfo-{alert.id}", format_func=bank_names.get,
                              index=options.index(doc.requested_bank_code), horizontal=True)
            if st.button("החלטה: לשלם", key=f"cfo-btn-{alert.id}"):
                system.decide_wrong_bank(doc.id, choice)
                flash(f"התשלום על {doc.doc_number} נשלח מ{bank_names[choice]}")
                st.rerun()

# --- Bank statement --------------------------------------------------------

if page == 'דף פירוט בנק':
    st.subheader("העלאת דף פירוט מדומה")
    bank = st.radio("בנק", list(system.banks), format_func=bank_names.get, horizontal=True,
                    key="statement-bank")
    st.caption("מלאו שורה לכל חיוב, או העלו CSV עם העמודות payee_name, amount, value_date")
    csv_file = st.file_uploader("CSV", type=["csv"])
    if csv_file is not None:
        start = pd.read_csv(csv_file, dtype=str)
    else:
        start = pd.DataFrame({"payee_name": [""], "amount": [""],
                              "value_date": [date.today().isoformat()]})
    edited = st.data_editor(start, num_rows="dynamic", width="stretch", key="statement-editor")
    if st.button("קליטת דף הפירוט", type="primary"):
        entries, errors = [], []
        for i, row in edited.iterrows():
            name = str(row.get("payee_name") or "").strip()
            if not name:
                continue
            amount = parse_amount(row.get("amount"))
            try:
                when = date.fromisoformat(str(row.get("value_date")).strip())
            except ValueError:
                when = None
            if amount is None or when is None:
                errors.append(f"שורה {i + 1}: סכום או תאריך לא תקינים")
            else:
                entries.append(StatementEntry(name, amount, when))
        if errors:
            st.error("\n".join(errors))
        elif entries:
            result = system.ingest_statement(bank, entries)
            summary = pd.Series([l.status.value for l in result]).value_counts()
            flash("נקלטו " + ", ".join(f"{v} {k}" for k, v in summary.items()))
            st.rerun()

    st.subheader("תנועות שנקלטו")
    paid_doc = {p.id: p.document_id for p in system.payments()}
    st.dataframe(pd.DataFrame([{
        "בנק": bank_names[l.bank_code],
        "תאריך": l.value_date.isoformat(),
        "שם בתנועה": l.payee_name,
        "סכום": usd(l.amount),
        "סטטוס": l.status.value if l.status else "",
        "משויכת למסמך": docs[paid_doc[l.matched_payment_id]].doc_number if l.matched_payment_id else "",
    } for l in lines]), hide_index=True, width="stretch")

# --- Bookkeeper ------------------------------------------------------------

if page == 'פניות למנהלת החשבונות':
    st.subheader("תנועות לבירור")
    review = [a for a in open_alerts if a.alert_type == AlertType.UNCERTAIN_MATCH]
    line_by_id = {l.id: l for l in lines}
    if not review:
        st.info("אין תנועות לבירור")
    for alert in review:
        line = line_by_id[alert.statement_line_id]
        with st.container(border=True):
            st.write(f"**{esc(line.payee_name)}** · {usd(line.amount)} · {bank_names[line.bank_code]} · "
                     f"{line.value_date.isoformat()}")
            st.text(alert.message)
            pick = st.radio("למי התנועה שייכת?", line.candidate_document_ids,
                            format_func=doc_label.get, key=f"rev-{alert.id}")
            if st.button("אישור השיוך", key=f"rev-btn-{alert.id}"):
                before = set(system.aliases)
                system.confirm_match(line.id, pick)
                learned = set(system.aliases) - before
                flash("השיוך אושר" + (f". נלמד שם חדש: {', '.join(learned)}" if learned else ""))
                st.rerun()

    st.subheader("מסמכים שהועלו פעמיים")
    dups = [a for a in open_alerts if a.alert_type == AlertType.DUPLICATE]
    if not dups:
        st.info("אין")
    for alert in dups:
        with st.container(border=True):
            st.write(f"**{esc(doc_label[alert.document_id])}**: {esc(alert.message)}")
            if st.button("סימון כטופל", key=f"dup-{alert.id}"):
                system.resolve_alert(alert.id)
                flash("ההתראה סומנה כטופלה")
                st.rerun()

    st.subheader("קובץ תנועות")
    st.download_button("הורדת קובץ תנועות (CSV)", system.export_transactions_csv().encode("utf-8-sig"),
                       file_name="transactions.csv", mime="text/csv")

# --- Learned names ---------------------------------------------------------

if page == 'שמות שהמערכת למדה':
    st.subheader("שמות שהמערכת למדה לכל ספק")
    st.caption("שם נלמד כשמנהלת החשבונות מאשרת שיוך של תנועה ששמה שונה משם הספק. "
               "מחיקת שם שגוי מחזירה תנועות חדשות בשם הזה לבירור.")
    learned = system.aliases_by_supplier()
    if not learned:
        st.info("עוד לא נלמדו שמות. אשרו שיוך בלשונית הפניות כדי לראות כאן שם.")
    for supplier, names in learned.items():
        with st.container(border=True):
            st.write(f"**{esc(supplier)}**")
            for alias in names:
                col_name, col_btn = st.columns([4, 1])
                col_name.code(alias)
                if col_btn.button("מחיקה", key=f"alias-{alias}"):
                    system.remove_alias(alias)
                    flash(f"השם {alias} נמחק מ-{supplier}")
                    st.rerun()
