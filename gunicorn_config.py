# gunicorn_config.py

def post_fork(server, worker):
    """
    Hook Gunicorn qui est appelé après la création d'un processus worker.
    C'est l'endroit idéal pour démarrer des threads d'arrière-plan.
    """
    from app_render import start_background_tasks
    start_background_tasks()
