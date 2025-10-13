from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Blueprint
from flask_login import login_required, current_user

bp = Blueprint("api_polling", __name__, url_prefix="/api/polling")

# Legacy toggle endpoint removed; control moved to /api/update_polling_config (enable_polling)
