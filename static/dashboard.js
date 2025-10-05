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

// Affiche le statut des vacances sous les sélecteurs de dates
function updateVacationStatus() {
    const el = document.getElementById('vacationStatus');
    if (!el) return;
    const vs = (document.getElementById('vacationStart')?.value || '').trim();
    const ve = (document.getElementById('vacationEnd')?.value || '').trim();
    if (!vs && !ve) {
        el.textContent = 'Vacances désactivées';
        return;
    }
    if (vs && ve && vs > ve) {
        el.textContent = '⚠️ Plage invalide: la date de début doit être antérieure ou égale à la date de fin';
        return;
    }
    const fr = (iso) => {
        try {
            const d = new Date(iso + 'T00:00:00');
            return d.toLocaleDateString('fr-FR');
        } catch { return iso; }
    };
    const left = vs ? fr(vs) : '—';
    const right = ve ? fr(ve) : '—';
    el.textContent = `Vacances: du ${left} au ${right}`;
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

// Affichage convivial de la dernière fenêtre horaire enregistrée
function renderTimeWindowDisplay(start, end) {
    const displayEl = document.getElementById('timeWindowDisplay');
    if (!displayEl) return;
    const hasStart = Boolean(start && String(start).trim());
    const hasEnd = Boolean(end && String(end).trim());
    if (!hasStart && !hasEnd) {
        displayEl.textContent = 'Dernière fenêtre enregistrée: aucune contrainte horaire active';
        return;
    }
    const startText = hasStart ? String(start) : '—';
    const endText = hasEnd ? String(end) : '—';
    displayEl.textContent = `Dernière fenêtre enregistrée: ${startText} → ${endText}`;
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
            // Mettre à jour l'affichage sous le bouton
            renderTimeWindowDisplay(data.webhooks_time_start || '', data.webhooks_time_end || '');
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
            // Mettre à jour les inputs selon la normalisation renvoyée par le backend
            if (Object.prototype.hasOwnProperty.call(data, 'webhooks_time_start')) {
                document.getElementById('webhooksTimeStart').value = data.webhooks_time_start || '';
            }
            if (Object.prototype.hasOwnProperty.call(data, 'webhooks_time_end')) {
                document.getElementById('webhooksTimeEnd').value = data.webhooks_time_end || '';
            }
            // Mettre à jour l'affichage sous le bouton
            renderTimeWindowDisplay(data.webhooks_time_start || start, data.webhooks_time_end || end);
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
            document.getElementById('recadrageUrl').placeholder = config.recadrage_webhook_url || 'Non configuré';
            document.getElementById('presenceTrueUrl').placeholder = config.presence_true_url || 'Non configuré';
            document.getElementById('presenceFalseUrl').placeholder = config.presence_false_url || 'Non configuré';
            document.getElementById('autorepondeurUrl').placeholder = config.autorepondeur_webhook_url || 'Non configuré';
            
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
    
    const recadrageUrl = document.getElementById('recadrageUrl').value.trim();
    if (recadrageUrl) payload.recadrage_webhook_url = recadrageUrl;
    
    const presenceTrueUrl = document.getElementById('presenceTrueUrl').value.trim();
    if (presenceTrueUrl) payload.presence_true_url = presenceTrueUrl;
    
    const presenceFalseUrl = document.getElementById('presenceFalseUrl').value.trim();
    if (presenceFalseUrl) payload.presence_false_url = presenceFalseUrl;
    
    const autorepondeurUrl = document.getElementById('autorepondeurUrl').value.trim();
    if (autorepondeurUrl) payload.autorepondeur_webhook_url = autorepondeurUrl;
    
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
                document.getElementById('recadrageUrl').value = '';
                document.getElementById('presenceTrueUrl').value = '';
                document.getElementById('presenceFalseUrl').value = '';
                document.getElementById('autorepondeurUrl').value = '';
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
    loadPollingConfig();
    loadWebhookLogs();
    
    // Attacher les gestionnaires d'événements
    document.getElementById('saveTimeWindowBtn').addEventListener('click', saveTimeWindow);
    document.getElementById('togglePollingBtn').addEventListener('click', togglePolling);
    document.getElementById('saveConfigBtn').addEventListener('click', saveWebhookConfig);
    document.getElementById('refreshLogsBtn').addEventListener('click', loadWebhookLogs);
    document.getElementById('savePollingCfgBtn').addEventListener('click', savePollingConfig);
    // Mettre à jour le statut vacances quand l'utilisateur change les dates
    const vacStartEl = document.getElementById('vacationStart');
    const vacEndEl = document.getElementById('vacationEnd');
    if (vacStartEl && vacEndEl) {
        const onChange = () => updateVacationStatus();
        vacStartEl.addEventListener('change', onChange);
        vacEndEl.addEventListener('change', onChange);
    }
    
    // Auto-refresh des logs toutes les 30 secondes
    setInterval(loadWebhookLogs, 30000);
    
    console.log('📊 Dashboard Webhooks initialisé.');
});

