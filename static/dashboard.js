// static/dashboard.js
// Dashboard de contrôle des webhooks
window.DASHBOARD_BUILD = 'tabs-2025-10-05-15h29';
console.log('[build] static/dashboard.js loaded:', window.DASHBOARD_BUILD);

// Utilitaires
function showMessage(elementId, message, type) {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.className = 'status-msg ' + type;
    setTimeout(() => {
        el.className = 'status-msg';
    }, 5000);
}

// -------------------- Runtime Flags (Debug) --------------------
async function loadRuntimeFlags() {
    try {
        const res = await fetch('/api/get_runtime_flags');
        const data = await res.json();
        if (!data.success || !data.flags) return;
        const f = data.flags;
        const dedupToggle = document.getElementById('disableEmailIdDedupToggle');
        const allowCustomToggle = document.getElementById('allowCustomWithoutLinksToggle');
        if (dedupToggle) dedupToggle.checked = !!f.disable_email_id_dedup;
        if (allowCustomToggle) allowCustomToggle.checked = !!f.allow_custom_webhook_without_links;
    } catch (e) {
        console.warn('loadRuntimeFlags error', e);
    }
}

async function saveRuntimeFlags() {
    const msgId = 'runtimeFlagsMsg';
    const btn = document.getElementById('runtimeFlagsSaveBtn');
    try {
        btn && (btn.disabled = true);
        const payload = {
            disable_email_id_dedup: !!document.getElementById('disableEmailIdDedupToggle')?.checked,
            allow_custom_webhook_without_links: !!document.getElementById('allowCustomWithoutLinksToggle')?.checked,
        };
        const res = await fetch('/api/update_runtime_flags', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showMessage(msgId, 'Flags runtime enregistrés.', 'success');
        } else {
            showMessage(msgId, data.message || 'Erreur lors de la sauvegarde des flags.', 'error');
        }
    } catch (e) {
        showMessage(msgId, 'Erreur de communication avec le serveur.', 'error');
    } finally {
        btn && (btn.disabled = false);
    }
}

// --- Bootstrap: attach handlers after DOM load ---
window.addEventListener('DOMContentLoaded', () => {
    // Existing initializers
    loadWebhookConfig();
    loadTimeWindow();
    loadProcessingPrefsFromServer();
    computeAndRenderMetrics();
    loadPollingConfig();
    // Note: global Make toggle and vacation controls removed from UI
    // New: runtime flags
    loadRuntimeFlags();

    // Buttons
    const rfBtn = document.getElementById('runtimeFlagsSaveBtn');
    if (rfBtn) rfBtn.addEventListener('click', saveRuntimeFlags);
});

// --- Processing Prefs (server) ---
async function loadProcessingPrefsFromServer() {
    try {
        const res = await fetch('/api/get_processing_prefs');
        const data = await res.json();
        if (!data.success) return;
        const p = data.prefs || {};
        // Backward compatibility: legacy single list + new per-webhook lists
        const legacy = Array.isArray(p.exclude_keywords) ? p.exclude_keywords : [];
        const rec = Array.isArray(p.exclude_keywords_recadrage) ? p.exclude_keywords_recadrage : [];
        const aut = Array.isArray(p.exclude_keywords_autorepondeur) ? p.exclude_keywords_autorepondeur : [];
        const recEl = document.getElementById('excludeKeywordsRecadrage');
        const autEl = document.getElementById('excludeKeywordsAutorepondeur');
        if (recEl) {
            recEl.value = rec.join('\n');
            recEl.placeholder = (rec.length ? rec : ['ex: annulation', 'ex: rappel']).join('\n');
        }
        if (autEl) {
            autEl.value = aut.join('\n');
            autEl.placeholder = (aut.length ? aut : ['ex: facture', 'ex: hors périmètre']).join('\n');
        }
        // Keep legacy field if present in DOM
        setIfPresent('excludeKeywords', legacy.join('\n'), v => v);
        const att = document.getElementById('attachmentDetectionToggle');
        if (att) att.checked = !!p.require_attachments;
        const maxSz = document.getElementById('maxEmailSizeMB');
        if (maxSz) maxSz.value = p.max_email_size_mb ?? '';
        const sp = document.getElementById('senderPriority');
        if (sp) sp.value = JSON.stringify(p.sender_priority || {}, null, 2);
        const rc = document.getElementById('retryCount'); if (rc) rc.value = p.retry_count ?? '';
        const rd = document.getElementById('retryDelaySec'); if (rd) rd.value = p.retry_delay_sec ?? '';
        const to = document.getElementById('webhookTimeoutSec'); if (to) to.value = p.webhook_timeout_sec ?? '';
        const rl = document.getElementById('rateLimitPerHour'); if (rl) rl.value = p.rate_limit_per_hour ?? '';
        const nf = document.getElementById('notifyOnFailureToggle'); if (nf) nf.checked = !!p.notify_on_failure;
    } catch (e) {
        console.warn('loadProcessingPrefsFromServer error', e);
    }
}

