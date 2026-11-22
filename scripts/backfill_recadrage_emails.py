"""Enrichissement rétro-actif des missions de recadrage (30 jours).

Ce script reconstruit l'archive publique servie par ``email_proxy.php`` à partir
du mbox Gmail. Il ne rejoue jamais les emails vers ``index.php`` : seuls les
fichiers JSON de stockage et l'index sont générés. Aucun email de confirmation
n'est donc envoyé au client.

Exemple d'utilisation :

    python3 scripts/backfill_recadrage_emails.py \
        --mbox debug/mails/a_exporter.mbox \
        --output-dir deployment/dist
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_module
import json
import logging
import mailbox
import os
import re
import sys
import tarfile
import unicodedata
import urllib.error
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from email_processing.delivery_time_resolver import (  # noqa: E402
    is_urgent_subject,
    resolve_recadrage_delivery_time,
)
from email_processing.link_extraction import (  # noqa: E402
    extract_provider_links_from_text,
)
from email_processing.pattern_matching import (  # noqa: E402
    check_media_solution_pattern,
)
from utils.text_helpers import normalize_no_accents_lower_trim  # noqa: E402
from utils.time_helpers import parse_time_hhmm  # noqa: E402

DEFAULT_TZ = "Europe/Luxembourg"
DEFAULT_MBOX = _REPO_ROOT / "debug" / "mails" / "a_exporter.mbox"
DEFAULT_OUTPUT_DIR = _REPO_ROOT / "deployment" / "dist"
DEFAULT_LIVE_INDEX_URL = "https://webhook.kidpixel.fr/email_proxy.php"
DEFAULT_LINKS_URL = "https://webhook.kidpixel.fr/webhook_proxy.php"
LOCAL_LINKS_FILE = _REPO_ROOT / "deployment" / "data" / "webhook_links.json"
WEBHOOK_CONFIG_FILE = _REPO_ROOT / "debug" / "webhook_config.json"
DEFAULT_MAX_INDEX_ENTRIES = 200
DEFAULT_MAX_BODY_BYTES = 5 * 1024 * 1024
SOURCE_NAME = "backfill_mbox_30d"
ARCHIVE_BASENAME = "backfill_recadrage_30d"

_URGENT_PATTERN = re.compile(r"\b(urgent|urgence)\b", re.IGNORECASE)
_REPLY_PREFIX_PATTERN = re.compile(r"^\s*(?:re|tr|fw|fwd)\s*:", re.IGNORECASE)
_RECADRAGE_SUBJECT_PATTERN = re.compile(
    r"\bmissions\s+(?:de\s+)?recadrage\b.*\blot\s*\d+", re.IGNORECASE
)
_LOT_PATTERN = re.compile(r"\blot\s*(\d{1,6})\b", re.IGNORECASE)
_SAFE_FILE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,120}\.json$")
_HTML_PATTERN = re.compile(
    r"<\s*(?:!doctype|html|body|div|p|br|a|table|span|img|ul|ol|li|h[1-6])\b",
    re.IGNORECASE,
)
_DEADLINE_DATE_PATTERN = re.compile(
    r"a\s+faire\s+pour\s+le\s+(\d{1,2}/\d{1,2}/\d{4})\s+a\s+(\d{1,2}h\d{0,2})",
    re.IGNORECASE,
)
_DEADLINE_TIME_PATTERN = re.compile(
    r"a\s+faire\s+pour\s+(\d{1,2}h\d{0,2})", re.IGNORECASE
)


@dataclass(frozen=True)
class Mission:
    """Mission de recadrage extraite du mbox, avant enrichissement R2."""

    message_index: int
    lot: int
    received_at: datetime
    subject: str
    sender_email: str
    body_text: str
    body_html: str | None
    message_id: str
    delivery_time_raw: str | None
    delivery_time: str | None
    urgent: bool
    raw_links: list[dict[str, str]]


def decode_mime_header(value: str | None) -> str:
    """Décode un en-tête MIME (sujet, expéditeur) de façon tolérante."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return str(value).strip()


def extract_sender_email(from_header: str) -> str:
    """Extrait l'adresse email d'un en-tête From, même au format « Nom <email> »."""
    _, address = parseaddr(from_header or "")
    if not address:
        match = re.search(r"<([^>]+)>", from_header or "")
        address = match.group(1) if match else (from_header or "")
    address = address.strip().lower()
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address) is None:
        return ""
    return address


