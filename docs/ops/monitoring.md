# Monitoring

**TL;DR**: On surveille la performance avec des health checks, logs structurés, et métriques temps réel. Le frontend utilise la Visibility API pour optimiser le polling, et le backend a des timeouts robustes, anti-OOM, et fallbacks garantis pour la résilience.

---

## Le problème : le monitoring inexistant qui nous rendait aveugles

J'ai découvert qu'on avait aucune visibilité sur la santé du système en production. Les logs étaient éparpillés, pas de métriques, et les pannes n'étaient détectées que lorsqu'un utilisateur se plaignait.

Les problèmes concrets :
- **Pas de health checks** : On ne savait pas si le service était vivant
- **Logs non structurés** : Impossible de filtrer ou analyser
- **Pas de métriques** : On ne pouvait pas mesurer la performance
- **Alertes tardives** : Les problèmes étaient détectés trop tard

---

## La solution : tour de contrôle avec système de surveillance

Pensez au monitoring comme une tour de contrôle avec système de surveillance : les health checks sont les radars qui détectent les problèmes, les logs structurés sont les rapports de vol détaillés, et les métriques sont les instruments de bord qui surveillent la performance en temps réel. Le polling intelligent optimise les ressources comme un système de détection automatique.

### ❌ L'ancien monde : rapports manuscrits

```python
# ANTI-PATTERN - logging.py
import logging

logger.info("Processing email...")
logger.error("Failed to send webhook")
# Pas de structure, pas de contexte, pas de filtrage
```

### ✅ Le nouveau monde : système de surveillance automatisé

```python
# app_logging/logger.py
import structlog
import logging

# Logger structuré avec contexte
logger = structlog.get_logger("webhook")
logger.info("Webhook sent", 
    webhook_url=mask_url(webhook_url),
    email_id=email_id,
    status="success",
    duration_ms=duration_ms
)

# Health check endpoint
@bp.route("/health")
def health_check():
    checks = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "redis": check_redis_health(),
            "database": check_database_health(),
            "background_tasks": check_background_tasks()
        },
        "metrics": get_current_metrics()
    }
    return jsonify(checks)
```

**Le gain** : tour de contrôle complète, alertes proactives, et surveillance de la performance.

---

## Idées reçues sur la tour de contrôle

### ❌ "Le monitoring alourdit l'application"
Les health checks sont légers (<10ms) et les logs structurés sont asynchrones. La tour de contrôle ne ralentit pas les opérations, elle les observe seulement.

### ❌ "Les métriques sont compliquées à maintenir"
Les métriques sont collectées automatiquement par des observateurs passifs. C'est comme des instruments qui fonctionnent seuls sans intervention manuelle.

