// static/dashboard.js
// Dashboard de contrôle des webhooks
window.DASHBOARD_BUILD = 'tabs-2025-10-05-15h29';
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    console.log('[build] static/dashboard.js loaded:', window.DASHBOARD_BUILD);
}

// Utilitaires
function showMessage(elementId, message, type) {
    const el = document.getElementById(elementId);
    if (!el) return; // Safe-guard: element may be absent in some contexts
    el.textContent = message;
    el.className = 'status-msg ' + type;
    setTimeout(() => {
        if (!el) return;
        el.className = 'status-msg';
    }, 5000);
}

// Client API centralisé pour la gestion des erreurs
class ApiClient {
    static async handleResponse(res) {
        if (res.status === 401) {
            window.location.href = '/login';
            throw new Error('Session expirée');
        }
        if (res.status === 403) {
            throw new Error('Accès refusé');
        }
        if (res.status >= 500) {
            throw new Error('Erreur serveur');
        }
        return res;
    }
    
    static async request(url, options = {}) {
        const res = await fetch(url, options);
        return ApiClient.handleResponse(res);
    }
}


async function generateMagicLink() {
    const btn = document.getElementById('generateMagicLinkBtn');
    const output = document.getElementById('magicLinkOutput');
    const unlimitedToggle = document.getElementById('magicLinkUnlimitedToggle');
    if (!btn || !output) return;
    output.textContent = '';
    try {
        btn.disabled = true;
        const payload = unlimitedToggle && unlimitedToggle.checked ? { unlimited: true } : {};
        const res = await ApiClient.request('/api/auth/magic-link', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (res.status === 401) {
            output.textContent = "Session expirée. Merci de vous reconnecter.";
            output.className = 'status-msg error';
            return;
        }
        if (!data.success || !data.magic_link) {
            output.textContent = data.message || 'Impossible de générer le magic link.';
            output.className = 'status-msg error';
            return;
        }
        const expiresText = data.unlimited ? 'aucune expiration' : (data.expires_at || 'bientôt');
        output.textContent = data.magic_link + ' (exp. ' + expiresText + ')';
        output.className = 'status-msg success';
        try {
            await navigator.clipboard.writeText(data.magic_link);
            output.textContent += ' — Copié dans le presse-papiers';
        } catch (clipErr) {
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                console.warn('Clipboard write failed', clipErr);
            }
        }
    } catch (e) {
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.error('generateMagicLink error', e);
        }
        output.textContent = 'Erreur de génération du magic link.';
        output.className = 'status-msg error';
    } finally {
        if (btn) btn.disabled = false;
        setTimeout(() => {
            if (output) output.className = 'status-msg';
        }, 7000);
    }
}

// -------------------- Runtime Flags (Debug) --------------------
async function loadRuntimeFlags() {
    try {
        const res = await ApiClient.request('/api/get_runtime_flags');
        const data = await res.json();
        if (!data.success || !data.flags) return;
        const f = data.flags;
        const dedupToggle = document.getElementById('disableEmailIdDedupToggle');
        const allowCustomToggle = document.getElementById('allowCustomWithoutLinksToggle');
        if (dedupToggle) dedupToggle.checked = !!f.disable_email_id_dedup;
        if (allowCustomToggle) allowCustomToggle.checked = !!f.allow_custom_webhook_without_links;
    } catch (e) {
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.warn('loadRuntimeFlags error', e);
        }
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
        const res = await ApiClient.request('/api/update_runtime_flags', {
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
    initMagicLinkTools();

    // Buttons
    const rfBtn = document.getElementById('runtimeFlagsSaveBtn');
    if (rfBtn) rfBtn.addEventListener('click', saveRuntimeFlags);
});


function initMagicLinkTools() {
    const btn = document.getElementById('generateMagicLinkBtn');
    if (btn) {
        btn.addEventListener('click', generateMagicLink);
    }
}

// --- Processing Prefs (server) ---
async function loadProcessingPrefsFromServer() {
    try {
        const res = await ApiClient.request('/api/get_processing_prefs');
        if (!res.ok) { 
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                console.warn('loadProcessingPrefsFromServer: non-200', res.status);
            }
            return; 
        }
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
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.warn('loadProcessingPrefsFromServer error', e);
        }
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

        const res = await ApiClient.request('/api/update_processing_prefs', {
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
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.warn('Prefs load error', e);
        }
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
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.warn('Prefs save error', e);
        }
    }
}

