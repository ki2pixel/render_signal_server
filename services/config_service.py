"""
services.config_service
~~~~~~~~~~~~~~~~~~~~~~~

Service centralisé pour accéder à la configuration applicative.

Ce service remplace l'accès direct aux variables de config.settings et fournit:
- Validation des valeurs de configuration
- Transformation et normalisation
- Interface stable indépendante de l'implémentation sous-jacente
- Méthodes typées pour accès sécurisé

Usage:
    from services import ConfigService
    
    config = ConfigService()
    
    if config.is_email_config_valid():
        email_cfg = config.get_email_config()
        # ... use email_cfg
"""

from __future__ import annotations
from typing import Optional


class ConfigService:
    """Service centralisé pour accéder à la configuration applicative.
    
    Attributes:
        _settings: Module de configuration (config.settings par défaut)
    """
    
    def __init__(self, settings_module=None):
        """Initialise le service avec un module de configuration.
        
        Args:
            settings_module: Module contenant la configuration (None = import dynamique)
        """
        if settings_module:
            self._settings = settings_module
        else:
            from config import settings
            self._settings = settings
    
    # =========================================================================
    # Configuration IMAP / Email
    # =========================================================================
    
    def get_email_config(self) -> dict:
        """Retourne la configuration email complète et validée.
        
        Returns:
            dict avec clés: address, password, server, port, use_ssl
        """
        return {
            "address": self._settings.EMAIL_ADDRESS,
            "password": self._settings.EMAIL_PASSWORD,
            "server": self._settings.IMAP_SERVER,
            "port": self._settings.IMAP_PORT,
            "use_ssl": self._settings.IMAP_USE_SSL,
        }
    
    def is_email_config_valid(self) -> bool:
        """Vérifie si la configuration email est complète et valide.
        
        Returns:
            True si tous les champs requis sont présents
        """
        return bool(
            self._settings.EMAIL_ADDRESS
            and self._settings.EMAIL_PASSWORD
            and self._settings.IMAP_SERVER
        )
    
    def get_email_address(self) -> str:
        """Retourne l'adresse email configurée."""
        return self._settings.EMAIL_ADDRESS
    
    def get_email_password(self) -> str:
        """Retourne le mot de passe email (sensible)."""
        return self._settings.EMAIL_PASSWORD
    
    def get_imap_server(self) -> str:
        """Retourne le serveur IMAP."""
        return self._settings.IMAP_SERVER
    
    def get_imap_port(self) -> int:
        """Retourne le port IMAP."""
        return self._settings.IMAP_PORT
    
    def get_imap_use_ssl(self) -> bool:
        """Retourne si SSL est activé pour IMAP."""
        return self._settings.IMAP_USE_SSL
    
    # =========================================================================
    # Configuration Webhooks
    # =========================================================================
    
    def get_webhook_url(self) -> str:
        """Retourne l'URL webhook principale."""
        return self._settings.WEBHOOK_URL
    
    def get_webhook_ssl_verify(self) -> bool:
        """Retourne si la vérification SSL est activée pour les webhooks."""
        return self._settings.WEBHOOK_SSL_VERIFY
    
    def has_webhook_url(self) -> bool:
        """Vérifie si une URL webhook est configurée."""
        return bool(self._settings.WEBHOOK_URL)
    
    # =========================================================================
    # Configuration API / Tokens
    # =========================================================================
    
    def get_api_token(self) -> str:
        """Retourne le token API pour Make.com (sensible).
        
        Returns:
            Token API ou chaîne vide si non configuré
        """
        return self._settings.EXPECTED_API_TOKEN or ""
    
    def verify_api_token(self, token: str) -> bool:
        """Vérifie si un token correspond au token API configuré.
        
        Args:
            token: Token à vérifier
            
        Returns:
            True si le token est valide
        """
        expected = self.get_api_token()
        if not expected:
            return False
        return token == expected
    
    def has_api_token(self) -> bool:
        """Vérifie si un token API est configuré."""
        return bool(self._settings.EXPECTED_API_TOKEN)
    
    def get_test_api_key(self) -> str:
        """Retourne la clé API pour les endpoints de test.
        
        Returns:
            Clé API de test depuis TEST_API_KEY env var
        """
        import os
        return os.environ.get("TEST_API_KEY", "")
    
    def verify_test_api_key(self, key: str) -> bool:
        """Vérifie une clé API de test.
        
        Args:
            key: Clé à vérifier
            
        Returns:
            True si valide
        """
        expected = self.get_test_api_key()
        if not expected:
            return False
        return key == expected
    
    # =========================================================================
    # Configuration Render (Déploiement)
    # =========================================================================
    
    def get_render_config(self) -> dict:
        """Retourne la configuration Render pour déploiement.
        
        Returns:
            dict avec api_key, service_id, deploy_hook_url, clear_cache
        """
        return {
            "api_key": self._settings.RENDER_API_KEY,
            "service_id": self._settings.RENDER_SERVICE_ID,
            "deploy_hook_url": self._settings.RENDER_DEPLOY_HOOK_URL,
            "clear_cache": self._settings.RENDER_DEPLOY_CLEAR_CACHE,
        }
    
    def has_render_config(self) -> bool:
        """Vérifie si la configuration Render est complète."""
        return bool(
            self._settings.RENDER_API_KEY and self._settings.RENDER_SERVICE_ID
        ) or bool(self._settings.RENDER_DEPLOY_HOOK_URL)
    
    # =========================================================================
    # Configuration Présence
    # =========================================================================
    
    def get_presence_config(self) -> dict:
        """Retourne la configuration des webhooks de présence.
        
        Returns:
            dict avec flag, true_url, false_url
        """
        return {
            "flag": self._settings.PRESENCE_FLAG,
            "true_url": self._settings.PRESENCE_TRUE_MAKE_WEBHOOK_URL,
            "false_url": self._settings.PRESENCE_FALSE_MAKE_WEBHOOK_URL,
        }
    
    def is_presence_enabled(self) -> bool:
        """Vérifie si le flag de présence est activé."""
        return bool(self._settings.PRESENCE_FLAG)
    
    # =========================================================================
    # Configuration Authentification Dashboard
    # =========================================================================
    
    def get_dashboard_user(self) -> str:
        """Retourne le nom d'utilisateur du dashboard."""
        return self._settings.TRIGGER_PAGE_USER
    
    def get_dashboard_password(self) -> str:
        """Retourne le mot de passe du dashboard (sensible)."""
        return self._settings.TRIGGER_PAGE_PASSWORD
    
    def verify_dashboard_credentials(self, username: str, password: str) -> bool:
        """Vérifie les credentials du dashboard.
        
        Args:
            username: Nom d'utilisateur
            password: Mot de passe
            
        Returns:
            True si credentials valides
        """
        return (
            username == self._settings.TRIGGER_PAGE_USER
            and password == self._settings.TRIGGER_PAGE_PASSWORD
        )
    
    # =========================================================================
    # Configuration Déduplication
    # =========================================================================
    
    def is_email_id_dedup_disabled(self) -> bool:
        """Vérifie si la déduplication par email ID est désactivée."""
        return bool(self._settings.DISABLE_EMAIL_ID_DEDUP)
    
    def is_subject_group_dedup_enabled(self) -> bool:
        """Vérifie si la déduplication par subject group est activée."""
        return bool(self._settings.ENABLE_SUBJECT_GROUP_DEDUP)
    
    def get_dedup_redis_keys(self) -> dict:
        """Retourne les clés Redis pour la déduplication.
        
        Returns:
            dict avec email_ids_key, subject_groups_key, subject_group_prefix
        """
        return {
            "email_ids_key": self._settings.PROCESSED_EMAIL_IDS_REDIS_KEY,
            "subject_groups_key": self._settings.PROCESSED_SUBJECT_GROUPS_REDIS_KEY,
            "subject_group_prefix": self._settings.SUBJECT_GROUP_REDIS_PREFIX,
            "subject_group_ttl": self._settings.SUBJECT_GROUP_TTL_SECONDS,
        }
    
    # =========================================================================
    # Configuration Make.com
    # =========================================================================
    
    def get_makecom_api_key(self) -> str:
        """Retourne la clé API Make.com."""
        return self._settings.MAKECOM_API_KEY or ""
    
    def has_makecom_api_key(self) -> bool:
        """Vérifie si une clé API Make.com est configurée."""
        return bool(self._settings.MAKECOM_API_KEY)
    
    # =========================================================================
    # Configuration Tâches de Fond
    # =========================================================================
    
    def is_background_tasks_enabled(self) -> bool:
        """Vérifie si les tâches de fond sont activées."""
        return bool(getattr(self._settings, "ENABLE_BACKGROUND_TASKS", False))
    
    def get_bg_poller_lock_file(self) -> str:
        """Retourne le chemin du fichier de lock du poller."""
        return getattr(
            self._settings,
            "BG_POLLER_LOCK_FILE",
            "/tmp/render_signal_server_email_poller.lock",
        )
    
    # =========================================================================
    # Chemins de Fichiers
    # =========================================================================
    
    def get_runtime_flags_file(self):
        """Retourne le Path du fichier runtime flags."""
        return self._settings.RUNTIME_FLAGS_FILE
    
    def get_polling_config_file(self):
        """Retourne le Path du fichier polling config."""
        return self._settings.POLLING_CONFIG_FILE
    
    def get_trigger_signal_file(self):
        """Retourne le Path du fichier trigger signal."""
        return self._settings.TRIGGER_SIGNAL_FILE
    
    # =========================================================================
    # Méthodes Utilitaires
    # =========================================================================
    
    def get_raw_settings(self):
        """Retourne le module settings brut (pour compatibilité).
        
        ⚠️ À utiliser uniquement pour migration progressive.
        """
        return self._settings
    
    def __repr__(self) -> str:
        """Représentation du service."""
        return f"<ConfigService(email_valid={self.is_email_config_valid()}, webhook={self.has_webhook_url()})>"
