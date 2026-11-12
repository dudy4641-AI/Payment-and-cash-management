"""Supplier name cleaning and comparison (SPEC section 5).

Cleaning removes company-type suffixes, punctuation, repeated spaces and case
differences. Two names are the same if they are equal after cleaning.
"""

from __future__ import annotations

import re
from enum import Enum

# Company-type suffixes removed from the end of a name.
COMPANY_SUFFIXES = {
    "ltd", "limited", "inc", "incorporated", "co", "corp", "corporation",
    "company", "llc", "plc", "gmbh", "בעמ",
}

_QUOTES = re.compile(r"[\"'`׳״]")  # removed without a gap (בע"מ -> בעמ)
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


def clean_name(name: str) -> str:
    text = _QUOTES.sub("", name.casefold())
    words = _NON_WORD.sub(" ", text).split()
    while words and words[-1] in COMPANY_SUFFIXES:
        words.pop()
    return " ".join(words)


class NameRelation(Enum):
    SAME = "same"  # equal after cleaning
    STARTS_WITH = "starts_with"  # line starts with the supplier name, then more words
    AFTER_OTHER_TEXT = "after_other_text"  # supplier name follows other text


def relation(line_name: str, supplier_name: str) -> NameRelation | None:
    """How a bank line's payee name relates to a supplier name, if at all.
    Both arguments are raw names; they are cleaned here."""
    line, supplier = clean_name(line_name), clean_name(supplier_name)
    if not line or not supplier:
        return None
    if line == supplier:
        return NameRelation.SAME
    if line.startswith(supplier + " "):
        return NameRelation.STARTS_WITH
    if f" {supplier} " in f" {line} ":
        return NameRelation.AFTER_OTHER_TEXT
    return None
