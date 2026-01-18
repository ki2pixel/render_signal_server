// static/dashboard.js
// Dashboard de contrôle des webhooks - Version modulaire
import { ApiService } from './services/ApiService.js';
import { WebhookService } from './services/WebhookService.js';
import { LogService } from './services/LogService.js';
import { MessageHelper } from './utils/MessageHelper.js';
import { TabManager } from './components/TabManager.js';

window.DASHBOARD_BUILD = 'modular-2026-01-18';

console.log('[build] static/dashboard.js loaded:', window.DASHBOARD_BUILD);

// Variables globales pour le gestionnaire d'onglets
let tabManager = null;

// -------------------- Initialisation --------------------
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Initialiser le gestionnaire d'onglets
        tabManager = new TabManager();
        tabManager.init();
        tabManager.enhanceAccessibility();
        
        // Initialiser les services
        await initializeServices();
        
        // Lier les événements
        bindEvents();
        
        // Charger les données initiales
        await loadInitialData();
        
        // Démarrer le polling des logs
        LogService.startLogPolling();
        
        console.log('Dashboard initialisé avec succès');
    } catch (e) {
        console.error('Erreur lors de l\'initialisation du dashboard:', e);
        MessageHelper.showError('global', 'Erreur lors du chargement du dashboard');
    }
});

/**
 * Initialise les services nécessaires
 */
async function initializeServices() {
    // Les services sont déjà importés, pas besoin d'initialisation supplémentaire
    // On pourrait ajouter des configurations globales ici si nécessaire
}

/**
 * Lie les événements aux éléments DOM
 */
function bindEvents() {
    // Magic Link
    const magicLinkBtn = document.getElementById('generateMagicLinkBtn');
    if (magicLinkBtn) {
        magicLinkBtn.addEventListener('click', generateMagicLink);
    }
    
    // Configuration webhooks
    const saveWebhookBtn = document.getElementById('saveConfigBtn');
    if (saveWebhookBtn) {
        saveWebhookBtn.addEventListener('click', () => WebhookService.saveConfig());
    }
    
    // Préférences email (polling config)
    const saveEmailPrefsBtn = document.getElementById('saveEmailPrefsBtn');
    if (saveEmailPrefsBtn) {
        saveEmailPrefsBtn.addEventListener('click', savePollingConfig);
    }
    
    // Logs
    const clearLogsBtn = document.getElementById('clearLogsBtn');
    if (clearLogsBtn) {
        clearLogsBtn.addEventListener('click', () => LogService.clearLogs());
    }
    
    const exportLogsBtn = document.getElementById('exportLogsBtn');
    if (exportLogsBtn) {
        exportLogsBtn.addEventListener('click', () => LogService.exportLogs());
    }
    
    // Périodes de logs
    const logPeriodSelect = document.getElementById('logPeriodSelect');
    if (logPeriodSelect) {
        logPeriodSelect.addEventListener('change', (e) => {
            LogService.changeLogPeriod(parseInt(e.target.value));
        });
    }
    
    // Polling
    const pollingToggle = document.getElementById('pollingToggle');
    if (pollingToggle) {
        pollingToggle.addEventListener('change', togglePolling);
    }
    
    // Time window
    const saveTimeWindowBtn = document.getElementById('saveTimeWindowBtn');
    if (saveTimeWindowBtn) {
        saveTimeWindowBtn.addEventListener('click', saveTimeWindow);
    }
    
    // Global webhook time window
    const saveGlobalWebhookTimeBtn = document.getElementById('saveGlobalWebhookTimeBtn');
    if (saveGlobalWebhookTimeBtn) {
        saveGlobalWebhookTimeBtn.addEventListener('click', saveGlobalWebhookTimeWindow);
    }
    
    // Polling config
    const savePollingConfigBtn = document.getElementById('savePollingCfgBtn');
    if (savePollingConfigBtn) {
        savePollingConfigBtn.addEventListener('click', savePollingConfig);
    }
    
    // Runtime flags
    const saveRuntimeFlagsBtn = document.getElementById('runtimeFlagsSaveBtn');
    if (saveRuntimeFlagsBtn) {
        saveRuntimeFlagsBtn.addEventListener('click', saveRuntimeFlags);
    }
    
    // Processing prefs
    const saveProcessingPrefsBtn = document.getElementById('processingPrefsSaveBtn');
    if (saveProcessingPrefsBtn) {
        saveProcessingPrefsBtn.addEventListener('click', saveProcessingPrefsToServer);
    }
    
    // Config management
    const exportConfigBtn = document.getElementById('exportConfigBtn');
    if (exportConfigBtn) {
        exportConfigBtn.addEventListener('click', exportAllConfig);
    }
    
    const importConfigInput = document.getElementById('importConfigInput');
    if (importConfigInput) {
        importConfigInput.addEventListener('change', handleImportConfigFile);
    }
    
    // Validation URL webhook
    const testWebhookUrl = document.getElementById('testWebhookUrl');
    if (testWebhookUrl) {
        testWebhookUrl.addEventListener('input', validateWebhookUrlFromInput);
    }
    
    // Preview payload
    const previewInputs = ['previewSubject', 'previewSender', 'previewBody'];
    previewInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', buildPayloadPreview);
        }
    });
    
    // Email fields management
    const addEmailBtn = document.getElementById('addEmailBtn');
    if (addEmailBtn) {
        addEmailBtn.addEventListener('click', () => addEmailField(''));
    }
}

