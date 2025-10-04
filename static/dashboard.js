// static/dashboard.js
// Dashboard de contrôle des webhooks

// Utilitaires
function showMessage(elementId, message, type) {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.className = 'status-msg ' + type;
    setTimeout(() => {
        el.className = 'status-msg';
    }, 5000);
}

function formatTimestamp(isoString) {
    try {
        const date = new Date(isoString);
        return date.toLocaleString('fr-FR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (e) {
        return isoString;
    }
}

// Section 1: Fenêtre horaire
async function loadTimeWindow() {
    try {
        const res = await fetch('/api/get_webhook_time_window');
        const data = await res.json();
        
        if (data.success) {
            if (data.webhooks_time_start) {
                document.getElementById('webhooksTimeStart').value = data.webhooks_time_start;
            }
            if (data.webhooks_time_end) {
                document.getElementById('webhooksTimeEnd').value = data.webhooks_time_end;
            }
        }
    } catch (e) {
        console.error('Erreur chargement fenêtre horaire:', e);
    }
}

async function saveTimeWindow() {
    const start = document.getElementById('webhooksTimeStart').value.trim();
    const end = document.getElementById('webhooksTimeEnd').value.trim();
    
    try {
        const res = await fetch('/api/set_webhook_time_window', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start, end })
        });
        const data = await res.json();
        
        if (data.success) {
            showMessage('timeWindowMsg', 'Fenêtre horaire enregistrée avec succès !', 'success');
        } else {
            showMessage('timeWindowMsg', data.message || 'Erreur lors de la sauvegarde.', 'error');
        }
    } catch (e) {
        showMessage('timeWindowMsg', 'Erreur de communication avec le serveur.', 'error');
    }
}

// Section 2: Contrôle du polling
async function loadPollingStatus() {
    try {
        const res = await fetch('/api/get_webhook_config');
        const data = await res.json();
        
        if (data.success) {
            const isEnabled = data.config.polling_enabled;
            document.getElementById('pollingToggle').checked = isEnabled;
            document.getElementById('pollingStatusText').textContent = 
                isEnabled ? '✅ Polling activé' : '❌ Polling désactivé';
        }
    } catch (e) {
        console.error('Erreur chargement statut polling:', e);
        document.getElementById('pollingStatusText').textContent = '⚠️ Erreur de chargement';
    }
}

async function togglePolling() {
    const enable = document.getElementById('pollingToggle').checked;
    
    try {
        const res = await fetch('/api/toggle_polling', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable })
        });
        const data = await res.json();
        
        if (data.success) {
            showMessage('pollingMsg', data.message, 'info');
            document.getElementById('pollingStatusText').textContent = 
                enable ? '✅ Polling activé' : '❌ Polling désactivé';
        } else {
            showMessage('pollingMsg', data.message || 'Erreur lors du changement.', 'error');
        }
    } catch (e) {
        showMessage('pollingMsg', 'Erreur de communication avec le serveur.', 'error');
    }
}

// Section 3: Configuration des webhooks
async function loadWebhookConfig() {
    try {
        const res = await fetch('/api/get_webhook_config');
        const data = await res.json();
        
        if (data.success) {
            const config = data.config;
            
            // Afficher les valeurs (masquées partiellement pour sécurité)
            document.getElementById('webhookUrl').placeholder = config.webhook_url || 'Non configuré';
            document.getElementById('makecomUrl').placeholder = config.makecom_webhook_url || 'Non configuré';
            document.getElementById('presenceTrueUrl').placeholder = config.presence_true_url || 'Non configuré';
            document.getElementById('presenceFalseUrl').placeholder = config.presence_false_url || 'Non configuré';
            document.getElementById('desaboUrl').placeholder = config.desabo_url || 'Non configuré';
            
            document.getElementById('presenceFlag').value = config.presence_flag ? 'true' : 'false';
            document.getElementById('sslVerifyToggle').checked = config.webhook_ssl_verify;
        }
    } catch (e) {
        console.error('Erreur chargement config webhooks:', e);
    }
}