def mask_email(email: str) -> str:
    """Masque l'expéditeur comme le fait EmailStorageLogger."""
    if not email or "@" not in email:
        return "[redacted]"
    local, domain = email.split("@", 1)
    if not domain:
        return "[redacted]"
    return f"{local[:1]}***@{domain}"


def looks_like_html(content: str) -> bool:
    """Reproduit l'heuristique de EmailStorageLogger."""
    return bool(_HTML_PATTERN.search(content or ""))


def html_to_text(html_content: str) -> str:
    """Convertit un corps HTML en texte, avec la même logique que le stockage PHP."""
    text = re.sub(
        r"<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>",
        " ",
        html_content or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(r"<[^>]+>", "", text)
    text = html_module.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_accents(value: str) -> str:
    """Supprime les accents pour les regex de deadline."""
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def parse_received_at(message: Message, tz: ZoneInfo) -> datetime | None:
    """Convertit l'en-tête Date du message dans le fuseau de référence."""
    raw = message.get("Date")
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(str(raw))
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def extract_bodies(message: Message) -> tuple[str, str | None]:
    """Retourne (texte brut, HTML) en ignorant les pièces jointes."""
    plain = ""
    html_body = ""
    for part in message.walk():
        if part.is_multipart():
            continue
        if part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            continue
        charset = part.get_content_charset() or "utf-8"
        try:
            decoded = payload.decode(charset, errors="replace")
        except LookupError:
            decoded = payload.decode("utf-8", errors="replace")
        if content_type == "text/plain" and not plain:
            plain = decoded
        elif content_type == "text/html" and not html_body:
            html_body = decoded

    html_value = html_body or None
    if not plain and html_value:
        plain = html_to_text(html_value)
    return plain, html_value


def is_recadrage_subject(subject: str) -> bool:
    """Reconnaît un sujet de mission de recadrage avec numéro de lot."""
    normalized = normalize_no_accents_lower_trim(subject or "")
    return bool(_RECADRAGE_SUBJECT_PATTERN.search(normalized))


def is_reply_or_forward(subject: str) -> bool:
    """Indique si le sujet est une réponse ou un transfert."""
    return bool(_REPLY_PREFIX_PATTERN.match(subject or ""))


def extract_lot(subject: str) -> int | None:
    """Extrait le numéro de lot du sujet."""
    match = _LOT_PATTERN.search(subject or "")
    if match is None:
        return None
    lot = int(match.group(1))
    return lot if lot > 0 else None


def is_urgent_like(subject: str) -> bool:
    """Reconnaît URGENT et URGENCE, comme EmailStorageLogger."""
    return bool(_URGENT_PATTERN.search(subject or ""))


def extract_deadline_fallback(body_text: str, subject: str) -> str | None:
    """Extrait la deadline quand le pattern matcher n'a rien retourné."""
    if is_urgent_like(subject):
        return "URGENCE"
    normalized = strip_accents(body_text or "")
    date_match = _DEADLINE_DATE_PATTERN.search(normalized)
    if date_match is not None:
        return f"le {date_match.group(1)} à {date_match.group(2)}"
    time_match = _DEADLINE_TIME_PATTERN.search(normalized)
    if time_match is not None:
        return time_match.group(1)
    return None


def compute_delivery_time(
    subject: str,
    combined_text: str,
    received_at: datetime,
    tz: ZoneInfo,
    window_start: time | None,
    window_end: time | None,
    logger: logging.Logger,
) -> tuple[str | None, str | None]:
    """Calcule le créneau brut puis l'ajuste hors fenêtre comme l'orchestrateur."""
    result = check_media_solution_pattern(subject, combined_text, tz, logger)
    if not isinstance(result, dict) or not result.get("matches"):
        return None, None

    raw_value = result.get("delivery_time")
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None, None

    adjusted = resolve_recadrage_delivery_time(
        raw_value,
        received_dt=received_at,
        window_start=window_start,
        window_end=window_end,
        is_urgent=is_urgent_subject(subject),
    )
    return raw_value, adjusted or raw_value


def load_webhook_time_window(path: Path) -> tuple[time | None, time | None]:
    """Lit la fenêtre horaire globale utilisée par l'orchestrateur."""
    if not path.is_file():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    if not isinstance(data, dict):
        return None, None

    start_raw = data.get("webhook_time_start") or data.get("global_time_start")
    end_raw = data.get("webhook_time_end") or data.get("global_time_end")
    start = parse_time_hhmm(start_raw) if isinstance(start_raw, str) else None
    end = parse_time_hhmm(end_raw) if isinstance(end_raw, str) else None
    return start, end


def extract_missions_from_mbox(
    mbox_path: Path,
    *,
    since: datetime,
    until: datetime,
    tz: ZoneInfo,
    window_start: time | None = None,
    window_end: time | None = None,
    logger: logging.Logger | None = None,
) -> list[Mission]:
    """Extrait les missions de recadrage valides de la fenêtre demandée."""
    if not mbox_path.is_file():
        raise FileNotFoundError(f"mbox introuvable : {mbox_path}")
    if since >= until:
        raise ValueError("La borne de début doit précéder la borne de fin")

    active_logger = logger or logging.getLogger(__name__)
    missions: list[Mission] = []
    box = mailbox.mbox(str(mbox_path), create=False)
    try:
        for index, message in enumerate(box):
            subject = decode_mime_header(message.get("Subject"))
            if not subject or not is_recadrage_subject(subject):
                continue
            if is_reply_or_forward(subject):
                continue

            sender = extract_sender_email(decode_mime_header(message.get("From")))
            if not sender.endswith("@media-solution.fr"):
                continue

            received_at = parse_received_at(message, tz)
            if received_at is None or received_at < since or received_at >= until:
                continue

            lot = extract_lot(subject)
            if lot is None:
                continue

            body_text, body_html = extract_bodies(message)
            if not body_text and not body_html:
                continue

            combined_text = (body_text or "") + "\n" + (body_html or "")
            raw_links = extract_provider_links_from_text(combined_text)
            if not raw_links:
                continue

            raw_delivery, adjusted_delivery = compute_delivery_time(
                subject,
                combined_text,
                received_at,
                tz,
                window_start,
                window_end,
                active_logger,
            )
            missions.append(
                Mission(
                    message_index=index,
                    lot=lot,
                    received_at=received_at,
                    subject=subject,
                    sender_email=sender,
                    body_text=body_text,
                    body_html=body_html,
                    message_id=decode_mime_header(message.get("Message-ID")),
                    delivery_time_raw=raw_delivery,
                    delivery_time=adjusted_delivery,
                    urgent=is_urgent_like(subject),
                    raw_links=[dict(link) for link in raw_links],
                )
            )
    finally:
        box.close()

    missions.sort(key=lambda item: (item.received_at, item.lot))
    return missions


def normalize_link_url(url: str) -> str:
    """Normalise une URL de livraison pour la recherche dans webhook_links."""
    if not url:
        return ""
    value = html_module.unescape(url.strip())
    try:
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

        parts = urlsplit(value)
        query = [
            (key, val)
            for key, val in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() != "dl"
        ]
        query.sort(key=lambda item: (item[0].lower(), item[1]))
        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                parts.path,
                urlencode(query, doseq=True),
                "",
            )
        )
    except Exception:
        return value