/**
 * Charge les données initiales
 */
async function loadInitialData() {
    console.log('[loadInitialData] Function called - hostname:', window.location.hostname);
    
    try {
        // Charger en parallèle les données initiales
        await Promise.all([
            WebhookService.loadConfig(),
            loadPollingStatus(),
            loadTimeWindow(),
            loadPollingConfig(),
            loadRuntimeFlags(),
            loadProcessingPrefsFromServer(),
            loadLocalPreferences()
        ]);
        
        // Charger la fenêtre horaire webhook globale après les autres
        await loadGlobalWebhookTimeWindow();
        
        // Charger les logs après les autres données
        await LogService.loadAndRenderLogs();
        
    } catch (e) {
        console.error('Erreur lors du chargement des données initiales:', e);
    }
}

// -------------------- Magic Links --------------------
async function generateMagicLink() {
    const btn = document.getElementById('generateMagicLinkBtn');
    const output = document.getElementById('magicLinkOutput');
    const unlimitedToggle = document.getElementById('magicLinkUnlimitedToggle');
    
    if (!btn || !output) return;
    
    output.textContent = '';
    MessageHelper.setButtonLoading(btn, true);
    
    try {
        const unlimited = unlimitedToggle?.checked ?? false;
        const data = await ApiService.post('/api/auth/magic-link', { unlimited });
        
        if (data.success && data.magic_link) {
            const expiresText = data.unlimited ? 'aucune expiration' : (data.expires_at || 'bientôt');
            output.textContent = `${data.magic_link} (exp. ${expiresText})`;
            output.className = 'status-msg success';
            
            try {
                await navigator.clipboard.writeText(data.magic_link);
                output.textContent += ' — Copié dans le presse-papiers';
            } catch (clipboardError) {
                // Silently fail clipboard copy
            }
        } else {
            output.textContent = data.message || 'Impossible de générer le magic link.';
            output.className = 'status-msg error';
        }
    } catch (e) {
        console.error('generateMagicLink error', e);
        output.textContent = 'Erreur de génération du magic link.';
        output.className = 'status-msg error';
    } finally {
        MessageHelper.setButtonLoading(btn, false);
        setTimeout(() => {
            if (output) output.className = 'status-msg';
        }, 7000);
    }
}

// -------------------- Polling Control --------------------
async function loadPollingStatus() {
    try {
        const data = await ApiService.get('/api/webhooks/config');
        
        if (data.success) {
            const isEnabled = data.config.polling_enabled;
            const toggle = document.getElementById('pollingToggle');
            const statusText = document.getElementById('pollingStatusText');
            
            if (toggle) toggle.checked = isEnabled;
            if (statusText) {
                statusText.textContent = isEnabled ? '✅ Polling activé' : '❌ Polling désactivé';
            }
        }
    } catch (e) {
        console.error('Erreur chargement statut polling:', e);
        const statusText = document.getElementById('pollingStatusText');
        if (statusText) statusText.textContent = '⚠️ Erreur de chargement';
    }
}

