"""Tests du backfill rétro-actif des missions de recadrage."""

from __future__ import annotations

import argparse
import json
import logging
import tarfile
import zipfile
from datetime import datetime, time
from email import policy
from email.parser import BytesParser
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts import backfill_recadrage_emails as backfill

REPO_ROOT = Path(__file__).resolve().parents[1]
MBOX_PATH = REPO_ROOT / "debug" / "mails" / "a_exporter.mbox"
LOT_115_EML = (
    REPO_ROOT / "debug" / "mails" / "Média Solution - Missions Recadrage - Lot 115.eml"
)
TZ = ZoneInfo("Europe/Luxembourg")
WINDOW_START = datetime(2026, 10, 23, tzinfo=TZ)
WINDOW_END = datetime(2026, 11, 12, 10, 46, 17, tzinfo=TZ)
LOT_115_URL = (
    "https://www.dropbox.com/scl/fo/8fhbn0o0b23imzxkctn6w/"
    "AC1xzT9OFil81C4obJxm1qw?rlkey=vlb6pz2btt3gzqq27bwlkh9m6&dl=0"
)


@pytest.fixture(scope="module")
def extracted_missions() -> list[backfill.Mission]:
    """Extrait une seule fois les missions de la fenêtre de référence."""
    if not MBOX_PATH.is_file():
        pytest.skip("mbox d'archive absent")
    logger = logging.getLogger("test_backfill")
    logger.setLevel(logging.CRITICAL)
    return backfill.extract_missions_from_mbox(
        MBOX_PATH,
        since=WINDOW_START,
        until=WINDOW_END,
        tz=TZ,
        window_start=time(10, 30),
        window_end=time(19, 0),
        logger=logger,
    )


@pytest.fixture
def lot_115_mission(extracted_missions: list[backfill.Mission]) -> backfill.Mission:
    """Retourne la mission du lot 115 du 9 novembre 2026."""
    for mission in extracted_missions:
        if mission.lot == 115:
            return mission
    pytest.fail("Lot 115 absent du mbox")


@pytest.fixture
def lot_115_links() -> list[dict[str, str]]:
    """Paire R2 connue pour le lot 115."""
    return [
        {
            "source_url": LOT_115_URL,
            "r2_url": (
                "https://server.kidpixel.workers.dev/dropbox/" "352ef810/1ef2a04f/file"
            ),
            "provider": "dropbox",
            "original_filename": "115 Camille.zip",
        }
    ]


@pytest.mark.integration
def test_extract_lot_115_from_mbox(
    extracted_missions: list[backfill.Mission],
) -> None:
    # Given: la fenêtre 30 jours s'arrête juste avant le lot 166
    # When: le mbox est filtré
    # Then: 62 missions historiques sont extraites, dont le lot 115
    assert len(extracted_missions) == 62
    lot_115 = next(mission for mission in extracted_missions if mission.lot == 115)
    assert lot_115.message_index == 41
    assert lot_115.received_at.isoformat() == "2026-11-09T15:06:51+01:00"
    assert lot_115.subject == "Média Solution - Missions Recadrage - Lot 115"
    assert lot_115.sender_email == "technique@media-solution.fr"
    assert "Recadrage 9:16 standard" in lot_115.body_text
    assert any("dropbox.com/scl/fo" in link["raw_url"] for link in lot_115.raw_links)
    assert lot_115.delivery_time == "le 10/11/2026 à 09h00"
    assert lot_115.urgent is False
    assert all(mission.delivery_time for mission in extracted_missions)


@pytest.mark.integration
def test_mbox_window_boundaries(
    extracted_missions: list[backfill.Mission],
) -> None:
    # Given: les missions triées par date croissante
    # When: on inspecte les bornes
    # Then: le lot 166 (déjà live) est exclu et les bornes sont correctes
    assert extracted_missions[0].lot == 268
    assert extracted_missions[0].received_at.isoformat() == "2026-10-23T09:49:59+02:00"
    assert extracted_missions[-1].lot == 158
    assert all(mission.lot != 166 for mission in extracted_missions)
    assert all(
        WINDOW_START <= mission.received_at < WINDOW_END
        for mission in extracted_missions
    )


