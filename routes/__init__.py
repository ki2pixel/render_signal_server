# routes package initializer

from .health import bp as health_bp  # noqa: F401
from .api_webhooks import bp as api_webhooks_bp  # noqa: F401
from .api_polling import bp as api_polling_bp  # noqa: F401
from .api_processing import bp as api_processing_bp  # noqa: F401
from .api_processing import legacy_bp as api_processing_legacy_bp  # noqa: F401
from .api_test import bp as api_test_bp  # noqa: F401
from .dashboard import bp as dashboard_bp  # noqa: F401
from .api_logs import bp as api_logs_bp  # noqa: F401
from .api_admin import bp as api_admin_bp  # noqa: F401
from .api_utility import bp as api_utility_bp  # noqa: F401
from .api_config import bp as api_config_bp  # noqa: F401
