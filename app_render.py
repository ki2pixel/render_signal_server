# --- Singleton lock to avoid multiple pollers across Gunicorn workers ---
BG_LOCK_FH = None  # Keep a global reference so the lock is held for the process lifetime

def acquire_singleton_lock(lock_path: str) -> bool:
    """
    Try to acquire an exclusive, non-blocking lock on a lock file.
    Returns True if the lock is acquired, False otherwise.
    """
    global BG_LOCK_FH
    try:
        # Open file handle and try to lock it exclusively
        BG_LOCK_FH = open(lock_path, "a+")
        fcntl.flock(BG_LOCK_FH.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        BG_LOCK_FH.write(f"pid={os.getpid()}\n")
        BG_LOCK_FH.flush()
        return True
    except BlockingIOError:
        # Another process holds the lock
        try:
            if BG_LOCK_FH:
                BG_LOCK_FH.close()
        finally:
            BG_LOCK_FH = None
        return False
    except Exception:
        # On any unexpected error, do not start multiple pollers
        try:
            if BG_LOCK_FH:
                BG_LOCK_FH.close()
        finally:
            BG_LOCK_FH = None
        return False
from flask import Flask, jsonify, request, send_from_directory, render_template, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import time
from pathlib import Path
import json
import logging
import re
import requests
import threading
from datetime import datetime, timedelta, timezone
import imaplib
import email
from email.header import decode_header
import ssl
import hashlib
import urllib3
import re
import unicodedata
from bs4 import BeautifulSoup  # HTML parsing for resolving direct download links
from urllib.parse import urlparse, urljoin
import fcntl  # File locking to ensure singleton background poller across processes
try:
    # Playwright is optional, enabled via env var ENABLE_HEADLESS_RESOLUTION=true
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError  # type: ignore
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False
import threading as _threading

# --- URL Providers Pattern ---
# Détecte les liens de livraison pris en charge dans le corps de l'email
# - Dropbox folder links
# - FromSmash share links
# - SwissTransfer download links
# Utilise un regex compilé (insensible à la casse) pour robustesse et maintenabilité.
URL_PROVIDERS_PATTERN = re.compile(
    r"(https?://(?:www\.)?(?:"
    r"dropbox\.com/scl/fo"            # Dropbox folder
    r"|fromsmash\.com/[A-Za-z0-9_-]+" # FromSmash share id
    r"|swisstransfer\.com/d/[A-Za-z0-9-]+" # SwissTransfer download id
    r"))",
    re.IGNORECASE,
)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    # Logging at module level might not use app's logger config yet.
    # Standard logging can be used if needed here, or rely on app.logger later.


# --- Helpers: Provider link extraction and resolution (FromSmash, SwissTransfer) ---
def _detect_provider(url: str) -> str | None:
    """Retourne le fournisseur à partir de l'URL ("dropbox"|"fromsmash"|"swisstransfer")."""
    if not url:
        return None
    u = url.lower()
    if "dropbox.com" in u:
        return "dropbox"
    if "fromsmash.com" in u:
        return "fromsmash"
    if "swisstransfer.com" in u:
        return "swisstransfer"
    return None


def extract_provider_links_from_text(text: str) -> list[dict]:
    """
    Extrait toutes les URLs supportées présentes dans un texte via URL_PROVIDERS_PATTERN.

    Retourne une liste de dicts: [{"provider": str, "raw_url": str}]
    """
    results = []
    if not text:
        return results
    for m in URL_PROVIDERS_PATTERN.finditer(text):
        raw = m.group(1)
        provider = _detect_provider(raw)
        if provider:
            results.append({"provider": provider, "raw_url": raw})
    return results


def _http_get(url: str, timeout: int = 15) -> tuple[int | None, str]:
    """Effectue une requête GET simple et retourne (status_code, text)."""
    try:
        headers = {
            "User-Agent": "render-signal-server/1.0 (+https://example.local)"
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        return resp.status_code, resp.text
    except Exception as e:
        logging.warning(f"RESOLVER: GET failed for {url}: {e}")
        return None, ""


def resolve_fromsmash_direct_url(landing_url: str) -> str | None:
    """
    Tente de déduire un lien de téléchargement direct à partir d'une landing page FromSmash.
    Heuristique: parser le HTML et chercher une URL contenant "fromsmash.co/transfer/<id>/zip".
    Retourne None si non trouvé.
    """
    status, html = _http_get(landing_url)
    if not status or status >= 400 or not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Chercher des liens explicites
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "fromsmash.co/transfer/" in href and "/zip/" in href:
                # S'assurer que l'URL est absolue
                return href if href.startswith("http") else urljoin(landing_url, href)
        # Chercher dans les scripts/texte brut (certains sites injectent via JS)
        text = soup.get_text("\n")
        m = re.search(r'https?://[^\s\'\"]*fromsmash\.co/transfer/[^\s\'\"]*/zip/[^\s\'\"]*', text)
        if m:
            return m.group(0)
    except Exception as e:
        logging.warning(f"RESOLVER: FromSmash parse failed for {landing_url}: {e}")
    return None


def resolve_swisstransfer_direct_url(landing_url: str) -> str | None:
    """
    Tente de déduire un lien direct SwissTransfer en parsant la landing page
    et en recherchant un href vers "/api/download/<uuid>". Conserve les paramètres si présents.
    Retourne None si non trouvé.
    """
    status, html = _http_get(landing_url)
    if not status or status >= 400 or not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
        # 1) Lien direct explicite sous forme d'ancre
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/api/download/" in href:
                return href if href.startswith("http") else urljoin(landing_url, href)
        # 2) Parfois présent dans des scripts inline
        for script in soup.find_all("script"):
            content = script.string or ""
            if not content:
                continue
            m = re.search(r"https?://[^\s\'\"]*swisstransfer\.com/api/download/[^\s\'\"]+", content)
            if m:
                return m.group(0)
        # 3) Recherche texte globale
        text = soup.get_text("\n")
        m2 = re.search(r"https?://[^\s\'\"]*swisstransfer\.com/api/download/[^\s\'\"]+", text)
        if m2:
            return m2.group(0)
    except Exception as e:
        logging.warning(f"RESOLVER: SwissTransfer parse failed for {landing_url}: {e}")
    return None


def resolve_direct_download_url(provider: str, raw_url: str) -> str | None:
    """Route la résolution selon le fournisseur. Retourne l'URL directe si trouvée, sinon None."""
    try:
        if provider == "fromsmash":
            direct = resolve_fromsmash_direct_url(raw_url)
            if direct:
                return direct
        if provider == "swisstransfer":
            direct = resolve_swisstransfer_direct_url(raw_url)
            if direct:
                return direct
        # Dropbox: un dossier n'a pas de lien direct unique (nécessite API / auth)
        # Fallback headless si activé et pertinent
        enable_headless = os.environ.get("ENABLE_HEADLESS_RESOLUTION", "false").lower() == "true"
        if enable_headless and provider in {"fromsmash", "swisstransfer"}:
            return resolve_with_headless_browser(provider, raw_url)
        return None
    except Exception as e:
        logging.warning(f"RESOLVER: Failed to resolve direct URL for {provider} / {raw_url}: {e}")
        return None


# --- Headless resolution with Playwright (optional) ---
_HEADLESS_LOCK = _threading.Lock()

def _with_playwright(fn):
    """Utility wrapper to start/stop playwright in a safe manner."""
    if not PLAYWRIGHT_AVAILABLE:
        return None
    with _HEADLESS_LOCK:
        try:
            with sync_playwright() as p:
                return fn(p)
        except Exception as e:
            logging.warning(f"HEADLESS: Playwright error: {e}")
            return None


def resolve_with_headless_browser(provider: str, raw_url: str) -> str | None:
    """
    Utilise un navigateur headless (Playwright) pour simuler le clic de téléchargement et
    intercepter l'URL de téléchargement directe. Nécessite ENABLE_HEADLESS_RESOLUTION=true et Playwright installé.

    Sécurité/Perf:
    - Timeout global ~30s
    - Un seul navigateur à la fois (lock)
    - Aucun stockage de session
    """
    if not PLAYWRIGHT_AVAILABLE:
        logging.info("HEADLESS: Playwright not available. Skipping headless resolution.")
        return None

    # Filtre d'URL basique pour éviter des domaines arbitraires
    prov = _detect_provider(raw_url)
    if prov not in {"fromsmash", "swisstransfer"}:
        return None

    # Charger la configuration depuis les variables d'environnement
    try:
        max_attempts = int(os.environ.get("HEADLESS_MAX_ATTEMPTS", "3"))
    except Exception:
        max_attempts = 3
    try:
        click_timeout_ms = int(os.environ.get("HEADLESS_CLICK_TIMEOUT_MS", "5000"))
    except Exception:
        click_timeout_ms = 5000
    try:
        total_timeout_ms = int(os.environ.get("HEADLESS_TOTAL_TIMEOUT_MS", "45000"))
    except Exception:
        total_timeout_ms = 45000
    try:
        scrolls_per_attempt = int(os.environ.get("HEADLESS_SCROLLS_PER_ATTEMPT", "1"))
    except Exception:
        scrolls_per_attempt = 1
    trace_enabled = os.environ.get("HEADLESS_TRACE", "false").lower() == "true"

    def run(p):
        # Permet de "dés-automatiser" un peu l'empreinte navigateur
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
        headless_mode = os.environ.get("HEADLESS_MODE", "true").lower() != "false"
        browser = p.chromium.launch(headless=headless_mode, args=launch_args)
        try:
            # UA réaliste pour limiter les 403 (bot-protection)
            ua = os.environ.get("HEADLESS_USER_AGENT", (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ))
            context = browser.new_context(
                user_agent=ua,
                locale="fr-FR",
                timezone_id=os.environ.get("HEADLESS_TZ", "Europe/Paris"),
                color_scheme="light",
                java_script_enabled=True,
                extra_http_headers={
                    "Accept-Language": os.environ.get("HEADLESS_ACCEPT_LANGUAGE", "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"),
                }
            )
            page = context.new_page()

            # Collecte des requêtes réseau susceptibles d'être le téléchargement
            captured_url = {"value": None}
            candidates: list[str] = []
            seen_urls = []  # pour le mode trace

            # Fonction utilitaire: heuristique stricte pour n'accepter que des fichiers
            FILE_CT_WHITELIST = (
                "application/zip",
                "application/octet-stream",
                "application/x-zip-compressed",
                "application/x-7z-compressed",
                "application/x-tar",
                "application/gzip",
            )
            URL_BLACKLIST_SUBSTR = (
                "/customization/",
                "/customization/logo/",
                "/managedThemes/",
                "/preview/",
                "/thumbnail",
                "/assets/",
                "/fonts/",
                ".svg",
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
                ".ttf",
                "theme.fromsmash.co",
                "/processed/Managed/",
                "promotional.storage.infomaniak.com",
            )

            def is_likely_file_download(url: str, resp) -> bool:
                if any(part in url for part in URL_BLACKLIST_SUBSTR):
                    return False
                try:
                    headers = resp.headers or {}
                except Exception:
                    headers = {}
                ct = (headers.get("content-type", "") or "").lower()
                cd = (headers.get("content-disposition", "") or "").lower()
                # Exclure explicitement les images même si 'attachment'
                if ct.startswith("image/"):
                    return False
                if "attachment" in cd:
                    return True
                if any(ct.startswith(w) for w in FILE_CT_WHITELIST):
                    return True
                # Whitelist d'URL indicative côté FromSmash (et éviter les domaines de thème)
                if provider == "fromsmash" and ("/transfer/" in url) and ("/zip" in url or "/download" in url or "/archive" in url):
                    return True
                # SwissTransfer API pattern
                if provider == "swisstransfer" and "/api/download/" in url:
                    return True
                return False

            # Variante sans accès aux headers de réponse
            def accept_url(url: str) -> bool:
                if any(part in url for part in URL_BLACKLIST_SUBSTR):
                    return False
                lower = url.lower()
                if any(lower.endswith(ext) for ext in (".svg", ".png", ".jpg", ".jpeg", ".webp", ".ttf")):
                    return False
                if provider == "fromsmash":
                    return ("/transfer/" in url) and ("/zip" in url or "/download" in url or "/archive" in url or "/file/")
                if provider == "swisstransfer":
                    return "/api/download/" in url
                return False

            # Classement des URLs candidates par pertinence
            def rank_url(url: str) -> int:
                u = url.lower()
                if provider == "fromsmash":
                    if "/zip/" in u or u.endswith(".zip"):
                        return 100
                    if "/download" in u or "/archive" in u:
                        return 90
                    if "/file/" in u:
                        return 50
                    return 10
                if provider == "swisstransfer":
                    if "/api/download/" in u:
                        return 100
                    return 0
                return 0

            # Intercepter les réponses réseau (redirections, Content-Disposition)
            def on_response(resp):
                try:
                    url = resp.url
                    if trace_enabled:
                        seen_urls.append(f"RESP {resp.status}: {url}")
                    # Appliquer un filtrage strict fichier uniquement
                    if is_likely_file_download(url, resp):
                        if url not in candidates and accept_url(url):
                            candidates.append(url)

                    # Analyse des payloads JSON pour extraire un lien
                    ctype = (resp.headers.get("content-type", "") or "").lower()
                    if "application/json" in ctype and not captured_url["value"]:
                        try:
                            data = resp.json()
                        except Exception:
                            data = None
                        
                        def scan_json(obj):
                            if not obj:
                                return None
                            if isinstance(obj, dict):
                                for k, v in obj.items():
                                    # Inspecter les champs texte susceptibles de contenir une URL
                                    if isinstance(v, str):
                                        s = v
                                        if provider == "fromsmash" and ("fromsmash.co/transfer/" in s or "/transfer/" in s) and ("/zip" in s or "/download" in s or "/archive" in s):
                                            return s
                                        if provider == "swisstransfer" and ("swisstransfer.com" in s and "/api/download" in s):
                                            return s
                                    else:
                                        found = scan_json(v)
                                        if found:
                                            return found
                            elif isinstance(obj, list):
                                for it in obj:
                                    found = scan_json(it)
                                    if found:
                                        return found
                            return None

                        found_url = scan_json(data)
                        if found_url and accept_url(found_url):
                            if found_url not in candidates:
                                candidates.append(found_url)
                except Exception:
                    pass

            def on_request(req):
                url = req.url
                if trace_enabled:
                    seen_urls.append(f"REQ: {url}")
                # Ne capture pas au stade request; attend la réponse filtrée

            page.on("request", on_request)
            page.on("response", on_response)

            # Navigation
            # Timeouts
            page.set_default_timeout(min(15000, total_timeout_ms))
            page.goto(raw_url)
            # Attendre l'idle réseau initial
            try:
                page.wait_for_load_state("networkidle", timeout=min(15000, total_timeout_ms))
            except PlaywrightTimeoutError:
                pass

            # Tentative d'accepter les consentements au plus tôt (utile pour SwissTransfer)
            if provider == "swisstransfer":
                try:
                    time.sleep(1.0)
                    for consent_sel in [
                        "text=J'accepte",
                        "text=Tout accepter",
                        "text=Accepter",
                        "text=Accept all",
                        "text=I agree",
                    ]:
                        elc = page.query_selector(consent_sel)
                        if elc:
                            elc.click()
                            try:
                                page.wait_for_load_state("networkidle", timeout=min(5000, total_timeout_ms))
                            except PlaywrightTimeoutError:
                                pass
                            break
                except Exception:
                    pass

            # Heuristiques de clics possibles
            selectors = [
                "text=Download",
                "text=Télécharger",
                "text=download",
                "text=télécharger",
                "button:has-text('Download')",
                "button:has-text('Télécharger')",
                "a:has-text('Download')",
                "a:has-text('Télécharger')",
                # ZIP direct anchors when present
                "a[href*='/zip/']",
                # Quelques sélecteurs spécifiques probables
                "text=Télécharger tout",
                "text=Download all",
                "button:has-text('Télécharger tout')",
                "button:has-text('Download all')",
                # Variantes possibles
                "role=button[name='Télécharger']",
                "role=button[name='Download']",
                # Consentements fréquents
                "text=J'accepte",
                "text=Tout accepter",
                "text=Accepter",
                "text=Accept all",
                "text=I agree",
            ]
            # Faire plusieurs passes avec scrolls, en respectant une deadline globale
            start_ts = time.monotonic()
            def remaining_ms():
                return max(0, int(total_timeout_ms - (time.monotonic() - start_ts) * 1000))

            for attempt in range(max_attempts):
                for sel in selectors:
                    try:
                        el = page.query_selector(sel)
                        if el:
                            # Essayer d'attendre un éventuel download
                            try:
                                with page.expect_download(timeout=max(1, min(click_timeout_ms, remaining_ms()))) as dl_info:
                                    el.click()
                                download = dl_info.value
                                # Certaines versions n'exposent pas directement l'URL; tenter resp.url
                                d_url = download.url or captured_url["value"]
                                if d_url and accept_url(d_url):
                                    if d_url not in candidates:
                                        candidates.append(d_url)
                            except PlaywrightTimeoutError:
                                # Pas de download event; fallback simple
                                el.click()
                            # attendre réseau après clic
                            try:
                                page.wait_for_load_state("networkidle", timeout=max(1, min(10000, remaining_ms())))
                            except PlaywrightTimeoutError:
                                pass
                            # Attendre une réponse correspondant aux patterns connus
                            if not captured_url["value"]:
                                try:
                                    pattern = "/api/download/" if provider == "swisstransfer" else "/transfer/"
                                    page.wait_for_response(lambda r: pattern in r.url, timeout=max(1, min(5000, remaining_ms())))
                                except PlaywrightTimeoutError:
                                    pass
                    except Exception:
                        continue

                    if captured_url["value"]:
                        break
                if captured_url["value"]:
                    break
                # Scroll pour révéler d'autres éléments éventuels
                for _ in range(max(0, scrolls_per_attempt)):
                    try:
                        page.mouse.wheel(0, 1200)
                    except Exception:
                        pass
                # Tentative: cliquer tous les boutons/ancres visibles contenant des mots clés
                try:
                    if remaining_ms() > 0 and not captured_url["value"]:
                        texts = ["télécharger", "download", "accepter", "accept"]
                        # Boutons
                        for b in page.query_selector_all("button"):
                            try:
                                label = (b.inner_text() or "").lower()
                                if any(t in label for t in texts):
                                    try:
                                        with page.expect_download(timeout=max(1, min(click_timeout_ms, remaining_ms()))) as dl_info:
                                            b.click()
                                        d = dl_info.value
                                        d_url = d.url or captured_url["value"]
                                        if d_url:
                                            captured_url["value"] = d_url
                                    except PlaywrightTimeoutError:
                                        b.click()
                                    try:
                                        page.wait_for_load_state("networkidle", timeout=max(1, min(5000, remaining_ms())))
                                    except PlaywrightTimeoutError:
                                        pass
                                    if captured_url["value"]:
                                        break
                            except Exception:
                                pass
                        # Liens
                        if not captured_url["value"]:
                            for a in page.query_selector_all("a[href]"):
                                try:
                                    al = (a.inner_text() or "").lower()
                                    if any(t in al for t in texts):
                                        try:
                                            with page.expect_download(timeout=max(1, min(click_timeout_ms, remaining_ms()))) as dl_info:
                                                a.click()
                                            d = dl_info.value
                                            d_url = d.url or captured_url["value"]
                                            if d_url:
                                                captured_url["value"] = d_url
                                        except PlaywrightTimeoutError:
                                            a.click()
                                        try:
                                            page.wait_for_load_state("networkidle", timeout=max(1, min(5000, remaining_ms())))
                                        except PlaywrightTimeoutError:
                                            pass
                                        if captured_url["value"]:
                                            break
                                except Exception:
                                    pass
                    
                except Exception:
                    pass
                # Si deadline dépassée, on sort
                if remaining_ms() <= 0:
                    break

            # Si pas capturé via clic, inspecter les <a> visibles
            if not captured_url["value"]:
                anchors = page.query_selector_all("a[href]")
                for a in anchors:
                    try:
                        href = a.get_attribute("href") or ""
                        if provider == "fromsmash" and ("/transfer/" in href and "/zip/" in href):
                            # Essayer de cliquer pour obtenir l'URL signée finale via expect_download
                            try:
                                with page.expect_download(timeout=max(1, min(5000, total_timeout_ms))) as dl_info:
                                    a.click()
                                d = dl_info.value
                                d_url = d.url or href
                                if d_url and accept_url(d_url):
                                    if d_url not in candidates:
                                        candidates.append(d_url)
                                    captured_url["value"] = d_url
                                    break
                            except PlaywrightTimeoutError:
                                # Si pas d'event, utiliser l'href tel quel (s'il est déjà signé)
                                if accept_url(href):
                                    if href not in candidates:
                                        candidates.append(href)
                                    captured_url["value"] = href
                                    break
                        if provider == "swisstransfer" and "/api/download/" in href:
                            captured_url["value"] = href
                            break
                    except Exception:
                        continue

            # Sélection finale: choisir la meilleure URL candidate selon le provider
            direct = None
            if candidates:
                direct = sorted(candidates, key=rank_url, reverse=True)[0]
            else:
                direct = captured_url["value"]
            if trace_enabled and not direct:
                logging.info("HEADLESS_TRACE: no direct url captured; seen URLs:\n" + "\n".join(seen_urls[:200]))
            return direct
        finally:
            try:
                browser.close()
            except Exception:
                pass

    return _with_playwright(run)


app = Flask(__name__, template_folder='.', static_folder='static')
# NOUVEAU: Une clé secrète est OBLIGATOIRE pour les sessions.
# Pour la production, utilisez une valeur complexe stockée dans les variables d'environnement.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "une-cle-secrete-tres-complexe-pour-le-developpement-a-changer")

# --- Tokens et Config de référence (basés sur l'image/description fournie) ---
REF_TRIGGER_PAGE_USER = "admin"
REF_TRIGGER_PAGE_PASSWORD = "UDPVA#esKf40r@"
REF_PROCESS_API_TOKEN = "rnd_PW5cGYVf4gl3limu9cYkFw27u8dY"
REF_EMAIL_ADDRESS = "kidpixel@inbox.lt"
REF_EMAIL_PASSWORD = "YvP3Zw66Xx"  # Special IMAP/SMTP password for inbox.lt
REF_IMAP_SERVER = "mail.inbox.lt"
REF_IMAP_PORT = 993
REF_IMAP_USE_SSL = True
REF_WEBHOOK_URL = "https://webhook.kidpixel.fr/index.php"
REF_MAKECOM_WEBHOOK_URL = "https://hook.eu2.make.com/s98s0s735h23qakb9pp0id8c8hbhfqph"
REF_MAKECOM_API_KEY = "12e8b61d-a78e-47f5-9f87-359af19f46cb"
REF_SENDER_OF_INTEREST_FOR_POLLING = "achats@media-solution.fr,camille.moine.pro@gmail.com,a.peault@media-solution.fr,v.lorent@media-solution.fr,technique@media-solution.fr,t.deslus@media-solution.fr"
REF_POLLING_TIMEZONE = "Europe/Paris"
REF_POLLING_ACTIVE_START_HOUR = 9
REF_POLLING_ACTIVE_END_HOUR = 23
REF_POLLING_ACTIVE_DAYS = "0,1,2,3,4"
REF_EMAIL_POLLING_INTERVAL_SECONDS = 30
# ------------------------------------------------------------------------------------

# --- Configuration du Logging ---
log_level_str = os.environ.get('FLASK_LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')
if not REDIS_AVAILABLE:
    logging.warning(
        "CFG REDIS (module level): 'redis' Python library not installed. Redis-based features will be disabled or use fallbacks.")

# --- Configuration des Webhooks Make.com et présence ---
# Valeurs d'environnement attendues:
# - MAKECOM_WEBHOOK_URL (URL par défaut existante)
# - MAKECOM_API_KEY (clé API existante)
# - PRESENCE (bool string: true/false)
# - PRESENCE_TRUE_MAKE_WEBHOOK_URL (URL Make pour présence True) 
# - PRESENCE_FALSE_MAKE_WEBHOOK_URL (URL Make pour présence False)
#   Ces deux dernières peuvent être fournies sous forme:
#   * URL complète: "https://hook.eu2.make.com/<token>"
#   * OU alias de type "<token>@hook.eu2.make.com" (nous le normaliserons en URL HTTPS)

def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}

def _normalize_make_webhook_url(value: str | None) -> str | None:
    """
    Accepte une valeur:
    - URL complète Make: https://hook.eu2.make.com/<token>
    - Forme email/alias: <token>@hook.eu2.make.com
    Retourne toujours une URL HTTPS normalisée ou None si invalide.
    """
    if not value:
        return None
    v = value.strip()
    if v.startswith("http://") or v.startswith("https://"):
        return v
    # forme alias token@hook.eu2.make.com
    if "@hook.eu2.make.com" in v:
        token = v.split("@", 1)[0].strip()
        if token:
            return f"https://hook.eu2.make.com/{token}"
    # si seulement le token est fourni
    if "/" not in v and " " not in v and "@" not in v:
        return f"https://hook.eu2.make.com/{v}"
    return None

PRESENCE_FLAG = _env_bool("PRESENCE", False)
PRESENCE_TRUE_MAKE_WEBHOOK_URL = _normalize_make_webhook_url(os.environ.get("PRESENCE_TRUE_MAKE_WEBHOOK_URL"))
PRESENCE_FALSE_MAKE_WEBHOOK_URL = _normalize_make_webhook_url(os.environ.get("PRESENCE_FALSE_MAKE_WEBHOOK_URL"))

# Feature flag: allow disabling subject-group deduplication temporarily for testing
ENABLE_SUBJECT_GROUP_DEDUP = _env_bool("ENABLE_SUBJECT_GROUP_DEDUP", True)

# Webhook Make (désabonnement/journée/tarifs) configurable
# Default to the latest provided URL so it works out-of-the-box; can be overridden in Render env
DESABO_MAKE_WEBHOOK_URL = _normalize_make_webhook_url(
    os.environ.get("DESABO_MAKE_WEBHOOK_URL") or "https://hook.eu2.make.com/2g65argnpyzgk3lz9t0xzt8tpuylcc8x"
)

# --- Global time window for Make webhooks (DESABO + PRESENCE) ---
# Two ENV variables expected (optional). When both are set, we enforce the time window [start, end) in local timezone.
# Format examples: "11h30", "08h00", "17:45" (both separators supported). If invalid, the constraint is ignored.
WEBHOOKS_TIME_START_STR = os.environ.get("WEBHOOKS_TIME_START", "").strip()
WEBHOOKS_TIME_END_STR = os.environ.get("WEBHOOKS_TIME_END", "").strip()

def _parse_time_hhmm(s: str):
    """Parse 'HHhMM' or 'HH:MM' string into a datetime.time. Returns None if invalid."""
    if not s:
        return None
    try:
        s = s.strip().lower().replace("h", ":")
        m = re.match(r"^(\d{1,2}):(\d{2})$", s)
        if not m:
            return None
        hh = int(m.group(1))
        mm = int(m.group(2))
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return None
        from datetime import time as _time
        return _time(hh, mm)
    except Exception:
        return None

WEBHOOKS_TIME_START = _parse_time_hhmm(WEBHOOKS_TIME_START_STR)
WEBHOOKS_TIME_END = _parse_time_hhmm(WEBHOOKS_TIME_END_STR)

def _is_within_time_window_local(now_dt: datetime) -> bool:
    """Return True if now_dt (localized) falls within [start, end) when both are defined.
    Supports wrap-around windows (e.g., 22:00 -> 06:00). If start/end invalid or absent, returns True (no constraint).
    """
    if not (WEBHOOKS_TIME_START and WEBHOOKS_TIME_END):
        return True
    now_t = now_dt.time()
    start = WEBHOOKS_TIME_START
    end = WEBHOOKS_TIME_END
    if start <= end:
        return start <= now_t < end
    # Wrap-around across midnight
    return (now_t >= start) or (now_t < end)

# --- Configuration des Identifiants pour la page de connexion ---
TRIGGER_PAGE_USER_ENV = os.environ.get("TRIGGER_PAGE_USER", REF_TRIGGER_PAGE_USER)
TRIGGER_PAGE_PASSWORD_ENV = os.environ.get("TRIGGER_PAGE_PASSWORD", REF_TRIGGER_PAGE_PASSWORD)
users = {}
if TRIGGER_PAGE_USER_ENV and TRIGGER_PAGE_PASSWORD_ENV:
    users[TRIGGER_PAGE_USER_ENV] = TRIGGER_PAGE_PASSWORD_ENV
    app.logger.info(f"CFG AUTH: Utilisateur '{TRIGGER_PAGE_USER_ENV}' configuré pour la connexion.")
else:
    app.logger.warning(
        "CFG AUTH: TRIGGER_PAGE_USER ou TRIGGER_PAGE_PASSWORD non défini. La connexion à l'interface sera impossible.")

# --- NOUVELLE CONFIGURATION : FLASK-LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirige les utilisateurs non connectés vers la route /login
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "info"


# NOUVEAU: Classe utilisateur requise par Flask-Login
class User(UserMixin):
    def __init__(self, id):
        self.id = id

    @staticmethod
    def get(user_id):
        if user_id in users:
            return User(user_id)
        return None


# NOUVEAU: Fonction pour charger un utilisateur depuis la session
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


# --- Configuration du Polling des Emails ---
POLLING_TIMEZONE_STR = os.environ.get("POLLING_TIMEZONE", REF_POLLING_TIMEZONE)
POLLING_ACTIVE_START_HOUR = int(os.environ.get("POLLING_ACTIVE_START_HOUR", REF_POLLING_ACTIVE_START_HOUR))
POLLING_ACTIVE_END_HOUR = int(os.environ.get("POLLING_ACTIVE_END_HOUR", REF_POLLING_ACTIVE_END_HOUR))
POLLING_ACTIVE_DAYS_RAW = os.environ.get("POLLING_ACTIVE_DAYS", REF_POLLING_ACTIVE_DAYS)
POLLING_ACTIVE_DAYS = []
if POLLING_ACTIVE_DAYS_RAW:
    try:
        POLLING_ACTIVE_DAYS = [int(d.strip()) for d in POLLING_ACTIVE_DAYS_RAW.split(',') if
                               d.strip().isdigit() and 0 <= int(d.strip()) <= 6]
    except ValueError:
        app.logger.warning(
            f"CFG POLL: Invalid POLLING_ACTIVE_DAYS ('{POLLING_ACTIVE_DAYS_RAW}'). Using default Mon-Fri.")
        POLLING_ACTIVE_DAYS = [0, 1, 2, 3, 4]
if not POLLING_ACTIVE_DAYS: POLLING_ACTIVE_DAYS = [0, 1, 2, 3, 4]
TZ_FOR_POLLING = None
if POLLING_TIMEZONE_STR.upper() != "UTC":
    if ZoneInfo:
        try:
            TZ_FOR_POLLING = ZoneInfo(POLLING_TIMEZONE_STR)
            app.logger.info(f"CFG POLL: Using timezone '{POLLING_TIMEZONE_STR}' for polling schedule.")
        except Exception as e:
            app.logger.warning(f"CFG POLL: Error loading TZ '{POLLING_TIMEZONE_STR}': {e}. Using UTC.")
            POLLING_TIMEZONE_STR = "UTC"
    else:
        app.logger.warning(f"CFG POLL: 'zoneinfo' module not available. Using UTC. '{POLLING_TIMEZONE_STR}' ignored.")
        POLLING_TIMEZONE_STR = "UTC"
if TZ_FOR_POLLING is None:
    TZ_FOR_POLLING = timezone.utc
    app.logger.info(f"CFG POLL: Using timezone 'UTC' for polling schedule (default or fallback).")
EMAIL_POLLING_INTERVAL_SECONDS = int(
    os.environ.get("EMAIL_POLLING_INTERVAL_SECONDS", REF_EMAIL_POLLING_INTERVAL_SECONDS))
POLLING_INACTIVE_CHECK_INTERVAL_SECONDS = int(os.environ.get("POLLING_INACTIVE_CHECK_INTERVAL_SECONDS", 600))
app.logger.info(
    f"CFG POLL: Active polling interval: {EMAIL_POLLING_INTERVAL_SECONDS}s. Inactive period check interval: {POLLING_INACTIVE_CHECK_INTERVAL_SECONDS}s.")
app.logger.info(
    f"CFG POLL: Active schedule ({POLLING_TIMEZONE_STR}): {POLLING_ACTIVE_START_HOUR:02d}:00-{POLLING_ACTIVE_END_HOUR:02d}:00. Days (0=Mon): {POLLING_ACTIVE_DAYS}")

# --- Chemins et Fichiers ---
SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data_app_render"))
TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "local_workflow_trigger_signal.json"
SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
app.logger.info(f"CFG PATH: Signal directory for ephemeral files: {SIGNAL_DIR.resolve()}")

# --- Configuration Redis ---
REDIS_URL = os.environ.get('REDIS_URL')
redis_client = None
PROCESSED_EMAIL_IDS_REDIS_KEY = "processed_email_ids_set_v1"
PROCESSED_SUBJECT_GROUPS_REDIS_KEY = "processed_subject_groups_set_v1"

# In-memory fallback for subject-group dedup when Redis is unavailable
SUBJECT_GROUPS_MEMORY: set[str] = set()

# TTL for subject-group deduplication (in days). If > 0 and Redis is available, we set
# a per-group key with an expiration so a new series can re-trigger after TTL.
try:
    SUBJECT_GROUP_TTL_DAYS = int(os.environ.get("SUBJECT_GROUP_TTL_DAYS", "0").strip() or "0")
except Exception:
    SUBJECT_GROUP_TTL_DAYS = 0
SUBJECT_GROUP_TTL_SECONDS = max(0, SUBJECT_GROUP_TTL_DAYS * 24 * 60 * 60)
# Per-group Redis key prefix (we use string keys with TTL instead of a set).
SUBJECT_GROUP_REDIS_PREFIX = "subject_group_processed_v1:"

if REDIS_AVAILABLE and REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL, socket_connect_timeout=5, socket_timeout=5, health_check_interval=30)
        redis_client.ping()
        app.logger.info(
            f"CFG REDIS: Successfully connected to Redis at {REDIS_URL.split('@')[-1] if '@' in REDIS_URL else REDIS_URL}.")
    except redis.exceptions.ConnectionError as e_redis:
        app.logger.error(
            f"CFG REDIS: Could not connect to Redis. Error: {e_redis}. Redis-dependent features will be impaired or use fallbacks.")
        redis_client = None
    except Exception as e_redis_other:
        app.logger.error(
            f"CFG REDIS: An unexpected error occurred during Redis initialization: {e_redis_other}. Redis-dependent features will be impaired or use fallbacks.")
        redis_client = None