async function togglePolling() {
    const enable = document.getElementById('pollingToggle').checked;
    
    try {
        const data = await ApiService.post('/api/toggle_polling', { enable });
        
        if (data.success) {
            MessageHelper.showInfo('pollingMsg', data.message);
            const statusText = document.getElementById('pollingStatusText');
            if (statusText) {
                statusText.textContent = enable ? '✅ Polling activé' : '❌ Polling désactivé';
            }
        } else {
            MessageHelper.showError('pollingMsg', data.message || 'Erreur lors du changement.');
        }
    } catch (e) {
        MessageHelper.showError('pollingMsg', 'Erreur de communication avec le serveur.');
    }
}

// -------------------- Time Window --------------------
async function loadTimeWindow() {
    console.log('[loadTimeWindow] Function called - hostname:', window.location.hostname);
    
    const applyWindowValues = (startValue = '', endValue = '') => {
        const startInput = document.getElementById('webhooksTimeStart');
        const endInput = document.getElementById('webhooksTimeEnd');
        console.log('[loadTimeWindow] Applying values:', { startValue, endValue, startInput: !!startInput, endInput: !!endInput });
        if (startInput) startInput.value = startValue || '';
        if (endInput) endInput.value = endValue || '';
        renderTimeWindowDisplay(startValue || '', endValue || '');
    };
    
    try {
        // 0) Source principale : configuration webhooks persistée
        const configResponse = await ApiService.get('/api/webhooks/config');
        console.log('[loadTimeWindow] /api/webhooks/config response:', configResponse);
        if (configResponse.success && configResponse.config) {
            const cfg = configResponse.config;
            if (cfg.global_time_start || cfg.global_time_end) {
                applyWindowValues(cfg.global_time_start || '', cfg.global_time_end || '');
                return;
            }
        }
    } catch (e) {
        console.warn('Impossible de charger la fenêtre horaire via /api/webhooks/config:', e);
    }
    
    try {
        // 1) Préférence: configuration persistée (webhook config service)
        const persisted = await ApiService.get('/api/webhooks/time-window');
        console.log('[loadTimeWindow] /api/webhooks/time-window response:', persisted);
        if (persisted.success && (persisted.webhooks_time_start || persisted.webhooks_time_end)) {
            applyWindowValues(persisted.webhooks_time_start, persisted.webhooks_time_end);
            return;
        }
    } catch (e) {
        console.warn('Impossible de charger la fenêtre horaire via /api/webhooks/time-window:', e);
    }
    
    try {
        // 2) Fallback: ancienne source (time window override)
        const data = await ApiService.get('/api/get_webhook_time_window');
        console.log('[loadTimeWindow] /api/get_webhook_time_window response:', data);
        if (data.success) {
            applyWindowValues(data.webhooks_time_start, data.webhooks_time_end);
        }
    } catch (e) {
        console.error('Erreur chargement fenêtre horaire (fallback):', e);
    }
}

async function saveTimeWindow() {
    const startInput = document.getElementById('webhooksTimeStart');
    const endInput = document.getElementById('webhooksTimeEnd');
    const start = startInput.value.trim();
    const end = endInput.value.trim();
    
    // Validation des formats
    if (start && !MessageHelper.isValidTimeFormat(start)) {
        MessageHelper.showError('timeWindowMsg', 'Format d\'heure invalide (ex: 09:30 ou 9h30).');
        return;
    }
    
    if (end && !MessageHelper.isValidTimeFormat(end)) {
        MessageHelper.showError('timeWindowMsg', 'Format d\'heure invalide (ex: 17:30 ou 17h30).');
        return;
    }
    
    // Normalisation des formats
    const normalizedStart = start ? MessageHelper.normalizeTimeFormat(start) : '';
    const normalizedEnd = end ? MessageHelper.normalizeTimeFormat(end) : '';
    
    try {
        const data = await ApiService.post('/api/webhooks/time-window', { 
            start: normalizedStart, 
            end: normalizedEnd 
        });
        
        if (data.success) {
            MessageHelper.showSuccess('timeWindowMsg', 'Fenêtre horaire enregistrée avec succès !');
            
            // Mettre à jour les inputs selon la normalisation renvoyée par le backend
            if (startInput && Object.prototype.hasOwnProperty.call(data, 'webhooks_time_start')) {
                startInput.value = data.webhooks_time_start || '';
            }
            if (endInput && Object.prototype.hasOwnProperty.call(data, 'webhooks_time_end')) {
                endInput.value = data.webhooks_time_end || '';
            }
            
            renderTimeWindowDisplay(data.webhooks_time_start || normalizedStart, data.webhooks_time_end || normalizedEnd);
            
            // S'assurer que la source persistée est rechargée
            await loadTimeWindow();
        } else {
            MessageHelper.showError('timeWindowMsg', data.message || 'Erreur lors de la sauvegarde.');
        }
    } catch (e) {
        MessageHelper.showError('timeWindowMsg', 'Erreur de communication avec le serveur.');
    }
}

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

