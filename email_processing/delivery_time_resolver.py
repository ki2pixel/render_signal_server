"""
email_processing.delivery_time_resolver
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Résolution des créneaux de livraison des missions « Média Solution - Missions Recadrage ».

Une cible extraite hors de la fenêtre horaire d'activité (ex: 21h00 ou 00h25 pour une
fenêtre 09h30-19h00) est reportée au prochain matin ouvré à 09h00. Le samedi est
considéré comme ouvré, le dimanche est exclu. Les jours fériés ne sont pas gérés.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, tzinfo
from email.utils import parsedate_to_datetime

from utils.time_helpers import parse_time_hhmm

DEFAULT_TARGET_MORNING_TIME = "09h00"
SUNDAY_WEEKDAY = 6

_DATE_TIME_PATTERN = re.compile(
    r"^le\s+(\d{1,2})/(\d{1,2})/(\d{4})\s+(?:à|a)\s+(\d{1,2})[h:](\d{2})$",
    re.IGNORECASE,
)
_TIME_ONLY_PATTERN = re.compile(r"^(\d{1,2})[h:](\d{2})$")
_URGENCE_PATTERN = re.compile(r"\burgence\b", re.IGNORECASE)


def parse_received_datetime(
    raw_value: str | None,
    tz_for_polling: tzinfo | None,
    fallback: datetime,
) -> datetime:
    """Convertit la date brute d'un email (ISO 8601 ou RFC 2822) dans le fuseau de polling."""
    raw = (raw_value or "").strip()
    if not raw:
        return fallback

    parsed = _parse_iso_datetime(raw) or _parse_rfc2822_datetime(raw)
    if parsed is None:
        return fallback
    if tz_for_polling is None:
        return parsed
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz_for_polling)
    return parsed.astimezone(tz_for_polling)


def is_urgent_subject(subject: str | None) -> bool:
    """Indique si le sujet active la règle d'urgence (même mot-clé que le pattern matching)."""
    return bool(_URGENCE_PATTERN.search(subject or ""))


def resolve_recadrage_delivery_time(
    delivery_time_str: str | None,
    *,
    received_dt: datetime,
    window_start: time | None,
    window_end: time | None,
    target_morning_time: str = DEFAULT_TARGET_MORNING_TIME,
    is_urgent: bool = False,
) -> str | None:
    """Reporte une livraison hors fenêtre au prochain matin ouvré.

    La chaîne d'origine est retournée sans modification lorsque la cible est dans
    ``[window_start, window_end)``, lorsque la fenêtre est absente ou invalide,
    lorsque le format est inconnu ou lorsque le sujet est urgent. Les fenêtres
    traversant minuit ne sont volontairement pas ajustées.
    """
    if not delivery_time_str or is_urgent:
        return delivery_time_str

    parsed_target = _parse_delivery_time(delivery_time_str, received_dt.date())
    morning = parse_time_hhmm(target_morning_time)
    if parsed_target is None or morning is None:
        return delivery_time_str
    if window_start is None or window_end is None or window_start >= window_end:
        return delivery_time_str

    target_date, target_time = parsed_target
    if _is_time_within_window(target_time, window_start, window_end):
        return delivery_time_str

    next_date = _next_open_morning_date(
        target_date=target_date,
        target_time=target_time,
        window_end=window_end,
        morning=morning,
        received_dt=received_dt,
    )
    return f"le {next_date:%d/%m/%Y} à {morning.hour:02d}h{morning.minute:02d}"


def _parse_iso_datetime(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _parse_rfc2822_datetime(raw: str) -> datetime | None:
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None


def _parse_delivery_time(value: str, received_date: date) -> tuple[date, time] | None:
    text = value.strip()
    date_match = _DATE_TIME_PATTERN.match(text)
    if date_match:
        day, month, year, hour, minute = (int(part) for part in date_match.groups())
        try:
            return date(year, month, day), time(hour, minute)
        except ValueError:
            return None

    time_match = _TIME_ONLY_PATTERN.match(text)
    if not time_match:
        return None
    try:
        target_time = time(int(time_match.group(1)), int(time_match.group(2)))
    except ValueError:
        return None
    return received_date, target_time


def _is_time_within_window(target: time, start: time, end: time) -> bool:
    return start <= target < end


def _next_open_morning_date(
    *,
    target_date: date,
    target_time: time,
    window_end: time,
    morning: time,
    received_dt: datetime,
) -> date:
    candidate = target_date + timedelta(days=1) if target_time >= window_end else target_date
    while True:
        morning_dt = datetime.combine(candidate, morning, tzinfo=received_dt.tzinfo)
        if morning_dt > received_dt and candidate.weekday() != SUNDAY_WEEKDAY:
            return candidate
        candidate += timedelta(days=1)
