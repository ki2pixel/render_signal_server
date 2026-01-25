#!/bin/bash
source /mnt/venv_ext4/venv_render_signal_server/bin/activate
python -m scripts.check_config_store --keys processing_prefs webhook_config polling_config
