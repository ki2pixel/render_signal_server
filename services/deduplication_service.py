"""
services.deduplication_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Service pour la déduplication d'emails avec Redis et fallback mémoire.

Features:
- Déduplication par email ID (identifiant unique de l'email)
- Déduplication par subject group (regroupement par sujet)
- Fallback automatique en mémoire si Redis indisponible
- Scoping mensuel optionnel pour subject groups
- Thread-safe via design immutable

Usage:
    from services import DeduplicationService, ConfigService
    from config.polling_config import PollingConfigService
    
    config = ConfigService()
    polling_config = PollingConfigService()
    
    dedup = DeduplicationService(
        redis_client=redis_client,
        logger=app.logger,
        config_service=config,
        polling_config_service=polling_config
    )
    
    # Vérifier si un email a été traité
    if not dedup.is_email_processed(email_id):
        # Traiter l'email
        dedup.mark_email_processed(email_id)
    
    # Vérifier un subject group
    if not dedup.is_subject_group_processed(subject):
        # Traiter
        dedup.mark_subject_group_processed(subject)
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from services.config_service import ConfigService
    from config.polling_config import PollingConfigService

from utils.text_helpers import (
    normalize_no_accents_lower_trim,
    strip_leading_reply_prefixes,
)


class DeduplicationService:
    """Service pour la déduplication d'emails et subject groups.
    
    Attributes:
        _redis: Client Redis optionnel
        _logger: Logger pour diagnostics
        _config: ConfigService pour accès à la configuration
        _polling_config: PollingConfigService pour timezone
        _processed_email_ids: Set en mémoire (fallback)
        _processed_subject_groups: Set en mémoire (fallback)
    """
    
    def __init__(
        self,
        redis_client=None,
        logger=None,
        config_service: Optional[ConfigService] = None,
        polling_config_service: Optional[PollingConfigService] = None,
    ):
        """Initialise le service de déduplication.
        
        Args:
            redis_client: Client Redis optionnel (None = fallback mémoire)
            logger: Logger optionnel pour diagnostics
            config_service: ConfigService pour configuration
            polling_config_service: PollingConfigService pour timezone
        """
        self._redis = redis_client
        self._logger = logger
        self._config = config_service
        self._polling_config = polling_config_service
        
        # Fallbacks en mémoire (process-local uniquement)
        self._processed_email_ids: Set[str] = set()
        self._processed_subject_groups: Set[str] = set()
    
    # =========================================================================
    # Déduplication Email ID
    # =========================================================================
    
    def is_email_processed(self, email_id: str) -> bool:
        """Vérifie si un email a déjà été traité.
        
        Args:
            email_id: Identifiant unique de l'email
            
        Returns:
            True si déjà traité, False sinon
        """
        if not email_id:
            return False
        
        # Vérifier si la dédup email est désactivée
        if self.is_email_dedup_disabled():
            return False
        
        # Essayer Redis d'abord
        if self._use_redis():
            try:
                keys_config = self._get_dedup_keys()
                key = keys_config["email_ids_key"]
                return bool(self._redis.sismember(key, email_id))
            except Exception as e:
                if self._logger:
                    self._logger.error(
                        f"DEDUP: Error checking email ID '{email_id}': {e}. "
                        f"Assuming NOT processed."
                    )
                # Fall through to memory
        
        # Fallback mémoire
        return email_id in self._processed_email_ids
    
    def mark_email_processed(self, email_id: str) -> bool:
        """Marque un email comme traité.
        
        Args:
            email_id: Identifiant unique de l'email
            
        Returns:
            True si marqué avec succès
        """
        if not email_id:
            return False
        
        # Si dédup désactivée, ne rien faire
        if self.is_email_dedup_disabled():
            return True  # Considéré comme succès (pas d'erreur)
        
        # Essayer Redis d'abord
        if self._use_redis():
            try:
                keys_config = self._get_dedup_keys()
                key = keys_config["email_ids_key"]
                self._redis.sadd(key, email_id)
                return True
            except Exception as e:
                if self._logger:
                    self._logger.error(f"DEDUP: Error marking email ID '{email_id}': {e}")
                # Fall through to memory
        
        # Fallback mémoire
        self._processed_email_ids.add(email_id)
        return True
    
    # =========================================================================
    # Déduplication Subject Group
    # =========================================================================
    
    def is_subject_group_processed(self, subject: str) -> bool:
        """Vérifie si un subject group a été traité.
        
        Args:
            subject: Sujet de l'email
            
        Returns:
            True si déjà traité
        """
        if not subject:
            return False
        
        # Vérifier si la dédup subject est activée
        if not self.is_subject_dedup_enabled():
            return False
        
        # Générer l'ID du groupe
        group_id = self.generate_subject_group_id(subject)
        scoped_id = self._get_scoped_group_id(group_id)
        
        # Essayer Redis d'abord
        if self._use_redis():
            try:
                keys_config = self._get_dedup_keys()
                ttl_seconds = keys_config["subject_group_ttl"]
                ttl_prefix = keys_config["subject_group_prefix"]
                groups_key = keys_config["subject_groups_key"]
                
                # Vérifier dans la clé TTL si configuré
                if ttl_seconds and ttl_seconds > 0:
                    ttl_key = ttl_prefix + scoped_id
                    val = self._redis.get(ttl_key)
                    if val is not None:
                        return True
                
                # Vérifier dans le set permanent
                return bool(self._redis.sismember(groups_key, scoped_id))
            except Exception as e:
                if self._logger:
                    self._logger.error(
                        f"DEDUP: Error checking subject group '{group_id}': {e}. "
                        f"Assuming NOT processed."
                    )
                # Fall through to memory
        
        # Fallback mémoire
        return scoped_id in self._processed_subject_groups
    
    def mark_subject_group_processed(self, subject: str) -> bool:
        """Marque un subject group comme traité.
        
        Args:
            subject: Sujet de l'email
            
        Returns:
            True si succès
        """
        if not subject:
            return False
        
        # Si dédup désactivée, ne rien faire
        if not self.is_subject_dedup_enabled():
            return True
        
        # Générer l'ID du groupe
        group_id = self.generate_subject_group_id(subject)
        scoped_id = self._get_scoped_group_id(group_id)
        
        # Essayer Redis d'abord
        if self._use_redis():
            try:
                keys_config = self._get_dedup_keys()
                ttl_seconds = keys_config["subject_group_ttl"]
                ttl_prefix = keys_config["subject_group_prefix"]
                groups_key = keys_config["subject_groups_key"]
                
                # Marquer avec TTL si configuré
                if ttl_seconds and ttl_seconds > 0:
                    ttl_key = ttl_prefix + scoped_id
                    self._redis.set(ttl_key, 1, ex=ttl_seconds)
                
                # Ajouter au set permanent
                self._redis.sadd(groups_key, scoped_id)
                return True
            except Exception as e:
                if self._logger:
                    self._logger.error(f"DEDUP: Error marking subject group '{group_id}': {e}")
                # Fall through to memory
        
        # Fallback mémoire
        self._processed_subject_groups.add(scoped_id)
        return True
    
    def generate_subject_group_id(self, subject: str) -> str:
        """Génère un ID de groupe stable pour un sujet.
        
        Heuristique:
        - Normalise le sujet (sans accents, minuscules, espaces réduits)
        - Retire les préfixes Re:/Fwd:
        - Si détecte "Média Solution Missions Recadrage Lot <num>" → groupe par lot
        - Sinon si détecte "Lot <num>" → groupe par lot
        - Sinon → hash MD5 du sujet normalisé
        
        Args:
            subject: Sujet de l'email
            
        Returns:
            Identifiant de groupe stable
        """
        # Normaliser
        norm = normalize_no_accents_lower_trim(subject or "")
        core = strip_leading_reply_prefixes(norm)
        
        # Essayer d'extraire un numéro de lot
        m_lot = re.search(r"\blot\s+(\d+)\b", core)
        lot_part = m_lot.group(1) if m_lot else None
        
        # Détecter les mots-clés Média Solution
        is_media_solution = (
            all(tok in core for tok in ["media solution", "missions recadrage", "lot"])
            if core
            else False
        )
        
        if is_media_solution and lot_part:
            return f"media_solution_missions_recadrage_lot_{lot_part}"
        
        if lot_part:
            return f"lot_{lot_part}"
        
        # Fallback: hash du sujet normalisé
        subject_hash = hashlib.md5(core.encode("utf-8")).hexdigest()
        return f"subject_hash_{subject_hash}"
    
    # =========================================================================
    # Configuration
    # =========================================================================
    
    def is_email_dedup_disabled(self) -> bool:
        """Vérifie si la déduplication par email ID est désactivée.
        
        Returns:
            True si désactivée
        """
        if self._config:
            return self._config.is_email_id_dedup_disabled()
        return False
    
    def is_subject_dedup_enabled(self) -> bool:
        """Vérifie si la déduplication par subject group est activée.
        
        Returns:
            True si activée
        """
        if self._config:
            return self._config.is_subject_group_dedup_enabled()
        return False
    
    # =========================================================================
    # Helpers Internes
    # =========================================================================
    
    def _get_scoped_group_id(self, group_id: str) -> str:
        """Applique le scoping mensuel si activé.
        
        Args:
            group_id: ID de base du groupe
            
        Returns:
            ID scopé (ex: "2025-11:lot_42") si scoping activé, sinon ID original
        """
        if not self.is_subject_dedup_enabled():
            return group_id
        
        # Scoping mensuel basé sur le timezone de polling
        try:
            tz = self._polling_config.get_tz() if self._polling_config else None
            now_local = datetime.now(tz) if tz else datetime.now()
        except Exception:
            now_local = datetime.now()
        
        month_prefix = now_local.strftime("%Y-%m")
        return f"{month_prefix}:{group_id}"
    
    def _use_redis(self) -> bool:
        """Vérifie si Redis est disponible.
        
        Returns:
            True si Redis peut être utilisé
        """
        return self._redis is not None
    
    def _get_dedup_keys(self) -> dict:
        """Récupère les clés Redis depuis la configuration.
        
        Returns:
            dict avec email_ids_key, subject_groups_key, etc.
        """
        if self._config:
            return self._config.get_dedup_redis_keys()
        
        # Fallback sur valeurs par défaut
        return {
            "email_ids_key": "r:ss:processed_email_ids:v1",
            "subject_groups_key": "r:ss:processed_subject_groups:v1",
            "subject_group_prefix": "r:ss:subj_grp:",
            "subject_group_ttl": 2592000,  # 30 jours
        }
    
    # =========================================================================
    # Diagnostic & Stats
    # =========================================================================
    
    def get_memory_stats(self) -> dict:
        """Retourne les statistiques du fallback mémoire.
        
        Returns:
            dict avec email_ids_count, subject_groups_count
        """
        return {
            "email_ids_count": len(self._processed_email_ids),
            "subject_groups_count": len(self._processed_subject_groups),
            "using_redis": self._use_redis(),
        }
    
    def clear_memory_cache(self) -> None:
        """Vide le cache mémoire (pour tests ou débogage)."""
        self._processed_email_ids.clear()
        self._processed_subject_groups.clear()
    
    def __repr__(self) -> str:
        """Représentation du service."""
        backend = "Redis" if self._use_redis() else "Memory"
        email_dedup = "disabled" if self.is_email_dedup_disabled() else "enabled"
        subject_dedup = "enabled" if self.is_subject_dedup_enabled() else "disabled"
        return (
            f"<DeduplicationService(backend={backend}, "
            f"email_dedup={email_dedup}, subject_dedup={subject_dedup})>"
        )