elif REDIS_AVAILABLE and not REDIS_URL:
    app.logger.warning(
        "CFG REDIS: REDIS_URL not set, but 'redis' library is available. Redis will not be used for primary storage; fallbacks may apply.")
    redis_client = None
else:
    app.logger.warning("CFG REDIS: 'redis' Python library not installed. Redis will not be used; fallbacks may apply.")
    redis_client = None

app.logger.info(f"CFG DEDUP: SUBJECT_GROUP_TTL_DAYS={SUBJECT_GROUP_TTL_DAYS} (seconds={SUBJECT_GROUP_TTL_SECONDS}) — applies only when Redis is available.")

# --- Configuration IMAP Email ---
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS', REF_EMAIL_ADDRESS)
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', REF_EMAIL_PASSWORD)
IMAP_SERVER = os.environ.get('IMAP_SERVER', REF_IMAP_SERVER)
IMAP_PORT = int(os.environ.get('IMAP_PORT', REF_IMAP_PORT))
IMAP_USE_SSL = os.environ.get('IMAP_USE_SSL', str(REF_IMAP_USE_SSL)).lower() in ('true', '1', 'yes')

# Log configuration sources for debugging
app.logger.info("CFG EMAIL_DEBUG: Configuration sources:")
app.logger.info(f"CFG EMAIL_DEBUG: - EMAIL_ADDRESS: {'ENV' if 'EMAIL_ADDRESS' in os.environ else 'DEFAULT'} = {EMAIL_ADDRESS}")
app.logger.info(f"CFG EMAIL_DEBUG: - EMAIL_PASSWORD: {'ENV' if 'EMAIL_PASSWORD' in os.environ else 'DEFAULT'} = {'*' * len(EMAIL_PASSWORD) if EMAIL_PASSWORD else 'NOT_SET'}")
app.logger.info(f"CFG EMAIL_DEBUG: - IMAP_SERVER: {'ENV' if 'IMAP_SERVER' in os.environ else 'DEFAULT'} = {IMAP_SERVER}")
app.logger.info(f"CFG EMAIL_DEBUG: - IMAP_PORT: {'ENV' if 'IMAP_PORT' in os.environ else 'DEFAULT'} = {IMAP_PORT}")
app.logger.info(f"CFG EMAIL_DEBUG: - IMAP_USE_SSL: {'ENV' if 'IMAP_USE_SSL' in os.environ else 'DEFAULT'} = {IMAP_USE_SSL}")