async function computeAndRenderMetrics() {
    try {
        const res = await ApiClient.request('/api/webhook_logs?days=1');
        if (!res.ok) { 
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                console.warn('metrics: non-200', res.status);
            }
            clearMetrics(); return; 
        }
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
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.warn('metrics error', e);
        }
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
        const [webhookCfgRes, timeWinRes] = await Promise.all([
            ApiClient.request('/api/webhooks/config'),
            ApiClient.request('/api/get_webhook_time_window')
        ]);
        const [webhookCfg, timeWin] = await Promise.all([
            webhookCfgRes.json(), timeWinRes.json()
        ]);
        const prefsRaw = localStorage.getItem('dashboard_prefs_v1');
        const exportObj = {
            exported_at: new Date().toISOString(),
            webhook_config: webhookCfg,
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
        if (typeof cfg.webhook_ssl_verify === 'boolean') payload.webhook_ssl_verify = cfg.webhook_ssl_verify;
        if (Object.keys(payload).length) {
            await ApiClient.request('/api/webhooks/config', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
            });
            await loadWebhookConfig();
        }
    }
    // polling config removed
    // time window
    if (obj?.time_window) {
        const start = obj.time_window.webhooks_time_start ?? '';
        const end = obj.time_window.webhooks_time_end ?? '';
        await ApiClient.request('/api/set_webhook_time_window', {
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
        const res = await ApiClient.request('/api/get_webhook_time_window');
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
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.error('Erreur chargement fenêtre horaire:', e);
        }
    }
}