// --- Polling Config (jours, heures, dédup) ---
function parseDaysInputToIndices(input) {
    // Accepte "0,1,2" ou "monday, friday"; retourne liste [0..6]
    if (!input) return [];
    const map = {
        monday: 0, mon: 0, lundi: 0,
        tuesday: 1, tue: 1, mardi: 1,
        wednesday: 2, wed: 2, mercredi: 2,
        thursday: 3, thu: 3, jeudi: 3,
        friday: 4, fri: 4, vendredi: 4,
        saturday: 5, sat: 5, samedi: 5,
        sunday: 6, sun: 6, dimanche: 6
    };
    const out = [];
    input.split(',').map(s => s.trim()).filter(Boolean).forEach(tok => {
        const low = tok.toLowerCase();
        if (/^\d+$/.test(low)) {
            const v = parseInt(low, 10);
            if (v >= 0 && v <= 6) out.push(v);
        } else if (map.hasOwnProperty(low)) {
            out.push(map[low]);
        }
    });
    // unique, trié
    return Array.from(new Set(out)).sort((a,b)=>a-b);
}

async function loadPollingConfig() {
    try {
        const res = await fetch('/api/get_polling_config');
        const data = await res.json();
        if (data.success) {
            const cfg = data.config || {};
            const days = Array.isArray(cfg.active_days) ? cfg.active_days : [];
            document.getElementById('pollingActiveDays').value = days.join(',');
            document.getElementById('pollingStartHour').value = cfg.active_start_hour ?? '';
            document.getElementById('pollingEndHour').value = cfg.active_end_hour ?? '';
            document.getElementById('enableSubjectGroupDedup').checked = !!cfg.enable_subject_group_dedup;
            const senders = Array.isArray(cfg.sender_of_interest_for_polling) ? cfg.sender_of_interest_for_polling : [];
            document.getElementById('senderOfInterest').value = senders.join(', ');
            // Dates vacances
            if (cfg.vacation_start) document.getElementById('vacationStart').value = cfg.vacation_start;
            if (cfg.vacation_end) document.getElementById('vacationEnd').value = cfg.vacation_end;
            updateVacationStatus();
        }
    } catch (e) {
        console.error('Erreur chargement config polling:', e);
    }
}

async function savePollingConfig() {
    const btn = document.getElementById('savePollingCfgBtn');
    const daysRaw = document.getElementById('pollingActiveDays').value.trim();
    const startStr = document.getElementById('pollingStartHour').value.trim();
    const endStr = document.getElementById('pollingEndHour').value.trim();
    const dedup = document.getElementById('enableSubjectGroupDedup').checked;
    const sendersRaw = document.getElementById('senderOfInterest').value.trim();
    const vacStart = document.getElementById('vacationStart').value.trim();
    const vacEnd = document.getElementById('vacationEnd').value.trim();

    const payload = {};
    const parsedDays = parseDaysInputToIndices(daysRaw);
    if (parsedDays.length) payload.active_days = parsedDays;
    if (startStr !== '') payload.active_start_hour = parseInt(startStr, 10);
    if (endStr !== '') payload.active_end_hour = parseInt(endStr, 10);
    payload.enable_subject_group_dedup = dedup;

    // Parse and validate emails
    const emails = sendersRaw
        ? sendersRaw.split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
        : [];
    const emailRe = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
    const valid = [];
    const seen = new Set();
    for (const e of emails) {
        if (emailRe.test(e) && !seen.has(e)) {
            seen.add(e);
            valid.push(e);
        }
    }
    payload.sender_of_interest_for_polling = valid;
    // Dates ISO (ou null)
    payload.vacation_start = vacStart || null;
    payload.vacation_end = vacEnd || null;

    try {
        btn.disabled = true;
        const res = await fetch('/api/update_polling_config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showMessage('pollingCfgMsg', data.message || 'Configuration polling enregistrée.', 'success');
            // Recharger pour refléter la normalisation côté serveur
            loadPollingConfig();
        } else {
            showMessage('pollingCfgMsg', data.message || 'Erreur lors de la sauvegarde.', 'error');
        }
    } catch (e) {
        showMessage('pollingCfgMsg', 'Erreur de communication avec le serveur.', 'error');
    } finally {
        btn.disabled = false;
    }
}