# Log reference values for comparison
app.logger.info("CFG EMAIL_DEBUG: Reference values:")
app.logger.info(f"CFG EMAIL_DEBUG: - REF_EMAIL_ADDRESS = {REF_EMAIL_ADDRESS}")
app.logger.info(f"CFG EMAIL_DEBUG: - REF_IMAP_SERVER = {REF_IMAP_SERVER}")
app.logger.info(f"CFG EMAIL_DEBUG: - REF_IMAP_PORT = {REF_IMAP_PORT}")

# Validation de la configuration email
email_config_valid = True
if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
    app.logger.warning("CFG EMAIL: Email address or password missing. Email polling features will be disabled.")
    email_config_valid = False
elif not IMAP_SERVER:
    app.logger.warning("CFG EMAIL: IMAP server not configured. Email polling features will be disabled.")
    email_config_valid = False
else:
    app.logger.info(f"CFG EMAIL: Email polling configured for {EMAIL_ADDRESS} via {IMAP_SERVER}:{IMAP_PORT} (SSL: {IMAP_USE_SSL})")

# --- Configuration des Webhooks et Tokens ---
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", REF_WEBHOOK_URL)
MAKECOM_WEBHOOK_URL = os.environ.get("MAKECOM_WEBHOOK_URL", REF_MAKECOM_WEBHOOK_URL)
MAKECOM_API_KEY = os.environ.get("MAKECOM_API_KEY", REF_MAKECOM_API_KEY)
WEBHOOK_SSL_VERIFY = os.environ.get("WEBHOOK_SSL_VERIFY", "true").strip().lower() in ("1", "true", "yes", "on")