### ❌ "Les alertes créent du bruit"
Les alertes ont des seuils intelligents (10% d'erreur, 80% mémoire) et sont envoyées uniquement quand nécessaire. La tour de contrôle signale seulement les vrais problèmes.

---

## Tableau comparatif des approches de monitoring

| Approche | Visibilité | Performance impact | Maintenance | Alertes proactives | Coût |
|----------|-----------|-------------------|--------------|-------------------|------|
| Aucun monitoring | Nulle | Nul | Nulle | Nulle | Nul |
| Logs manuels | Faible | Faible | Élevée | Tardives | Faible |
| Tour de contrôle | Complète | Très faible | Faible | Immédiates | Moyen |
| Monitoring avancé | Très complète | Variable | Très faible | Prédictives | Élevé |

---

## Radars de santé : monitoring de la santé du système

### Radar principal `/health`

```python
# routes/health.py
@bp.route("/health")
def health_check():
    """Health check endpoint pour Render et monitoring externe"""
    
    checks = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": get_app_version(),
        "uptime": get_uptime_seconds(),
        "services": {}
    }
    
    # Vérification Redis
    if redis_client:
        try:
            redis_client.ping()
            checks["services"]["redis"] = {
                "status": "ok",
                "url": mask_redis_url(os.environ.get("REDIS_URL", "")),
                "connected": True
            }
        except Exception as e:
            checks["services"]["redis"] = {
                "status": "error",
                "error": str(e),
                "connected": False
            }
            checks["status"] = "degraded"
    else:
        checks["services"]["redis"] = {
            "status": "not_configured",
            "connected": False
        }
    
    # Vérification tâches de fond
    checks["services"]["background_tasks"] = check_background_tasks()
    
    # Métriques de performance
    checks["metrics"] = {
        "memory_usage": get_memory_usage(),
        "active_webhooks": get_active_webhook_count(),
        "error_rate_24h": get_error_rate_24h(),
        "last_webhook": get_last_webhook_timestamp()
    }
    
    status_code = 200 if checks["status"] == "ok" else 503
    return jsonify(checks), status_code

def check_background_tasks():
    """Vérifie l'état des tâches de fond"""
    tasks = {}
    
    # Vérification du poller IMAP (legacy)
    if os.environ.get('ENABLE_BACKGROUND_TASKS') == 'true':
        try:
            lock_status = check_imap_lock()
            tasks["imap_poller"] = {
                "status": "running" if lock_status else "stopped",
                "lock_acquired": lock_status,
                "last_check": datetime.utcnow().isoformat()
            }
        except Exception as e:
            tasks["imap_poller"] = {
                "status": "error",
                "error": str(e)
            }
    else:
        tasks["imap_poller"] = {"status": "disabled"}
    
    # Vérification du watcher Make (legacy)
    if os.environ.get('MAKECOM_API_KEY'):
        tasks["make_watcher"] = {
            "status": "running",
            "last_check": datetime.utcnow().isoformat()
        }
    
    return tasks

def check_imap_lock():
    """Vérifie si le verrou IMAP est acquis"""
    if redis_client:
        return bool(redis_client.get("render_signal:poller_lock"))
    return False
```

### Surveillance externe

```bash
# Health check depuis monitoring externe
curl -s https://your-domain.onrender.com/health | jq '.status'

# Vérification détaillée
curl -s https://your-domain.onrender.com/health | jq '.'

# Monitoring avec UptimeRobot
# URL : https://your-domain.onrender.com/health
# Intervalle : ≤ 5 minutes pour maintenir le service "warm"
```

---

## Rapports de vol : visibilité complète

### Système de reporting structuré

```python
# app_logging/logger.py
import structlog

# Configuration des loggers
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ],
    context_class=dict,
    wrapper_class=structlog.stdlib.LoggerFactory(),
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Loggers spécialisés
webhook_logger = structlog.get_logger("webhook")
imap_logger = structlog.get_logger("imap")
r2_logger = structlog.get_logger("r2_transfer")
performance_logger = structlog.get_logger("performance")
```

### Rapports par domaine

```python
# Logs webhooks structurés
webhook_logger.info("Webhook sent successfully", 
    webhook_url=mask_url(webhook_url),
    email_id=email_id,
    status="success",
    duration_ms=duration_ms,
    delivery_links_count=len(delivery_links)
)

# Logs R2 avec métriques
r2_logger.info("File transferred to R2",
    provider=provider,
    source_url=mask_url(source_url),
    r2_url=r2_url,
    file_size_bytes=file_size,
    duration_ms=duration_ms,
    original_filename=original_filename
)

# Logs performance
performance_logger.info("Request processed",
    endpoint=endpoint,
    method=method,
    status_code=status_code,
    duration_ms=duration_ms,
    memory_usage_mb=get_memory_usage_mb()
)
```

### Filtrage et recherche de rapports

```python
# utils/log_utils.py
def filter_logs(logs, level=None, service=None, since=None):
    """Filtre les logs selon critères"""
    filtered = logs
    
    if level:
        filtered = [log for log in filtered if log.get("level") == level]
    
    if service:
        filtered = [log for log in filtered if log.get("service") == service]
    
    if since:
        since_dt = datetime.fromisoformat(since)
        filtered = [log for log in filtered 
                   if datetime.fromisoformat(log["timestamp"]) > since_dt]
    
    return filtered

def search_logs(logs, query):
    """Recherche dans les logs"""
    query_lower = query.lower()
    return [log for log in logs 
            if query_lower in log.get("message", "").lower()]
```

---

## Instruments de bord : monitoring performance frontend

### Navigation optimisée

```javascript
// static/utils/PerformanceMonitor.js
class PerformanceMonitor {
    constructor() {
        this.metrics = {};
        this.observers = [];
    }
    
    startMonitoring() {
        // Observer Performance API
        if ('PerformanceObserver' in window) {
            const observer = new PerformanceObserver((list) => {
                list.getEntries().forEach(entry => {
                    this.recordMetric(entry);
                });
            });
            
            observer.observe({ entryTypes: ['navigation', 'resource', 'paint'] });
            this.observers.push(observer);
        }
        
        // Monitoring temps de chargement
        window.addEventListener('load', () => {
            const loadTime = performance.now();
            this.recordMetric({
                name: 'page_load',
                value: loadTime,
                timestamp: Date.now()
            });
        });
    }
    
    recordMetric(metric) {
        this.metrics[metric.name] = {
            value: metric.value,
            timestamp: metric.timestamp,
            type: metric.type || 'custom'
        };
        
        // Logging en développement seulement
        if (window.location.hostname === 'localhost') {
            console.log(`[PERFORMANCE] ${metric.name}: ${metric.value}ms`);
        }
    }
    
    getMetrics() {
        return this.metrics;
    }
    
    // Nettoyage des observers
    cleanup() {
        this.observers.forEach(observer => observer.disconnect());
        this.observers = [];
    }
}
```

### Système de détection intelligent

```javascript
// static/services/LogService.js
class LogService {
    constructor(apiService) {
        this.apiService = apiService;
        this.timer = null;
        this.isVisible = true;
        this.setupVisibilityAPI();
    }
    
    setupVisibilityAPI() {
        // Pause/resume automatique du polling
        document.addEventListener('visibilitychange', () => {
            this.isVisible = !document.hidden;
            
            if (this.isVisible) {
                this.startPolling();
                console.log('[PERFORMANCE] Page visible - resuming polling');
            } else {
                this.stopPolling();
                console.log('[PERFORMANCE] Page hidden - pausing polling');
            }
        });
        
        // Pause quand on perd le focus
        window.addEventListener('blur', () => {
            if (this.isVisible) {
                this.stopPolling();
            }
        });
        
        window.addEventListener('focus', () => {
            if (!document.hidden && this.isVisible) {
                this.startPolling();
            }
        });
    }
    
    startPolling(intervalMs = 30000) {
        if (this.timer) {
            clearInterval(this.timer);
        }
        
        this.timer = setInterval(async () => {
            if (this.isVisible) {
                try {
                    await this.refreshLogs();
                } catch (error) {
                    console.error('[PERFORMANCE] Polling error:', error);
                }
            }
        }, intervalMs);
        
        console.log(`[PERFORMANCE] Started polling with ${intervalMs}ms interval`);
    }
    
    stopPolling() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
            console.log('[PERFORMANCE] Stopped polling');
        }
    }
}
```

---

## Tableau de bord backend : métriques et alertes

### Instruments de performance

```python
# utils/metrics.py
class MetricsCollector:
    def __init__(self):
        self.start_time = time.time()
        self.metrics = {}
    
    def collect_system_metrics(self):
        """Collecte les métriques système"""
        import psutil
        
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_mb": psutil.virtual_memory().used / 1024 / 1024,
            "disk_usage_gb": psutil.disk_usage('/').used / 1024 / 1024 / 1024,
            "network_io": psutil.net_io_counters(),
            "process_count": len(psutil.pids())
        }
    
    def collect_application_metrics(self):
        """Collecte les métriques applicatives"""
        return {
            "uptime_seconds": time.time() - self.start_time,
            "active_webhooks": self.get_active_webhook_count(),
            "error_rate_24h": self.calculate_error_rate_24h(),
            "last_webhook_timestamp": self.get_last_webhook_timestamp(),
            "redis_connected": self.check_redis_connection(),
            "background_tasks_running": self.check_background_tasks()
        }
    
    def get_active_webhook_count(self):
        """Compte les webhooks actifs des dernières 24h"""
        try:
            logs = webhook_logs_service.get_logs(days=1)
            return len([log for log in logs if log.get('status') == 'success'])
        except:
            return 0
    
    def calculate_error_rate_24h(self):
        """Calcule le taux d'erreur des 24 dernières heures"""
        try:
            logs = webhook_logs_service.get_logs(days=1)
            total = len(logs)
            errors = len([log for log in logs if log.get('status') == 'error'])
            return (errors / total * 100) if total > 0 else 0
        except:
            return 0
```

### Système d'alertes automatique

```python
# utils/alerts.py
class AlertManager:
    def __init__(self):
        self.thresholds = {
            "error_rate": 10,  # %
            "memory_usage": 80,  # %
            "disk_usage": 85,  # %
            "cpu_usage": 90   # %
        }
    
    def check_and_alert(self, metrics):
        """Vérifie les seuils et envoie des alertes"""
        alerts = []
        
        # Taux d'erreur
        error_rate = metrics.get("error_rate_24h", 0)
        if error_rate > self.thresholds["error_rate"]:
            alerts.append({
                "type": "error_rate",
                "severity": "warning",
                "message": f"High error rate: {error_rate:.1f}% (threshold: {self.thresholds['error_rate']}%)",
                "value": error_rate
            })
        
        # Usage mémoire
        memory_usage = metrics.get("memory_mb", 0)
        memory_percent = (memory_usage / 512) * 100  # 512MB = 100%
        if memory_percent > self.thresholds["memory_usage"]:
            alerts.append({
                "type": "memory_usage",
                "severity": "critical",
                "message": f"High memory usage: {memory_percent:.1f}% ({memory_usage:.1f}MB)",
                "value": memory_percent
            })
        
        # Envoi les alertes
        for alert in alerts:
            self.send_alert(alert)
    
    def send_alert(self, alert):
        """Envoie une alerte (log + webhook si configuré)"""
        # Log structuré
        logger.error("ALERT", 
            type=alert["type"],
            severity=alert["severity"],
            message=alert["message"],
            value=alert["value"]
        )
        
        # Webhook d'alerte si configuré
        webhook_url = os.environ.get("ALERT_WEBHOOK_URL")
        if webhook_url:
            try:
                requests.post(webhook_url, json=alert, timeout=10)
            except Exception as e:
                logger.error(f"Failed to send alert webhook: {e}")
```

---

## Protection anti-surcharge : garde-fous mémoire

### Parsing HTML sécurisé

```python
# email_processing/html_parser.py
MAX_HTML_BYTES = 1024 * 1024  # 1MB limite stricte

def extract_text_from_html(html_content: str) -> str:
    """Extrait le texte du HTML avec protection anti-OOM"""
    
    if len(html_content.encode('utf-8')) > MAX_HTML_BYTES:
        logger.warning(
            "HTML content truncated (exceeded 1MB limit)",
            original_size=len(html_content),
            truncated_size=MAX_HTML_BYTES
        )
        html_content = html_content[:MAX_HTML_BYTES]
    
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        return text
    except Exception as e:
        logger.error(f"HTML parsing failed: {e}")
        return html_content[:500]  # Fallback minimal
```

### Surveillance de la mémoire

```python
# utils/memory_monitor.py
def get_memory_usage():
    """Surveille l'utilisation mémoire"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
            "available_mb": (psutil.virtual_memory().available / 1024 / 1024)
        }
    except Exception as e:
        logger.error(f"Failed to get memory usage: {e}")
        return {"error": str(e)}

def check_memory_threshold():
    """Vérifie les seuils de mémoire"""
    memory_info = get_memory_usage()
    
    if "error" not in memory_info:
        memory_percent = memory_info["percent"]
        
        if memory_percent > 80:
            logger.warning(
                f"High memory usage: {memory_percent:.1f}%",
                rss_mb=memory_info["rss_mb"],
                vms_mb=memory_info["vms_mb"]
            )
        
        if memory_percent > 90:
            # Alerte critique
            alert_manager.send_alert({
                "type": "memory_usage",
                "severity": "critical",
                "message": f"Critical memory usage: {memory_percent:.1f}%",
                "value": memory_percent
            })
```

---

## Gardiens anti-zombie : timeouts robustes

### Gardien IMAP

```python
# email_processing/imap_client.py
class IMAPClient:
    def __init__(self, timeout=30):
        self.timeout = timeout
        self.socket_timeout = timeout
    
    def create_connection(self, server, username, password, use_ssl=True):
        """Crée une connexion IMAP avec timeout anti-zombie"""
        try:
            if use_ssl:
                imap = imaplib.IMAP4_SSL(server, timeout=self.socket_timeout)
            else:
                imap = imaplib.IMAP4(server, timeout=self.socket_timeout)
            
            imap.login(username, password)
            logger.info(f"IMAP: Connected to {server}")
            return imap
            
        except (socket.timeout, imaplib.IMAP4.error) as e:
            logger.error(f"IMAP: Connection failed: {e}")
            raise IMAPConnectionError(f"Cannot connect to {server}: {e}")
    
    def select_inbox(self, imap):
        """Sélection de boîte de réception avec timeout"""
        try:
            return imap.select('INBOX')
        except (socket.timeout, imaplib.IMAP4.error) as e:
            logger.error(f"IMAP: Select failed: {e}")
            self._reconnect(imap)
            raise
    
    def _reconnect(self, imap):
        """Reconnexion automatique"""
        try:
            imap.close()
            logger.info("IMAP: Reconnecting...")
            return self.create_connection(
                self.server, self.username, self.password, self.use_ssl
            )
        except Exception as e:
            logger.error(f"IMAP: Reconnection failed: {e}")
            raise
```

### Timeouts adaptatifs pour livraison

```python
# services/r2_transfer_service.py
def get_timeout_for_provider(self, provider, source_url):
    """Retourne le timeout adaptatif par fournisseur"""
    if provider == 'dropbox' and '/scl/fo/' in source_url:
        return 120  # Dossiers partagés Dropbox
    elif provider in ['fromsmash', 'swisstransfer']:
        return 30   # Fichiers simples
    else:
        return 15   # Défaut
    
def request_remote_fetch(self, source_url, provider, email_id=None):
    """Requête R2 avec timeout adaptatif"""
    timeout = self.get_timeout_for_provider(provider, source_url)
    
    try:
        response = requests.post(
            self.endpoint,
            json=payload,
            headers={
                'X-R2-FETCH-TOKEN': self.token,
                'User-Agent': 'RenderSignalServer/1.0'
            },
            timeout=timeout
        )
        return self._process_response(response)
    except requests.exceptions.Timeout:
        logger.warning(f"R2_TRANSFER: Timeout for {provider} after {timeout}s")
        return None
    except Exception as e:
        logger.error(f"R2_TRANSFER: Error for {provider}: {e}")
        return None
```

---

## La Golden Rule : Tour de contrôle avec radars, rapports structurés, surveillance temps réel

Le système utilise des radars (`/health`) pour la surveillance externe, des rapports de vol structurés avec structlog pour la visibilité, et des instruments de bord temps réel pour la performance. Le polling intelligent optimise les ressources, et les gardiens anti-zombie protègent la production avec timeouts robustes, anti-OOM, et fallbacks garantis.

---

*Pour la configuration complète : voir `docs/v2/core/configuration-reference.md`. Pour le déploiement : voir `docs/v2/ops/deployment.md`.*