@pytest.mark.unit
def test_deadline_and_urgency_detection(
    extracted_missions: list[backfill.Mission],
) -> None:
    # Given: trois missions aux profils différents
    by_lot = {mission.lot: mission for mission in extracted_missions}
    # When: on lit leurs créneaux
    # Then: la deadline hors fenêtre est reportée et l'urgence est conservée
    assert by_lot[115].delivery_time_raw == "le 10/11/2026 à 00h40"
    assert by_lot[115].delivery_time == "le 10/11/2026 à 09h00"
    assert by_lot[115].urgent is False

    assert by_lot[276].urgent is True
    assert by_lot[276].delivery_time == "15h00"

    assert by_lot[286].urgent is True
    assert by_lot[286].delivery_time == "11h30"


@pytest.mark.unit
def test_detail_schema_matches_email_storage_logger(
    lot_115_mission: backfill.Mission,
    lot_115_links: list[dict[str, str]],
) -> None:
    # Given: la mission 115 et sa paire R2
    links_index = backfill.build_links_index(lot_115_links)
    links = backfill.sanitize_delivery_links(lot_115_mission.raw_links, links_index)
    # When: le fichier détail est construit
    detail = backfill.build_detail_entry(
        lot_115_mission,
        stored_at=datetime(2026, 11, 22, 12, 0, tzinfo=TZ),
        delivery_links=links,
    )
    # Then: le schéma et les métadonnées sont conformes au stockage PHP
    assert set(detail) == {
        "schema_version",
        "id",
        "lot",
        "subject",
        "received_at",
        "stored_at",
        "deadline",
        "urgent",
        "sender_masked",
        "snippet",
        "body_html",
        "body_text",
        "body_omitted",
        "body_size_bytes",
        "delivery_links",
        "email_id_hash",
        "source",
    }
    assert detail["schema_version"] == 1
    assert detail["id"] == "recadrage_lot_115_20261109"
    assert detail["lot"] == 115
    assert detail["received_at"] == "2026-11-09T15:06:51+01:00"
    assert detail["sender_masked"] == "t***@media-solution.fr"
    assert detail["body_html"].startswith("<div")
    assert detail["body_text"].startswith("Voici les missions pour le lot 115.")
    assert detail["body_omitted"] is False
    assert detail["body_size_bytes"] > 0
    assert detail["email_id_hash"].startswith("sha256:")
    assert len(detail["email_id_hash"]) == 71
    assert detail["delivery_links"][0]["r2_url"].startswith(
        "https://server.kidpixel.workers.dev/"
    )
    assert detail["delivery_links"][0]["original_filename"] == "115 Camille.zip"


@pytest.mark.unit
def test_index_entry_schema_and_size(
    tmp_path: Path,
    lot_115_mission: backfill.Mission,
) -> None:
    # Given: un fichier détail écrit sur disque
    detail = backfill.build_detail_entry(
        lot_115_mission,
        stored_at=datetime(2026, 11, 22, 12, 0, tzinfo=TZ),
        delivery_links=[],
    )
    detail_path = tmp_path / "recadrage_lot_115_20261109.json"
    backfill.write_json_atomic(detail_path, detail)
    # When: l'entrée d'index est construite
    entry = backfill.build_index_entry(
        detail, detail_path.name, detail_path.stat().st_size
    )
    # Then: les champs attendus par email_proxy.php sont présents
    assert entry["id"] == detail["id"]
    assert entry["file"] == detail_path.name
    assert entry["links_count"] == 0
    assert entry["size_bytes"] == detail_path.stat().st_size
    assert entry["sender"] == detail["sender_masked"]
    assert set(entry) == {
        "id",
        "lot",
        "subject",
        "received_at",
        "stored_at",
        "deadline",
        "urgent",
        "sender",
        "snippet",
        "file",
        "links_count",
        "size_bytes",
    }