app.logger.info(f"CFG WEBHOOK: Custom webhook URL configured to: {WEBHOOK_URL}")
app.logger.info(f"CFG MAKECOM: Make.com webhook URL configured to: {MAKECOM_WEBHOOK_URL}")
app.logger.info(f"CFG WEBHOOK: SSL verification = {WEBHOOK_SSL_VERIFY}")
if not WEBHOOK_SSL_VERIFY:
    # Suppress SSL warnings only if verification is explicitly disabled
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    app.logger.warning("CFG WEBHOOK: SSL verification DISABLED for webhook calls (development/legacy). Use valid certificates in production.")
SENDER_OF_INTEREST_FOR_POLLING_RAW = os.environ.get("SENDER_OF_INTEREST_FOR_POLLING",
                                                    REF_SENDER_OF_INTEREST_FOR_POLLING)
SENDER_LIST_FOR_POLLING = [e.strip().lower() for e in SENDER_OF_INTEREST_FOR_POLLING_RAW.split(',') if
                           e.strip()] if SENDER_OF_INTEREST_FOR_POLLING_RAW else []
if SENDER_LIST_FOR_POLLING:
    app.logger.info(
        f"CFG POLL: Monitoring emails from {len(SENDER_LIST_FOR_POLLING)} senders: {SENDER_LIST_FOR_POLLING}")
else:
    app.logger.warning("CFG POLL: SENDER_OF_INTEREST_FOR_POLLING not set. Email polling likely ineffective.")
EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN", REF_PROCESS_API_TOKEN)
if not EXPECTED_API_TOKEN:
    app.logger.warning("CFG TOKEN: PROCESS_API_TOKEN not set. API endpoints called by Make.com will be insecure.")
else:
    app.logger.info(f"CFG TOKEN: PROCESS_API_TOKEN (for Make.com calls) configured: '{EXPECTED_API_TOKEN[:5]}...')")


# --- Fonctions Utilitaires IMAP ---
def create_imap_connection():
    """Crée une connexion IMAP sécurisée au serveur email."""
    # Log detailed configuration for debugging
    app.logger.info(f"IMAP_DEBUG: Attempting connection with:")
    app.logger.info(f"IMAP_DEBUG: - Server: {IMAP_SERVER}")
    app.logger.info(f"IMAP_DEBUG: - Port: {IMAP_PORT}")
    app.logger.info(f"IMAP_DEBUG: - SSL: {IMAP_USE_SSL}")
    app.logger.info(f"IMAP_DEBUG: - Email: {EMAIL_ADDRESS}")
    app.logger.info(f"IMAP_DEBUG: - Password: {'*' * len(EMAIL_PASSWORD) if EMAIL_PASSWORD else 'NOT_SET'}")

    try:
        if IMAP_USE_SSL:
            # Connexion SSL/TLS
            app.logger.info(f"IMAP_DEBUG: Creating SSL connection to {IMAP_SERVER}:{IMAP_PORT}")
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        else:
            # Connexion non-sécurisée (non recommandée)
            app.logger.info(f"IMAP_DEBUG: Creating non-SSL connection to {IMAP_SERVER}:{IMAP_PORT}")
            mail = imaplib.IMAP4(IMAP_SERVER, IMAP_PORT)

        app.logger.info(f"IMAP_DEBUG: Connection established, attempting authentication...")
        # Authentification
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        app.logger.info(f"IMAP: Successfully connected to {IMAP_SERVER}:{IMAP_PORT}")
        return mail
    except imaplib.IMAP4.error as e:
        app.logger.error(f"IMAP: Authentication failed for {EMAIL_ADDRESS} on {IMAP_SERVER}:{IMAP_PORT} - {e}")
        return None
    except Exception as e:
        app.logger.error(f"IMAP: Connection error to {IMAP_SERVER}:{IMAP_PORT} - {e}")
        return None


def close_imap_connection(mail):
    """Ferme proprement une connexion IMAP."""
    try:
        if mail:
            mail.close()
            mail.logout()
            app.logger.debug("IMAP: Connection closed successfully")
    except Exception as e:
        app.logger.warning(f"IMAP: Error closing connection: {e}")


def generate_email_id(msg_data):
    """Génère un ID unique pour un email basé sur son contenu."""
    # Utilise un hash du Message-ID, sujet et date pour créer un ID unique
    msg_id = msg_data.get('Message-ID', '')
    subject = msg_data.get('Subject', '')
    date = msg_data.get('Date', '')

    # Combine les éléments et crée un hash
    unique_string = f"{msg_id}|{subject}|{date}"
    return hashlib.md5(unique_string.encode('utf-8')).hexdigest()


def extract_sender_email(from_header):
    """
    Extrait l'adresse email du header 'From'.

    Gère les formats:
    - "Name <email@domain.com>" → "email@domain.com"
    - "email@domain.com" → "email@domain.com"

    Args:
        from_header (str): Contenu du header 'From'

    Returns:
        str: Adresse email extraite ou chaîne vide si non trouvée
    """
    if not from_header:
        return ""

    # Pattern regex pour extraire l'email entre < > ou directement
    email_pattern = r'<([^>]+)>|([^\s<>]+@[^\s<>]+)'
    match = re.search(email_pattern, from_header)

    if match:
        # Si trouvé entre < >, utiliser le premier groupe, sinon le second
        return match.group(1) if match.group(1) else match.group(2)

    return ""