async function saveProcessingPrefsToServer() {
    const btn = document.getElementById('processingPrefsSaveBtn');
    const msgId = 'processingPrefsMsg';
    try {
        btn && (btn.disabled = true);
        // Build payload from UI
        const excludeKeywordsRaw = (document.getElementById('excludeKeywords')?.value || '').split(/\n+/).map(s => s.trim()).filter(Boolean);
        const excludeKeywordsRecadrage = (document.getElementById('excludeKeywordsRecadrage')?.value || '').split(/\n+/).map(s => s.trim()).filter(Boolean);
        const excludeKeywordsAutorepondeur = (document.getElementById('excludeKeywordsAutorepondeur')?.value || '').split(/\n+/).map(s => s.trim()).filter(Boolean);
        const requireAttachments = !!document.getElementById('attachmentDetectionToggle')?.checked;
        const maxEmailSize = document.getElementById('maxEmailSizeMB')?.value.trim();
        let senderPriorityObj = {};
        const senderPriorityStr = (document.getElementById('senderPriority')?.value || '').trim();
        if (senderPriorityStr) {
            try { senderPriorityObj = JSON.parse(senderPriorityStr); } catch { senderPriorityObj = {}; }
        }
        const retryCount = document.getElementById('retryCount')?.value.trim();
        const retryDelaySec = document.getElementById('retryDelaySec')?.value.trim();
        const webhookTimeoutSec = document.getElementById('webhookTimeoutSec')?.value.trim();
        const rateLimitPerHour = document.getElementById('rateLimitPerHour')?.value.trim();
        const notifyOnFailure = !!document.getElementById('notifyOnFailureToggle')?.checked;

        const payload = {
            // keep legacy for backward compatibility
            exclude_keywords: excludeKeywordsRaw,
            // new per-webhook lists
            exclude_keywords_recadrage: excludeKeywordsRecadrage,
            exclude_keywords_autorepondeur: excludeKeywordsAutorepondeur,
            require_attachments: requireAttachments,
            max_email_size_mb: maxEmailSize === '' ? null : parseInt(maxEmailSize, 10),
            sender_priority: senderPriorityObj,
            retry_count: retryCount === '' ? 0 : parseInt(retryCount, 10),
            retry_delay_sec: retryDelaySec === '' ? 0 : parseInt(retryDelaySec, 10),
            webhook_timeout_sec: webhookTimeoutSec === '' ? 30 : parseInt(webhookTimeoutSec, 10),
            rate_limit_per_hour: rateLimitPerHour === '' ? 0 : parseInt(rateLimitPerHour, 10),
            notify_on_failure: notifyOnFailure,
        };

        const res = await fetch('/api/update_processing_prefs', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showMessage(msgId, 'Préférences enregistrées.', 'success');
            // Recharger pour refléter la normalisation côté serveur
            loadProcessingPrefsFromServer();
        } else {
            showMessage(msgId, data.message || 'Erreur lors de la sauvegarde.', 'error');
        }
    } catch (e) {
        showMessage(msgId, 'Erreur de communication avec le serveur.', 'error');
    } finally {
        btn && (btn.disabled = false);
    }
}

// -------------------- Nouvelles fonctionnalités UI (client-side only) --------------------

function loadLocalPreferences() {
    try {
        const raw = localStorage.getItem('dashboard_prefs_v1');
        if (!raw) return;
        const prefs = JSON.parse(raw);
        setIfPresent('excludeKeywords', prefs.excludeKeywords, v => v);
        setIfPresent('excludeKeywordsRecadrage', prefs.excludeKeywordsRecadrage, v => v);
        setIfPresent('excludeKeywordsAutorepondeur', prefs.excludeKeywordsAutorepondeur, v => v);
        setIfPresent('attachmentDetectionToggle', prefs.attachmentDetection, (v, el) => el.checked = !!v);
        setIfPresent('maxEmailSizeMB', prefs.maxEmailSizeMB, v => v);
        setIfPresent('senderPriority', prefs.senderPriorityJson, v => v);
        setIfPresent('retryCount', prefs.retryCount, v => v);
        setIfPresent('retryDelaySec', prefs.retryDelaySec, v => v);
        setIfPresent('webhookTimeoutSec', prefs.webhookTimeoutSec, v => v);
        setIfPresent('rateLimitPerHour', prefs.rateLimitPerHour, v => v);
        setIfPresent('notifyOnFailureToggle', prefs.notifyOnFailure, (v, el) => el.checked = !!v);
        setIfPresent('enableMetricsToggle', prefs.enableMetrics, (v, el) => el.checked = !!v);
    } catch (e) {
        console.warn('Prefs load error', e);
    }
}

function setIfPresent(id, value, setter) {
    if (value === undefined) return;
    const el = document.getElementById(id);
    if (!el) return;
    if (typeof setter === 'function') {
        const ret = setter(value, el);
        if (ret !== undefined && el.value !== undefined) el.value = ret;
    } else {
        el.value = value;
    }
}