// -------------------- Polling Configuration --------------------
async function loadPollingConfig() {
    try {
        const data = await ApiService.get('/api/get_polling_config');
        
        if (data.success) {
            const cfg = data.config || {};
            
            // Déduplication
            const dedupEl = document.getElementById('enableSubjectGroupDedup');
            if (dedupEl) dedupEl.checked = !!cfg.enable_subject_group_dedup;
            
            // Senders
            const senders = Array.isArray(cfg.sender_of_interest_for_polling) ? cfg.sender_of_interest_for_polling : [];
            renderSenderInputs(senders);
            
            // Active days and hours
            try {
                if (Array.isArray(cfg.active_days)) setDayCheckboxes(cfg.active_days);
                
                const sh = document.getElementById('pollingStartHour');
                const eh = document.getElementById('pollingEndHour');
                if (sh && Number.isInteger(cfg.active_start_hour)) sh.value = String(cfg.active_start_hour);
                if (eh && Number.isInteger(cfg.active_end_hour)) eh.value = String(cfg.active_end_hour);
            } catch (e) {
                console.warn('loadPollingConfig: applying days/hours failed', e);
            }
        }
    } catch (e) {
        console.error('Erreur chargement config polling:', e);
    }
}

async function savePollingConfig(event) {
    const btn = event?.target || document.getElementById('savePollingCfgBtn');
    if (btn) btn.disabled = true;
    
    const dedup = document.getElementById('enableSubjectGroupDedup')?.checked;
    const senders = collectSenderInputs();
    const activeDays = collectDayCheckboxes();
    const startHourStr = document.getElementById('pollingStartHour')?.value?.trim() ?? '';
    const endHourStr = document.getElementById('pollingEndHour')?.value?.trim() ?? '';
    const statusId = document.getElementById('emailPrefsSaveStatus') ? 'emailPrefsSaveStatus' : 'pollingCfgMsg';

    // Validation
    const startHour = startHourStr === '' ? null : Number.parseInt(startHourStr, 10);
    const endHour = endHourStr === '' ? null : Number.parseInt(endHourStr, 10);
    
    if (!activeDays || activeDays.length === 0) {
        MessageHelper.showError(statusId, 'Veuillez sélectionner au moins un jour actif.');
        if (btn) btn.disabled = false;
        return;
    }
    
    if (startHour === null || Number.isNaN(startHour) || startHour < 0 || startHour > 23) {
        MessageHelper.showError(statusId, 'Heure de début invalide (0-23).');
        if (btn) btn.disabled = false;
        return;
    }
    
    if (endHour === null || Number.isNaN(endHour) || endHour < 0 || endHour > 23) {
        MessageHelper.showError(statusId, 'Heure de fin invalide (0-23).');
        if (btn) btn.disabled = false;
        return;
    }
    
    if (startHour === endHour) {
        MessageHelper.showError(statusId, 'L\'heure de début et de fin ne peuvent pas être identiques.');
        if (btn) btn.disabled = false;
        return;
    }

    const payload = {
        enable_subject_group_dedup: dedup,
        sender_of_interest_for_polling: senders,
        active_days: activeDays,
        active_start_hour: startHour,
        active_end_hour: endHour
    };

    try {
        const data = await ApiService.post('/api/update_polling_config', payload);
        
        if (data.success) {
            MessageHelper.showSuccess(statusId, data.message || 'Préférences enregistrées avec succès !');
            await loadPollingConfig();
        } else {
            MessageHelper.showError(statusId, data.message || 'Erreur lors de la sauvegarde.');
        }
    } catch (e) {
        MessageHelper.showError(statusId, 'Erreur de communication avec le serveur.');
    } finally {
        if (btn) btn.disabled = false;
    }
}