def build_links_index(entries: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Indexe les paires source_url/r2_url par URL exacte et normalisée."""
    index: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source_url = entry.get("source_url") or entry.get("url")
        if not isinstance(source_url, str) or not source_url.strip():
            continue
        source_url = source_url.strip()
        normalized = normalize_link_url(source_url)
        for key in (source_url, normalized):
            if not key:
                continue
            current = index.get(key)
            if current is None or (not current.get("r2_url") and entry.get("r2_url")):
                index[key] = entry
    return index


def sanitize_filename(value: Any) -> str | None:
    """Nettoie le nom d'archive d'origine avant publication."""
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", value).strip()
    if not cleaned:
        return None
    return cleaned[:255]


def sanitize_delivery_links(
    raw_links: Iterable[dict[str, Any]],
    links_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Enrichit les liens Dropbox/FromSmash/SwissTransfer avec les URLs R2."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_links:
        if len(result) >= 50:
            break
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "unknown").strip()
        if re.fullmatch(r"[a-z0-9_-]{1,32}", provider, re.IGNORECASE) is None:
            provider = "unknown"
        raw_url = item.get("raw_url")
        if not isinstance(raw_url, str):
            continue
        raw_url = raw_url.strip()
        if not raw_url.startswith(("http://", "https://")) or raw_url in seen:
            continue
        seen.add(raw_url)

        entry: dict[str, Any] = {
            "provider": provider,
            "raw_url": raw_url,
            "direct_url": raw_url,
        }
        match = links_index.get(raw_url) or links_index.get(normalize_link_url(raw_url))
        if isinstance(match, dict):
            r2_url = match.get("r2_url")
            if isinstance(r2_url, str) and r2_url.startswith(("http://", "https://")):
                entry["r2_url"] = r2_url
            filename = sanitize_filename(match.get("original_filename"))
            if filename is not None:
                entry["original_filename"] = filename
        result.append(entry)
    return result


def build_detail_entry(
    mission: Mission,
    *,
    stored_at: datetime,
    delivery_links: list[dict[str, Any]],
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
) -> dict[str, Any]:
    """Construit le fichier détail au format de EmailStorageLogger."""
    body_html = mission.body_html
    body_text = mission.body_text
    if body_html and not looks_like_html(body_html):
        if not body_text:
            body_text = body_html
        body_html = None
    if not body_text and body_html:
        body_text = html_to_text(body_html)
    if body_html is None and looks_like_html(body_text):
        body_html = body_text
        body_text = html_to_text(body_text)

    raw_body = body_html or body_text
    body_size_bytes = len(raw_body.encode("utf-8"))
    omitted = max_body_bytes > 0 and body_size_bytes > max_body_bytes
    if omitted:
        body_html = None
        body_text = ""

    deadline = mission.delivery_time or extract_deadline_fallback(
        mission.body_text, mission.subject
    )
    seed = mission.message_id or (
        f"{mission.subject}|{mission.received_at.isoformat()}"
    )
    email_id_hash = "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()

    return {
        "schema_version": 1,
        "id": f"recadrage_lot_{mission.lot}_{mission.received_at:%Y%m%d}",
        "lot": mission.lot,
        "subject": mission.subject,
        "received_at": mission.received_at.isoformat(),
        "stored_at": stored_at.replace(microsecond=0).isoformat(),
        "deadline": deadline,
        "urgent": mission.urgent,
        "sender_masked": mask_email(mission.sender_email),
        "snippet": mission.body_text[:200],
        "body_html": body_html,
        "body_text": body_text,
        "body_omitted": omitted,
        "body_size_bytes": body_size_bytes,
        "delivery_links": delivery_links,
        "email_id_hash": email_id_hash,
        "source": SOURCE_NAME,
    }


def build_index_entry(
    detail: dict[str, Any], file_name: str, size_bytes: int
) -> dict[str, Any]:
    """Construit l'entrée légère de l'index public."""
    return {
        "id": detail["id"],
        "lot": detail["lot"],
        "subject": detail["subject"],
        "received_at": detail["received_at"],
        "stored_at": detail["stored_at"],
        "deadline": detail["deadline"],
        "urgent": detail["urgent"],
        "sender": detail["sender_masked"],
        "snippet": detail["snippet"],
        "file": file_name,
        "links_count": len(detail["delivery_links"]),
        "size_bytes": size_bytes,
    }


def _received_at_timestamp(entry: dict[str, Any]) -> float:
    raw = entry.get("received_at")
    if not isinstance(raw, str):
        return float("-inf")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("-inf")


def _entry_month(entry: dict[str, Any]) -> str:
    raw = entry.get("received_at")
    return raw[:7] if isinstance(raw, str) else ""


def merge_index_entries(
    live_entries: Sequence[dict[str, Any]],
    new_entries: Sequence[dict[str, Any]],
    max_entries: int = DEFAULT_MAX_INDEX_ENTRIES,
) -> list[dict[str, Any]]:
    """Fusionne les entrées live et rétroactives, puis trie par date décroissante.

    La déduplication se fait par identifiant, puis par couple (lot, mois) : les
    numéros de lot sont réinitialisés chaque mois, donc un lot 268 d'octobre et
    un lot 268 de novembre sont deux missions distinctes.
    """
    combined: dict[str, dict[str, Any]] = {}
    for entry in new_entries:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            combined[entry["id"]] = entry
    for entry in live_entries:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            combined[entry["id"]] = entry

    by_lot: dict[tuple[int, str], dict[str, Any]] = {}
    without_lot: list[dict[str, Any]] = []
    for entry in combined.values():
        lot_raw = entry.get("lot")
        if isinstance(lot_raw, bool) or not isinstance(lot_raw, (int, str)):
            without_lot.append(entry)
            continue
        try:
            lot = int(lot_raw)
        except (TypeError, ValueError):
            without_lot.append(entry)
            continue
        if lot <= 0:
            without_lot.append(entry)
            continue
        key = (lot, _entry_month(entry))
        current = by_lot.get(key)
        if current is None or _received_at_timestamp(entry) > _received_at_timestamp(
            current
        ):
            by_lot[key] = entry

    merged = list(by_lot.values()) + without_lot
    merged.sort(
        key=lambda entry: (
            _received_at_timestamp(entry),
            str(entry.get("id") or ""),
        ),
        reverse=True,
    )
    if max_entries > 0:
        merged = merged[:max_entries]
    return merged


def write_json_atomic(path: Path, data: Any) -> None:
    """Écrit un JSON via un fichier temporaire puis un renommage atomique."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    temp_path = path.with_name(f"{path.name}.tmp.{uuid.uuid4().hex}")
    temp_path.write_text(payload, encoding="utf-8")
    os.chmod(temp_path, 0o644)
    os.replace(temp_path, path)


def load_json_file(path: Path) -> Any:
    """Charge un fichier JSON avec un message d'erreur explicite."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Lecture impossible : {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON invalide : {path} ({exc})") from exc


def fetch_json(url: str, timeout: float = 20.0) -> Any:
    """Télécharge et décode un JSON public."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "render-signal-backfill/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Téléchargement impossible : {url} ({exc})") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Réponse JSON invalide : {url} ({exc})") from exc