def decode_email_header(header_value):
    """Décode les en-têtes d'email qui peuvent être encodés."""
    if not header_value:
        return ""

    decoded_parts = decode_header(header_value)
    decoded_string = ""

    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            if encoding:
                try:
                    decoded_string += part.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    decoded_string += part.decode('utf-8', errors='ignore')
            else:
                decoded_string += part.decode('utf-8', errors='ignore')
        else:
            decoded_string += str(part)

    return decoded_string


def mark_email_as_read_imap(mail, email_num):
    """Marque un email comme lu via IMAP."""
    try:
        mail.store(email_num, '+FLAGS', '\\Seen')
        app.logger.debug(f"IMAP: Email {email_num} marked as read")
        return True
    except Exception as e:
        app.logger.error(f"IMAP: Error marking email {email_num} as read: {e}")
        return False


def check_media_solution_pattern(subject, email_content):
    """
    Vérifie si l'email correspond au pattern Média Solution spécifique et extrait la fenêtre de livraison.

    Conditions minimales:
    1. Contenu contient: "https://www.dropbox.com/scl/fo"
    2. Sujet contient: "Média Solution - Missions Recadrage - Lot"

    Détails d'extraction pour delivery_time:
    - Pattern A (heure seule): "à faire pour" suivi d'une heure (variantes supportées):
      * 11h51, 9h, 09h, 9:00, 09:5, 9h5 -> normalisé en "HHhMM"
    - Pattern B (date + heure): "à faire pour le D/M/YYYY à HhMM?" ou "à faire pour le D/M/YYYY à H:MM"
      * exemples: "le 03/09/2025 à 09h00", "le 3/9/2025 à 9h", "le 3/9/2025 à 9:05"
      * normalisé en "le dd/mm/YYYY à HHhMM"
    - Cas URGENCE: si le sujet contient "URGENCE", on ignore tout horaire présent dans le corps
      et on met l'heure locale actuelle + 1h au format "HHhMM" (ex: "13h35").

    Returns: dict avec 'matches' (bool) et 'delivery_time' (str ou None)
    """
    result = {'matches': False, 'delivery_time': None}

    if not subject or not email_content:
        return result

    # Helpers de normalisation de texte (sans accents, en minuscule) pour des regex robustes
    def normalize_text(s: str) -> str:
        if not s:
            return ""
        # Supprime les accents et met en minuscule pour une comparaison robuste
        nfkd = unicodedata.normalize('NFD', s)
        no_accents = ''.join(ch for ch in nfkd if not unicodedata.combining(ch))
        return no_accents.lower()

    norm_subject = normalize_text(subject)

    # Conditions principales
    # 1) Présence d'au moins un lien de fournisseur supporté (Dropbox, FromSmash, SwissTransfer)
    body_text = email_content or ""
    condition1 = bool(URL_PROVIDERS_PATTERN.search(body_text)) or (
        ("dropbox.com/scl/fo" in body_text)
        or ("fromsmash.com/" in body_text.lower())
        or ("swisstransfer.com/d/" in body_text.lower())
    )
    # 2) Sujet conforme
    #    Tolérant: on accepte la chaîne exacte (avec accents) OU la présence des mots-clés dans le sujet normalisé
    keywords_ok = all(token in norm_subject for token in [
        "media solution", "missions recadrage", "lot"
    ])
    condition2 = ("Média Solution - Missions Recadrage - Lot" in (subject or "")) or keywords_ok

    # Si conditions principales non remplies, on sort
    if not (condition1 and condition2):
        app.logger.debug(
            f"PATTERN_CHECK: Delivery URL present (dropbox/fromsmash/swisstransfer): {condition1}, Subject pattern: {condition2}"
        )
        return result

    # --- Helpers de normalisation ---
    def normalize_hhmm(hh_str: str, mm_str: str | None) -> str:
        """Normalise heures/minutes en "HHhMM". Minutes par défaut à 00."""
        try:
            hh = int(hh_str)
        except Exception:
            hh = 0
        if not mm_str:
            mm = 0
        else:
            try:
                mm = int(mm_str)
            except Exception:
                mm = 0
        return f"{hh:02d}h{mm:02d}"

    def normalize_date(d_str: str, m_str: str, y_str: str) -> str:
        """Normalise D/M/YYYY en dd/mm/YYYY (zero-pad jour/mois)."""
        try:
            d = int(d_str)
            m = int(m_str)
            y = int(y_str)
        except Exception:
            return f"{d_str}/{m_str}/{y_str}"
        return f"{d:02d}/{m:02d}/{y:04d}"

    # --- Extraction de delivery_time ---
    delivery_time_str = None

    # 1) URGENCE: si le sujet contient "URGENCE", on ignore tout horaire présent dans le corps
    if re.search(r"\burgence\b", norm_subject or ""):
        try:
            now_local = datetime.now(TZ_FOR_POLLING)
            one_hour_later = now_local + timedelta(hours=1)
            delivery_time_str = f"{one_hour_later.hour:02d}h{one_hour_later.minute:02d}"
            app.logger.info(f"PATTERN_MATCH: URGENCE detected, overriding delivery_time with now+1h: {delivery_time_str}")
        except Exception as e_time:
            app.logger.error(f"PATTERN_CHECK: Failed to compute URGENCE override time: {e_time}")
    else:
        # 2) Pattern B: Date + Heure (variantes)
        #    Variante "h" -> minutes optionnelles
        pattern_date_time_h = r"(?:à|a)\s+faire\s+pour\s+le\s+(\d{1,2})/(\d{1,2})/(\d{4})\s+(?:à|a)\s+(?:(?:à|a)\s+)?(\d{1,2})h(\d{0,2})"
        m_dth = re.search(pattern_date_time_h, email_content or "", re.IGNORECASE)
        if m_dth:
            d, m, y, hh, mm = m_dth.group(1), m_dth.group(2), m_dth.group(3), m_dth.group(4), m_dth.group(5)
            date_norm = normalize_date(d, m, y)
            time_norm = normalize_hhmm(hh, mm if mm else None)
            delivery_time_str = f"le {date_norm} à {time_norm}"
            app.logger.info(f"PATTERN_MATCH: Found date+time (h) delivery window: {delivery_time_str}")
        else:
            #    Variante ":" -> minutes obligatoires
            pattern_date_time_colon = r"(?:à|a)\s+faire\s+pour\s+le\s+(\d{1,2})/(\d{1,2})/(\d{4})\s+(?:à|a)\s+(?:(?:à|a)\s+)?(\d{1,2}):(\d{2})"
            m_dtc = re.search(pattern_date_time_colon, email_content or "", re.IGNORECASE)
            if m_dtc:
                d, m, y, hh, mm = m_dtc.group(1), m_dtc.group(2), m_dtc.group(3), m_dtc.group(4), m_dtc.group(5)
                date_norm = normalize_date(d, m, y)
                time_norm = normalize_hhmm(hh, mm)
                delivery_time_str = f"le {date_norm} à {time_norm}"
                app.logger.info(f"PATTERN_MATCH: Found date+time (colon) delivery window: {delivery_time_str}")

        # 3) Pattern A: Heure seule (variantes)
        if not delivery_time_str:
            # Variante "h" (minutes optionnelles), avec éventuel "à" superflu
            pattern_time_h = r"(?:à|a)\s+faire\s+pour\s+(?:(?:à|a)\s+)?(\d{1,2})h(\d{0,2})"
            m_th = re.search(pattern_time_h, email_content or "", re.IGNORECASE)
            if m_th:
                hh, mm = m_th.group(1), m_th.group(2)
                delivery_time_str = normalize_hhmm(hh, mm if mm else None)
                app.logger.info(f"PATTERN_MATCH: Found time-only (h) delivery window: {delivery_time_str}")
            else:
                # Variante ":" (minutes obligatoires)
                pattern_time_colon = r"(?:à|a)\s+faire\s+pour\s+(?:(?:à|a)\s+)?(\d{1,2}):(\d{2})"
                m_tc = re.search(pattern_time_colon, email_content or "", re.IGNORECASE)
                if m_tc:
                    hh, mm = m_tc.group(1), m_tc.group(2)
                    delivery_time_str = normalize_hhmm(hh, mm)
                    app.logger.info(f"PATTERN_MATCH: Found time-only (colon) delivery window: {delivery_time_str}")

        # 4) Fallback permissif: si toujours rien trouvé, tenter une heure isolée (sécurité: restreint aux formats attendus)
        if not delivery_time_str:
            m_fallback_h = re.search(r"\b(\d{1,2})h(\d{0,2})\b", email_content or "", re.IGNORECASE)
            if m_fallback_h:
                hh, mm = m_fallback_h.group(1), m_fallback_h.group(2)
                delivery_time_str = normalize_hhmm(hh, mm if mm else None)
                app.logger.info(f"PATTERN_MATCH: Fallback time (h) detected: {delivery_time_str}")
            else:
                m_fallback_colon = re.search(r"\b(\d{1,2}):(\d{2})\b", email_content or "")
                if m_fallback_colon:
                    hh, mm = m_fallback_colon.group(1), m_fallback_colon.group(2)
                    delivery_time_str = normalize_hhmm(hh, mm)
                    app.logger.info(f"PATTERN_MATCH: Fallback time (colon) detected: {delivery_time_str}")

    if delivery_time_str:
        result['delivery_time'] = delivery_time_str
        result['matches'] = True
        app.logger.info(
            f"PATTERN_MATCH: Email matches Média Solution pattern. Delivery time: {result['delivery_time']}"
        )
    else:
        app.logger.debug("PATTERN_CHECK: Base conditions met but no delivery_time pattern matched")

    return result


def send_makecom_webhook(subject, delivery_time, sender_email, email_id, override_webhook_url: str | None = None, extra_payload: dict | None = None):
    """
    Envoie les données à Make.com webhook pour les emails Média Solution.

    Args:
        subject (str): Sujet complet de l'email
        delivery_time (str): Heure de livraison extraite (ex: "11h38")
        sender_email (str): Adresse email de l'expéditeur
        email_id (str): ID unique de l'email pour les logs

    Returns:
        bool: True si succès, False sinon
    """
    payload = {
        "subject": subject,
        "delivery_time": delivery_time,
        "sender_email": sender_email
    }
    if extra_payload:
        # merge sans écraser les clés principales si en conflit
        for k, v in extra_payload.items():
            if k not in payload:
                payload[k] = v

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {MAKECOM_API_KEY}'
    }

    try:
        app.logger.info(f"MAKECOM: Sending webhook for email {email_id} - Subject: '{subject}', Delivery: {delivery_time}, Sender: {sender_email}")

        target_url = override_webhook_url or MAKECOM_WEBHOOK_URL
        if not target_url:
            app.logger.error("MAKECOM: No webhook URL configured (target_url is empty). Aborting send.")
            return False

        response = requests.post(
            target_url,
            json=payload,
            headers=headers,
            timeout=30,
            verify=True  # Make.com should have valid SSL certificates
        )

        if response.status_code == 200:
            app.logger.info(f"MAKECOM: Webhook sent successfully for email {email_id}")
            return True
        else:
            app.logger.error(f"MAKECOM: Webhook failed for email {email_id}. Status: {response.status_code}, Response: {response.text[:200]}")
            return False

    except requests.exceptions.RequestException as e:
        app.logger.error(f"MAKECOM: Exception during webhook call for email {email_id}: {e}")
        return False


