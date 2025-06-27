# gunicorn_config.py (Version finale et correcte)
import threading

def post_fork(server, worker):
    """
    Ce hook est appelé après la création d'un processus worker.
    C'est l'endroit idéal et sûr pour démarrer des threads d'arrière-plan.
    """
    # On importe les fonctions nécessaires depuis notre application
    from app_render import start_background_tasks
    
    # On log dans quel worker on se trouve
    worker.log.info(f"Worker (PID: {worker.pid}) : Lancement des tâches d'arrière-plan.")
    
    # On démarre le thread
    start_background_tasks()