// -------------------- Runtime Flags --------------------
async function loadRuntimeFlags() {
    try {
        const data = await ApiService.get('/api/get_runtime_flags');
        
        if (data.success) {
            const flags = data.flags || {};
            
            // Appliquer les flags aux éléments UI
            Object.keys(flags).forEach(flagKey => {
                const el = document.getElementById(flagKey);
                if (el) {
                    if (el.type === 'checkbox') {
                        el.checked = flags[flagKey];
                    } else {
                        el.value = flags[flagKey];
                    }
                }
            });
        }
    } catch (e) {
        console.error('loadRuntimeFlags error', e);
    }
}

async function saveRuntimeFlags() {
    const msgId = 'runtimeFlagsMsg';
    const btn = document.getElementById('runtimeFlagsSaveBtn');
    
    MessageHelper.setButtonLoading(btn, true);
    
    try {
        // Collecter tous les flags depuis les éléments UI
        const flags = {};
        const flagElements = document.querySelectorAll('[id^="flag_"], [id$="_flag"]');
        
        flagElements.forEach(el => {
            const flagName = el.id.replace(/^flag_/, '').replace(/_flag$/, '');
            if (el.type === 'checkbox') {
                flags[flagName] = el.checked;
            } else {
                flags[flagName] = el.value;
            }
        });
        
        const data = await ApiService.post('/api/set_runtime_flags', { flags });
        
        if (data.success) {
            MessageHelper.showSuccess(msgId, 'Flags de débogage enregistrés avec succès !');
        } else {
            MessageHelper.showError(msgId, data.message || 'Erreur lors de la sauvegarde.');
        }
    } catch (e) {
        MessageHelper.showError(msgId, 'Erreur de communication avec le serveur.');
    } finally {
        MessageHelper.setButtonLoading(btn, false);
    }
}

// -------------------- Processing Preferences --------------------
async function loadProcessingPrefsFromServer() {
    try {
        const data = await ApiService.get('/api/get_processing_prefs');
        
        if (data.success) {
            const prefs = data.prefs || {};
            
            // Appliquer les préférences aux éléments UI
            Object.keys(prefs).forEach(prefKey => {
                const el = document.getElementById(prefKey);
                if (el) {
                    if (el.type === 'checkbox') {
                        el.checked = prefs[prefKey];
                    } else {
                        el.value = prefs[prefKey];
                    }
                }
            });
        }
    } catch (e) {
        console.error('loadProcessingPrefs error', e);
    }
}

async function saveProcessingPrefsToServer() {
    const btn = document.getElementById('processingPrefsSaveBtn');
    const msgId = 'processingPrefsMsg';
    
    MessageHelper.setButtonLoading(btn, true);
    
    try {
        // Collecter toutes les préférences depuis les éléments UI
        const prefs = {};
        const prefElements = document.querySelectorAll('[id^="pref_"], [id$="_pref"]');
        
        prefElements.forEach(el => {
            const prefName = el.id.replace(/^pref_/, '').replace(/_pref$/, '');
            if (el.type === 'checkbox') {
                prefs[prefName] = el.checked;
            } else {
                prefs[prefName] = el.value;
            }
        });
        
        const data = await ApiService.post('/api/set_processing_prefs', { prefs });
        
        if (data.success) {
            MessageHelper.showSuccess(msgId, 'Préférences de traitement enregistrées avec succès !');
        } else {
            MessageHelper.showError(msgId, data.message || 'Erreur lors de la sauvegarde.');
        }
    } catch (e) {
        MessageHelper.showError(msgId, 'Erreur de communication avec le serveur.');
    } finally {
        MessageHelper.setButtonLoading(btn, false);
    }
}

// -------------------- Local Preferences --------------------
function loadLocalPreferences() {
    try {
        const raw = localStorage.getItem('dashboard_prefs_v1');
        if (!raw) return;
        
        const prefs = JSON.parse(raw);
        
        // Appliquer les préférences locales
        Object.keys(prefs).forEach(key => {
            const el = document.getElementById(key);
            if (el) {
                if (el.type === 'checkbox') {
                    el.checked = prefs[key];
                } else {
                    el.value = prefs[key];
                }
            }
        });
    } catch (e) {
        console.warn('Erreur chargement préférences locales:', e);
    }
}

function saveLocalPreferences() {
    try {
        const prefs = {};
        
        // Collecter les préférences locales
        const localElements = document.querySelectorAll('[data-pref="local"]');
        localElements.forEach(el => {
            const prefName = el.id;
            if (el.type === 'checkbox') {
                prefs[prefName] = el.checked;
            } else {
                prefs[prefName] = el.value;
            }
        });
        
        localStorage.setItem('dashboard_prefs_v1', JSON.stringify(prefs));
    } catch (e) {
        console.warn('Erreur sauvegarde préférences locales:', e);
    }
}