async function saveTimeWindow() {
    const start = document.getElementById('webhooksTimeStart').value.trim();
    const end = document.getElementById('webhooksTimeEnd').value.trim();
    
    try {
        const res = await ApiClient.request('/api/set_webhook_time_window', {
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


// Section 3: Configuration des webhooks
async function loadWebhookConfig() {
    try {
        const res = await ApiClient.request('/api/webhooks/config');
        const data = await res.json();
        
        if (data.success) {
            const config = data.config;
            
            // Afficher les valeurs (masquées partiellement pour sécurité)
            const wh = document.getElementById('webhookUrl');
            if (wh) wh.placeholder = config.webhook_url || 'Non configuré';
            
            const ssl = document.getElementById('sslVerifyToggle');
            if (ssl) ssl.checked = !!config.webhook_ssl_verify;
            const sending = document.getElementById('webhookSendingToggle');
            if (sending) sending.checked = !!config.webhook_sending_enabled;
            
            // Absence pause
            const absenceToggle = document.getElementById('absencePauseToggle');
            if (absenceToggle) absenceToggle.checked = !!config.absence_pause_enabled;
            
            // Jours d'absence pause
            const absenceDays = Array.isArray(config.absence_pause_days) ? config.absence_pause_days : [];
            const dayCheckboxes = document.querySelectorAll('input[name="absencePauseDay"]');
            dayCheckboxes.forEach(cb => {
                cb.checked = absenceDays.includes(cb.value);
            });
            
            // Charger la fenêtre horaire dédiée
            await loadGlobalWebhookTimeWindow();
        }
    } catch (e) {
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.error('Erreur chargement config webhooks:', e);
        }
    }
}

// Charge la fenêtre horaire dédiée aux webhooks
async function loadGlobalWebhookTimeWindow() {
    try {
        const res = await ApiClient.request('/api/webhooks/time-window');
        const data = await res.json();
        if (!data.success) return;

        const startEl = document.getElementById('globalWebhookTimeStart');
        const endEl = document.getElementById('globalWebhookTimeEnd');
        
        if (startEl) startEl.value = data.webhooks_time_start || '';
        if (endEl) endEl.value = data.webhooks_time_end || '';
        
        // Mettre à jour l'affichage
        renderGlobalWebhookTimeWindowDisplay(data.webhooks_time_start, data.webhooks_time_end);
    } catch (e) {
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.error('Erreur chargement fenêtre horaire webhooks:', e);
        }
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
        
        const res = await ApiClient.request('/api/webhooks/time-window', {
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
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.error('Erreur sauvegarde fenêtre horaire webhooks:', e);
        }
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
    const sslEl = document.getElementById('sslVerifyToggle');
    const sendingEl = document.getElementById('webhookSendingToggle');
    const absenceToggle = document.getElementById('absencePauseToggle');
    
    const webhookUrl = (webhookUrlEl?.value || '').trim();
    
    // Validation: bloquer l'envoi si le champ est vide ou contient uniquement le placeholder
    if (webhookUrl) {
        // Vérifier que ce n'est pas le placeholder masqué
        const placeholder = webhookUrlEl?.placeholder || '';
        if (webhookUrl === placeholder || webhookUrl === 'Non configuré') {
            showMessage('configMsg', 'Veuillez saisir une URL webhook valide.', 'error');
            return;
        }
        payload.webhook_url = webhookUrl;
    }
    
    if (sslEl) payload.webhook_ssl_verify = !!sslEl.checked;
    if (sendingEl) payload.webhook_sending_enabled = !!sendingEl.checked;
    
    // Absence pause
    if (absenceToggle) {
        payload.absence_pause_enabled = !!absenceToggle.checked;
        
        // Collecter les jours sélectionnés
        const selectedDays = [];
        const dayCheckboxes = document.querySelectorAll('input[name="absencePauseDay"]:checked');
        dayCheckboxes.forEach(cb => selectedDays.push(cb.value));
        payload.absence_pause_days = selectedDays;
        
        // Validation: si le toggle est activé, au moins un jour doit être sélectionné
        if (absenceToggle.checked && selectedDays.length === 0) {
            showMessage('configMsg', 'Au moins un jour doit être sélectionné pour activer l\'absence.', 'error');
            return;
        }
    }
    
    try {
        const res = await ApiClient.request('/api/webhooks/config', {
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
        const res = await ApiClient.request('/api/webhook_logs?days=7');
        const data = await res.json();
        
        if (data.success && data.logs && data.logs.length > 0) {
            logsContainer.innerHTML = '';
            
            data.logs.forEach(log => {
                const logEntry = document.createElement('div');
                logEntry.className = 'log-entry ' + log.status;
                
                const timeDiv = document.createElement('div');
                timeDiv.className = 'log-entry-time';
                timeDiv.textContent = formatTimestamp(log.timestamp);
                logEntry.appendChild(timeDiv);
                
                const typeSpan = document.createElement('span');
                typeSpan.className = 'log-entry-type ' + (log.type === 'custom' ? 'custom' : 'makecom');
                typeSpan.textContent = log.type === 'custom' ? 'CUSTOM' : 'MAKE.COM';
                logEntry.appendChild(typeSpan);
                
                const statusStrong = document.createElement('strong');
                statusStrong.textContent = log.status === 'success' ? '✅ Succès' : '❌ Erreur';
                logEntry.appendChild(statusStrong);
                
                if (log.subject) {
                    const subjectDiv = document.createElement('div');
                    subjectDiv.textContent = 'Sujet: ' + log.subject;
                    logEntry.appendChild(subjectDiv);
                }
                
                if (log.target_url) {
                    const urlDiv = document.createElement('div');
                    urlDiv.textContent = 'URL: ' + log.target_url;
                    logEntry.appendChild(urlDiv);
                }
                
                if (log.status_code) {
                    const statusDiv = document.createElement('div');
                    statusDiv.textContent = 'Code HTTP: ' + log.status_code;
                    logEntry.appendChild(statusDiv);
                }
                
                if (log.error) {
                    const errorDiv = document.createElement('div');
                    errorDiv.style.color = 'var(--cork-danger)';
                    errorDiv.style.marginTop = '5px';
                    errorDiv.textContent = 'Erreur: ' + log.error;
                    logEntry.appendChild(errorDiv);
                }
                
                if (log.email_id) {
                    const emailIdDiv = document.createElement('div');
                    emailIdDiv.style.fontSize = '0.8em';
                    emailIdDiv.style.color = 'var(--cork-text-secondary)';
                    emailIdDiv.style.marginTop = '5px';
                    emailIdDiv.textContent = 'Email ID: ' + log.email_id;
                    logEntry.appendChild(emailIdDiv);
                }
                
                logsContainer.appendChild(logEntry);
            });
        } else {
            logsContainer.innerHTML = '<div class="log-empty">Aucun log webhook trouvé pour les 7 derniers jours.</div>';
        }
    } catch (e) {
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.error('Erreur chargement logs:', e);
        }
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
    if (window.__tabsInitialized) { 
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.log('[tabs] initTabs: already initialized');
        }
        return; 
    }
    window.__tabsInitialized = true;
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        console.log('[tabs] initTabs: starting');
    }
    const tabButtons = Array.from(document.querySelectorAll('.tab-btn'));
    const panels = Array.from(document.querySelectorAll('.section-panel'));
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        console.log(`[tabs] found buttons=${tabButtons.length}, panels=${panels.length}`);
    }

    const mapHashToId = {
        '#overview': '#sec-overview',
        '#webhooks': '#sec-webhooks',
        '#preferences': '#sec-preferences',
        '#tools': '#sec-tools',
    };

    function activate(targetSelector) {
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.log('[tabs] activate called for target:', targetSelector);
        }
        // Toggle active class on panels
        panels.forEach(p => { p.classList.remove('active'); p.style.display = 'none'; });
        const panel = document.querySelector(targetSelector);
        if (panel) {
            panel.classList.add('active');
            panel.style.display = 'block';
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                console.log('[tabs] panel activated:', panel.id);
            }
        } else {
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                console.warn('[tabs] panel not found for selector:', targetSelector);
            }
        }

        // Toggle active class on buttons
        tabButtons.forEach(btn => btn.classList.remove('active'));
        const btn = tabButtons.find(b => b.getAttribute('data-target') === targetSelector);
        if (btn) {
            btn.classList.add('active');
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                console.log('[tabs] button activated (data-target):', targetSelector);
            }
        } else {
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                console.warn('[tabs] button not found for selector:', targetSelector);
            }
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
        }
    }

    // Wire click handlers
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-target');
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                console.log('[tabs] click on tab-btn, target=', target);
            }
            if (target) {
                // Update URL hash for deep-linking (without scrolling)
                // Prefer canonical hash for the target
                const preferred = (target === '#sec-overview') ? '#overview' :
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
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        console.log('[tabs] initialHash=', initialHash, ' -> initialTarget=', initialTarget);
    }
    activate(initialTarget);

    // React to hash changes (e.g., manual URL edit)
    window.addEventListener('hashchange', () => {
        const t = mapHashToId[window.location.hash];
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            console.log('[tabs] hashchange ->', window.location.hash, ' mapped to ', t);
        }
        if (t) activate(t);
    });
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        console.log('[tabs] initTabs: ready');
    }
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
    try { console.log('[init] loadWebhookLogs'); loadWebhookLogs(); } catch (e) { console.error('[init] loadWebhookLogs failed', e); }
    
    // Attacher les gestionnaires d'événements (avec garde)
    const elSaveTimeWindow = document.getElementById('saveTimeWindowBtn');
    elSaveTimeWindow && elSaveTimeWindow.addEventListener('click', saveTimeWindow);
    // old togglePollingBtn removed
    const elSaveConfig = document.getElementById('saveConfigBtn');
    elSaveConfig && elSaveConfig.addEventListener('click', saveWebhookConfig);
    const elRefreshLogs = document.getElementById('refreshLogsBtn');
    elRefreshLogs && elRefreshLogs.addEventListener('click', loadWebhookLogs);
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

    // --- Déploiement application ---
    const restartBtn = document.getElementById('restartServerBtn');
    if (restartBtn) {
        restartBtn.addEventListener('click', async () => {
            const msgId = 'restartMsg';
            try {
                if (!confirm('Confirmez-vous le déploiement de l\'application ? Elle peut être indisponible quelques secondes.')) return;
                restartBtn.disabled = true;
                showMessage(msgId, 'Déploiement en cours...', 'info');
                const res = await ApiClient.request('/api/deploy_application', { method: 'POST' });
                const data = await res.json().catch(() => ({}));
                if (res.ok && data.success) {
                    showMessage(msgId, data.message || 'Déploiement planifié. Vérification de disponibilité…', 'success');
                    // Poll health endpoint jusqu'à disponibilité puis recharger
                    try {
                        await pollHealthCheck({ attempts: 10, intervalMs: 1500, timeoutMs: 25000 });
                        try { location.reload(); } catch {}
                    } catch (e) {
                        // Si la vérification échoue, proposer un rechargement manuel
                        showMessage(msgId, 'Le service ne répond pas encore. Réessayez plus tard ou rechargez la page.', 'error');
                    }
                } else {
                    showMessage(msgId, data.message || 'Échec du déploiement (vérifiez permissions sudoers).', 'error');
                }
            } catch (e) {
                showMessage(msgId, 'Erreur de communication avec le serveur.', 'error');
            } finally {
                restartBtn.disabled = false;
            }
        });
    }

    /**
     * Vérifie la disponibilité du serveur en appelant /health à intervalles réguliers.
     * @param {{attempts:number, intervalMs:number, timeoutMs:number}} opts
     */
    async function pollHealthCheck(opts) {
        const attempts = Math.max(1, Number(opts?.attempts || 8));
        const intervalMs = Math.max(250, Number(opts?.intervalMs || 1000));
        const timeoutMs = Math.max(intervalMs, Number(opts?.timeoutMs || 15000));

        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), timeoutMs);
        try {
            for (let i = 0; i < attempts; i++) {
                try {
                    const res = await ApiClient.request('/health', { signal: controller.signal, cache: 'no-store' });
                    if (res.ok) {
                        clearTimeout(id);
                        return true;
                    }
                } catch (_) { /* service peut être indisponible pendant le reload */ }
                await new Promise(r => setTimeout(r, intervalMs));
            }
            throw new Error('healthcheck failed');
        } finally {
            clearTimeout(id);
        }
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
            const map = { '#sec-overview': '#overview', '#sec-webhooks': '#webhooks', '#sec-preferences': '#preferences', '#sec-tools': '#tools' };
            const hash = map[target]; if (hash) history.replaceState(null, '', hash);
        } catch (e) {
            console.error('[tabs-fallback] activation failed:', e);
        }
    });
});