@pytest.mark.unit
def test_merge_index_sorts_and_dedupes_per_month() -> None:
    # Given: un index live de novembre et des missions d'octobre/novembre
    live = [
        {"id": "live_280", "lot": 280, "received_at": "2026-11-20T12:18:05+01:00"},
        {"id": "live_268_nov", "lot": 268, "received_at": "2026-11-19T17:06:10+01:00"},
    ]
    new = [
        {"id": "old_268_oct", "lot": 268, "received_at": "2026-10-23T09:49:59+02:00"},
        {
            "id": "old_268_oct_newer",
            "lot": 268,
            "received_at": "2026-10-23T10:00:00+02:00",
        },
        {"id": "old_115", "lot": 115, "received_at": "2026-11-09T15:06:51+01:00"},
    ]
    # When: les index sont fusionnés
    merged = backfill.merge_index_entries(live, new, max_entries=200)
    # Then: le lot 268 d'octobre et celui de novembre coexistent, et le doublon
    # d'octobre le plus récent remplace l'ancien
    assert [entry["id"] for entry in merged] == [
        "live_280",
        "live_268_nov",
        "old_115",
        "old_268_oct_newer",
    ]
    timestamps = [datetime.fromisoformat(entry["received_at"]) for entry in merged]
    assert timestamps == sorted(timestamps, reverse=True)


@pytest.mark.unit
def test_merge_index_prefers_live_on_exact_id_collision() -> None:
    # Given: le même identifiant dans l'index live et dans le backfill
    live = [
        {
            "id": "recadrage_lot_115_20261109",
            "lot": 115,
            "received_at": "2026-11-09T15:06:51+01:00",
            "sender": "live",
        }
    ]
    new = [
        {
            "id": "recadrage_lot_115_20261109",
            "lot": 115,
            "received_at": "2026-11-09T15:06:51+01:00",
            "sender": "backfill",
        }
    ]
    # When: la fusion est effectuée
    merged = backfill.merge_index_entries(live, new)
    # Then: l'entrée live existante prime
    assert len(merged) == 1
    assert merged[0]["sender"] == "live"


@pytest.mark.unit
def test_merge_index_caps_and_handles_invalid_dates() -> None:
    # Given: plus d'entrées que la limite, dont une date invalide
    entries = [
        {"id": f"e{i}", "lot": i, "received_at": f"2026-11-{i:02d}T10:00:00+01:00"}
        for i in range(1, 6)
    ]
    entries.append({"id": "invalid", "lot": 99, "received_at": "not-a-date"})
    # When: la fusion est plafonnée à trois entrées
    merged = backfill.merge_index_entries([], entries, max_entries=3)
    # Then: les plus récentes sont conservées, la date invalide passe en dernier
    assert len(merged) == 3
    assert [entry["id"] for entry in merged] == ["e5", "e4", "e3"]


@pytest.mark.unit
def test_build_links_index_and_enrich_delivery_links(
    lot_115_links: list[dict[str, str]],
) -> None:
    # Given: une paire R2 et un lien Dropbox identique
    links_index = backfill.build_links_index(lot_115_links)
    raw_links = [{"provider": "dropbox", "raw_url": LOT_115_URL}]
    # When: les liens sont enrichis
    enriched = backfill.sanitize_delivery_links(raw_links, links_index)
    # Then: l'URL R2 et le nom d'archive sont ajoutés
    assert len(enriched) == 1
    assert enriched[0]["provider"] == "dropbox"
    assert enriched[0]["raw_url"] == LOT_115_URL
    assert enriched[0]["direct_url"] == LOT_115_URL
    assert enriched[0]["r2_url"].startswith("https://server.kidpixel.workers.dev/")
    assert enriched[0]["original_filename"] == "115 Camille.zip"


@pytest.mark.unit
def test_enrich_delivery_links_without_match_keeps_source() -> None:
    # Given: un lien sans correspondance R2
    raw_links = [{"provider": "dropbox", "raw_url": LOT_115_URL}]
    # When: l'enrichissement est tenté
    enriched = backfill.sanitize_delivery_links(raw_links, {})
    # Then: le lien source reste disponible, sans r2_url
    assert enriched == [
        {
            "provider": "dropbox",
            "raw_url": LOT_115_URL,
            "direct_url": LOT_115_URL,
        }
    ]


