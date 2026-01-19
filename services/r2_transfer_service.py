"""
Service for transferring files to Cloudflare R2 with fetch mode.

Features:
- Singleton pattern
- Remote fetch (R2 downloads directly from source) to save Render bandwidth
- Persistence of source_url/r2_url pairs in webhook_links.json
- Fallback support when R2 is unavailable
- Secure logging (no secrets)
"""

from __future__ import annotations

import logging
import os
import json
import hashlib
import html
import time
import fcntl
import urllib.parse
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


ALLOWED_REMOTE_FETCH_DOMAINS = {
    "dropbox.com",
    "fromsmash.com",
    "swisstransfer.com",
    "wetransfer.com",
}

try:
    import requests
except ImportError:
    requests = None  # type: ignore


class R2TransferService:
    """Service pour transférer des fichiers vers Cloudflare R2.
    
    Attributes:
        _instance: Instance singleton
        _fetch_endpoint: URL du Worker Cloudflare pour fetch distant
        _public_base_url: URL de base publique pour accès aux objets R2
        _enabled: Flag d'activation global
        _bucket_name: Nom du bucket R2
        _links_file: Chemin du fichier webhook_links.json
    """
    
    _instance: Optional[R2TransferService] = None
    
    def __init__(
        self,
        fetch_endpoint: Optional[str] = None,
        public_base_url: Optional[str] = None,
        bucket_name: Optional[str] = None,
        links_file: Optional[Path] = None,
    ):
        """Initialise le service (utiliser get_instance() de préférence).
        
        Args:
            fetch_endpoint: URL du Worker R2 Fetch (ex: https://r2-fetch.workers.dev)
            public_base_url: URL publique du CDN R2 (ex: https://media.example.com)
            bucket_name: Nom du bucket R2
            links_file: Chemin du fichier webhook_links.json
        """
        self._fetch_endpoint = fetch_endpoint or os.environ.get("R2_FETCH_ENDPOINT", "")
        self._public_base_url = public_base_url or os.environ.get("R2_PUBLIC_BASE_URL", "")
        self._bucket_name = bucket_name or os.environ.get("R2_BUCKET_NAME", "")
        self._fetch_token = os.environ.get("R2_FETCH_TOKEN", "")
        
        if links_file:
            self._links_file = links_file
        else:
            default_path = Path(__file__).resolve().parents[1] / "deployment" / "data" / "webhook_links.json"
            self._links_file = Path(os.environ.get("WEBHOOK_LINKS_FILE", str(default_path)))
        
        enabled_str = os.environ.get("R2_FETCH_ENABLED", "false").strip().lower()
        self._enabled = enabled_str in ("1", "true", "yes", "on")
        
        if self._enabled and not self._fetch_endpoint:
            pass
    
    @classmethod
    def get_instance(
        cls,
        fetch_endpoint: Optional[str] = None,
        public_base_url: Optional[str] = None,
        bucket_name: Optional[str] = None,
        links_file: Optional[Path] = None,
    ) -> R2TransferService:
        """Récupère ou crée l'instance singleton.
        
        Args:
            fetch_endpoint: URL du Worker (requis à la première création)
            public_base_url: URL publique CDN
            bucket_name: Nom du bucket
            links_file: Chemin du fichier de liens
            
        Returns:
            Instance unique du service
        """
        if cls._instance is None:
            cls._instance = cls(fetch_endpoint, public_base_url, bucket_name, links_file)
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Réinitialise l'instance (pour tests)."""
        cls._instance = None
    
    def is_enabled(self) -> bool:
        """Vérifie si le service est activé et configuré.
        
        Returns:
            True si R2_FETCH_ENABLED=true et configuration valide
        """
        return self._enabled and bool(self._fetch_endpoint)
    
    def request_remote_fetch(
        self,
        source_url: str,
        provider: str,
        email_id: Optional[str] = None,
        timeout: int = 30,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Demande à R2 de télécharger le fichier depuis l'URL source (mode pull).
        
        Cette méthode envoie une requête au Worker Cloudflare qui effectue le fetch
        directement, évitant ainsi de consommer la bande passante de Render.
        
        Args:
            source_url: URL du fichier à télécharger (Dropbox, FromSmash, etc.)
            provider: Nom du provider (dropbox, fromsmash, swisstransfer)
            email_id: ID de l'email source (pour traçabilité)
            timeout: Timeout en secondes pour la requête
            
        Returns:
            Tuple (r2_url, original_filename) si succès, (None, None) si échec
        """
        if not self.is_enabled():
            return None, None

        if not self._fetch_token or not self._fetch_token.strip():
            return None, None
        
        if not source_url or not provider:
            return None, None
        
        if requests is None:
            return None, None
        
        try:
            normalized_url = self.normalize_source_url(source_url, provider)

            try:
                parsed = urllib.parse.urlsplit(normalized_url)
                domain = (parsed.hostname or "").lower().strip(".")
            except Exception:
                domain = ""

            if not domain:
                logger.warning(
                    "SECURITY: Blocked attempt to fetch from unauthorized domain (domain missing)"
                )
                return None, None

            if not any(
                domain == allowed or domain.endswith("." + allowed)
                for allowed in ALLOWED_REMOTE_FETCH_DOMAINS
            ):
                logger.warning(
                    "SECURITY: Blocked attempt to fetch from unauthorized domain (domain=%s, provider=%s, email_id=%s)",
                    domain,
                    provider,
                    email_id or "n/a",
                )
                return None, None

            object_key = self._generate_object_key(normalized_url, provider)
            
            payload = {
                "source_url": normalized_url,
                "object_key": object_key,
                "bucket": self._bucket_name,
                "provider": provider,
            }
            
            if email_id:
                payload["email_id"] = email_id
            
            start_time = time.time()
            response = requests.post(
                self._fetch_endpoint,
                json=payload,
                timeout=timeout,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "render-signal-server/r2-transfer",
                    "X-R2-FETCH-TOKEN": self._fetch_token,
                }
            )
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("r2_url"):
                    r2_url = data["r2_url"]
                    original_filename = data.get("original_filename")
                    if original_filename is not None and not isinstance(original_filename, str):
                        original_filename = None
                    return r2_url, original_filename
                else:
                    return None, None
            else:
                return None, None
                
        except requests.exceptions.Timeout:
            return None, None
        except requests.exceptions.RequestException:
            return None, None
        except Exception:
            return None, None
    
    def persist_link_pair(
        self,
        source_url: str,
        r2_url: str,
        provider: str,
        original_filename: Optional[str] = None,
    ) -> bool:
        """Persiste la paire source_url/r2_url dans webhook_links.json.
        
        Utilise un verrouillage fichier (fcntl) pour garantir l'intégrité
        en environnement multi-processus (Gunicorn).
        
        Args:
            source_url: URL source du fichier
            r2_url: URL R2 publique du fichier
            provider: Nom du provider
            original_filename: Nom de fichier original (best-effort, optionnel)
            
        Returns:
            True si succès, False si échec
        """
        if not source_url or not r2_url:
            return False

        normalized_source_url = self.normalize_source_url(source_url, provider)
        
        try:
            self._links_file.parent.mkdir(parents=True, exist_ok=True)
            
            if not self._links_file.exists():
                with open(self._links_file, 'w', encoding='utf-8') as f:
                    json.dump([], f)
            
            with open(self._links_file, 'r+', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                
                try:
                    f.seek(0)
                    try:
                        links = json.load(f)
                        if not isinstance(links, list):
                            links = []
                    except json.JSONDecodeError:
                        links = []
                    
                    entry = {
                        "source_url": normalized_source_url,
                        "r2_url": r2_url,
                        "provider": provider,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }

                    if isinstance(original_filename, str):
                        cleaned_original_filename = original_filename.strip()
                        if cleaned_original_filename:
                            entry["original_filename"] = cleaned_original_filename

                    for existing in reversed(links):
                        if not isinstance(existing, dict):
                            continue
                        if (
                            existing.get("source_url") == entry["source_url"]
                            and existing.get("r2_url") == entry["r2_url"]
                            and existing.get("provider") == entry["provider"]
                        ):
                            return True
                    
                    links.append(entry)
                    
                    max_entries = int(os.environ.get("R2_LINKS_MAX_ENTRIES", "1000"))
                    if len(links) > max_entries:
                        links = links[-max_entries:]
                    
                    f.seek(0)
                    f.truncate()
                    json.dump(links, f, indent=2, ensure_ascii=False)
                    
                    return True
                    
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    
        except Exception:
            return False
    
    def get_r2_url_for_source(self, source_url: str) -> Optional[str]:
        """Recherche l'URL R2 correspondant à une URL source.
        
        Args:
            source_url: URL source à rechercher
            
        Returns:
            URL R2 si trouvée, None sinon
        """
        try:
            if not self._links_file.exists():
                return None

            normalized_input_by_provider: Dict[str, str] = {}
            
            with open(self._links_file, 'r', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                
                try:
                    links = json.load(f)
                    if not isinstance(links, list):
                        return None
                    
                    for entry in reversed(links):
                        if not isinstance(entry, dict):
                            continue

                        entry_source_url = entry.get("source_url")
                        if not entry_source_url:
                            continue

                        if entry_source_url == source_url:
                            return entry.get("r2_url")

                        entry_provider = entry.get("provider") or ""
                        if entry_provider not in normalized_input_by_provider:
                            normalized_input_by_provider[entry_provider] = self.normalize_source_url(
                                source_url, entry_provider
                            )
                        normalized_input = normalized_input_by_provider[entry_provider]

                        if entry_source_url == normalized_input:
                            return entry.get("r2_url")

                        entry_source_url_normalized = self.normalize_source_url(
                            entry_source_url, entry_provider
                        )
                        if entry_source_url_normalized == normalized_input:
                            return entry.get("r2_url")
                    
                    return None
                    
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    
        except Exception:
            return None
    
    def _generate_object_key(self, source_url: str, provider: str) -> str:
        """Génère un nom d'objet unique pour R2.
        
        Format: {provider}/{hash[:8]}/{hash[8:16]}/{filename}
        
        Args:
            source_url: URL source
            provider: Nom du provider
            
        Returns:
            Clé d'objet (ex: dropbox/a1b2c3d4/e5f6g7h8/file.zip)
        """
        normalized_url = self._normalize_source_url(source_url, provider)

        url_hash = hashlib.sha256(normalized_url.encode('utf-8')).hexdigest()
        
        filename = "file"
        try:
            from urllib.parse import urlparse, unquote
            parsed = urlparse(normalized_url)
            path_parts = parsed.path.split('/')
            if path_parts:
                last_part = unquote(path_parts[-1])
                if last_part and '.' in last_part:
                    filename = last_part
        except Exception:
            pass
        
        prefix = url_hash[:8]
        subdir = url_hash[8:16]
        
        object_key = f"{provider}/{prefix}/{subdir}/{filename}"
        
        return object_key

    def _normalize_source_url(self, source_url: str, provider: str) -> str:
        """Normalise certains liens pour garantir un téléchargement direct.

        Args:
            source_url: URL d'origine
            provider: Nom du provider

        Returns:
            URL normalisée (string)
        """
        return self.normalize_source_url(source_url, provider)

    @staticmethod
    def _decode_and_unescape_url(url: str) -> str:
        if not url:
            return ""

        raw = url.strip()
        try:
            raw = html.unescape(raw)
        except Exception:
            pass

        prev_url = None
        for _ in range(3):
            if raw == prev_url:
                break
            prev_url = raw

            raw = raw.replace("amp%3B", "&").replace("amp%3b", "&")
            try:
                decoded = urllib.parse.unquote(raw)
                if "://" in decoded:
                    raw = decoded
            except Exception:
                pass

        return raw

    @staticmethod
    def _is_dropbox_shared_folder_link(url: str) -> bool:
        """Retourne True si l'URL pointe vers un dossier partagé Dropbox (/scl/fo/...)."""
        if not url:
            return False
        try:
            parsed = urllib.parse.urlsplit(url)
            host = (parsed.hostname or "").lower()
            path = (parsed.path or "").lower()
            if not host.endswith("dropbox.com"):
                return False
            return path.startswith("/scl/fo/")
        except Exception:
            return False

    def get_skip_reason(self, source_url: str, provider: str) -> Optional[str]:
        if provider != "dropbox":
            return None

        return None

    def normalize_source_url(self, source_url: str, provider: str) -> str:
        if not source_url or not provider:
            return source_url

        raw = source_url.strip()
        try:
            raw = html.unescape(raw)
        except Exception:
            pass

        if provider != "dropbox":
            return raw

        raw = self._decode_and_unescape_url(raw)

        try:
            parsed = urllib.parse.urlsplit(raw)
            if not parsed.hostname:
                return raw

            scheme = "https"
            host = (parsed.hostname or "").lower()
            port = parsed.port

            netloc = host
            if parsed.username or parsed.password:
                userinfo = ""
                if parsed.username:
                    userinfo += urllib.parse.quote(parsed.username)
                if parsed.password:
                    userinfo += f":{urllib.parse.quote(parsed.password)}"
                if userinfo:
                    netloc = f"{userinfo}@{netloc}"

            if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
                netloc = f"{netloc}:{port}"

            path = urllib.parse.unquote(parsed.path or "")
            while "//" in path:
                path = path.replace("//", "/")
            if path.endswith("/") and path != "/":
                path = path[:-1]
            path = urllib.parse.quote(path, safe="/-._~")

            q = urllib.parse.parse_qsl(parsed.query or "", keep_blank_values=True)
            filtered: List[Tuple[str, str]] = []
            seen = set()
            for k, v in q:
                key = (k or "").strip()
                val = (v or "").strip()
                if not key:
                    continue
                if not val and key.lower() not in ("rlkey",):
                    continue

                if key.lower() == "dl":
                    continue

                tup = (key, val)
                if tup in seen:
                    continue
                seen.add(tup)
                filtered.append((key, val))

            filtered.append(("dl", "1"))
            filtered.sort(key=lambda kv: (kv[0].lower(), kv[1]))
            query = urllib.parse.urlencode(filtered, doseq=True)

            return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))
        except Exception:
            return raw
    
    def __repr__(self) -> str:
        """Représentation du service."""
        status = "enabled" if self.is_enabled() else "disabled"
        return f"<R2TransferService(status={status}, bucket={self._bucket_name or 'N/A'})>"