function saveLocalPreferences() {
    try {
        const prefs = {
            excludeKeywords: (document.getElementById('excludeKeywords')?.value || ''),
            excludeKeywordsRecadrage: (document.getElementById('excludeKeywordsRecadrage')?.value || ''),
            excludeKeywordsAutorepondeur: (document.getElementById('excludeKeywordsAutorepondeur')?.value || ''),
            attachmentDetection: !!document.getElementById('attachmentDetectionToggle')?.checked,
            maxEmailSizeMB: parseInt(document.getElementById('maxEmailSizeMB')?.value || '0', 10) || undefined,
            senderPriorityJson: (document.getElementById('senderPriority')?.value || ''),
            retryCount: parseInt(document.getElementById('retryCount')?.value || '0', 10) || undefined,
            retryDelaySec: parseInt(document.getElementById('retryDelaySec')?.value || '0', 10) || undefined,
            webhookTimeoutSec: parseInt(document.getElementById('webhookTimeoutSec')?.value || '0', 10) || undefined,
            rateLimitPerHour: parseInt(document.getElementById('rateLimitPerHour')?.value || '0', 10) || undefined,
            notifyOnFailure: !!document.getElementById('notifyOnFailureToggle')?.checked,
            enableMetrics: !!document.getElementById('enableMetricsToggle')?.checked,
        };
        localStorage.setItem('dashboard_prefs_v1', JSON.stringify(prefs));
    } catch (e) {
        console.warn('Prefs save error', e);
    }
}

async function computeAndRenderMetrics() {
    try {
        const res = await fetch('/api/webhook_logs?days=1');
        const data = await res.json();
        const logs = (data.success && Array.isArray(data.logs)) ? data.logs : [];
        const total = logs.length;
        const sent = logs.filter(l => l.status === 'success').length;
        const errors = logs.filter(l => l.status === 'error').length;
        const successRate = total ? Math.round((sent / total) * 100) : 0;
        setMetric('metricEmailsProcessed', String(total));
        setMetric('metricWebhooksSent', String(sent));
        setMetric('metricErrors', String(errors));
        setMetric('metricSuccessRate', String(successRate));
        renderMiniChart(logs);
    } catch (e) {
        console.warn('metrics error', e);
        clearMetrics();
    }
}

function clearMetrics() {
    setMetric('metricEmailsProcessed', '—');
    setMetric('metricWebhooksSent', '—');
    setMetric('metricErrors', '—');
    setMetric('metricSuccessRate', '—');
    const chart = document.getElementById('metricsMiniChart');
    if (chart) chart.innerHTML = '';
}

function setMetric(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function renderMiniChart(logs) {
    const chart = document.getElementById('metricsMiniChart');
    if (!chart) return;
    chart.innerHTML = '';
    const width = chart.clientWidth || 300;
    const height = chart.clientHeight || 60;
    const canvas = document.createElement('canvas');
    canvas.width = width; canvas.height = height;
    chart.appendChild(canvas);
    const ctx = canvas.getContext('2d');
    // Simple timeline: success=1, error=0
    const n = Math.min(logs.length, Math.floor(width / 4));
    const step = width / (n || 1);
    ctx.strokeStyle = '#22c98f';
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
        const log = logs[logs.length - n + i];
        const val = (log && log.status === 'success') ? 1 : 0;
        const x = i * step + 1;
        const y = height - (val * (height - 4)) - 2;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
}

async function exportFullConfiguration() {
    try {
        // Gather server-side configs
        const [webhookCfgRes, pollingCfgRes, timeWinRes] = await Promise.all([
            fetch('/api/webhooks/config'),
            fetch('/api/get_polling_config'),
            fetch('/api/get_webhook_time_window')
        ]);
        const [webhookCfg, pollingCfg, timeWin] = await Promise.all([
            webhookCfgRes.json(), pollingCfgRes.json(), timeWinRes.json()
        ]);
        const prefsRaw = localStorage.getItem('dashboard_prefs_v1');
        const exportObj = {
            exported_at: new Date().toISOString(),
            webhook_config: webhookCfg,
            polling_config: pollingCfg,
            time_window: timeWin,
            ui_preferences: prefsRaw ? JSON.parse(prefsRaw) : {}
        };
        const blob = new Blob([JSON.stringify(exportObj, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'render_signal_dashboard_config.json';
        a.click();
        URL.revokeObjectURL(a.href);
        showMessage('configMgmtMsg', 'Export réalisé avec succès.', 'success');
    } catch (e) {
        showMessage('configMgmtMsg', 'Erreur lors de l\'export.', 'error');
    }
}

function handleImportConfigFile(evt) {
    const file = evt.target.files && evt.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
        try {
            const obj = JSON.parse(String(reader.result || '{}'));
            // Apply server-supported parts
            await applyImportedServerConfig(obj);
            // Store UI preferences
            if (obj.ui_preferences) {
                localStorage.setItem('dashboard_prefs_v1', JSON.stringify(obj.ui_preferences));
                loadLocalPreferences();
            }
            showMessage('configMgmtMsg', 'Import appliqué.', 'success');
        } catch (e) {
            showMessage('configMgmtMsg', 'Fichier invalide.', 'error');
        }
    };
    reader.readAsText(file);
    // reset input so consecutive imports fire change
    evt.target.value = '';
}

async function applyImportedServerConfig(obj) {
    // webhook config
    if (obj?.webhook_config?.config) {
        const cfg = obj.webhook_config.config;
        const payload = {};
        if (cfg.webhook_url) payload.webhook_url = cfg.webhook_url;
        if (typeof cfg.presence_flag === 'boolean') payload.presence_flag = cfg.presence_flag;
        if (typeof cfg.webhook_ssl_verify === 'boolean') payload.webhook_ssl_verify = cfg.webhook_ssl_verify;
        if (Object.keys(payload).length) {
            await fetch('/api/webhooks/config', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
            });
            await loadWebhookConfig();
        }
    }
    // polling config
    if (obj?.polling_config?.config) {
        const cfg = obj.polling_config.config;
        const payload = {};
        if (Array.isArray(cfg.active_days)) payload.active_days = cfg.active_days;
        if (Number.isInteger(cfg.active_start_hour)) payload.active_start_hour = cfg.active_start_hour;
        if (Number.isInteger(cfg.active_end_hour)) payload.active_end_hour = cfg.active_end_hour;
        if (typeof cfg.enable_subject_group_dedup === 'boolean') payload.enable_subject_group_dedup = cfg.enable_subject_group_dedup;
        if (Array.isArray(cfg.sender_of_interest_for_polling)) payload.sender_of_interest_for_polling = cfg.sender_of_interest_for_polling;
        if ('vacation_start' in cfg) payload.vacation_start = cfg.vacation_start || null;
        if ('vacation_end' in cfg) payload.vacation_end = cfg.vacation_end || null;
        if (Object.keys(payload).length) {
            await fetch('/api/update_polling_config', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
            });
            await loadPollingConfig();
        }
    }
    // time window
    if (obj?.time_window) {
        const start = obj.time_window.webhooks_time_start ?? '';
        const end = obj.time_window.webhooks_time_end ?? '';
        await fetch('/api/set_webhook_time_window', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ start, end })
        });
        await loadTimeWindow();
    }
}