@pytest.mark.unit
def test_enrich_delivery_links_rejects_invalid_and_duplicate_urls() -> None:
    # Given: des liens invalides, dupliqués et un nom de fichier pollué
    links_index = backfill.build_links_index(
        [
            {
                "source_url": LOT_115_URL,
                "r2_url": "https://server.kidpixel.workers.dev/file",
                "original_filename": "115\x00 Camille.zip",
            }
        ]
    )
    raw_links = [
        {"provider": "dropbox", "raw_url": "javascript:alert(1)"},
        {"provider": "dropbox", "raw_url": LOT_115_URL},
        {"provider": "dropbox", "raw_url": LOT_115_URL},
    ]
    # When: les liens sont nettoyés
    enriched = backfill.sanitize_delivery_links(raw_links, links_index)
    # Then: seuls les liens HTTP valides et uniques sont conservés
    assert len(enriched) == 1
    assert enriched[0]["original_filename"] == "115 Camille.zip"


@pytest.mark.unit
def test_normalize_link_url_ignores_dl_parameter() -> None:
    # Given: deux variantes du même lien Dropbox
    with_dl_zero = f"{LOT_115_URL}"
    with_dl_one = LOT_115_URL.replace("&dl=0", "&dl=1")
    # When: les URLs sont normalisées
    # Then: elles sont équivalentes
    assert backfill.normalize_link_url(with_dl_zero) == backfill.normalize_link_url(
        with_dl_one
    )


@pytest.mark.unit
def test_package_archives_layout(tmp_path: Path) -> None:
    # Given: un répertoire de staging avec deux détails et un index
    data_root = tmp_path / "data"
    emails_dir = data_root / "emails"
    emails_dir.mkdir(parents=True)
    detail_a = emails_dir / "recadrage_lot_115_20261109.json"
    detail_b = emails_dir / "recadrage_lot_116_20261109.json"
    detail_a.write_text("{}", encoding="utf-8")
    detail_b.write_text("{}", encoding="utf-8")
    index_file = data_root / "emails_recadrage_index.json"
    index_file.write_text("[]", encoding="utf-8")
    output_dir = tmp_path / "dist"
    output_dir.mkdir()
    # When: les archives sont créées
    tar_path, zip_path = backfill.package_archives(
        data_root, output_dir, [detail_a, detail_b], index_file
    )
    # Then: les entrées sont à la racine de data/, sans préfixe data/
    with tarfile.open(tar_path, "r:gz") as archive:
        tar_names = archive.getnames()
    with zipfile.ZipFile(zip_path) as archive:
        zip_names = archive.namelist()
    expected = [
        "emails/recadrage_lot_115_20261109.json",
        "emails/recadrage_lot_116_20261109.json",
        "emails_recadrage_index.json",
    ]
    assert tar_names == expected
    assert zip_names == expected


def _make_live_entries() -> list[dict[str, object]]:
    """Construit 42 entrées live synthétiques, dont un lot 268 de novembre."""
    live_entries: list[dict[str, object]] = [
        {
            "id": "live_lot_280",
            "lot": 280,
            "received_at": "2026-11-20T12:18:05+01:00",
        },
        {
            "id": "live_lot_268",
            "lot": 268,
            "received_at": "2026-11-19T17:06:10+01:00",
        },
    ]
    for offset, lot in enumerate(range(166, 206)):
        day = 12 + offset // 8
        hour = 10 + offset % 8
        live_entries.append(
            {
                "id": f"live_lot_{lot}",
                "lot": lot,
                "received_at": f"2026-11-{day:02d}T{hour:02d}:00:00+01:00",
            }
        )
    return live_entries


@pytest.mark.integration
def test_build_outputs_produces_104_entries(
    tmp_path: Path,
    extracted_missions: list[backfill.Mission],
) -> None:
    # Given: 42 entrées live (dont un lot 268 de novembre) et 62 missions historiques
    live_entries = _make_live_entries()
    assert len(live_entries) == 42

    # When: les sorties complètes sont générées
    summary = backfill.build_outputs(
        extracted_missions,
        live_entries,
        [],
        output_dir=tmp_path,
        stored_at=datetime(2026, 11, 22, 12, 0, tzinfo=TZ),
        window_since=WINDOW_START,
        window_until=WINDOW_END,
        max_entries=200,
    )
    # Then: l'index contient 104 entrées, du lot 280 au lot 268 d'octobre
    assert summary["index_merged"] == 104
    assert summary["lot_115"] is True
    assert summary["first"]["lot"] == 280
    assert summary["last"]["lot"] == 268
    assert summary["last"]["received_at"] == "2026-10-23T09:49:59+02:00"
    assert summary["tar_file"].is_file()
    assert summary["zip_file"].is_file()
    assert summary["payload_file"].is_file()

    index = json.loads(
        (tmp_path / "data" / "emails_recadrage_index.json").read_text(encoding="utf-8")
    )
    assert len(index) == 104
    assert (tmp_path / "data" / "emails" / "recadrage_lot_115_20261109.json").is_file()


