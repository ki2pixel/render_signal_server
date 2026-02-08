#!/bin/bash
source /mnt/venv_ext4/venv_render_signal_server/bin/activate
python -m scripts.check_config_store --keys processing_prefs webhook_config routing_rules runtime_flags magic_link_tokens