async function saveWebhookConfig() {
    const payload = {};
    
    // Collecter seulement les champs modifiés (non vides)
    const webhookUrl = document.getElementById('webhookUrl').value.trim();
    if (webhookUrl) payload.webhook_url = webhookUrl;
    
    const makecomUrl = document.getElementById('makecomUrl').value.trim();
    if (makecomUrl) payload.makecom_webhook_url = makecomUrl;
    
    const presenceTrueUrl = document.getElementById('presenceTrueUrl').value.trim();
    if (presenceTrueUrl) payload.presence_true_url = presenceTrueUrl;
    
    const presenceFalseUrl = document.getElementById('presenceFalseUrl').value.trim();
    if (presenceFalseUrl) payload.presence_false_url = presenceFalseUrl;
    
    const desaboUrl = document.getElementById('desaboUrl').value.trim();
    if (desaboUrl) payload.desabo_url = desaboUrl;
    
    payload.presence_flag = document.getElementById('presenceFlag').value === 'true';
    payload.webhook_ssl_verify = document.getElementById('sslVerifyToggle').checked;
    
    try {
        const res = await fetch('/api/update_webhook_config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if (data.success) {
            showMessage('configMsg', 'Configuration sauvegardée avec succès !', 'success');
            // Recharger pour afficher les nouvelles valeurs masquées
            setTimeout(() => {
                // Vider les champs pour montrer les placeholders masqués
                document.getElementById('webhookUrl').value = '';
                document.getElementById('makecomUrl').value = '';
                document.getElementById('presenceTrueUrl').value = '';
                document.getElementById('presenceFalseUrl').value = '';
                document.getElementById('desaboUrl').value = '';
                loadWebhookConfig();
            }, 1000);
        } else {
            showMessage('configMsg', data.message || 'Erreur lors de la sauvegarde.', 'error');
        }
    } catch (e) {
        showMessage('configMsg', 'Erreur de communication avec le serveur.', 'error');
    }
}

// Section 4: Logs des webhooks
async function loadWebhookLogs() {
    const logsContainer = document.getElementById('logsContainer');
    logsContainer.innerHTML = '<div class="log-empty">Chargement des logs...</div>';
    
    try {
        const res = await fetch('/api/webhook_logs?days=7');
        const data = await res.json();
        
        if (data.success && data.logs && data.logs.length > 0) {
            logsContainer.innerHTML = '';
            
            data.logs.forEach(log => {
                const logEntry = document.createElement('div');
                logEntry.className = 'log-entry ' + log.status;
                
                const timeStr = formatTimestamp(log.timestamp);
                const typeClass = log.type === 'custom' ? 'custom' : 'makecom';
                const typeLabel = log.type === 'custom' ? 'CUSTOM' : 'MAKE.COM';
                
                let content = `
                    <div class="log-entry-time">${timeStr}</div>
                    <span class="log-entry-type ${typeClass}">${typeLabel}</span>
                    <strong>${log.status === 'success' ? '✅ Succès' : '❌ Erreur'}</strong>
                `;
                
                if (log.subject) {
                    content += `<div>Sujet: ${escapeHtml(log.subject)}</div>`;
                }
                
                if (log.target_url) {
                    content += `<div>URL: ${escapeHtml(log.target_url)}</div>`;
                }
                
                if (log.status_code) {
                    content += `<div>Code HTTP: ${log.status_code}</div>`;
                }
                
                if (log.error) {
                    content += `<div style="color: var(--cork-danger); margin-top: 5px;">Erreur: ${escapeHtml(log.error)}</div>`;
                }
                
                if (log.email_id) {
                    content += `<div style="font-size: 0.8em; color: var(--cork-text-secondary); margin-top: 5px;">Email ID: ${log.email_id}</div>`;
                }
                
                logEntry.innerHTML = content;
                logsContainer.appendChild(logEntry);
            });
        } else {
            logsContainer.innerHTML = '<div class="log-empty">Aucun log webhook trouvé pour les 7 derniers jours.</div>';
        }
    } catch (e) {
        console.error('Erreur chargement logs:', e);
        logsContainer.innerHTML = '<div class="log-empty">Erreur lors du chargement des logs.</div>';
    }
}

// Utilitaire pour échapper le HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialisation au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    // Charger les données initiales
    loadTimeWindow();
    loadPollingStatus();
    loadWebhookConfig();
    loadWebhookLogs();
    
    // Attacher les gestionnaires d'événements
    document.getElementById('saveTimeWindowBtn').addEventListener('click', saveTimeWindow);
    document.getElementById('togglePollingBtn').addEventListener('click', togglePolling);
    document.getElementById('saveConfigBtn').addEventListener('click', saveWebhookConfig);
    document.getElementById('refreshLogsBtn').addEventListener('click', loadWebhookLogs);
    
    // Auto-refresh des logs toutes les 30 secondes
    setInterval(loadWebhookLogs, 30000);
    
    console.log('📊 Dashboard Webhooks initialisé.');
});