function validateWebhookUrlFromInput() {
    const inp = document.getElementById('testWebhookUrl');
    const msgId = 'webhookUrlValidationMsg';
    const val = (inp?.value || '').trim();
    if (!val) return showMessage(msgId, 'Veuillez saisir une URL ou un alias.', 'error');
    const ok = isValidMakeWebhookUrl(val) || isValidHttpsUrl(val);
    if (ok) showMessage(msgId, 'Format valide.', 'success'); else showMessage(msgId, 'Format invalide.', 'error');
}

function isValidHttpsUrl(url) {
    try {
        const u = new URL(url);
        return u.protocol === 'https:' && !!u.hostname;
    } catch { return false; }
}

function isValidMakeWebhookUrl(value) {
    // Accept either full https URL or alias token@hook.eu2.make.com
    if (isValidHttpsUrl(value)) return /hook\.eu\d+\.make\.com/i.test(value);
    return /^[A-Za-z0-9_-]{10,}@[Hh]ook\.eu\d+\.make\.com$/.test(value);
}

function buildPayloadPreview() {
    const subject = (document.getElementById('previewSubject')?.value || '').trim();
    const sender = (document.getElementById('previewSender')?.value || '').trim();
    const body = (document.getElementById('previewBody')?.value || '').trim();
    const payload = {
        subject,
        sender_email: sender,
        body_excerpt: body.slice(0, 500),
        delivery_links: [],
        first_direct_download_url: null,
        meta: { preview: true, generated_at: new Date().toISOString() }
    };
    const pre = document.getElementById('payloadPreview');
    if (pre) pre.textContent = JSON.stringify(payload, null, 2);
}

// Nouvelle approche: gestion via cases à cocher (0=Mon .. 6=Sun)
function setDayCheckboxes(days) {
    const group = document.getElementById('pollingActiveDaysGroup');
    if (!group) return;
    const set = new Set(Array.isArray(days) ? days : []);
    const boxes = group.querySelectorAll('input[name="pollingDay"][type="checkbox"]');
    boxes.forEach(cb => {
        const idx = parseInt(cb.value, 10);
        cb.checked = set.has(idx);
    });
}

function collectDayCheckboxes() {
    const group = document.getElementById('pollingActiveDaysGroup');
    if (!group) return [];
    const boxes = group.querySelectorAll('input[name="pollingDay"][type="checkbox"]');
    const out = [];
    boxes.forEach(cb => {
        if (cb.checked) out.push(parseInt(cb.value, 10));
    });
    // tri croissant et unique par sécurité
    return Array.from(new Set(out)).sort((a,b)=>a-b);
}

// ---- UI dynamique pour la liste d'emails ----
function addEmailField(value) {
    const container = document.getElementById('senderOfInterestContainer');
    if (!container) return;
    const row = document.createElement('div');
    row.className = 'inline-group';
    const input = document.createElement('input');
    input.type = 'email';
    input.placeholder = 'ex: email@example.com';
    input.value = value || '';
    input.style.flex = '1';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'email-remove-btn';
    btn.textContent = '❌';
    btn.title = 'Supprimer cet email';
    btn.addEventListener('click', () => row.remove());
    row.appendChild(input);
    row.appendChild(btn);
    container.appendChild(row);
}

function renderSenderInputs(list) {
    const container = document.getElementById('senderOfInterestContainer');
    if (!container) return;
    container.innerHTML = '';
    (list || []).forEach(e => addEmailField(e));
    if (!list || list.length === 0) addEmailField('');
}

