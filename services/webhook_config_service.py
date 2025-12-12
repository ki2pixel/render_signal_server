"""
services.webhook_config_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Service pour gérer la configuration des webhooks avec validation stricte.

Features:
- Pattern Singleton
- Validation stricte des URLs (HTTPS requis)
- Normalisation URLs Make.com (format token@domain)
- Cache avec invalidation
- Persistence JSON
- Intégration avec external store optionnel

Usage:
    from services import WebhookConfigService
    from pathlib import Path
    
    service = WebhookConfigService.get_instance(
        file_path=Path("debug/webhook_config.json")
    )
    
    # Valider et définir une URL
    ok, msg = service.set_webhook_url("https://hook.eu2.make.com/abc123")
    if ok:
        url = service.get_webhook_url()
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional, Any, Tuple

from utils.validators import normalize_make_webhook_url


class WebhookConfigService:
    """Service pour gérer la configuration des webhooks.
    
    Attributes:
        _instance: Instance singleton
        _file_path: Chemin du fichier JSON
        _external_store: Store externe optionnel (app_config_store)
        _cache: Cache en mémoire
        _cache_timestamp: Timestamp du cache
        _cache_ttl: TTL du cache en secondes
    """
    
    _instance: Optional[WebhookConfigService] = None
    
    def __init__(self, file_path: Path, external_store=None):
        """Initialise le service (utiliser get_instance() de préférence).
        
        Args:
            file_path: Chemin du fichier JSON
            external_store: Module app_config_store optionnel
        """
        self._file_path = file_path
        self._external_store = external_store
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl = 60  # 60 secondes
    
    @classmethod
    def get_instance(
        cls,
        file_path: Optional[Path] = None,
        external_store=None
    ) -> WebhookConfigService:
        """Récupère ou crée l'instance singleton.
        
        Args:
            file_path: Chemin du fichier (requis à la première création)
            external_store: Store externe optionnel
            
        Returns:
            Instance unique du service
        """
        if cls._instance is None:
            if file_path is None:
                raise ValueError("WebhookConfigService: file_path required for first initialization")
            cls._instance = cls(file_path, external_store)
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Réinitialise l'instance (pour tests)."""
        cls._instance = None
    
    # =========================================================================
    # Configuration Webhook Principal
    # =========================================================================
    
    def get_webhook_url(self) -> str:
        """Retourne l'URL webhook principale.
        
        Returns:
            URL webhook ou chaîne vide si non configurée
        """
        config = self._get_cached_config()
        return config.get("webhook_url", "")
    
    def set_webhook_url(self, url: str) -> Tuple[bool, str]:
        """Définit l'URL webhook avec validation stricte.
        
        Args:
            url: URL webhook (doit être HTTPS)
            
        Returns:
            Tuple (success: bool, message: str)
        """
        # Normaliser si c'est un format Make.com
        normalized_url = normalize_make_webhook_url(url)
        
        # Valider
        ok, msg = self.validate_webhook_url(normalized_url)
        if not ok:
            return False, msg
        
        # Charger config actuelle
        config = self._load_from_disk()
        config["webhook_url"] = normalized_url
        
        # Sauvegarder
        if self._save_to_disk(config):
            self._invalidate_cache()
            return True, "Webhook URL mise à jour avec succès."
        return False, "Erreur lors de la sauvegarde."
    
    def has_webhook_url(self) -> bool:
        """Vérifie si une URL webhook est configurée."""
        return bool(self.get_webhook_url())
    
    # =========================================================================
    # Absence Globale (Pause Webhook)
    # =========================================================================
    
    def get_absence_pause_enabled(self) -> bool:
        """Retourne si la pause absence est activée.
        
        Returns:
            False par défaut
        """
        config = self._get_cached_config()
        return config.get("absence_pause_enabled", False)
    
    def set_absence_pause_enabled(self, enabled: bool) -> bool:
        """Active/désactive la pause absence.
        
        Args:
            enabled: True pour activer la pause
            
        Returns:
            True si sauvegarde réussie
        """
        config = self._load_from_disk()
        config["absence_pause_enabled"] = bool(enabled)
        
        if self._save_to_disk(config):
            self._invalidate_cache()
            return True
        return False
    
    def get_absence_pause_days(self) -> list[str]:
        """Retourne la liste des jours de pause.
        
        Returns:
            Liste des jours (format lowercase: monday, tuesday, etc.)
        """
        config = self._get_cached_config()
        days = config.get("absence_pause_days", [])
        return days if isinstance(days, list) else []
    
    def set_absence_pause_days(self, days: list[str]) -> Tuple[bool, str]:
        """Définit les jours de pause avec validation.
        
        Args:
            days: Liste des jours (monday, tuesday, etc.)
            
        Returns:
            Tuple (success: bool, message: str)
        """
        # Valider les jours
        valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        normalized_days = [str(d).strip().lower() for d in days if isinstance(d, str)]
        
        invalid_days = [d for d in normalized_days if d not in valid_days]
        if invalid_days:
            return False, f"Jours invalides: {', '.join(invalid_days)}"
        
        # Charger config actuelle
        config = self._load_from_disk()
        config["absence_pause_days"] = normalized_days
        
        # Sauvegarder
        if self._save_to_disk(config):
            self._invalidate_cache()
            return True, "Jours de pause mis à jour avec succès."
        return False, "Erreur lors de la sauvegarde."
    
    # =========================================================================
    # Configuration SSL et Enabled
    # =========================================================================
    
    def get_ssl_verify(self) -> bool:
        """Retourne si la vérification SSL est activée.
        
        Returns:
            True par défaut
        """
        config = self._get_cached_config()
        return config.get("webhook_ssl_verify", True)
    
    def set_ssl_verify(self, enabled: bool) -> bool:
        """Active/désactive la vérification SSL.
        
        Args:
            enabled: True pour activer
            
        Returns:
            True si sauvegarde réussie
        """
        config = self._load_from_disk()
        config["webhook_ssl_verify"] = bool(enabled)
        
        if self._save_to_disk(config):
            self._invalidate_cache()
            return True
        return False
    
    def is_webhook_sending_enabled(self) -> bool:
        """Vérifie si l'envoi de webhooks est activé globalement.
        
        Returns:
            True par défaut
        """
        config = self._get_cached_config()
        return config.get("webhook_sending_enabled", True)
    
    def set_webhook_sending_enabled(self, enabled: bool) -> bool:
        """Active/désactive l'envoi de webhooks.
        
        Args:
            enabled: True pour activer
            
        Returns:
            True si succès
        """
        config = self._load_from_disk()
        config["webhook_sending_enabled"] = bool(enabled)
        
        if self._save_to_disk(config):
            self._invalidate_cache()
            return True
        return False
    
    # =========================================================================
    # Fenêtre Horaire
    # =========================================================================
    
    def get_time_window(self) -> Dict[str, str]:
        """Retourne la fenêtre horaire pour les webhooks.
        
        Returns:
            dict avec webhook_time_start, webhook_time_end, global_time_start, global_time_end
        """
        config = self._get_cached_config()
        return {
            "webhook_time_start": config.get("webhook_time_start", ""),
            "webhook_time_end": config.get("webhook_time_end", ""),
            "global_time_start": config.get("global_time_start", ""),
            "global_time_end": config.get("global_time_end", ""),
        }
    
    def update_time_window(self, updates: Dict[str, str]) -> bool:
        """Met à jour la fenêtre horaire.
        
        Args:
            updates: dict avec les champs à mettre à jour
            
        Returns:
            True si succès
        """
        config = self._load_from_disk()
        
        for key in ["webhook_time_start", "webhook_time_end", "global_time_start", "global_time_end"]:
            if key in updates:
                config[key] = updates[key]
        
        if self._save_to_disk(config):
            self._invalidate_cache()
            return True
        return False
    
    # =========================================================================
    # Validation
    # =========================================================================
    
    @staticmethod
    def validate_webhook_url(url: str) -> Tuple[bool, str]:
        """Valide une URL webhook.
        
        Args:
            url: URL à valider
            
        Returns:
            Tuple (is_valid, message)
        """
        if not url:
            return True, "URL vide autorisée (désactivation)"
        
        # Vérifier que c'est HTTPS
        if not url.startswith("https://"):
            return False, "L'URL doit commencer par https://"
        
        # Vérifier format minimal
        if len(url) < 10 or "." not in url:
            return False, "Format d'URL invalide"
        
        return True, "URL valide"
    
    # =========================================================================
    # Accès Complet
    # =========================================================================
    
    def get_all_config(self) -> Dict[str, Any]:
        """Retourne toute la configuration webhook.
        
        Returns:
            Dictionnaire complet
        """
        return dict(self._get_cached_config())
    
    def update_config(self, updates: Dict[str, Any]) -> Tuple[bool, str]:
        """Met à jour plusieurs champs de configuration.
        
        Args:
            updates: Dictionnaire des champs à mettre à jour
            
        Returns:
            Tuple (success, message)
        """
        config = self._load_from_disk()

        if "absence_pause_enabled" in updates:
            updates["absence_pause_enabled"] = bool(updates.get("absence_pause_enabled"))

        if "absence_pause_days" in updates:
            days_val = updates.get("absence_pause_days")
            if not isinstance(days_val, list):
                return False, "absence_pause_days invalide: doit être une liste"
            valid_days = [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
            normalized_days = [
                str(d).strip().lower() for d in days_val if isinstance(d, str)
            ]
            invalid_days = [d for d in normalized_days if d not in valid_days]
            if invalid_days:
                return False, f"absence_pause_days invalide: {', '.join(invalid_days)}"
            updates["absence_pause_days"] = normalized_days

        enabled_effective = bool(
            updates.get("absence_pause_enabled", config.get("absence_pause_enabled", False))
        )
        days_effective = updates.get("absence_pause_days", config.get("absence_pause_days", []))
        if enabled_effective and (not isinstance(days_effective, list) or not days_effective):
            return False, "absence_pause_enabled=true requiert au moins un jour dans absence_pause_days"
        
        # Valider les URLs si présentes
        for key in ["webhook_url"]:
            if key in updates and updates[key]:
                normalized = normalize_make_webhook_url(updates[key])
                ok, msg = self.validate_webhook_url(normalized)
                if not ok:
                    return False, f"{key} invalide: {msg}"
                updates[key] = normalized
        
        # Appliquer les mises à jour
        config.update(updates)
        
        if self._save_to_disk(config):
            self._invalidate_cache()
            return True, "Configuration mise à jour."
        return False, "Erreur lors de la sauvegarde."
    
    # =========================================================================
    # Gestion du Cache
    # =========================================================================
    
    def _get_cached_config(self) -> Dict[str, Any]:
        """Récupère la config depuis le cache ou recharge."""
        now = time.time()
        
        if (
            self._cache is not None
            and self._cache_timestamp is not None
            and (now - self._cache_timestamp) < self._cache_ttl
        ):
            return self._cache
        
        self._cache = self._load_from_disk()
        self._cache_timestamp = now
        return self._cache
    
    def _invalidate_cache(self) -> None:
        """Invalide le cache."""
        self._cache = None
        self._cache_timestamp = None
    
    def reload(self) -> None:
        """Force le rechargement."""
        self._invalidate_cache()
    
    # =========================================================================
    # Persistence
    # =========================================================================
    
    def _load_from_disk(self) -> Dict[str, Any]:
        """Charge la configuration depuis le fichier ou external store.
        
        Returns:
            Dictionnaire de configuration
        """
        # Essayer external store d'abord
        if self._external_store:
            try:
                data = self._external_store.get_config_json("webhook_config", file_fallback=self._file_path)
                if data and isinstance(data, dict):
                    return data
            except Exception:
                pass
        
        # Fallback sur fichier local
        try:
            if self._file_path.exists():
                with open(self._file_path, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
                    if isinstance(data, dict):
                        return data
        except Exception:
            pass
        
        return {}
    
    def _save_to_disk(self, data: Dict[str, Any]) -> bool:
        """Sauvegarde la configuration.
        
        Args:
            data: Configuration à sauvegarder
            
        Returns:
            True si succès
        """
        # Essayer external store d'abord
        if self._external_store:
            try:
                if self._external_store.set_config_json("webhook_config", data, file_fallback=self._file_path):
                    return True
            except Exception:
                pass
        
        # Fallback sur fichier local
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def __repr__(self) -> str:
        """Représentation du service."""
        has_url = "yes" if self.has_webhook_url() else "no"
        return f"<WebhookConfigService(file={self._file_path.name}, has_url={has_url})>"