def load_live_index(
    args: argparse.Namespace, logger: logging.Logger
) -> list[dict[str, Any]]:
    """Charge l'index de production, avec garde-fou contre une fusion vide."""
    if args.live_index_file is not None:
        data = load_json_file(Path(args.live_index_file))
    elif args.no_network:
        raise RuntimeError("--no-network exige --live-index-file pour l'index live")
    else:
        try:
            data = fetch_json(args.live_index_url)
        except RuntimeError as exc:
            if args.allow_empty_live:
                logger.warning("Index live indisponible, fusion à vide : %s", exc)
                return []
            raise RuntimeError(
                "Index live indisponible. Utilisez --live-index-file, "
                "ou --allow-empty-live pour forcer une fusion à vide."
            ) from exc

    if not isinstance(data, list):
        raise RuntimeError("L'index live doit être une liste JSON")
    entries = [entry for entry in data if isinstance(entry, dict)]
    if len(entries) != len(data):
        logger.warning(
            "Index live : %d entrée(s) non-objet ignorée(s)", len(data) - len(entries)
        )
    return entries


def load_webhook_links(
    args: argparse.Namespace, logger: logging.Logger
) -> list[dict[str, Any]]:
    """Charge les paires R2 depuis le proxy live, avec repli local."""
    data: Any = None
    if args.links_file is not None:
        data = load_json_file(Path(args.links_file))
    elif args.no_network:
        if LOCAL_LINKS_FILE.is_file():
            data = load_json_file(LOCAL_LINKS_FILE)
        else:
            logger.warning(
                "Aucun fichier webhook_links.json local : liens non enrichis"
            )
            return []
    else:
        try:
            data = fetch_json(args.links_url)
        except RuntimeError as exc:
            if LOCAL_LINKS_FILE.is_file():
                logger.warning("Proxy R2 indisponible, repli local : %s", exc)
                data = load_json_file(LOCAL_LINKS_FILE)
            else:
                logger.warning("Proxy R2 indisponible, liens non enrichis : %s", exc)
                return []

    if not isinstance(data, list):
        raise RuntimeError("webhook_links doit être une liste JSON")
    return [entry for entry in data if isinstance(entry, dict)]


