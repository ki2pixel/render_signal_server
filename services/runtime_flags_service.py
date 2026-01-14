"""
services.runtime_flags_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Service pour gérer les flags runtime avec cache intelligent et persistence.

Features:
- Pattern Singleton (instance unique)
- Cache en mémoire avec TTL
- Persistence JSON automatique
- Thread-safe (via design immutable)
- Validation des valeurs

Usage:
    from services import RuntimeFlagsService
    from pathlib import Path
    
    # Initialisation (une seule fois au démarrage)
    service = RuntimeFlagsService.get_instance(
        file_path=Path("debug/runtime_flags.json"),
        defaults={
            "disable_email_id_dedup": False,
            "allow_custom_webhook_without_links": False,
        }
    )
    
    # Utilisation
    if service.get_flag("disable_email_id_dedup"):
        # ...
    
    service.set_flag("disable_email_id_dedup", True)
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Any


class RuntimeFlagsService:
    """Service pour gérer les flags runtime avec cache et persistence.
    
    Implémente le pattern Singleton pour garantir une instance unique.
    Le cache est invalidé automatiquement après un TTL configuré.
    
    Attributes:
        _instance: Instance singleton
        _file_path: Chemin du fichier JSON de persistence
        _defaults: Valeurs par défaut des flags
        _cache: Cache en mémoire des flags
        _cache_timestamp: Timestamp du dernier chargement du cache
        _cache_ttl: Durée de vie du cache en secondes
    """
    
    _instance: Optional[RuntimeFlagsService] = None
    
    def __init__(self, file_path: Path, defaults: Dict[str, bool]):
        """Initialise le service (utiliser get_instance() de préférence).
        
        Args:
            file_path: Chemin du fichier JSON
            defaults: Dictionnaire des valeurs par défaut
        """
        self._lock = threading.RLock()
        self._file_path = file_path
        self._defaults = defaults
        self._cache: Optional[Dict[str, bool]] = None
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl = 60  # 60 secondes
    
    @classmethod
    def get_instance(
        cls,
        file_path: Optional[Path] = None,
        defaults: Optional[Dict[str, bool]] = None
    ) -> RuntimeFlagsService:
        """Récupère ou crée l'instance singleton.
        
        Args:
            file_path: Chemin du fichier (requis à la première création)
            defaults: Valeurs par défaut (requis à la première création)
            
        Returns:
            Instance unique du service
            
        Raises:
            ValueError: Si instance pas encore créée et paramètres manquants
        """
        if cls._instance is None:
            if file_path is None or defaults is None:
                raise ValueError(
                    "RuntimeFlagsService: file_path and defaults required for first initialization"
                )
            cls._instance = cls(file_path, defaults)
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Réinitialise l'instance singleton (pour tests uniquement)."""
        cls._instance = None
    
    # =========================================================================
    # Accès aux Flags
    # =========================================================================
    
    def get_flag(self, key: str, default: Optional[bool] = None) -> bool:
        """Récupère la valeur d'un flag avec cache.
        
        Args:
            key: Nom du flag
            default: Valeur par défaut si flag inexistant
            
        Returns:
            Valeur du flag (bool)
        """
        flags = self._get_cached_flags()
        if key in flags:
            return flags[key]
        if default is not None:
            return default
        return self._defaults.get(key, False)
    
    def set_flag(self, key: str, value: bool) -> bool:
        """Définit la valeur d'un flag et persiste immédiatement.
        
        Args:
            key: Nom du flag
            value: Nouvelle valeur (bool)
            
        Returns:
            True si sauvegarde réussie, False sinon
        """
        with self._lock:
            flags = self._load_from_disk()
            flags[key] = bool(value)
            if self._save_to_disk(flags):
                self._invalidate_cache()
                return True
            return False
    
    def get_all_flags(self) -> Dict[str, bool]:
        """Retourne tous les flags actuels.
        
        Returns:
            Dictionnaire complet des flags
        """
        return dict(self._get_cached_flags())
    
    def update_flags(self, updates: Dict[str, bool]) -> bool:
        """Met à jour plusieurs flags atomiquement.
        
        Args:
            updates: Dictionnaire des flags à mettre à jour
            
        Returns:
            True si sauvegarde réussie, False sinon
        """
        with self._lock:
            flags = self._load_from_disk()
            for key, value in updates.items():
                flags[key] = bool(value)
            if self._save_to_disk(flags):
                self._invalidate_cache()
                return True
            return False
    
    # =========================================================================
    # Gestion du Cache
    # =========================================================================
    
    def _get_cached_flags(self) -> Dict[str, bool]:
        """Récupère les flags depuis le cache ou recharge depuis le disque.
        
        Returns:
            Dictionnaire des flags
        """
        now = time.time()

        with self._lock:
            if (
                self._cache is not None
                and self._cache_timestamp is not None
                and (now - self._cache_timestamp) < self._cache_ttl
            ):
                return dict(self._cache)

            self._cache = self._load_from_disk()
            self._cache_timestamp = now
            return dict(self._cache)
    
    def _invalidate_cache(self) -> None:
        """Invalide le cache pour forcer un rechargement au prochain accès."""
        with self._lock:
            self._cache = None
            self._cache_timestamp = None
    
    def reload(self) -> None:
        """Force le rechargement des flags depuis le disque."""
        self._invalidate_cache()
    
    # =========================================================================
    # Persistence (I/O Disk)
    # =========================================================================
    
    def _load_from_disk(self) -> Dict[str, bool]:
        """Charge les flags depuis le fichier JSON avec fallback sur defaults.
        
        Returns:
            Dictionnaire des flags fusionnés avec les defaults
        """
        data: Dict[str, Any] = {}
        
        try:
            if self._file_path.exists():
                with open(self._file_path, "r", encoding="utf-8") as f:
                    raw = json.load(f) or {}
                    if isinstance(raw, dict):
                        data.update(raw)
        except Exception:
            # Erreur de lecture: utiliser defaults uniquement
            pass
        
        # Fusionner avec defaults (defaults en priorité pour clés manquantes)
        result = dict(self._defaults)
        
        # Appliquer uniquement les clés connues depuis le fichier
        for key, value in data.items():
            if key in self._defaults:
                result[key] = bool(value)
        
        return result
    
    def _save_to_disk(self, data: Dict[str, bool]) -> bool:
        """Sauvegarde les flags vers le fichier JSON.
        
        Args:
            data: Dictionnaire des flags à sauvegarder
            
        Returns:
            True si succès, False sinon
        """
        tmp_path = None
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._file_path.with_name(self._file_path.name + ".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._file_path)
            return True
        except Exception:
            try:
                if tmp_path is not None and tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            return False
    
    # =========================================================================
    # Méthodes Utilitaires
    # =========================================================================
    
    def get_file_path(self) -> Path:
        """Retourne le chemin du fichier de persistence."""
        return self._file_path
    
    def get_defaults(self) -> Dict[str, bool]:
        """Retourne les valeurs par défaut."""
        return dict(self._defaults)
    
    def get_cache_ttl(self) -> int:
        """Retourne le TTL du cache en secondes."""
        return self._cache_ttl
    
    def set_cache_ttl(self, ttl: int) -> None:
        """Définit le TTL du cache.
        
        Args:
            ttl: Nouvelle durée en secondes (minimum 1)
        """
        self._cache_ttl = max(1, int(ttl))
    
    def is_cache_valid(self) -> bool:
        """Vérifie si le cache est actuellement valide."""
        if self._cache is None or self._cache_timestamp is None:
            return False
        return (time.time() - self._cache_timestamp) < self._cache_ttl
    
    def __repr__(self) -> str:
        """Représentation du service."""
        cache_status = "valid" if self.is_cache_valid() else "expired"
        return f"<RuntimeFlagsService(file={self._file_path.name}, cache={cache_status})>"