function collectSenderInputs() {
    const container = document.getElementById('senderOfInterestContainer');
    if (!container) return [];
    const inputs = Array.from(container.querySelectorAll('input[type="email"]'));
    const emailRe = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
    const out = [];
    const seen = new Set();
    for (const i of inputs) {
        const v = (i.value || '').trim().toLowerCase();
        if (!v) continue;
        if (emailRe.test(v) && !seen.has(v)) {
            seen.add(v);
            out.push(v);
        }
    }
    return out;
}

// Affiche le statut des vacances sous les sélecteurs de dates
// vacation helpers removed with UI

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
        const res = await fetch('/api/webhooks/config');
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
        const res = await fetch('/api/webhooks/config');
        const data = await res.json();
        
        if (data.success) {
            const config = data.config;
            
            // Afficher les valeurs (masquées partiellement pour sécurité)
            const wh = document.getElementById('webhookUrl');
            if (wh) wh.placeholder = config.webhook_url || 'Non configuré';
            
            const pf = document.getElementById('presenceFlag');
            if (pf) pf.value = config.presence_flag ? 'true' : 'false';
            const ssl = document.getElementById('sslVerifyToggle');
            if (ssl) ssl.checked = !!config.webhook_ssl_verify;
            const sending = document.getElementById('webhookSendingToggle');
            if (sending) sending.checked = !!config.webhook_sending_enabled;
            
            // Charger la fenêtre horaire dédiée
            await loadGlobalWebhookTimeWindow();
        }
    } catch (e) {
        console.error('Erreur chargement config webhooks:', e);
    }
}

// Charge la fenêtre horaire dédiée aux webhooks
async function loadGlobalWebhookTimeWindow() {
    try {
        const res = await fetch('/api/webhooks/time-window');
        const data = await res.json();
        if (!data.success) return;

        const startEl = document.getElementById('globalWebhookTimeStart');
        const endEl = document.getElementById('globalWebhookTimeEnd');
        
        if (startEl) startEl.value = data.webhooks_time_start || '';
        if (endEl) endEl.value = data.webhooks_time_end || '';
        
        // Mettre à jour l'affichage
        renderGlobalWebhookTimeWindowDisplay(data.webhooks_time_start, data.webhooks_time_end);
    } catch (e) {
        console.error('Erreur chargement fenêtre horaire webhooks:', e);
    }
}

// Enregistre la fenêtre horaire dédiée aux webhooks
async function saveGlobalWebhookTimeWindow() {
    const start = document.getElementById('globalWebhookTimeStart').value.trim();
    const end = document.getElementById('globalWebhookTimeEnd').value.trim();
    const msgEl = document.getElementById('globalWebhookTimeMsg');
    const btn = document.getElementById('saveGlobalWebhookTimeBtn');
    
    if (!msgEl || !btn) return;
    
    try {
        btn.disabled = true;
        msgEl.textContent = 'Enregistrement en cours...';
        msgEl.className = 'status-msg info';
        
        const res = await fetch('/api/webhooks/time-window', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start, end })
        });
        
        const data = await res.json();
        if (data.success) {
            msgEl.textContent = 'Fenêtre horaire enregistrée avec succès !';
            msgEl.className = 'status-msg success';
            // Mettre à jour l'affichage avec les valeurs normalisées
            renderGlobalWebhookTimeWindowDisplay(
                data.webhooks_time_start || start,
                data.webhooks_time_end || end
            );
        } else {
            msgEl.textContent = data.message || 'Erreur lors de la sauvegarde';
            msgEl.className = 'status-msg error';
        }
    } catch (e) {
        console.error('Erreur sauvegarde fenêtre horaire webhooks:', e);
        msgEl.textContent = 'Erreur de communication avec le serveur';
        msgEl.className = 'status-msg error';
    } finally {
        btn.disabled = false;
        setTimeout(() => {
            msgEl.className = 'status-msg';
        }, 5000);
    }
}

// Affiche la fenêtre horaire dédiée
function renderGlobalWebhookTimeWindowDisplay(start, end) {
    const displayEl = document.getElementById('globalWebhookTimeMsg');
    if (!displayEl) return;
    
    const hasStart = start && start.trim();
    const hasEnd = end && end.trim();
    
    if (!hasStart && !hasEnd) {
        displayEl.textContent = 'Aucune contrainte horaire définie';
        return;
    }
    
    const startText = hasStart ? String(start) : '—';
    const endText = hasEnd ? String(end) : '—';
    displayEl.textContent = `Fenêtre active : ${startText} → ${endText}`;
}