@pytest.mark.unit
def test_extract_missions_raises_on_missing_mbox(tmp_path: Path) -> None:
    # Given: un chemin de mbox inexistant
    missing = tmp_path / "missing.mbox"
    # When/Then: l'extraction échoue explicitement
    with pytest.raises(FileNotFoundError):
        backfill.extract_missions_from_mbox(
            missing,
            since=WINDOW_START,
            until=WINDOW_END,
            tz=TZ,
        )


@pytest.mark.unit
def test_extract_missions_raises_on_empty_window() -> None:
    # Given: une fenêtre inversée
    if not MBOX_PATH.is_file():
        pytest.skip("mbox d'archive absent")
    # When/Then: l'extraction refuse la fenêtre
    with pytest.raises(ValueError):
        backfill.extract_missions_from_mbox(
            MBOX_PATH,
            since=WINDOW_END,
            until=WINDOW_START,
            tz=TZ,
        )


@pytest.mark.unit
def test_parse_cli_datetime_variants() -> None:
    # Given: trois formats de date acceptés
    # When: ils sont parsés
    # Then: le fuseau Europe/Luxembourg est appliqué
    date_only = backfill.parse_cli_datetime("2026-10-23", TZ)
    iso_offset = backfill.parse_cli_datetime("2026-11-09T15:06:51+01:00", TZ)
    naive = backfill.parse_cli_datetime("2026-11-09T15:06:51", TZ)
    assert date_only.isoformat() == "2026-10-23T00:00:00+02:00"
    assert iso_offset.isoformat() == "2026-11-09T15:06:51+01:00"
    assert naive.isoformat() == "2026-11-09T15:06:51+01:00"


@pytest.mark.unit
def test_parse_cli_datetime_rejects_invalid_value() -> None:
    # Given: une date invalide
    # When/Then: le parseur lève une erreur argparse
    with pytest.raises(argparse.ArgumentTypeError):
        backfill.parse_cli_datetime("not-a-date", TZ)


@pytest.mark.unit
def test_mask_email_and_html_helpers() -> None:
    # Given: une adresse et un HTML simple
    # When: les helpers sont appelés
    # Then: le masquage et la conversion respectent le stockage PHP
    assert backfill.mask_email("technique@media-solution.fr") == (
        "t***@media-solution.fr"
    )
    assert backfill.mask_email("") == "[redacted]"
    assert backfill.mask_email("invalid") == "[redacted]"
    assert backfill.looks_like_html("<div>Bonjour</div>") is True
    assert backfill.looks_like_html("Bonjour") is False
    text = backfill.html_to_text(
        "<style>x</style><p>Bonjour&nbsp;Camille</p><script>y</script>"
    )
    assert text == "Bonjour Camille"


@pytest.mark.unit
def test_load_webhook_time_window(tmp_path: Path) -> None:
    # Given: un fichier de configuration avec une fenêtre globale
    config_path = tmp_path / "webhook_config.json"
    config_path.write_text(
        json.dumps(
            {
                "global_time_start": "10:30",
                "global_time_end": "19:00",
            }
        ),
        encoding="utf-8",
    )
    # When: la fenêtre est chargée
    start, end = backfill.load_webhook_time_window(config_path)
    # Then: les bornes sont converties en objets time
    assert start == time(10, 30)
    assert end == time(19, 0)


@pytest.mark.unit
def test_load_webhook_time_window_missing_file(tmp_path: Path) -> None:
    # Given: un fichier absent
    # When: la fenêtre est chargée
    # Then: aucune contrainte n'est appliquée
    assert backfill.load_webhook_time_window(tmp_path / "missing.json") == (
        None,
        None,
    )