// -------------------- Configuration Management --------------------
async function exportAllConfig() {
    try {
        const [webhookCfg, pollingCfg, timeWin] = await Promise.all([
            ApiService.get('/api/webhooks/config'),
            ApiService.get('/api/get_polling_config'),
            ApiService.get('/api/get_webhook_time_window')
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
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'render_signal_dashboard_config.json';
        a.click();
        URL.revokeObjectURL(url);
        
        MessageHelper.showSuccess('configMgmtMsg', 'Export réalisé avec succès.');
    } catch (e) {
        MessageHelper.showError('configMgmtMsg', 'Erreur lors de l\'export.');
    }
}

function handleImportConfigFile(evt) {
    const file = evt.target.files && evt.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = async () => {
        try {
            const obj = JSON.parse(String(reader.result || '{}'));
            
            // Appliquer la configuration serveur
            await applyImportedServerConfig(obj);
            
            // Appliquer les préférences UI
            if (obj.ui_preferences) {
                localStorage.setItem('dashboard_prefs_v1', JSON.stringify(obj.ui_preferences));
                loadLocalPreferences();
            }
            
            MessageHelper.showSuccess('configMgmtMsg', 'Import appliqué.');
        } catch (e) {
            MessageHelper.showError('configMgmtMsg', 'Fichier invalide.');
        }
    };
    reader.readAsText(file);
    
    // Reset input pour permettre les imports consécutifs
    evt.target.value = '';
}

async function applyImportedServerConfig(obj) {
    // Webhook config
    if (obj?.webhook_config?.config) {
        const cfg = obj.webhook_config.config;
        const payload = {};
        
        if (cfg.webhook_url) payload.webhook_url = cfg.webhook_url;
        if (typeof cfg.webhook_ssl_verify === 'boolean') payload.webhook_ssl_verify = cfg.webhook_ssl_verify;
        
        if (Object.keys(payload).length) {
            await ApiService.post('/api/webhooks/config', payload);
            await WebhookService.loadConfig();
        }
    }
    
    // Polling config
    if (obj?.polling_config?.config) {
        const cfg = obj.polling_config.config;
        const payload = {};
        
        if (Array.isArray(cfg.active_days)) payload.active_days = cfg.active_days;
        if (Number.isInteger(cfg.active_start_hour)) payload.active_start_hour = cfg.active_start_hour;
        if (Number.isInteger(cfg.active_end_hour)) payload.active_end_hour = cfg.active_end_hour;
        if (typeof cfg.enable_subject_group_dedup === 'boolean') payload.enable_subject_group_dedup = cfg.enable_subject_group_dedup;
        if (Array.isArray(cfg.sender_of_interest_for_polling)) payload.sender_of_interest_for_polling = cfg.sender_of_interest_for_polling;
        
        if (Object.keys(payload).length) {
            await ApiService.post('/api/update_polling_config', payload);
            await loadPollingConfig();
        }
    }
    
    // Time window
    if (obj?.time_window) {
        const start = obj.time_window.webhooks_time_start ?? '';
        const end = obj.time_window.webhooks_time_end ?? '';
        await ApiService.post('/api/set_webhook_time_window', { start, end });
        await loadTimeWindow();
    }
}

// -------------------- Validation --------------------
function validateWebhookUrlFromInput() {
    const inp = document.getElementById('testWebhookUrl');
    const msgId = 'webhookUrlValidationMsg';
    const val = (inp?.value || '').trim();
    
    if (!val) {
        MessageHelper.showError(msgId, 'Veuillez saisir une URL ou un alias.');
        return;
    }
    
    const ok = WebhookService.isValidWebhookUrl(val) || WebhookService.isValidHttpsUrl(val);
    if (ok) {
        MessageHelper.showSuccess(msgId, 'Format valide.');
    } else {
        MessageHelper.showError(msgId, 'Format invalide.');
    }
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
        meta: { 
            preview: true, 
            generated_at: new Date().toISOString() 
        }
    };
    
    const pre = document.getElementById('payloadPreview');
    if (pre) pre.textContent = JSON.stringify(payload, null, 2);
}

// -------------------- UI Helpers --------------------
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
    
    // Trier croissant et garantir l'unicité
    return Array.from(new Set(out)).sort((a, b) => a - b);
}

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