async function saveWebhookConfig() {
    const payload = {};
    // Collecter seulement les champs pertinents
    const webhookUrlEl = document.getElementById('webhookUrl');
    const presenceFlagEl = document.getElementById('presenceFlag');
    const sslEl = document.getElementById('sslVerifyToggle');
    const sendingEl = document.getElementById('webhookSendingToggle');
    const webhookUrl = (webhookUrlEl?.value || '').trim();
    if (webhookUrl) payload.webhook_url = webhookUrl;
    if (presenceFlagEl) payload.presence_flag = presenceFlagEl.value === 'true';
    if (sslEl) payload.webhook_ssl_verify = !!sslEl.checked;
    if (sendingEl) payload.webhook_sending_enabled = !!sendingEl.checked;
    
    try {
        const res = await fetch('/api/webhooks/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if (data.success) {
            showMessage('configMsg', 'Configuration sauvegardée avec succès !', 'success');
            // Recharger pour afficher les nouvelles valeurs masquées
            setTimeout(() => {
                // Vider le champ pour montrer le placeholder masqué
                const wh2 = document.getElementById('webhookUrl');
                if (wh2) wh2.value = '';
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

// -------------------- Navigation par onglets --------------------
function initTabs() {
    console.log('[tabs] initTabs: starting');
    const tabButtons = Array.from(document.querySelectorAll('.tab-btn'));
    const panels = Array.from(document.querySelectorAll('.section-panel'));
    console.log(`[tabs] found buttons=${tabButtons.length}, panels=${panels.length}`);

    const mapHashToId = {
        '#overview': '#sec-overview',
        '#webhooks': '#sec-webhooks',
        '#make': '#sec-polling',
        '#polling': '#sec-polling', // legacy alias
        '#preferences': '#sec-preferences',
        '#tools': '#sec-tools',
    };

    function activate(targetSelector) {
        console.log('[tabs] activate called for target:', targetSelector);
        // Toggle active class on panels
        panels.forEach(p => { p.classList.remove('active'); p.style.display = 'none'; });
        const panel = document.querySelector(targetSelector);
        if (panel) {
            panel.classList.add('active');
            panel.style.display = 'block';
            console.log('[tabs] panel activated:', panel.id);
        } else {
            console.warn('[tabs] panel not found for selector:', targetSelector);
        }

        // Toggle active class on buttons
        tabButtons.forEach(btn => btn.classList.remove('active'));
        const btn = tabButtons.find(b => b.getAttribute('data-target') === targetSelector);
        if (btn) {
            btn.classList.add('active');
            console.log('[tabs] button activated (data-target):', targetSelector);
        } else {
            console.warn('[tabs] button not found for selector:', targetSelector);
        }

        // Optional: refresh section data on show
        if (targetSelector === '#sec-overview') {
            const enableMetricsToggle = document.getElementById('enableMetricsToggle');
            if (enableMetricsToggle && enableMetricsToggle.checked) {
                computeAndRenderMetrics();
            }
            loadWebhookLogs();
        } else if (targetSelector === '#sec-webhooks') {
            loadTimeWindow();
            loadWebhookConfig();
        } else if (targetSelector === '#sec-polling') {
            loadPollingConfig();
        }
    }

    // Wire click handlers
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-target');
            console.log('[tabs] click on tab-btn, target=', target);
            if (target) {
                // Update URL hash for deep-linking (without scrolling)
                // Prefer canonical hash for the target
                const preferred = (target === '#sec-polling') ? '#make' :
                                  (target === '#sec-overview') ? '#overview' :
                                  (target === '#sec-webhooks') ? '#webhooks' :
                                  (target === '#sec-preferences') ? '#preferences' :
                                  (target === '#sec-tools') ? '#tools' : '';
                if (preferred) history.replaceState(null, '', preferred);
                activate(target);
            }
        });
    });

    // Determine initial tab: from hash or default to overview
    const initialHash = window.location.hash;
    const initialTarget = mapHashToId[initialHash] || '#sec-overview';
    console.log('[tabs] initialHash=', initialHash, ' -> initialTarget=', initialTarget);
    activate(initialTarget);

    // React to hash changes (e.g., manual URL edit)
    window.addEventListener('hashchange', () => {
        const t = mapHashToId[window.location.hash];
        console.log('[tabs] hashchange ->', window.location.hash, ' mapped to ', t);
        if (t) activate(t);
    });
    console.log('[tabs] initTabs: ready');
}

// Gestionnaire pour le bouton de sauvegarde de la fenêtre horaire webhook
document.addEventListener('DOMContentLoaded', () => {
    const saveGlobalTimeBtn = document.getElementById('saveGlobalWebhookTimeBtn');
    if (saveGlobalTimeBtn) {
        saveGlobalTimeBtn.addEventListener('click', saveGlobalWebhookTimeWindow);
    }
    
    // Raccourci Entrée dans les champs de la fenêtre horaire
    const timeInputs = ['globalWebhookTimeStart', 'globalWebhookTimeEnd'];
    timeInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') saveGlobalWebhookTimeWindow();
            });
        }
    });
});

