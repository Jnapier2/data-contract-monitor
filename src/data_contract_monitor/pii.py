from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable

import pandas as pd

from .models import PiiSignal


NAME_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"(^|_)(e_?mail|email_?address)($|_)", re.I),
    "phone": re.compile(r"(^|_)(phone|mobile|telephone|cell)($|_)", re.I),
    "government_id": re.compile(r"(^|_)(ssn|social_?security|tax_?id|passport)($|_)", re.I),
    "payment_card": re.compile(r"(^|_)(card_?number|pan|credit_?card)($|_)", re.I),
    "ip_address": re.compile(r"(^|_)(ip|ip_?address)($|_)", re.I),
    "date_of_birth": re.compile(r"(^|_)(dob|birth_?date|date_?of_?birth)($|_)", re.I),
    "address": re.compile(r"(^|_)(street|address|postal|zip_?code)($|_)", re.I),
    "person_name": re.compile(r"(^|_)(first_?name|last_?name|full_?name|surname)($|_)", re.I),
    "account_identifier": re.compile(r"(^|_)(account_?id|customer_?id|member_?id)($|_)", re.I),
}

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SSN_RE = re.compile(r"^\d{3}-?\d{2}-?\d{4}$")
PHONE_RE = re.compile(r"^\+?[\d\s().-]{10,20}$")


def _luhn(value: str) -> bool:
    digits = [int(char) for char in value if char.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _value_detectors() -> dict[str, Callable[[str], bool]]:
    return {
        "email": lambda value: bool(EMAIL_RE.fullmatch(value)),
        "government_id": lambda value: bool(SSN_RE.fullmatch(value)),
        "phone": lambda value: bool(PHONE_RE.fullmatch(value)) and len(re.sub(r"\D", "", value)) >= 10,
        "payment_card": _luhn,
        "ip_address": _is_ip,
    }


def detect_pii(frame: pd.DataFrame, *, sample_limit: int = 200) -> list[PiiSignal]:
    signals: list[PiiSignal] = []
    detectors = _value_detectors()
    for column in frame.columns:
        column_name = str(column)
        categories = {
            category for category, pattern in NAME_PATTERNS.items() if pattern.search(column_name)
        }
        values = frame[column].dropna().astype(str).head(sample_limit)
        sample_size = len(values)
        value_matches: dict[str, int] = {}
        for category, detector in detectors.items():
            count = sum(1 for value in values if detector(value.strip()))
            if count:
                categories.add(category)
                value_matches[category] = count
        for category in sorted(categories):
            name_signal = bool(NAME_PATTERNS.get(category) and NAME_PATTERNS[category].search(column_name))
            matches = value_matches.get(category, 0)
            ratio = matches / sample_size if sample_size else 0.0
            confidence = "high" if name_signal and ratio >= 0.5 else "medium" if name_signal or ratio >= 0.5 else "low"
            signals.append(
                PiiSignal(
                    column=column_name,
                    category=category,
                    confidence=confidence,
                    name_signal=name_signal,
                    sampled_values=sample_size,
                    matching_values=matches,
                    match_ratio=round(ratio, 4),
                )
            )
    return signals