# --- Fonctions de Déduplication avec Redis ---
def is_email_id_processed_redis(email_id):
    if not redis_client: return False
    try:
        return redis_client.sismember(PROCESSED_EMAIL_IDS_REDIS_KEY, email_id)
    except redis.exceptions.RedisError as e_redis:
        app.logger.error(f"REDIS_DEDUP: Error checking email ID '{email_id}': {e_redis}. Assuming NOT processed.")
        return False


def mark_email_id_as_processed_redis(email_id):
    if not redis_client: return False
    try:
        redis_client.sadd(PROCESSED_EMAIL_IDS_REDIS_KEY, email_id)
        return True
    except redis.exceptions.RedisError as e_redis:
        app.logger.error(f"REDIS_DEDUP: Error adding email ID '{email_id}': {e_redis}")
        return False


def _normalize_no_accents_lower_trim(s: str) -> str:
    """
    Remove accents, lowercase, collapse whitespace, and strip.
    """
    if not s:
        return ""
    nfkd = unicodedata.normalize('NFD', s)
    no_accents = ''.join(ch for ch in nfkd if not unicodedata.combining(ch))
    lowered = no_accents.lower()
    # Collapse spaces and common unicode spaces
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def _strip_leading_reply_prefixes(subject_norm: str) -> str:
    """
    Remove leading reply/forward prefixes like 're:', 'fw:', 'fwd:', 'ré:', possibly repeated,
    and optional 'confirmation :' tokens that sometimes appear before the actual subject.
    The input must already be normalized (lower, no accents).
    """
    s = subject_norm
    # remove multiple prefixes
    while True:
        new_s = re.sub(r"^(re|fw|fwd|rv|tr)\s*:\s*", "", s)
        # also commonly seen token 'confirmation :'
        new_s = re.sub(r"^confirmation\s*:\s*", "", new_s)
        if new_s == s:
            break
        s = new_s
    return s.strip()


def generate_subject_group_id(subject: str) -> str:
    """
    Generate a stable subject-group identifier so that emails that belong to the same
    conversation/thread (same business intent) only trigger webhooks once.

    Heuristic:
    - Normalize subject (remove accents, lowercase, collapse spaces)
    - Strip leading reply/forward prefixes (re:, fwd:, ...), and 'confirmation :'
    - If it looks like a Média Solution subject with a 'lot <num>' number, use a canonical key
      'media_solution_missions_recadrage_lot_<num>'
    - Else, if any 'lot <num>' is present, use 'lot_<num>' as group
    - Else, fallback to a hash of the normalized subject
    """
    norm = _normalize_no_accents_lower_trim(subject)
    core = _strip_leading_reply_prefixes(norm)

    # Try to extract lot number
    m_lot = re.search(r"\blot\s+(\d+)\b", core)
    lot_part = m_lot.group(1) if m_lot else None

    # Detect Média Solution Missions Recadrage keywords
    is_media_solution = all(tok in core for tok in ["media solution", "missions recadrage", "lot"]) if core else False

    if is_media_solution and lot_part:
        return f"media_solution_missions_recadrage_lot_{lot_part}"
    if lot_part:
        return f"lot_{lot_part}"

    # Fallback: hash the core subject
    subject_hash = hashlib.md5(core.encode("utf-8")).hexdigest()
    return f"subject_hash_{subject_hash}"


def is_subject_group_processed(group_id: str) -> bool:
    """Check subject-group deduplication using Redis when available, else in-memory."""
    if not group_id:
        return False
    # Scope by current month (YYYY-MM) so dedup resets each month
    def _monthly_scope_group_id(gid: str) -> str:
        try:
            now_local = datetime.now(TZ_FOR_POLLING)
        except Exception:
            now_local = datetime.now()
        month_prefix = now_local.strftime('%Y-%m')
        return f"{month_prefix}:{gid}"

    scoped_id = _monthly_scope_group_id(group_id) if ENABLE_SUBJECT_GROUP_DEDUP else group_id
    if redis_client:
        try:
            # Prefer TTL-based key if configured
            if SUBJECT_GROUP_TTL_SECONDS > 0:
                ttl_key = SUBJECT_GROUP_REDIS_PREFIX + scoped_id
                val = redis_client.get(ttl_key)
                if val is not None:
                    return True
            # Fallback/back-compat: set membership
            return bool(redis_client.sismember(PROCESSED_SUBJECT_GROUPS_REDIS_KEY, scoped_id))
        except Exception as e_redis:
            app.logger.error(f"REDIS_DEDUP: Error checking subject group '{group_id}': {e_redis}. Assuming NOT processed.")
            return False
    # Fallback in-memory (process-local only)
    return scoped_id in SUBJECT_GROUPS_MEMORY


def mark_subject_group_processed(group_id: str) -> bool:
    """Mark subject-group as processed in Redis when available, else in-memory."""
    if not group_id:
        return False
    # Scope by current month (YYYY-MM) so dedup resets each month
    def _monthly_scope_group_id(gid: str) -> str:
        try:
            now_local = datetime.now(TZ_FOR_POLLING)
        except Exception:
            now_local = datetime.now()
        month_prefix = now_local.strftime('%Y-%m')
        return f"{month_prefix}:{gid}"

    scoped_id = _monthly_scope_group_id(group_id) if ENABLE_SUBJECT_GROUP_DEDUP else group_id
    if redis_client:
        try:
            if SUBJECT_GROUP_TTL_SECONDS > 0:
                ttl_key = SUBJECT_GROUP_REDIS_PREFIX + scoped_id
                # value content is irrelevant; only presence matters; set PX expiry
                redis_client.set(ttl_key, 1, ex=SUBJECT_GROUP_TTL_SECONDS)
            # Back-compat set membership for observability
            redis_client.sadd(PROCESSED_SUBJECT_GROUPS_REDIS_KEY, scoped_id)
            return True
        except Exception as e_redis:
            app.logger.error(f"REDIS_DEDUP: Error marking subject group '{group_id}': {e_redis}")
            return False
    SUBJECT_GROUPS_MEMORY.add(scoped_id)
    return True


# --- Fonctions de Polling des Emails IMAP ---


