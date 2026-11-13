"""
Tests de l'ajustement des livraisons « Missions Recadrage » hors fenêtre horaire.

Couvre le resolver pur, le parsing de la date de réception et le câblage dans
l'ingress Gmail Push et l'orchestrateur IMAP.
"""
from __future__ import annotations

import email
from datetime import datetime, time
from email import policy
from email.utils import parsedate_to_datetime
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from email_processing import orchestrator as orchestrator_module
from email_processing import pattern_matching
from email_processing.delivery_time_resolver import (
    is_urgent_subject,
    parse_received_datetime,
    resolve_recadrage_delivery_time,
)

MAILS_DIR = Path(__file__).resolve().parents[2] / "debug" / "mails"
TZ = ZoneInfo("Europe/Paris")
WINDOW_START = time(9, 30)
WINDOW_END = time(19, 0)
RECEIVED_AFTERNOON = datetime(2026, 11, 9, 15, 0, tzinfo=TZ)


def _load_eml(filename: str) -> tuple[str, str, datetime]:
    """Charge un email réel et retourne (sujet, corps texte, date de réception locale)."""
    raw = (MAILS_DIR / filename).read_bytes()
    message = email.message_from_bytes(raw, policy=policy.default)
    subject = message.get("Subject") or ""
    body = "\n".join(
        part.get_content()
        for part in message.walk()
        if part.get_content_type() in ("text/plain", "text/html")
    )
    received = parsedate_to_datetime(message.get("Date")).astimezone(TZ)
    return subject, body, received


def _resolve(
    delivery_time_str: str | None,
    received_dt: datetime = RECEIVED_AFTERNOON,
    *,
    window_start: time | None = WINDOW_START,
    window_end: time | None = WINDOW_END,
    is_urgent: bool = False,
) -> str | None:
    return resolve_recadrage_delivery_time(
        delivery_time_str,
        received_dt=received_dt,
        window_start=window_start,
        window_end=window_end,
        is_urgent=is_urgent,
    )


@pytest.mark.unit
def test_lot_113_evening_delivery_is_reported_to_next_morning(mock_logger):
    # Given: le lot 113, reçu le 09/11 après-midi, demande une livraison à 21h00
    subject, body, received = _load_eml("Média Solution - Missions Recadrage - Lot 113.eml")
    extracted = pattern_matching.check_media_solution_pattern(subject, body, TZ, mock_logger)

    # When: le créneau est résolu pour la fenêtre 09h30-19h00
    adjusted = _resolve(extracted["delivery_time"], received)

    # Then: l'engagement est reporté au mardi 10/11 à 09h00
    assert extracted["delivery_time"] == "21h00"
    assert adjusted == "le 10/11/2026 à 09h00"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("filename", "expected_raw"),
    [
        ("Média Solution - Missions Recadrage - Lot 114.eml", "le 10/11/2026 à 00h25"),
        ("Média Solution - Missions Recadrage - Lot 115.eml", "le 10/11/2026 à 00h40"),
        ("Média Solution - Missions Recadrage - Lot 116.eml", "le 10/11/2026 à 00h30"),
        ("Média Solution - Missions Recadrage - Lot 117.eml", "le 10/11/2026 à 00h55"),
    ],
)
def test_lots_114_to_117_night_deliveries_keep_target_date(filename, expected_raw, mock_logger):
    # Given: les lots 114 à 117 demandent une livraison nocturne le 10/11/2026
    subject, body, received = _load_eml(filename)
    extracted = pattern_matching.check_media_solution_pattern(subject, body, TZ, mock_logger)

    # When: le créneau est résolu pour la fenêtre 09h30-19h00
    adjusted = _resolve(extracted["delivery_time"], received)

    # Then: la date cible est conservée, l'heure est ramenée à 09h00
    assert extracted["delivery_time"] == expected_raw
    assert adjusted == "le 10/11/2026 à 09h00"


@pytest.mark.unit
@pytest.mark.parametrize("raw_value", ["16h00", "le 10/11/2026 à 16h00"])
def test_in_window_delivery_is_unchanged(raw_value):
    # Given: une livraison en journée dans la fenêtre 09h30-19h00
    # When: le créneau est résolu
    adjusted = _resolve(raw_value)

    # Then: la chaîne d'origine est conservée telle quelle
    assert adjusted == raw_value


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("09h30", "09h30"),
        ("19h00", "le 10/11/2026 à 09h00"),
    ],
)
def test_window_boundaries_are_respected(raw_value, expected):
    # Given: une cible exactement sur la borne d'ouverture ou de fermeture
    # When: le créneau est résolu
    adjusted = _resolve(raw_value)

    # Then: l'ouverture est inclusive, la fermeture est exclusive
    assert adjusted == expected