def package_archives(
    data_root: Path,
    output_dir: Path,
    detail_files: Sequence[Path],
    index_file: Path,
) -> tuple[Path, Path]:
    """Crée les archives tar.gz et zip prêtes à extraire dans data/."""
    entries: list[tuple[str, Path]] = [
        (f"emails/{path.name}", path) for path in detail_files
    ]
    entries.append(("emails_recadrage_index.json", index_file))

    tar_path = output_dir / f"{ARCHIVE_BASENAME}.tar.gz"
    zip_path = output_dir / f"{ARCHIVE_BASENAME}.zip"

    with tarfile.open(tar_path, "w:gz") as tar:
        for arcname, path in entries:
            tar.add(str(path), arcname=arcname)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for arcname, path in entries:
            archive.write(str(path), arcname=arcname)

    return tar_path, zip_path


def build_outputs(
    missions: Sequence[Mission],
    live_entries: Sequence[dict[str, Any]],
    links_entries: Sequence[dict[str, Any]],
    *,
    output_dir: Path,
    stored_at: datetime,
    window_since: datetime,
    window_until: datetime,
    max_entries: int = DEFAULT_MAX_INDEX_ENTRIES,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
) -> dict[str, Any]:
    """Génère les fichiers détail, l'index fusionné, le payload et les archives."""
    data_root = output_dir / "data"
    emails_dir = data_root / "emails"
    emails_dir.mkdir(parents=True, exist_ok=True)

    links_index = build_links_index(links_entries)
    new_entries: list[dict[str, Any]] = []
    detail_files: list[Path] = []
    payload_missions: list[dict[str, Any]] = []
    r2_missions = 0
    r2_links = 0

    for mission in missions:
        delivery_links = sanitize_delivery_links(mission.raw_links, links_index)
        detail = build_detail_entry(
            mission,
            stored_at=stored_at,
            delivery_links=delivery_links,
            max_body_bytes=max_body_bytes,
        )
        file_name = f"{detail['id']}.json"
        if _SAFE_FILE_PATTERN.match(file_name) is None:
            raise ValueError(f"Nom de fichier non sûr : {file_name}")

        detail_path = emails_dir / file_name
        write_json_atomic(detail_path, detail)
        size_bytes = detail_path.stat().st_size
        index_entry = build_index_entry(detail, file_name, size_bytes)
        new_entries.append(index_entry)
        detail_files.append(detail_path)
        payload_missions.append(
            {"file": file_name, "index": index_entry, "detail": detail}
        )

        mission_r2 = [link for link in delivery_links if link.get("r2_url")]
        r2_links += len(mission_r2)
        if mission_r2:
            r2_missions += 1

    merged_index = merge_index_entries(live_entries, new_entries, max_entries)
    index_file = data_root / "emails_recadrage_index.json"
    write_json_atomic(index_file, merged_index)

    payload = {
        "schema_version": 1,
        "generated_at": stored_at.replace(microsecond=0).isoformat(),
        "source": SOURCE_NAME,
        "window": {
            "since": window_since.isoformat(),
            "until": window_until.isoformat(),
        },
        "missions": payload_missions,
    }
    payload_path = output_dir / "backfill_payloads_30d.json"
    write_json_atomic(payload_path, payload)

    tar_path, zip_path = package_archives(
        data_root, output_dir, detail_files, index_file
    )

    return {
        "missions": len(missions),
        "index_live": len(live_entries),
        "index_merged": len(merged_index),
        "r2_missions": r2_missions,
        "r2_links": r2_links,
        "first": merged_index[0] if merged_index else None,
        "last": merged_index[-1] if merged_index else None,
        "lot_115": any(entry.get("lot") == 115 for entry in merged_index),
        "data_root": data_root,
        "index_file": index_file,
        "payload_file": payload_path,
        "tar_file": tar_path,
        "zip_file": zip_path,
    }