def check_new_emails_and_trigger_webhook():
    """
    Vérifie les nouveaux emails via IMAP et déclenche le webhook personnalisé pour chaque email valide.
    VERSION IMAP - remplace l'ancienne version Microsoft Graph API.
    """
    app.logger.info("POLLER: Email polling cycle started (IMAP).")
    if not all([SENDER_LIST_FOR_POLLING, WEBHOOK_URL, email_config_valid]):
        app.logger.error("POLLER: Incomplete config for polling. Aborting cycle.")
        return 0

    # Créer une connexion IMAP
    mail = create_imap_connection()
    if not mail:
        app.logger.error("POLLER: Failed to create IMAP connection. Aborting cycle.")
        return 0

    triggered_webhook_count = 0
    try:
        # Sélectionner la boîte de réception
        mail.select('INBOX')

        # Rechercher les emails non lus des derniers 2 jours
        since_date = (datetime.now() - timedelta(days=2)).strftime('%d-%b-%Y')
        search_criteria = f'(UNSEEN SINCE {since_date})'

        app.logger.info(f"POLLER: Searching for emails with criteria: {search_criteria}")

        # Rechercher les emails
        status, email_ids = mail.search(None, search_criteria)
        if status != 'OK':
            app.logger.error(f"POLLER: IMAP search failed: {status}")
            return 0

        email_list = email_ids[0].split()
        app.logger.info(f"POLLER: Found {len(email_list)} unread email(s).")

        if not email_list:
            return 0

        app.logger.info("POLLER: Proceeding with email batch processing.")

        # Traiter chaque email
        for email_num in email_list:
            try:
                # Récupérer l'email
                status, email_data = mail.fetch(email_num, '(RFC822)')
                if status != 'OK':
                    app.logger.warning(f"POLLER: Failed to fetch email {email_num}")
                    continue

                # Parser l'email
                raw_email = email_data[0][1]
                email_message = email.message_from_bytes(raw_email)

                # Extraire les informations de l'email
                subject = decode_email_header(email_message.get('Subject', ''))
                sender = email_message.get('From', '')
                date_received = email_message.get('Date', '')
                message_id = email_message.get('Message-ID', '')

                # Générer un ID unique pour l'email
                email_id = generate_email_id({
                    'Message-ID': message_id,
                    'Subject': subject,
                    'Date': date_received
                })

                app.logger.debug(f"POLLER: Processing email {email_num} - Subject: '{subject[:50]}...', From: {sender}")

                # --- Subject-group deduplication: prevent multiple webhooks for similar threads ---
                try:
                    subject_group_id = generate_subject_group_id(subject)
                except Exception as e_group:
                    subject_group_id = ""
                    app.logger.error(f"DEDUP_GROUP: Failed to compute subject group for email {email_id}: {e_group}")

                if ENABLE_SUBJECT_GROUP_DEDUP and subject_group_id and is_subject_group_processed(subject_group_id):
                    app.logger.info(
                        f"DEDUP_GROUP: Subject-group '{subject_group_id}' already processed. Skipping webhooks for email {email_id}.")
                    # Optionally mark as read to avoid reprocessing in next cycles
                    mark_email_as_read_imap(mail, email_num)
                    # Also mark the individual email (redis) to prevent loops if present
                    mark_email_id_as_processed_redis(email_id)
                    continue

                # Vérifier si l'expéditeur est dans la liste des expéditeurs d'intérêt
                sender_email = sender.lower()
                is_from_monitored_sender = any(monitored_sender in sender_email for monitored_sender in SENDER_LIST_FOR_POLLING)

                if not is_from_monitored_sender:
                    app.logger.debug(f"POLLER: Email {email_num} from {sender} is not from a monitored sender. Skipping.")
                    continue

                # Vérifier si l'email a déjà été traité
                if is_email_id_processed_redis(email_id):
                    app.logger.debug(f"POLLER: Email ID {email_id} already processed. Marking as read.")
                    mark_email_as_read_imap(mail, email_num)
                    continue

                # Extraire le contenu complet de l'email
                body_preview = ""
                full_email_content = ""

                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            try:
                                content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                if not body_preview:
                                    body_preview = content[:500]
                                if not full_email_content:
                                    full_email_content = content
                                break
                            except:
                                pass
                else:
                    try:
                        content = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                        body_preview = content[:500]
                        full_email_content = content
                    except:
                        pass

                # Indicateur d'exclusivité pour la logique "présence samedi"
                presence_routed = False
                # Indicateur d'exclusivité pour le nouveau webhook "désabonnement/journée/tarifs habituels"
                desabo_routed = False

                # --- Détection spéciale "samedi" (sujet ET corps) pour webhook Make basé sur PRESENCE ---
                try:
                    def _normalize_no_accents_lower(s: str) -> str:
                        if not s:
                            return ""
                        nfkd = unicodedata.normalize('NFD', s)
                        no_accents = ''.join(ch for ch in nfkd if not unicodedata.combining(ch))
                        return no_accents.lower()

                    norm_subject = _normalize_no_accents_lower(subject)
                    norm_body = _normalize_no_accents_lower(full_email_content)
                    contains_samedi = ("samedi" in norm_subject) and ("samedi" in norm_body)

                    if contains_samedi:
                        # Restriction: n'envoyer les webhooks présence/absence que le VENDREDI (weekday=4)
                        now_local = datetime.now(TZ_FOR_POLLING)
                        is_friday = now_local.weekday() == 4  # 0=Mon … 4=Fri
                        if not is_friday:
                            app.logger.info(
                                f"PRESENCE: 'samedi' detected for email {email_id} but today is not Friday (weekday={now_local.weekday()}). "
                                "Presence webhooks are restricted to Fridays. Skipping."
                            )
                        else:
                            # Vérifier contrainte horaire globale avant tout envoi Make
                            now_local = datetime.now(TZ_FOR_POLLING)
                            if not _is_within_time_window_local(now_local):
                                app.logger.info(
                                    f"PRESENCE: Time window not satisfied for email {email_id} (now={now_local.strftime('%H:%M')}, window={WEBHOOKS_TIME_START_STR or 'unset'}-{WEBHOOKS_TIME_END_STR or 'unset'}). Skipping."
                                )
                            else:
                                # Choisir l'URL Make cible selon PRESENCE
                                presence_url = PRESENCE_TRUE_MAKE_WEBHOOK_URL if PRESENCE_FLAG else PRESENCE_FALSE_MAKE_WEBHOOK_URL
                                if presence_url:
                                    app.logger.info(
                                        f"PRESENCE: 'samedi' detected on Friday for email {email_id}. PRESENCE={PRESENCE_FLAG}. "
                                        "Sending to dedicated Make webhook (Friday restriction satisfied)."
                                    )
                                    presence_sender_email = extract_sender_email(sender)
                                    send_ok = send_makecom_webhook(
                                        subject=subject,
                                        delivery_time=None,
                                        sender_email=presence_sender_email,
                                        email_id=email_id,
                                        override_webhook_url=presence_url,
                                        extra_payload={
                                            "presence": PRESENCE_FLAG,
                                            "detector": "samedi_presence",
                                        }
                                    )
                                    # Exclusivité uniquement si un envoi a été tenté ce vendredi
                                    presence_routed = True
                                    if send_ok:
                                        app.logger.info(f"PRESENCE: Make.com webhook (presence) sent successfully for email {email_id}")
                                    else:
                                        app.logger.error(f"PRESENCE: Make.com webhook (presence) failed for email {email_id}")
                                else:
                                    app.logger.warning(
                                        "PRESENCE: 'samedi' detected on Friday but PRESENCE_*_MAKE_WEBHOOK_URL not configured. Skipping presence webhook."
                                    )
                except Exception as e_presence:
                    app.logger.error(f"PRESENCE: Exception during samedi presence handling for email {email_id}: {e_presence}")

                # --- Nouveau déclencheur: corps contient "Se désabonner", "journée", "tarifs habituels";
                #     n'inclut PAS certains mots; et contient une URL Dropbox de type /request/ ---
                try:
                    def _normalize_no_accents_lower_v2(s: str) -> str:
                        if not s:
                            return ""
                        nfkd = unicodedata.normalize('NFD', s)
                        no_accents = ''.join(ch for ch in nfkd if not unicodedata.combining(ch))
                        return no_accents.lower()

                    norm_body2 = _normalize_no_accents_lower_v2(full_email_content)

                    required_terms = [
                        "se desabonner",  # "Se désabonner" sans accents
                        "journee",        # "journée"
                        "tarifs habituels",
                    ]
                    forbidden_terms = [
                        "annulation",
                        "facturation",
                        "facture",
                        "moment",
                        "reference client",
                        "total ht",
                    ]

                    has_required = all(term in norm_body2 for term in required_terms)
                    has_forbidden = any(term in norm_body2 for term in forbidden_terms)
                    has_dropbox_request = "https://www.dropbox.com/request/" in (full_email_content or "").lower()

                    if has_required and not has_forbidden and has_dropbox_request:
                        # Vérifier contrainte horaire globale avant envoi Make
                        now_local = datetime.now(TZ_FOR_POLLING)
                        if not _is_within_time_window_local(now_local):
                            app.logger.info(
                                f"DESABO: Time window not satisfied for email {email_id} (now={now_local.strftime('%H:%M')}, window={WEBHOOKS_TIME_START_STR or 'unset'}-{WEBHOOKS_TIME_END_STR or 'unset'}). Skipping."
                            )
                            raise Exception("DESABO_TIME_WINDOW_NOT_SATISFIED")
                        target_make_url = DESABO_MAKE_WEBHOOK_URL
                        sender_email_clean = extract_sender_email(sender)

                        app.logger.info(
                            f"DESABO: Conditions matched for email {email_id}. Sending Make webhook to {target_make_url}"
                        )

                        send_ok = send_makecom_webhook(
                            subject=subject,
                            delivery_time=None,
                            sender_email=sender_email_clean,
                            email_id=email_id,
                            override_webhook_url=target_make_url,
                            extra_payload={
                                "detector": "desabonnement_journee_tarifs",
                                # Inclure le corps texte complet, comme demandé
                                "email_content": full_email_content,
                                # Aliases façon Mailhook pour simplifier le mapping côté Make
                                "Text": full_email_content,
                                "Subject": subject,
                                "Sender": {"email": sender_email_clean},
                                # Exposer la fenêtre horaire globale pour mapping côté Make
                                "webhooks_time_start": WEBHOOKS_TIME_START_STR or None,
                                "webhooks_time_end": WEBHOOKS_TIME_END_STR or None,
                            },
                        )

                        # Activer l'exclusivité vis-à-vis du flux Média Solution si tentative d'envoi
                        desabo_routed = True
                        if send_ok:
                            app.logger.info(
                                f"DESABO: Make.com webhook sent successfully for email {email_id}"
                            )
                            try:
                                if subject_group_id:
                                    mark_subject_group_processed(subject_group_id)
                            except Exception:
                                pass
                        else:
                            app.logger.error(
                                f"DESABO: Make.com webhook failed for email {email_id}"
                            )
                except Exception as e_desabo:
                    app.logger.error(
                        f"DESABO: Exception during unsubscribe/journee/tarifs handling for email {email_id}: {e_desabo}"
                    )

                # Extraire et résoudre les liens de livraison (Dropbox/FromSmash/SwissTransfer)
                # Note: le scraping des pages publiques sert uniquement à découvrir un lien direct si visible dans le HTML.
                # Si aucun lien direct n'est exposé côté public, "direct_url" restera None.
                provider_links = extract_provider_links_from_text(full_email_content)
                delivery_links = []
                first_direct_url = None
                for link in provider_links:
                    provider = link["provider"]
                    raw_url = link["raw_url"]
                    direct_url = resolve_direct_download_url(provider, raw_url)
                    delivery_links.append({
                        "provider": provider,
                        "raw_url": raw_url,
                        "direct_url": direct_url
                    })
                    if not first_direct_url and direct_url:
                        first_direct_url = direct_url

                # Préparer le payload pour le webhook personnalisé (format requis + contenu complet)
                payload_for_webhook = {
                    "microsoft_graph_email_id": email_id,  # Maintenir le nom pour compatibilité
                    "subject": subject,
                    "receivedDateTime": date_received,
                    "sender_address": sender,
                    "bodyPreview": body_preview,
                    "email_content": full_email_content,  # Contenu complet pour éviter la recherche IMAP
                    # Nouveau: informations sur les liens de livraison détectés et résolus
                    "delivery_links": delivery_links,
                    "first_direct_download_url": first_direct_url,
                }

                # Déclencher le webhook personnalisé
                try:
                    webhook_response = requests.post(
                        WEBHOOK_URL,
                        json=payload_for_webhook,
                        headers={'Content-Type': 'application/json'},
                        timeout=30,
                        verify=WEBHOOK_SSL_VERIFY
                    )

                    # Vérifier la réponse du webhook
                    if webhook_response.status_code == 200:
                        response_data = webhook_response.json() if webhook_response.content else {}
                        if response_data.get('success', False):
                            app.logger.info(f"POLLER: Webhook triggered successfully for email {email_id}.")

                            # Marquer comme traité dans Redis
                            if mark_email_id_as_processed_redis(email_id):
                                triggered_webhook_count += 1
                                mark_email_as_read_imap(mail, email_num)
                            # Marquer le groupe de sujet comme traité (premier webhook de la série)
                            try:
                                if ENABLE_SUBJECT_GROUP_DEDUP and subject_group_id:
                                    mark_subject_group_processed(subject_group_id)
                            except Exception:
                                pass
                        else:
                            app.logger.error(f"POLLER: Webhook processing failed for email {email_id}. Response: {response_data.get('message', 'Unknown error')}")
                    else:
                        app.logger.error(f"POLLER: Webhook call FAILED for email {email_id}. Status: {webhook_response.status_code}, Response: {webhook_response.text[:200]}")
                except requests.exceptions.SSLError as ssl_err:
                    # SSL errors are often due to hostname mismatch or invalid certificate. Provide clear guidance.
                    app.logger.error(
                        "POLLER: SSL error during webhook call for email %s: %s. "
                        "Likely causes: hostname mismatch or invalid certificate for '%s'. "
                        "Verify that the certificate's CN/SAN includes the exact host or adjust WEBHOOK_URL. "
                        "For temporary debugging only, WEBHOOK_SSL_VERIFY=false can bypass verification (not recommended in prod).",
                        email_id, ssl_err, urlparse(WEBHOOK_URL).hostname
                    )
                    continue
                except requests.exceptions.RequestException as e_webhook:
                    app.logger.error(f"POLLER: Exception during webhook call for email {email_id}: {e_webhook}")
                    continue

                # Flux Make « Média Solution » seulement si aucun routage exclusif n'a eu lieu
                if not (presence_routed or desabo_routed):
                    try:
                        pattern_result = check_media_solution_pattern(subject, full_email_content)

                        if pattern_result['matches']:
                            app.logger.info(f"POLLER: Email {email_id} matches Média Solution pattern")

                            # Extraire l'adresse email de l'expéditeur
                            sender_email = extract_sender_email(sender)

                            # Envoyer à Make.com webhook (URL par défaut)
                            makecom_success = send_makecom_webhook(
                                subject=subject,
                                delivery_time=pattern_result['delivery_time'],
                                sender_email=sender_email,
                                email_id=email_id
                            )

                            if makecom_success:
                                app.logger.info(f"POLLER: Make.com webhook sent successfully for email {email_id}")
                                # Marquer le groupe de sujet comme traité même si le webhook custom a échoué
                                try:
                                    if ENABLE_SUBJECT_GROUP_DEDUP and subject_group_id:
                                        mark_subject_group_processed(subject_group_id)
                                except Exception:
                                    pass
                            else:
                                app.logger.error(f"POLLER: Make.com webhook failed for email {email_id}")
                        else:
                            app.logger.debug(f"POLLER: Email {email_id} does not match Média Solution pattern")

                    except Exception as e_makecom:
                        app.logger.error(f"POLLER: Exception during Média Solution pattern check for email {email_id}: {e_makecom}")
                        # Continue processing other emails even if this fails

            except Exception as e_email:
                app.logger.error(f"POLLER: Error processing email {email_num}: {e_email}")
                continue

        # Fin de la boucle des emails
        return triggered_webhook_count
    except Exception as e_general:
        app.logger.error(f"POLLER: Unexpected error in IMAP polling cycle: {e_general}", exc_info=True)
        return triggered_webhook_count
    finally:
        close_imap_connection(mail)