@pytest.mark.unit
def test_urgence_subject_is_never_adjusted():
    # Given: un sujet urgent et un créneau nocturne
    subject = "Média Solution - Missions Recadrage - Lot 5 - URGENCE"

    # When: la règle d'urgence est évaluée puis le créneau résolu
    urgent = is_urgent_subject(subject)
    adjusted = _resolve("21h00", is_urgent=urgent)

    # Then: l'urgence est détectée et le créneau reste inchangé
    assert urgent is True
    assert is_urgent_subject("Média Solution - Missions Recadrage - Lot 5") is False
    assert adjusted == "21h00"


@pytest.mark.unit
def test_year_rollover_is_supported():
    # Given: une cible le soir du 31/12/2026
    received = datetime(2026, 12, 31, 15, 0, tzinfo=TZ)

    # When: le créneau est résolu
    adjusted = _resolve("le 31/12/2026 à 22h00", received)

    # Then: l'engagement est reporté au 01/01/2027 à 09h00
    assert adjusted == "le 01/01/2027 à 09h00"


@pytest.mark.unit
def test_friday_evening_rolls_to_saturday_morning():
    # Given: un email reçu le vendredi 13/11/2026 avec une cible à 21h00
    received = datetime(2026, 11, 13, 15, 0, tzinfo=TZ)

    # When: le créneau est résolu
    adjusted = _resolve("21h00", received)

    # Then: le samedi est ouvré, la cible est le samedi 14/11 à 09h00
    assert adjusted == "le 14/11/2026 à 09h00"


@pytest.mark.unit
def test_saturday_evening_rolls_to_monday_morning():
    # Given: un email reçu le samedi 14/11/2026 avec une cible à 21h00
    received = datetime(2026, 11, 14, 15, 0, tzinfo=TZ)

    # When: le créneau est résolu
    adjusted = _resolve("21h00", received)

    # Then: le dimanche est exclu, la cible est le lundi 16/11 à 09h00
    assert adjusted == "le 16/11/2026 à 09h00"


@pytest.mark.unit
def test_sunday_night_target_rolls_to_monday_morning():
    # Given: une cible le dimanche 15/11/2026 à 00h25
    received = datetime(2026, 11, 13, 15, 0, tzinfo=TZ)

    # When: le créneau est résolu
    adjusted = _resolve("le 15/11/2026 à 00h25", received)

    # Then: le dimanche est exclu, la cible est le lundi 16/11 à 09h00
    assert adjusted == "le 16/11/2026 à 09h00"


@pytest.mark.unit
def test_future_sunday_evening_rolls_to_monday_morning():
    # Given: une cible le dimanche 15/11/2026 à 21h00
    # When: le créneau est résolu
    adjusted = _resolve("le 15/11/2026 à 21h00")

    # Then: le jour suivant est un dimanche exclu, la cible est le lundi 16/11
    assert adjusted == "le 16/11/2026 à 09h00"


@pytest.mark.unit
def test_past_in_window_delivery_is_left_unchanged():
    # Given: un email reçu à 15h00 demandant une livraison à 10h00 (déjà passée)
    # When: le créneau est résolu
    adjusted = _resolve("10h00", RECEIVED_AFTERNOON)

    # Then: le comportement reste inchangé (hors périmètre de la mission)
    assert adjusted == "10h00"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("window_start", "window_end"),
    [(None, None), (WINDOW_START, None), (None, WINDOW_END), (time(19, 0), time(9, 30))],
)
def test_missing_or_wrapping_window_is_not_adjusted(window_start, window_end):
    # Given: une fenêtre absente, partielle ou traversant minuit
    # When: le créneau est résolu
    adjusted = _resolve("21h00", window_start=window_start, window_end=window_end)

    # Then: le comportement d'origine est conservé
    assert adjusted == "21h00"


@pytest.mark.unit
@pytest.mark.parametrize("raw_value", ["URGENCE", "demain", "le 31/02/2026 à 22h00", "25h00", ""])
def test_unknown_or_invalid_delivery_time_is_unchanged(raw_value):
    # Given: une valeur non reconnue ou une date impossible
    # When: le créneau est résolu
    adjusted = _resolve(raw_value)

    # Then: la valeur d'origine est retournée sans erreur
    assert adjusted == raw_value


@pytest.mark.unit
def test_parse_received_datetime_handles_naive_values_and_missing_timezone():
    # Given: une date ISO sans fuseau et une date ISO avec fuseau
    fallback = datetime(2026, 1, 1, tzinfo=TZ)

    # When: le parsing est tenté avec ou sans fuseau de polling
    naive = parse_received_datetime("2026-11-09T14:17:30", TZ, fallback)
    without_tz = parse_received_datetime("2026-11-09T13:17:30Z", None, fallback)

    # Then: la date naïve reçoit le fuseau de polling, l'autre reste intacte
    assert naive == datetime(2026, 11, 9, 14, 17, 30, tzinfo=TZ)
    assert without_tz.utcoffset() is not None
    assert without_tz.hour == 13