// Initialisation au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    console.log('📊 DOMContentLoaded: init start');
    // Hide non-active panels immediately (not relying only on CSS)
    try {
        const allPanels = document.querySelectorAll('.section-panel');
        allPanels.forEach(p => {
            if (!p.classList.contains('active')) p.style.display = 'none';
            else p.style.display = 'block';
        });
        console.log(`[tabs] initial panel visibility set (count=${allPanels.length})`);
    } catch (e) {
        console.warn('[tabs] initial hide panels failed:', e);
    }
    // Initialiser les onglets en premier pour garantir l'UX même si des erreurs surviennent après
    try {
        console.log('[tabs] calling initTabs early');
        initTabs();
        console.log('[tabs] initTabs completed');
    } catch (e) {
        console.error('[tabs] initTabs threw (early):', e);
    }

    // Fallback: programmer un appel asynchrone très tôt pour contourner d'éventuels ordres d'exécution
    try {
        setTimeout(() => {
            try {
                console.log('[tabs] setTimeout fallback: calling initTabs');
                initTabs();
            } catch (err) {
                console.error('[tabs] setTimeout fallback failed:', err);
            }
        }, 0);
    } catch (e) {
        console.warn('[tabs] setTimeout fallback scheduling failed:', e);
    }

    // Charger les données initiales (protégées)
    try { console.log('[init] loadTimeWindow'); loadTimeWindow(); } catch (e) { console.error('[init] loadTimeWindow failed', e); }
    // old loadPollingStatus removed
    try { console.log('[init] loadWebhookConfig'); loadWebhookConfig(); } catch (e) { console.error('[init] loadWebhookConfig failed', e); }
    try { console.log('[init] loadPollingConfig'); loadPollingConfig(); } catch (e) { console.error('[init] loadPollingConfig failed', e); }
    try { console.log('[init] loadWebhookLogs'); loadWebhookLogs(); } catch (e) { console.error('[init] loadWebhookLogs failed', e); }
    
    // Attacher les gestionnaires d'événements (avec garde)
    const elSaveTimeWindow = document.getElementById('saveTimeWindowBtn');
    elSaveTimeWindow && elSaveTimeWindow.addEventListener('click', saveTimeWindow);
    // old togglePollingBtn removed
    const elSaveConfig = document.getElementById('saveConfigBtn');
    elSaveConfig && elSaveConfig.addEventListener('click', saveWebhookConfig);
    const elRefreshLogs = document.getElementById('refreshLogsBtn');
    elRefreshLogs && elRefreshLogs.addEventListener('click', loadWebhookLogs);
    const elSavePollingCfg = document.getElementById('savePollingCfgBtn');
    // Removed from UI; keep guard in case of legacy DOM
    elSavePollingCfg && elSavePollingCfg.addEventListener('click', savePollingConfig);
    const addSenderBtn = document.getElementById('addSenderBtn');
    if (addSenderBtn) addSenderBtn.addEventListener('click', () => addEmailField(''));
    // Mettre à jour le statut vacances quand l'utilisateur change les dates
    // vacation inputs removed
    
    // Auto-refresh des logs toutes les 30 secondes
    setInterval(loadWebhookLogs, 30000);
    
    console.log('📊 Dashboard Webhooks initialisé.');

    // --- Préférences UI locales (localStorage) ---
    loadLocalPreferences();

    // --- Events: Filtres Email Avancés ---
    const excludeKeywords = document.getElementById('excludeKeywords');
    const attachmentDetectionToggle = document.getElementById('attachmentDetectionToggle');
    const maxEmailSizeMB = document.getElementById('maxEmailSizeMB');
    const senderPriority = document.getElementById('senderPriority');
    ;[excludeKeywords, attachmentDetectionToggle, maxEmailSizeMB, senderPriority]
      .forEach(el => el && el.addEventListener('change', saveLocalPreferences));

    // --- Events: Fiabilité ---
    const retryCount = document.getElementById('retryCount');
    const retryDelaySec = document.getElementById('retryDelaySec');
    const webhookTimeoutSec = document.getElementById('webhookTimeoutSec');
    const rateLimitPerHour = document.getElementById('rateLimitPerHour');
    const notifyOnFailureToggle = document.getElementById('notifyOnFailureToggle');
    ;[retryCount, retryDelaySec, webhookTimeoutSec, rateLimitPerHour, notifyOnFailureToggle]
      .forEach(el => el && el.addEventListener('change', saveLocalPreferences));

    // --- Events: Metrics ---
    const enableMetricsToggle = document.getElementById('enableMetricsToggle');
    if (enableMetricsToggle) {
        enableMetricsToggle.addEventListener('change', async () => {
            saveLocalPreferences();
            if (enableMetricsToggle.checked) {
                await computeAndRenderMetrics();
            } else {
                clearMetrics();
            }
        });
    }

    // --- Export / Import de configuration ---
    const exportBtn = document.getElementById('exportConfigBtn');
    const importBtn = document.getElementById('importConfigBtn');
    const importFile = document.getElementById('importConfigFile');
    exportBtn && exportBtn.addEventListener('click', exportFullConfiguration);
    importBtn && importBtn.addEventListener('click', () => importFile && importFile.click());
    importFile && importFile.addEventListener('change', handleImportConfigFile);

    // --- Outils de test --- 
    const validateWebhookUrlBtn = document.getElementById('validateWebhookUrlBtn');
    validateWebhookUrlBtn && validateWebhookUrlBtn.addEventListener('click', validateWebhookUrlFromInput);
    const buildPayloadPreviewBtn = document.getElementById('buildPayloadPreviewBtn');
    buildPayloadPreviewBtn && buildPayloadPreviewBtn.addEventListener('click', buildPayloadPreview);

    // --- Ouvrir une page de téléchargement (manuel) ---
    const openDownloadPageBtn = document.getElementById('openDownloadPageBtn');
    if (openDownloadPageBtn) {
        openDownloadPageBtn.addEventListener('click', () => {
            const msgId = 'openDownloadMsg';
            try {
                const input = document.getElementById('downloadPageUrl');
                const val = (input?.value || '').trim();
                if (!val) {
                    showMessage(msgId, 'Veuillez saisir une URL.', 'error');
                    return;
                }
                // Vérification basique HTTPS + domaine attendu (optionnelle, on reste permissif)
                let ok = false;
                try {
                    const u = new URL(val);
                    ok = (u.protocol === 'https:');
                } catch (_) {
                    ok = false;
                }
                if (!ok) {
                    showMessage(msgId, 'URL invalide. Utilisez un lien HTTPS.', 'error');
                    return;
                }
                window.open(val, '_blank', 'noopener');
                showMessage(msgId, 'Ouverture dans un nouvel onglet…', 'info');
            } catch (e) {
                showMessage(msgId, 'Impossible d’ouvrir l’URL.', 'error');
            }
        });
    }

    // --- Charger les préférences serveur au démarrage ---
    loadProcessingPrefsFromServer();

    // --- Sauvegarder préférences de traitement ---
    const processingPrefsSaveBtn = document.getElementById('processingPrefsSaveBtn');
    processingPrefsSaveBtn && processingPrefsSaveBtn.addEventListener('click', saveProcessingPrefsToServer);

    // --- Redémarrage serveur ---
    const restartBtn = document.getElementById('restartServerBtn');
    if (restartBtn) {
        restartBtn.addEventListener('click', async () => {
            const msgId = 'restartMsg';
            try {
                if (!confirm('Confirmez-vous le redémarrage du serveur ? L\'application sera indisponible quelques secondes.')) return;
                restartBtn.disabled = true;
                showMessage(msgId, 'Redémarrage en cours...', 'info');
                const res = await fetch('/api/restart_server', { method: 'POST' });
                const data = await res.json().catch(() => ({}));
                if (res.ok && data.success) {
                    showMessage(msgId, data.message || 'Redémarrage planifié.', 'success');
                    // Attendre un court délai puis tenter un reload
                    setTimeout(() => {
                        try { location.reload(); } catch {}
                    }, 3000);
                } else {
                    showMessage(msgId, data.message || 'Échec du redémarrage (vérifiez permissions sudoers).', 'error');
                }
            } catch (e) {
                showMessage(msgId, 'Erreur de communication avec le serveur.', 'error');
            } finally {
                restartBtn.disabled = false;
            }
        });
    }

    // --- Délégation de clic (fallback) pour .tab-btn ---
    document.addEventListener('click', (evt) => {
        const btn = evt.target && evt.target.closest && evt.target.closest('.tab-btn');
        if (!btn) return;
        const target = btn.getAttribute('data-target');
        console.log('[tabs-fallback] click captured on', target);
        if (!target) return;
        // Activer/désactiver manuellement sans dépendre d'initTabs
        try {
            const panels = Array.from(document.querySelectorAll('.section-panel'));
            panels.forEach(p => { p.classList.remove('active'); p.style.display = 'none'; });
            const panel = document.querySelector(target);
            if (panel) { panel.classList.add('active'); panel.style.display = 'block'; }
            const allBtns = Array.from(document.querySelectorAll('.tab-btn'));
            allBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // Mettre à jour le hash pour deep-linking
            const map = { '#sec-overview': '#overview', '#sec-webhooks': '#webhooks', '#sec-polling': '#make', '#sec-preferences': '#preferences', '#sec-tools': '#tools' };
            const hash = map[target]; if (hash) history.replaceState(null, '', hash);
        } catch (e) {
            console.error('[tabs-fallback] activation failed:', e);
        }
    });
});