def background_email_poller():
    app.logger.info(f"BG_POLLER: Email polling thread started. TZ for schedule: {POLLING_TIMEZONE_STR}.")
    consecutive_error_count = 0
    MAX_CONSECUTIVE_ERRORS = 5

    while True:
        try:
            now_in_configured_tz = datetime.now(TZ_FOR_POLLING)
            is_active_day = now_in_configured_tz.weekday() in POLLING_ACTIVE_DAYS
            is_active_time = POLLING_ACTIVE_START_HOUR <= now_in_configured_tz.hour < POLLING_ACTIVE_END_HOUR

            if is_active_day and is_active_time:
                app.logger.info(f"BG_POLLER: In active period. Starting poll cycle.")
                if not all([email_config_valid, SENDER_LIST_FOR_POLLING, WEBHOOK_URL]):
                    app.logger.warning(f"BG_POLLER: Essential config for polling is incomplete. Waiting 60s.")
                    time.sleep(60)
                    continue

                webhooks_triggered = check_new_emails_and_trigger_webhook()
                app.logger.info(f"BG_POLLER: Active poll cycle finished. {webhooks_triggered} webhook(s) triggered.")
                consecutive_error_count = 0
                sleep_duration = EMAIL_POLLING_INTERVAL_SECONDS
            else:
                app.logger.info(f"BG_POLLER: Outside active period. Sleeping.")
                sleep_duration = POLLING_INACTIVE_CHECK_INTERVAL_SECONDS

            time.sleep(sleep_duration)

        except Exception as e:
            consecutive_error_count += 1
            app.logger.error(f"BG_POLLER: Unhandled error in polling loop (Error #{consecutive_error_count}): {e}",
                             exc_info=True)
            if consecutive_error_count >= MAX_CONSECUTIVE_ERRORS:
                app.logger.critical(f"BG_POLLER: Max consecutive errors reached. Stopping thread.")
                break
            sleep_on_error_duration = max(60, EMAIL_POLLING_INTERVAL_SECONDS) * (2 ** consecutive_error_count)
            app.logger.info(f"BG_POLLER: Sleeping for {sleep_on_error_duration}s due to error.")
            time.sleep(sleep_on_error_duration)




# --- NOUVELLES ROUTES POUR L'AUTHENTIFICATION ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user and current_user.is_authenticated:
        return redirect(url_for('serve_trigger_page_main'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username in users and users[username] == password:
            user_obj = User(username)
            login_user(user_obj)
            app.logger.info(f"AUTH: Connexion réussie pour l'utilisateur '{username}'.")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('serve_trigger_page_main'))
        else:
            app.logger.warning(f"AUTH: Tentative de connexion échouée pour '{username}'.")
            return render_template('login.html', error="Identifiants invalides.")

    return render_template('login.html', url_for=url_for)


@app.route('/logout')
@login_required
def logout():
    user_id = current_user.id
    logout_user()
    app.logger.info(f"AUTH: Déconnexion de l'utilisateur '{user_id}'.")
    return redirect(url_for('login'))


# --- Endpoints API (Non-UI, protégés par token) ---


@app.route('/api/check_trigger', methods=['GET'])
def check_local_workflow_trigger():
    if TRIGGER_SIGNAL_FILE.exists():
        with open(TRIGGER_SIGNAL_FILE, 'r') as f: payload = json.load(f)
        TRIGGER_SIGNAL_FILE.unlink()
        return jsonify({'command_pending': True, 'payload': payload})
    return jsonify({'command_pending': False, 'payload': None})


@app.route('/api/ping', methods=['GET', 'HEAD'])
def api_ping():
    return jsonify({"status": "pong", "timestamp_utc": datetime.now(timezone.utc).isoformat()}), 200


# --- ROUTES UI PROTÉGÉES MISES À JOUR ---

# --- Endpoint de test manuel des webhooks de présence (Make.com) ---
@app.route('/api/test_presence_webhook', methods=['POST'])
@login_required
def api_test_presence_webhook():
    """
    Déclenche manuellement le webhook Make de présence.

    Corps accepté (JSON ou form):
    - presence: "true" | "false"

    Réponses:
    - 200: { success: true, presence: bool, used_url: str }
    - 400: { success: false, message }
    - 500: { success: false, message }
    """
    try:
        # Support JSON ou form-urlencoded
        presence_raw = None
        if request.is_json:
            body = request.get_json(silent=True) or {}
            presence_raw = body.get('presence')
        if presence_raw is None:
            presence_raw = request.form.get('presence') or request.args.get('presence')

        if presence_raw is None:
            return jsonify({"success": False, "message": "Paramètre 'presence' requis (true|false)."}), 400

        presence_str = str(presence_raw).strip().lower()
        if presence_str not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
            return jsonify({"success": False, "message": "Valeur 'presence' invalide. Utilisez true|false."}), 400

        presence_bool = presence_str in ("true", "1", "yes", "on")
        target_url = PRESENCE_TRUE_MAKE_WEBHOOK_URL if presence_bool else PRESENCE_FALSE_MAKE_WEBHOOK_URL

        if not target_url:
            return jsonify({
                "success": False,
                "message": "URL de webhook de présence non configurée (PRESENCE_TRUE_MAKE_WEBHOOK_URL / PRESENCE_FALSE_MAKE_WEBHOOK_URL)"
            }), 400

        # Construire des valeurs de test sûres
        test_subject = "[TEST] Présence Samedi - Déclenchement manuel"
        test_sender_email = "test@render-signal-server.local"
        test_email_id = f"manual-{int(time.time())}"

        ok = send_makecom_webhook(
            subject=test_subject,
            delivery_time=None,
            sender_email=test_sender_email,
            email_id=test_email_id,
            override_webhook_url=target_url,
            extra_payload={
                "presence": presence_bool,
                "detector": "manual_test",
            }
        )

        if ok:
            app.logger.info(f"API_TEST_PRESENCE: Webhook envoyé avec succès (presence={presence_bool}) vers {target_url}")
            return jsonify({"success": True, "presence": presence_bool, "used_url": target_url}), 200
        else:
            app.logger.error(f"API_TEST_PRESENCE: Échec d'envoi du webhook (presence={presence_bool}) vers {target_url}")
            return jsonify({"success": False, "message": "Échec d'envoi du webhook vers Make."}), 500

    except Exception as e:
        app.logger.error(f"API_TEST_PRESENCE: Exception: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/')
@login_required
def serve_trigger_page_main():
    app.logger.info(f"ROOT_UI: Requête pour '/' par l'utilisateur '{current_user.id}'. Service de 'trigger_page.html'.")
    return render_template('trigger_page.html')





@app.route('/api/check_emails_and_download', methods=['POST'])
@login_required
def api_check_emails_and_download_authed():
    app.logger.info(f"API_EMAIL_CHECK: Déclenchement manuel par '{current_user.id}'.")

    def run_task():
        with app.app_context():
            check_new_emails_and_trigger_webhook()

    if not all([email_config_valid, SENDER_LIST_FOR_POLLING, WEBHOOK_URL]):
        return jsonify({"status": "error", "message": "Config serveur email incomplète."}), 503
    threading.Thread(target=run_task).start()
    return jsonify({"status": "success", "message": "Vérification en arrière-plan lancée."}), 202


# La fonction de démarrage des tâches reste ici, mais elle ne sera appelée que par Gunicorn ou par le __main__
def start_background_tasks():
    """
    Fonction qui initialise et démarre les threads d'arrière-plan.
    """
    app.logger.info("BACKGROUND_TASKS: Initialisation des tâches...")

    # Ne jamais démarrer par défaut dans des environnements multi-workers.
    # Exiger une intention explicite via ENABLE_BACKGROUND_TASKS.
    enable_bg = os.environ.get("ENABLE_BACKGROUND_TASKS", "0").lower() in ("1", "true", "yes")
    if not enable_bg:
        app.logger.warning(
            "BACKGROUND_TASKS: Désactivé (ENABLE_BACKGROUND_TASKS not set to 1/true). "
            "Recommandation: ne pas exécuter le poller IMAP dans plusieurs workers Gunicorn (risque OOM/timeouts)."
        )
        return

    # Assurer unicité inter-processus via un verrou fichier
    lock_path = os.environ.get("BG_POLLER_LOCK_FILE", "/tmp/render_signal_server_email_poller.lock")
    if not acquire_singleton_lock(lock_path):
        app.logger.warning(
            "BACKGROUND_TASKS: Un autre processus détient déjà le verrou du poller. "
            "Ce processus n'initialisera PAS le thread de polling (prévention multi-instances)."
        )
        return

    # On vérifie si toutes les conditions sont remplies pour lancer le thread.
    if all([email_config_valid, SENDER_LIST_FOR_POLLING, WEBHOOK_URL]):
        email_poller_thread = threading.Thread(target=background_email_poller, name="EmailPollerThread", daemon=True)
        email_poller_thread.start()
        app.logger.info("BACKGROUND_TASKS: Thread de polling des emails démarré (singleton lock acquis).")
    else:
        # Log détaillé si le thread ne peut pas démarrer
        missing_configs = []
        if not email_config_valid: missing_configs.append("Configuration email invalide")
        if not SENDER_LIST_FOR_POLLING: missing_configs.append("Liste des expéditeurs vide")
        if not WEBHOOK_URL: missing_configs.append("URL du webhook manquante")
        app.logger.warning(
            f"BACKGROUND_TASKS: Thread de polling non démarré. Configuration incomplète : {', '.join(missing_configs)}")
        # Libérer le verrou si on n'utilise pas le thread
        global BG_LOCK_FH
        try:
            if BG_LOCK_FH:
                fcntl.flock(BG_LOCK_FH.fileno(), fcntl.LOCK_UN)
                BG_LOCK_FH.close()
        finally:
            BG_LOCK_FH = None


# Le code ici est exécuté UNE SEULE FOIS par Gunicorn dans le processus maître
# avant la création des workers. C'est l'endroit parfait pour lancer notre tâche unique.
#
# IMPORTANT pour les tests: ne démarre pas les threads si les tests sont en cours
# (détecte 'PYTEST_CURRENT_TEST') ou si DISABLE_BACKGROUND_TASKS=1.
if os.environ.get("DISABLE_BACKGROUND_TASKS") not in ("1", "true", "True") and \
   os.environ.get("PYTEST_CURRENT_TEST") is None:
    # Note: start_background_tasks() est désormais sécurisé par un verrou fichier et un flag explicite.
    # En environnement Gunicorn multi-workers, configurez une seule instance avec ENABLE_BACKGROUND_TASKS=1
    # OU utilisez un service séparé (recommandé) pour le poller.
    start_background_tasks()

# Ce bloc ne sera JAMAIS exécuté par Gunicorn, mais il est utile pour le débogage local
if __name__ == '__main__':
    app.logger.info(f"MAIN_APP: (Lancement direct pour débogage local)")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