def parse_cli_datetime(value: str, tz: ZoneInfo) -> datetime:
    """Parse une date ISO ou une date simple dans le fuseau demandé."""
    raw = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        parsed = datetime.fromisoformat(raw)
        return parsed.replace(tzinfo=tz)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Date invalide : {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _oldest_received_at(entries: Sequence[dict[str, Any]]) -> datetime | None:
    oldest: datetime | None = None
    for entry in entries:
        raw = entry.get("received_at")
        if not isinstance(raw, str):
            continue
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if oldest is None or value < oldest:
            oldest = value
    return oldest


def build_parser() -> argparse.ArgumentParser:
    """Construit le parseur d'arguments du script."""
    parser = argparse.ArgumentParser(
        description="Enrichit l'archive email recadrage sur les 30 derniers jours."
    )
    parser.add_argument("--mbox", type=Path, default=DEFAULT_MBOX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Début de fenêtre (ISO 8601 ou YYYY-MM-DD, défaut: today - days)",
    )
    parser.add_argument(
        "--until",
        type=str,
        default=None,
        help="Fin exclusive de fenêtre (défaut: plus ancienne entrée live)",
    )
    parser.add_argument(
        "--now",
        type=str,
        default=None,
        help="Horodatage de référence pour la fenêtre et stored_at",
    )
    parser.add_argument("--live-index-url", default=DEFAULT_LIVE_INDEX_URL)
    parser.add_argument("--live-index-file", type=Path, default=None)
    parser.add_argument("--links-url", default=DEFAULT_LINKS_URL)
    parser.add_argument("--links-file", type=Path, default=None)
    parser.add_argument("--webhook-config", type=Path, default=WEBHOOK_CONFIG_FILE)
    parser.add_argument("--max-entries", type=int, default=DEFAULT_MAX_INDEX_ENTRIES)
    parser.add_argument("--allow-empty-live", action="store_true")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Point d'entrée CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    logger = logging.getLogger("backfill_recadrage")

    try:
        tz = ZoneInfo(DEFAULT_TZ)
        now = parse_cli_datetime(args.now, tz) if args.now else datetime.now(tz)
        if args.days <= 0:
            raise ValueError("--days doit être strictement positif")
        if args.max_entries < 0:
            raise ValueError("--max-entries doit être positif ou nul")

        live_entries = load_live_index(args, logger)
        if not live_entries:
            logger.warning(
                "Index live vide : la fusion ne contiendra que les missions "
                "rétroactives"
            )

        if args.until:
            until = parse_cli_datetime(args.until, tz)
        else:
            oldest_live = _oldest_received_at(live_entries)
            until = oldest_live.astimezone(tz) if oldest_live else now

        if args.since:
            since = parse_cli_datetime(args.since, tz)
        else:
            since = (now - timedelta(days=args.days)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        if since >= until:
            raise ValueError(
                "Fenêtre vide : "
                f"since={since.isoformat()} >= until={until.isoformat()}"
            )

        window_start, window_end = load_webhook_time_window(Path(args.webhook_config))
        missions = extract_missions_from_mbox(
            Path(args.mbox),
            since=since,
            until=until,
            tz=tz,
            window_start=window_start,
            window_end=window_end,
            logger=logger,
        )
        links_entries = load_webhook_links(args, logger)
        summary = build_outputs(
            missions,
            live_entries,
            links_entries,
            output_dir=Path(args.output_dir),
            stored_at=now,
            window_since=since,
            window_until=until,
            max_entries=args.max_entries,
        )
    except (
        RuntimeError,
        ValueError,
        FileNotFoundError,
        OSError,
        argparse.ArgumentTypeError,
    ) as exc:
        print(f"ERREUR: {exc}", file=sys.stderr)
        return 1

    first = summary["first"]
    last = summary["last"]
    print("=== Backfill recadrage 30 jours ===")
    print(f"Fenêtre         : {since.isoformat()} -> {until.isoformat()}")
    print(f"Missions mbox   : {summary['missions']}")
    print(f"Index live      : {summary['index_live']}")
    print(f"Index fusionné  : {summary['index_merged']}")
    print(
        f"Liens R2        : {summary['r2_missions']}/{summary['missions']} missions, "
        f"{summary['r2_links']} lien(s)"
    )
    print(f"Lot 115         : {'présent' if summary['lot_115'] else 'ABSENT'}")
    if isinstance(first, dict):
        print(f"Première entrée : lot {first.get('lot')} - {first.get('received_at')}")
    if isinstance(last, dict):
        print(f"Dernière entrée : lot {last.get('lot')} - {last.get('received_at')}")
    print(f"Archives        : {summary['tar_file']}")
    print(f"                  {summary['zip_file']}")
    print(f"Payload PHP     : {summary['payload_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
