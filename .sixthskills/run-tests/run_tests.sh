#!/bin/bash
# Activation du venv spécifique au projet
source /mnt/venv_ext4/venv_render_signal_server/bin/activate

# Exécution des tests avec couverture
pytest --cov=.