// -------------------- Fenêtre Horaire Global Webhook --------------------
async function loadGlobalWebhookTimeWindow() {
    console.log('[loadGlobalWebhookTimeWindow] Function called - hostname:', window.location.hostname);
    
    const applyGlobalWindowValues = (startValue = '', endValue = '') => {
        const startInput = document.getElementById('globalWebhookTimeStart');
        const endInput = document.getElementById('globalWebhookTimeEnd');
        console.log('[loadGlobalWebhookTimeWindow] Applying values:', { startValue, endValue, startInput: !!startInput, endInput: !!endInput });
        if (startInput) startInput.value = startValue || '';
        if (endInput) endInput.value = endValue || '';
        
        // Vérifier immédiatement après application
        setTimeout(() => {
            const startAfter = document.getElementById('globalWebhookTimeStart')?.value || '';
            const endAfter = document.getElementById('globalWebhookTimeEnd')?.value || '';
            console.log('[loadGlobalWebhookTimeWindow] Values after apply (delayed):', { startAfter, endAfter });
        }, 100);
    };
    
    try {
        // Utiliser la même source que la fenêtre horaire principale
        const configResponse = await ApiService.get('/api/webhooks/config');
        console.log('[loadGlobalWebhookTimeWindow] /api/webhooks/config response:', configResponse);
        if (configResponse.success && configResponse.config) {
            const cfg = configResponse.config;
            if (cfg.webhook_time_start || cfg.webhook_time_end) {
                applyGlobalWindowValues(cfg.webhook_time_start || '', cfg.webhook_time_end || '');
                return;
            }
        }
    } catch (e) {
        console.warn('Impossible de charger la fenêtre horaire webhook globale:', e);
    }
}

async function saveGlobalWebhookTimeWindow() {
    const startInput = document.getElementById('globalWebhookTimeStart');
    const endInput = document.getElementById('globalWebhookTimeEnd');
    const start = startInput.value.trim();
    const end = endInput.value.trim();
    
    // Validation des formats
    if (start && !MessageHelper.isValidTimeFormat(start)) {
        MessageHelper.showError('globalWebhookTimeMsg', 'Format d\'heure invalide (ex: 09:00 ou 9h00).');
        return;
    }
    
    if (end && !MessageHelper.isValidTimeFormat(end)) {
        MessageHelper.showError('globalWebhookTimeMsg', 'Format d\'heure invalide (ex: 19:00 ou 19h00).');
        return;
    }
    
    // Normalisation des formats
    const normalizedStart = start ? MessageHelper.normalizeTimeFormat(start) : '';
    const normalizedEnd = end ? MessageHelper.normalizeTimeFormat(end) : '';
    
    try {
        const data = await ApiService.post('/api/set_webhook_time_window', { 
            start: normalizedStart, 
            end: normalizedEnd 
        });
        
        if (data.success) {
            MessageHelper.showSuccess('globalWebhookTimeMsg', 'Fenêtre horaire webhook enregistrée avec succès !');
            
            // Mettre à jour les inputs selon la normalisation renvoyée par le backend
            if (startInput && Object.prototype.hasOwnProperty.call(data, 'webhooks_time_start')) {
                startInput.value = data.webhooks_time_start || '';
            }
            if (endInput && Object.prototype.hasOwnProperty.call(data, 'webhooks_time_end')) {
                endInput.value = data.webhooks_time_end || '';
            }
        } else {
            MessageHelper.showError('globalWebhookTimeMsg', data.message || 'Erreur lors de la sauvegarde.');
        }
    } catch (e) {
        MessageHelper.showError('globalWebhookTimeMsg', 'Erreur de communication avec le serveur.');
    }
}

// -------------------- Nettoyage --------------------
window.addEventListener('beforeunload', () => {
    // Arrêter le polling des logs
    LogService.stopLogPolling();
    
    // Nettoyer le gestionnaire d'onglets
    if (tabManager) {
        tabManager.destroy();
    }
    
    // Sauvegarder les préférences locales
    saveLocalPreferences();
});

// -------------------- Export pour compatibilité --------------------
// Exporter les classes pour utilisation externe si nécessaire
window.DashboardServices = {
    ApiService,
    WebhookService,
    LogService,
    MessageHelper,
    TabManager
};
