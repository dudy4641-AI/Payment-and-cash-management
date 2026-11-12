"""Deterministic mock data for the five metrics in SPEC section 8.

Every case is labelled with its expected outcome in advance, so the tests
compare the system against a known answer. Nothing here is random.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal as D

from .models import (
    Bank,
    BankKind,
    DocType,
    DocumentUpload,
    Entity,
    StatementEntry,
    Supplier,
)

STATEMENT_DATE = date(2026, 11, 10)

# --- Company: two entities, Leumi + Chase + a card platform, USD only ------

BANKS: list[Bank] = [
    Bank("leumi", "לאומי", Entity.IL, BankKind.BANK, D("250000.00")),
    Bank("chase", "צ'ייס", Entity.US, BankKind.BANK, D("1200000.00")),
    Bank("cards", "פלטפורמת כרטיסים", Entity.US, BankKind.CARD_PLATFORM, D("50000.00")),
]

# Bank used for each entity when the CFO picks the right one.
CORRECT_BANK = {Entity.IL: "leumi", Entity.US: "chase"}

SUPPLIERS: list[Supplier] = [
    # Israeli entity
    Supplier("Shapira Legal", Entity.IL, "משפטי"),
    Supplier("Negev Office Rent", Entity.IL, "שכירות"),
    Supplier("Carmel IT Services", Entity.IL, "מחשוב"),
    Supplier("Galil Catering", Entity.IL, "רווחה"),
    Supplier("Yarkon Cleaning", Entity.IL, "תחזוקה"),
    Supplier("Initech Israel", Entity.IL, "מחשוב"),
    Supplier("Tavor Translations", Entity.IL, "שיווק"),
    Supplier("Hermon Insurance", Entity.IL, "ביטוח"),
    # US entity
    Supplier("Acme Cloud", Entity.US, "מחשוב"),
    Supplier("Globex Ltd", Entity.US, "שיווק"),
    Supplier("Hooli Analytics", Entity.US, "מחשוב"),
    Supplier("Umbrella Security", Entity.US, "אבטחת מידע"),
    Supplier("Stark Hardware", Entity.US, "ציוד"),
    Supplier("Wayne Consulting", Entity.US, "ייעוץ"),
    Supplier("Initrode Inc", Entity.US, "מחשוב"),
    Supplier("Soylent Foods", Entity.US, "רווחה"),
    Supplier("Vandelay Imports", Entity.US, "ציוד"),
    Supplier("Cyberdyne Systems", Entity.US, "מחשוב"),
]

SUPPLIER_BY_NAME = {s.name: s for s in SUPPLIERS}


def correct_bank(supplier_name: str) -> str:
    return CORRECT_BANK[SUPPLIER_BY_NAME[supplier_name].entity]


def _inv(supplier: str, amount: str, number: str) -> DocumentUpload:
    return DocumentUpload(DocType.TAX_INVOICE, supplier, D(amount), number)


def _dem(supplier: str, amount: str, number: str) -> DocumentUpload:
    return DocumentUpload(DocType.PAYMENT_DEMAND, supplier, D(amount), number)


def _line(payee: str, amount: str) -> StatementEntry:
    return StatementEntry(payee, D(amount), STATEMENT_DATE)


# --- Metric 1: list completeness -------------------------------------------


@dataclass
class CompletenessScenario:
    uploads: list[DocumentUpload]
    expected_count: int


def completeness_scenario() -> CompletenessScenario:
    uploads = [
        _inv("Shapira Legal", "4200.00", "C-101"),
        _dem("Negev Office Rent", "18500.00", "C-102"),
        _inv("Carmel IT Services", "2340.50", "C-103"),
        _inv("Galil Catering", "1875.25", "C-104"),
        _dem("Yarkon Cleaning", "960.00", "C-105"),
        _inv("Initech Israel", "3100.00", "C-106"),
        _inv("Tavor Translations", "640.00", "C-107"),
        _dem("Hermon Insurance", "2210.40", "C-108"),
        _inv("Acme Cloud", "3600.00", "C-109"),
        _inv("Globex Ltd", "750.00", "C-110"),
        _dem("Hooli Analytics", "7800.00", "C-111"),
        _inv("Umbrella Security", "5250.75", "C-112"),
        _inv("Stark Hardware", "12999.99", "C-113"),
        _dem("Wayne Consulting", "15000.00", "C-114"),
        _inv("Initrode Inc", "2450.00", "C-115"),
        _inv("Soylent Foods", "1320.10", "C-116"),
        _dem("Vandelay Imports", "4875.00", "C-117"),
        _inv("Cyberdyne Systems", "9100.00", "C-118"),
        _inv("Acme Cloud", "1000.00", "C-119"),
        _inv("Hooli Analytics", "830.00", "C-120"),
    ]
    return CompletenessScenario(uploads=uploads, expected_count=20)


# --- Metric 2: matching ----------------------------------------------------

MATCHED = "matched"
MISSING = "missing_invoice"
REVIEW = "needs_review"


@dataclass(frozen=True)
class LabelledLine:
    bank_code: str
    entry: StatementEntry
    expected: str  # MATCHED, MISSING or REVIEW
    # For MATCHED: the document(s) this line may be matched to. When two
    # identical lines share two candidates, each must get a different one.
    # For REVIEW: the candidate documents (none of them may be matched).
    doc_numbers: tuple[str, ...] = ()
    note: str = ""  # why this line gets its expected result, for the review file


@dataclass
class MatchingScenario:
    uploads: list[DocumentUpload]  # all approved with the correct bank
    lines: list[LabelledLine]
    expected_matched: int = 12
    expected_missing: int = 5
    expected_review: int = 3


def matching_scenario() -> MatchingScenario:
    def plain(supplier, amount, number):
        """An ordinary case: exact name and amount, one payment, one line."""
        uploads.append(_inv(supplier, amount, number))
        lines.append(LabelledLine(correct_bank(supplier), _line(supplier, amount), MATCHED, (number,)))

    uploads: list[DocumentUpload] = []
    lines: list[LabelledLine] = []

    plain("Shapira Legal", "4200.00", "M-201")
    plain("Negev Office Rent", "18500.00", "M-202")
    plain("Carmel IT Services", "2340.50", "M-203")
    plain("Galil Catering", "1875.25", "M-204")
    plain("Yarkon Cleaning", "960.00", "M-205")
    plain("Initech Israel", "3100.00", "M-206")
    plain("Hooli Analytics", "7800.00", "M-207")

    # Doubt: the line starts with the supplier name, but two approved payments fit.
    uploads += [_inv("Umbrella Security", "5250.75", "M-208"),
                _inv("Umbrella Security", "5250.75", "M-217")]
    lines.append(LabelledLine("chase", _line("UMBRELLA SECURITY SERVICES", "5250.75"), REVIEW,
                              ("M-208", "M-217"),
                              "מתחיל בשם הספק, אבל יש שני תשלומים מאושרים שמתאימים"))

    # Automatic: the line starts with the supplier name, one approved payment fits.
    uploads.append(_inv("Stark Hardware", "12999.99", "M-209"))
    lines.append(LabelledLine("chase", _line("STARK HARDWARE SUPPLY CO", "12999.99"), MATCHED,
                              ("M-209",), "מתחיל בשם הספק, תשלום מאושר יחיד: שיוך אוטומטי"))

    # Doubt: supplier name after other text (a payment service). See ALIAS_CASE.
    uploads.append(_inv("Wayne Consulting", "15000.00", "M-210"))
    lines.append(LabelledLine("chase", _line("PAYPAL *WAYNE CONSULTING", "15000.00"), REVIEW,
                              ("M-210",), "שם הספק אחרי שירות תשלומים: בירור בפעם הראשונה"))

    # Doubt: same supplier and amount, two approved payments but one line.
    uploads += [_inv("Initrode Inc", "2450.00", "M-211"), _inv("Initrode Inc", "2450.00", "M-216")]
    lines.append(LabelledLine("chase", _line("Initrode Inc", "2450.00"), REVIEW, ("M-211", "M-216"),
                              "שני תשלומים מאושרים לאותו ספק באותו סכום, ותנועה אחת"))

    plain("Acme Cloud", "3600.00", "M-212")

    # Automatic: same supplier and amount, two payments and two lines. Each line
    # is matched to a different one of the two documents.
    uploads += [_inv("Acme Cloud", "1000.00", "M-213"), _inv("Acme Cloud", "1000.00", "M-214")]
    lines += [
        LabelledLine("chase", _line("Acme Cloud", "1000.00"), MATCHED, ("M-213", "M-214"),
                     "שני תשלומים ושתי תנועות: שיוך אוטומטי"),
        LabelledLine("chase", _line("Acme Cloud", "1000.00"), MATCHED, ("M-213", "M-214"),
                     "שני תשלומים ושתי תנועות: שיוך אוטומטי"),
    ]

    # Automatic: name equal after cleaning ("GLOBEX, LTD." -> "globex" <- "Globex Ltd").
    uploads.append(_inv("Globex Ltd", "750.00", "M-215"))
    lines.append(LabelledLine("chase", _line("GLOBEX, LTD.", "750.00"), MATCHED, ("M-215",),
                              "זהה ל-Globex Ltd אחרי ניקוי: שיוך אוטומטי"))

    # Missing invoice: lines that never went through the system.
    lines += [
        LabelledLine("leumi", _line("Bezeq International", "349.90"), MISSING,
                     note="ספק שלא עבר דרך המערכת"),
        # Known supplier, but no approved payment for this amount.
        LabelledLine("leumi", _line("Initech Israel", "1250.00"), MISSING,
                     note="ספק מוכר, אבל אין תשלום מאושר בסכום הזה"),
        LabelledLine("chase", _line("Zoom Video", "149.90"), MISSING,
                     note="ספק שלא עבר דרך המערכת"),
        LabelledLine("chase", _line("Delta Air Lines", "1284.60"), MISSING,
                     note="ספק שלא עבר דרך המערכת"),
        # One cent off an approved Hooli payment: must not be matched to it.
        LabelledLine("chase", _line("Hooli Analytics", "7800.01"), MISSING,
                     note="סנט אחד יותר מתשלום מאושר (M-207): אסור לשייך"),
    ]
    return MatchingScenario(uploads=uploads, lines=lines)


@dataclass(frozen=True)
class AliasCase:
    """Rule (b) follow-up: the bookkeeper confirms a doubtful line, then the
    same bank name in a later statement is matched automatically."""

    confirm_payee: str
    confirm_doc_number: str
    next_upload: DocumentUpload
    next_line: StatementEntry


ALIAS_CASE = AliasCase(
    confirm_payee="PAYPAL *WAYNE CONSULTING",
    confirm_doc_number="M-210",
    next_upload=_inv("Wayne Consulting", "4125.00", "M-218"),
    next_line=StatementEntry("PAYPAL *WAYNE CONSULTING", D("4125.00"), date(2026, 11, 17)),
)


# --- Metric 3: duplicate payments ------------------------------------------


@dataclass
class DuplicateScenario:
    regular: list[DocumentUpload]  # 12 ordinary tax invoices
    demand_pairs: list[tuple[DocumentUpload, DocumentUpload]]  # (demand, later tax invoice)
    duplicates: list[DocumentUpload]  # 4 documents, each uploaded twice
    expected_duplicate_alerts: int = 4
    expected_total_payments: int = 20  # 12 regular + 4 demands + 4 originals


def duplicate_scenario() -> DuplicateScenario:
    regular = [
        _inv("Shapira Legal", "1100.00", "R-301"),
        _inv("Negev Office Rent", "18500.00", "R-302"),
        _inv("Carmel IT Services", "990.90", "R-303"),
        _inv("Galil Catering", "2045.00", "R-304"),
        _inv("Yarkon Cleaning", "960.00", "R-305"),
        _inv("Tavor Translations", "415.50", "R-306"),
        _inv("Hooli Analytics", "6100.00", "R-307"),
        _inv("Umbrella Security", "3300.30", "R-308"),
        _inv("Stark Hardware", "8750.00", "R-309"),
        _inv("Wayne Consulting", "12000.00", "R-310"),
        _inv("Soylent Foods", "1480.75", "R-311"),
        _inv("Cyberdyne Systems", "5025.00", "R-312"),
    ]
    demand_pairs = [
        (_dem("Hermon Insurance", "2210.40", "D-321"), _inv("Hermon Insurance", "2210.40", "T-321")),
        (_dem("Initech Israel", "3400.00", "D-322"), _inv("Initech Israel", "3400.00", "T-322")),
        (_dem("Acme Cloud", "2700.00", "D-323"), _inv("Acme Cloud", "2700.00", "T-323")),
        (_dem("Vandelay Imports", "4875.00", "D-324"), _inv("Vandelay Imports", "4875.00", "T-324")),
    ]
    duplicates = [
        _inv("Globex Ltd", "1950.00", "X-331"),
        _inv("Initrode Inc", "2450.00", "X-332"),
        _inv("Shapira Legal", "4200.00", "X-333"),
        _inv("Galil Catering", "1875.25", "X-334"),
    ]
    return DuplicateScenario(regular=regular, demand_pairs=demand_pairs, duplicates=duplicates)


# --- Metric 4: wrong bank --------------------------------------------------


@dataclass
class WrongBankScenario:
    wrong: list[tuple[DocumentUpload, str]]  # supplier entity differs from bank entity
    control: list[tuple[DocumentUpload, str]]  # paid from the right bank
    expected_alerts: int = 4


def wrong_bank_scenario() -> WrongBankScenario:
    return WrongBankScenario(
        wrong=[
            (_inv("Initrode Inc", "3200.00", "W-401"), "leumi"),
            (_inv("Stark Hardware", "1150.00", "W-402"), "leumi"),
            # Israeli supplier paid from Chase (US entity).
            (_inv("Tavor Translations", "1340.00", "W-406"), "chase"),
            (_inv("Hermon Insurance", "2980.00", "W-407"), "chase"),
        ],
        control=[
            (_inv("Shapira Legal", "2600.00", "W-403"), "leumi"),
            (_inv("Hooli Analytics", "4400.00", "W-404"), "chase"),
            (_inv("Wayne Consulting", "780.00", "W-405"), "cards"),
        ],
    )


# --- Metric 5: balances (Leumi and Chase only) -----------------------------


@dataclass
class BankBalanceCase:
    bank_code: str
    opening_balance: D
    cleared: list[DocumentUpload]  # approved and appear in the statement
    pending: list[DocumentUpload]  # approved, not yet in the statement
    expected_current: D  # fixed in advance, to the cent
    expected_expected: D


@dataclass
class BalanceScenario:
    cases: list[BankBalanceCase] = field(default_factory=list)


def balance_scenario() -> BalanceScenario:
    leumi = BankBalanceCase(
        bank_code="leumi",
        opening_balance=D("250000.00"),
        cleared=[
            _inv("Shapira Legal", "12345.67", "B-501"),
            _inv("Negev Office Rent", "8910.11", "B-502"),
            _inv("Carmel IT Services", "4321.09", "B-503"),
        ],
        pending=[
            _inv("Galil Catering", "7654.32", "B-504"),
            _inv("Yarkon Cleaning", "1000.01", "B-505"),
        ],
        expected_current=D("224423.13"),
        expected_expected=D("215768.80"),
    )
    chase = BankBalanceCase(
        bank_code="chase",
        opening_balance=D("1200000.00"),
        cleared=[
            _inv("Hooli Analytics", "45000.50", "B-511"),
            _inv("Umbrella Security", "17250.25", "B-512"),
            _inv("Stark Hardware", "3333.33", "B-513"),
        ],
        pending=[
            _inv("Wayne Consulting", "22222.22", "B-514"),
            _inv("Initrode Inc", "9999.99", "B-515"),
        ],
        expected_current=D("1134415.92"),
        expected_expected=D("1102193.71"),
    )
    return BalanceScenario(cases=[leumi, chase])