@pytest.mark.unit
def test_lot_115_eml_matches_mbox_extraction(
    lot_115_mission: backfill.Mission,
) -> None:
    # Given: le fichier .eml individuel du lot 115
    if not LOT_115_EML.is_file():
        pytest.skip("fichier .eml du lot 115 absent")
    message = BytesParser(policy=policy.default).parse(LOT_115_EML.open("rb"))
    plain, html_body = backfill.extract_bodies(message)
    # When: ses corps sont comparés à l'extraction mbox
    # Then: le contenu est identique, aux fins de ligne près
    assert plain.replace("\r\n", "\n").strip() == (
        lot_115_mission.body_text.replace("\r\n", "\n").strip()
    )
    assert html_body is not None
    assert html_body.replace("\r\n", "\n").strip() == (
        (lot_115_mission.body_html or "").replace("\r\n", "\n").strip()
    )


@pytest.mark.integration
def test_main_cli_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    # Given: un index live local, un fichier de liens et un répertoire de sortie
    if not MBOX_PATH.is_file():
        pytest.skip("mbox d'archive absent")
    live_path = tmp_path / "live.json"
    live_path.write_text(json.dumps(_make_live_entries()), encoding="utf-8")
    links_path = tmp_path / "links.json"
    links_path.write_text(
        json.dumps(
            [
                {
                    "source_url": LOT_115_URL,
                    "r2_url": (
                        "https://server.kidpixel.workers.dev/dropbox/"
                        "352ef810/1ef2a04f/file"
                    ),
                    "provider": "dropbox",
                    "original_filename": "115 Camille.zip",
                }
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "dist"

    # When: le CLI complet est exécuté hors réseau
    exit_code = backfill.main(
        [
            "--mbox",
            str(MBOX_PATH),
            "--output-dir",
            str(output_dir),
            "--now",
            "2026-11-22T12:00:00",
            "--live-index-file",
            str(live_path),
            "--links-file",
            str(links_path),
            "--no-network",
        ]
    )

    # Then: les 104 entrées et les archives sont produites
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Index fusionné  : 104" in captured.out
    assert "Lot 115         : présent" in captured.out
    assert (output_dir / "backfill_recadrage_30d.tar.gz").is_file()
    assert (output_dir / "backfill_recadrage_30d.zip").is_file()
    assert (output_dir / "backfill_payloads_30d.json").is_file()


@pytest.mark.unit
def test_main_rejects_invalid_days(capsys: pytest.CaptureFixture) -> None:
    # Given: un nombre de jours invalide
    # When: le CLI démarre
    exit_code = backfill.main(["--days", "0"])
    # Then: il échoue proprement
    assert exit_code == 1
    assert "ERREUR" in capsys.readouterr().err


@pytest.mark.unit
def test_main_rejects_no_network_without_live_index(
    capsys: pytest.CaptureFixture,
) -> None:
    # Given: le mode hors réseau sans index live local
    # When: le CLI démarre
    exit_code = backfill.main(["--no-network"])
    # Then: il refuse de produire un index sans les entrées live
    assert exit_code == 1
    assert "live-index-file" in capsys.readouterr().err


@pytest.mark.unit
def test_load_live_index_failure_paths(tmp_path: Path) -> None:
    # Given: un mode hors réseau sans fichier
    logger = logging.getLogger("test_backfill")
    args = argparse.Namespace(
        live_index_file=None,
        no_network=True,
        allow_empty_live=False,
        live_index_url="https://example.invalid/index.json",
    )
    # When/Then: le chargement échoue explicitement
    with pytest.raises(RuntimeError):
        backfill.load_live_index(args, logger)

    # Given: un index live qui n'est pas une liste
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{}", encoding="utf-8")
    args.live_index_file = invalid_path
    args.no_network = True
    # When/Then: le format est refusé
    with pytest.raises(RuntimeError):
        backfill.load_live_index(args, logger)


@pytest.mark.unit
def test_load_live_index_allows_empty_on_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: un proxy injoignable et l'option de fusion à vide
    logger = logging.getLogger("test_backfill")

    def _raise(_url: str, timeout: float = 20.0) -> object:
        raise RuntimeError("offline")

    monkeypatch.setattr(backfill, "fetch_json", _raise)
    args = argparse.Namespace(
        live_index_file=None,
        no_network=False,
        allow_empty_live=True,
        live_index_url="https://example.invalid/index.json",
    )
    # When: le chargement est tenté
    entries = backfill.load_live_index(args, logger)
    # Then: la fusion repart d'un index vide
    assert entries == []


@pytest.mark.unit
def test_load_webhook_links_local_and_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: un fichier local de liens
    logger = logging.getLogger("test_backfill")
    local_links = tmp_path / "webhook_links.json"
    local_links.write_text(
        json.dumps(
            [
                {
                    "source_url": LOT_115_URL,
                    "r2_url": "https://server.kidpixel.workers.dev/file",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(backfill, "LOCAL_LINKS_FILE", local_links)
    args = argparse.Namespace(links_file=None, no_network=True, links_url="")
    # When: le repli local est utilisé
    entries = backfill.load_webhook_links(args, logger)
    # Then: la paire R2 est chargée
    assert len(entries) == 1
    assert entries[0]["r2_url"].endswith("/file")

    # Given: aucun fichier local
    monkeypatch.setattr(backfill, "LOCAL_LINKS_FILE", tmp_path / "missing.json")
    # When: le repli est tenté
    entries = backfill.load_webhook_links(args, logger)
    # Then: aucun lien n'est enrichi, sans erreur bloquante
    assert entries == []


@pytest.mark.unit
def test_load_json_file_errors(tmp_path: Path) -> None:
    # Given: un fichier absent puis un JSON invalide
    missing = tmp_path / "missing.json"
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{not json", encoding="utf-8")
    # When/Then: les deux cas produisent une erreur explicite
    with pytest.raises(RuntimeError):
        backfill.load_json_file(missing)
    with pytest.raises(RuntimeError):
        backfill.load_json_file(invalid)


@pytest.mark.unit
def test_extract_deadline_fallback_variants() -> None:
    # Given: des corps aux formats de deadline connus
    # When: le fallback est appliqué
    # Then: les formats sont normalisés comme dans EmailStorageLogger
    assert (
        backfill.extract_deadline_fallback("À faire pour le 3/9/2026 à 9h", "Lot 1")
        == "le 3/9/2026 à 9h"
    )
    assert backfill.extract_deadline_fallback("À faire pour 11h30", "Lot 1") == "11h30"
    assert backfill.extract_deadline_fallback("Aucun créneau", "Lot 1 URGENT") == (
        "URGENCE"
    )
    assert backfill.extract_deadline_fallback("Aucun créneau", "Lot 1") is None


@pytest.mark.unit
def test_compute_delivery_time_without_match() -> None:
    # Given: un email sans lien de livraison
    logger = logging.getLogger("test_backfill")
    logger.setLevel(logging.CRITICAL)
    # When: le pattern matcher est appelé
    raw, adjusted = backfill.compute_delivery_time(
        "Média Solution - Missions Recadrage - Lot 1",
        "Aucun lien ici",
        datetime(2026, 11, 9, 15, 6, tzinfo=TZ),
        TZ,
        time(10, 30),
        time(19, 0),
        logger,
    )
    # Then: aucun créneau n'est inventé
    assert raw is None
    assert adjusted is None


@pytest.mark.unit
def test_header_and_subject_helpers() -> None:
    # Given: des en-têtes MIME et des sujets variés
    # When: les helpers sont appelés
    # Then: le décodage et les filtres sont conformes
    assert backfill.decode_mime_header("=?UTF-8?Q?M=C3=A9dia?=") == "Média"
    assert backfill.extract_sender_email("Technique <technique@media-solution.fr>") == (
        "technique@media-solution.fr"
    )
    assert backfill.extract_sender_email("pas-un-email") == ""
    assert backfill.extract_lot("Média Solution - Missions Recadrage - Lot 115") == 115
    assert backfill.extract_lot("Sans numéro") is None
    assert (
        backfill.is_recadrage_subject("Média Solution - Missions Recadrage - Lot 115")
        is True
    )
    assert backfill.is_recadrage_subject("Newsletter") is False
    assert backfill.is_reply_or_forward("Re: Lot 115") is True
    assert backfill.is_reply_or_forward("Fwd: Lot 115") is True
    assert backfill.is_reply_or_forward("Lot 115") is False


@pytest.mark.unit
def test_oldest_received_at_ignores_invalid_entries() -> None:
    # Given: un mélange de dates valides et invalides
    entries = [
        {"received_at": "2026-11-20T12:00:00+01:00"},
        {"received_at": "2026-10-23T09:49:59+02:00"},
        {"received_at": "not-a-date"},
        {"received_at": None},
        {},
    ]
    # When: la plus ancienne date est recherchée
    oldest = backfill._oldest_received_at(entries)
    # Then: seule la date valide la plus ancienne est retenue
    assert oldest is not None
    assert oldest.isoformat() == "2026-10-23T09:49:59+02:00"
    assert backfill._oldest_received_at([]) is None


@pytest.mark.unit
def test_sanitize_filename_and_links_index_edges() -> None:
    # Given: des noms de fichiers invalides et des entrées d'index incomplètes
    assert backfill.sanitize_filename(None) is None
    assert backfill.sanitize_filename("") is None
    assert backfill.sanitize_filename(" 115\x00 Camille.zip ") == "115 Camille.zip"
    index = backfill.build_links_index(
        [
            None,
            {},
            {"source_url": "", "r2_url": "https://example.com/x"},
            {"source_url": LOT_115_URL, "r2_url": ""},
            {"source_url": LOT_115_URL, "r2_url": "https://example.com/y"},
        ]
    )
    # When/Then: la dernière paire valide est conservée
    assert index[LOT_115_URL]["r2_url"] == "https://example.com/y"


@pytest.mark.unit
def test_build_detail_entry_plain_and_omitted() -> None:
    # Given: une mission en texte brut
    mission = backfill.Mission(
        message_index=1,
        lot=42,
        received_at=datetime(2026, 11, 9, 15, 6, tzinfo=TZ),
        subject="Média Solution - Missions Recadrage - Lot 42",
        sender_email="technique@media-solution.fr",
        body_text="Bonjour Camille",
        body_html=None,
        message_id="<test@example.com>",
        delivery_time_raw=None,
        delivery_time=None,
        urgent=False,
        raw_links=[],
    )
    # When: le détail est construit
    detail = backfill.build_detail_entry(
        mission,
        stored_at=datetime(2026, 11, 22, 12, 0, tzinfo=TZ),
        delivery_links=[],
    )
    # Then: le HTML reste nul et le corps est conservé
    assert detail["body_html"] is None
    assert detail["body_text"] == "Bonjour Camille"
    assert detail["body_omitted"] is False

    # Given: une limite de corps volontairement trop basse
    omitted = backfill.build_detail_entry(
        mission,
        stored_at=datetime(2026, 11, 22, 12, 0, tzinfo=TZ),
        delivery_links=[],
        max_body_bytes=1,
    )
    # Then: le corps est omis mais sa taille réelle est conservée
    assert omitted["body_omitted"] is True
    assert omitted["body_text"] == ""
    assert omitted["body_html"] is None
    assert omitted["body_size_bytes"] > 1


@pytest.mark.unit
def test_write_json_atomic(tmp_path: Path) -> None:
    # Given: un chemin de fichier dans un sous-répertoire absent
    target = tmp_path / "nested" / "data.json"
    # When: le JSON est écrit
    backfill.write_json_atomic(target, {"ok": True})
    # Then: le fichier existe et est lisible
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}


@pytest.mark.unit
def test_php_import_script_is_storage_only() -> None:
    # Given: l'outil d'import serveur
    php_path = REPO_ROOT / "deployment" / "tools" / "import_retroactive_missions.php"
    if not php_path.is_file():
        pytest.skip("outil PHP d'import absent")
    content = php_path.read_text(encoding="utf-8")

    # When: son contenu est inspecté
    # Then: il écrit sous verrou et ne contient aucun envoi d'email
    assert "flock($lock, LOCK_EX)" in content
    assert "'size_bytes' => (int) $size" in content
    assert "importMergeIndexes" in content
    assert "GmailMailer" not in content
    assert "mail(" not in content
    assert "curl_" not in content
    assert "file_get_contents('http" not in content