@pytest.mark.unit
def test_parse_received_datetime_supports_iso_and_rfc2822():
    # Given: les deux formats émis par Apps Script et par IMAP
    fallback = datetime(2026, 1, 1, tzinfo=TZ)

    # When: les dates sont converties dans le fuseau de polling
    from_iso = parse_received_datetime("2026-11-09T13:17:30Z", TZ, fallback)
    from_rfc = parse_received_datetime("Mon, 09 Nov 2026 14:17:30 +0100", TZ, fallback)

    # Then: les deux représentent le 09/11/2026 à 14h17 Europe/Paris
    expected = datetime(2026, 11, 9, 14, 17, 30, tzinfo=TZ)
    assert from_iso == expected
    assert from_rfc == expected


@pytest.mark.unit
def test_parse_received_datetime_falls_back_on_missing_or_invalid_value():
    # Given: une date absente ou illisible
    fallback = datetime(2026, 1, 1, tzinfo=TZ)

    # When: le parsing est tenté
    missing = parse_received_datetime(None, TZ, fallback)
    invalid = parse_received_datetime("not-a-date", TZ, fallback)

    # Then: le fallback local est utilisé
    assert missing == fallback
    assert invalid == fallback


@pytest.mark.unit
def test_ingress_helper_adjusts_delivery_time_before_payload(monkeypatch):
    # Given: la fenêtre globale 09h30-19h00 et un email reçu le 09/11 à 14h00 Paris
    from services.ingress_service import IngressService

    service = IngressService(logger=MagicMock())
    monkeypatch.setattr(
        "services.ingress_service.email_orchestrator._load_webhook_global_time_window",
        lambda: ("09:30", "19:00"),
    )

    # When: l'ingress résout le créneau du lot 113
    adjusted = service._resolve_recadrage_delivery_time(
        "21h00",
        subject="Média Solution - Missions Recadrage - Lot 113",
        email_date="2026-11-09T13:00:00Z",
        now_local=datetime(2026, 11, 9, 15, 0, tzinfo=TZ),
    )

    # Then: le payload recevra la livraison reportée au 10/11 à 09h00
    assert adjusted == "le 10/11/2026 à 09h00"
    service._logger.info.assert_called_once()


@pytest.mark.unit
def test_ingress_helper_preserves_urgent_delivery_time(monkeypatch):
    # Given: la même fenêtre mais un sujet URGENCE
    from services.ingress_service import IngressService

    service = IngressService(logger=MagicMock())
    monkeypatch.setattr(
        "services.ingress_service.email_orchestrator._load_webhook_global_time_window",
        lambda: ("09:30", "19:00"),
    )

    # When: l'ingress résout le créneau
    adjusted = service._resolve_recadrage_delivery_time(
        "21h00",
        subject="Média Solution - Missions Recadrage - Lot 5 - URGENCE",
        email_date="2026-11-09T13:00:00Z",
        now_local=datetime(2026, 11, 9, 15, 0, tzinfo=TZ),
    )

    # Then: la règle d'urgence prime et la valeur reste inchangée
    assert adjusted == "21h00"


@pytest.mark.unit
def test_orchestrator_helper_adjusts_before_payload(mock_logger):
    # Given: un email IMAP reçu le 09/11 et le détecteur recadrage
    # When: l'orchestrateur résout le créneau avant de construire le payload
    adjusted = orchestrator_module._resolve_out_of_window_delivery_time(
        "recadrage",
        "21h00",
        "Média Solution - Missions Recadrage - Lot 113",
        "Mon, 09 Nov 2026 14:17:30 +0100",
        "09:30",
        "19:00",
        datetime(2026, 11, 9, 15, 0, tzinfo=TZ),
        mock_logger,
    )

    # Then: l'engagement est reporté au 10/11 à 09h00
    assert adjusted == "le 10/11/2026 à 09h00"
    mock_logger.info.assert_called_once()


@pytest.mark.unit
def test_orchestrator_helper_leaves_other_detectors_untouched(mock_logger):
    # Given: un email classé DESABO avec un créneau hors fenêtre
    # When: l'orchestrateur tente de résoudre le créneau
    adjusted = orchestrator_module._resolve_out_of_window_delivery_time(
        "desabonnement_journee_tarifs",
        "21h00",
        "Média Solution - Missions de recadrage 29/09",
        "Mon, 09 Nov 2026 14:17:30 +0100",
        "09:30",
        "19:00",
        datetime(2026, 11, 9, 15, 0, tzinfo=TZ),
        mock_logger,
    )

    # Then: les autres flux ne sont jamais modifiés
    assert adjusted == "21h00"