// --- Gestionnaire du bouton d'enregistrement des préférences email ---
document.addEventListener('DOMContentLoaded', () => {
    const saveEmailPrefsBtn = document.getElementById('saveEmailPrefsBtn');
    if (saveEmailPrefsBtn) {
        saveEmailPrefsBtn.addEventListener('click', savePollingConfig);
    }
});

// --- Polling Config (jours, heures, dédup) ---

async function loadPollingConfig() {
    try {
        const res = await fetch('/api/get_polling_config');
        const data = await res.json();
        if (data.success) {
            const cfg = data.config || {};
            const dedupEl = document.getElementById('enableSubjectGroupDedup');
            if (dedupEl) dedupEl.checked = !!cfg.enable_subject_group_dedup;
            const senders = Array.isArray(cfg.sender_of_interest_for_polling) ? cfg.sender_of_interest_for_polling : [];
            renderSenderInputs(senders);
            // vacations and global enable removed from UI
        }
    } catch (e) {
        console.error('Erreur chargement config polling:', e);
    }
}

async function savePollingConfig() {
    const btn = document.getElementById('savePollingCfgBtn');
    const dedup = document.getElementById('enableSubjectGroupDedup')?.checked;
    const senders = collectSenderInputs();

    const payload = {};
    payload.enable_subject_group_dedup = dedup;

    payload.sender_of_interest_for_polling = senders;
    // Dates ISO (ou null)
    // vacations and global enable removed

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
            // Mettre à jour le message de statut
            showMessage('emailPrefsSaveStatus', data.message || 'Préférences enregistrées avec succès !', 'success');
        } else {
            showMessage('pollingCfgMsg', data.message || 'Erreur lors de la sauvegarde.', 'error');
        }
    } catch (e) {
        showMessage('pollingCfgMsg', 'Erreur de communication avec le serveur.', 'error');
    } finally {
        btn.disabled = false;
    }
}
