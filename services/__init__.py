"""
services
~~~~~~~~

Module contenant les services applicatifs pour une architecture orientée services.

Les services encapsulent la logique métier et fournissent des interfaces cohérentes
pour accéder aux différentes fonctionnalités de l'application.

Services disponibles:
- ConfigService: Configuration applicative centralisée
- RuntimeFlagsService: Gestion des flags runtime avec cache
- WebhookConfigService: Configuration webhooks avec validation
- AuthService: Authentification unifiée (dashboard + API)
- DeduplicationService: Déduplication emails et subject groups
- R2TransferService: Transfert de fichiers vers Cloudflare R2

Usage:
    from services import ConfigService, AuthService
    
    config = ConfigService()
    auth = AuthService(config)
"""

from services.config_service import ConfigService
from services.runtime_flags_service import RuntimeFlagsService
from services.webhook_config_service import WebhookConfigService
from services.auth_service import AuthService
from services.deduplication_service import DeduplicationService
from services.magic_link_service import MagicLinkService
from services.r2_transfer_service import R2TransferService
from services.routing_rules_service import RoutingRulesService

__all__ = [
    "ConfigService",
    "RuntimeFlagsService",
    "WebhookConfigService",
    "AuthService",
    "DeduplicationService",
    "MagicLinkService",
    "R2TransferService",
    "RoutingRulesService",
]
