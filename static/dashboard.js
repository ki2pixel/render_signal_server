// static/dashboard.js
// Dashboard de contrôle des webhooks - Version modulaire
import { ApiService } from './services/ApiService.js';
import { WebhookService } from './services/WebhookService.js';
import { LogService } from './services/LogService.js';
import { MessageHelper } from './utils/MessageHelper.js';
import { TabManager } from './components/TabManager.js';

window.DASHBOARD_BUILD = 'modular-2026-01-19a';

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
        
        // Initialiser les panneaux pliables
        initializeCollapsiblePanels();
        
        // Initialiser l'auto-sauvegarde intelligente
        initializeAutoSave();
        
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

// -------------------- Migration Configs -> Redis --------------------
async function handleConfigMigration() {
    const button = document.getElementById('migrateConfigsBtn');
    const messageId = 'migrateConfigsMsg';
    const logEl = document.getElementById('migrateConfigsLog');

    if (!button) {
        MessageHelper.showError(messageId, 'Bouton de migration introuvable.');
        return;
    }

    const confirmed = window.confirm('Lancer la migration des configurations vers Redis ?');
    if (!confirmed) {
        return;
    }

    MessageHelper.setButtonLoading(button, true, '⏳ Migration en cours...');
    MessageHelper.showInfo(messageId, 'Migration en cours...');
    if (logEl) {
        logEl.style.display = 'none';
        logEl.textContent = '';
    }

    try {
        const response = await ApiService.post('/api/migrate_configs_to_redis', {});
        if (response?.success) {
            const keysText = (response.keys || []).join(', ') || 'aucune clé';
            MessageHelper.showSuccess(messageId, `Migration réussie (${keysText}).`);
        } else {
            MessageHelper.showError(messageId, response?.message || 'Échec de la migration.');
        }

        if (logEl) {
            const logContent = response?.log ? response.log.trim() : 'Aucun log renvoyé.';
            logEl.textContent = logContent;
            logEl.style.display = 'block';
        }
    } catch (error) {
        console.error('Erreur migration configs:', error);
        MessageHelper.showError(messageId, 'Erreur de communication avec le serveur.');
    } finally {
        MessageHelper.setButtonLoading(button, false);
    }
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
    
    // Statut Global
    const refreshStatusBtn = document.getElementById('refreshStatusBtn');
    if (refreshStatusBtn) {
        refreshStatusBtn.addEventListener('click', updateGlobalStatus);
    }
    
    // Panneaux webhooks (save buttons)
    document.querySelectorAll('.panel-save-btn[data-panel]').forEach(btn => {
        btn.addEventListener('click', () => {
            const panelType = btn.dataset.panel;
            if (panelType) {
                saveWebhookPanel(panelType);
            }
        });
    });
    
    // Déploiement application
    const restartBtn = document.getElementById('restartServerBtn');
    if (restartBtn) {
        restartBtn.addEventListener('click', handleDeployApplication);
    }
    
    const migrateBtn = document.getElementById('migrateConfigsBtn');
    if (migrateBtn) {
        migrateBtn.addEventListener('click', handleConfigMigration);
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
        
        // Mettre à jour le statut global
        await updateGlobalStatus();
        
    } catch (e) {
        console.error('Erreur lors du chargement des données initiales:', e);
    }
}

// -------------------- Feedback Visuel --------------------
function showCopiedFeedback() {
    // Créer le toast notification s'il n'existe pas
    let toast = document.querySelector('.copied-feedback');
    if (!toast) {
        toast = document.createElement('div');
        toast.className = 'copied-feedback';
        toast.textContent = '🔗 Magic link copié dans le presse-papiers !';
        document.body.appendChild(toast);
    }
    
    // Afficher le toast
    toast.classList.add('show');
    
    // Cacher après 3 secondes
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
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
                showCopiedFeedback();
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
        // 0) Source principale : fenêtre horaire globale (ancien endpoint)
        const globalTimeResponse = await ApiService.get('/api/get_webhook_time_window');
        console.log('[loadTimeWindow] /api/get_webhook_time_window response:', globalTimeResponse);
        if (globalTimeResponse.success && (globalTimeResponse.webhooks_time_start || globalTimeResponse.webhooks_time_end)) {
            applyWindowValues(globalTimeResponse.webhooks_time_start, globalTimeResponse.webhooks_time_end);
            return;
        }
    } catch (e) {
        console.warn('Impossible de charger la fenêtre horaire globale:', e);
    }
    
    try {
        // 1) Fallback : configuration webhooks (valeurs webhook spécifiques)
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
        return false;
    }
    
    if (end && !MessageHelper.isValidTimeFormat(end)) {
        MessageHelper.showError('timeWindowMsg', 'Format d\'heure invalide (ex: 17:30 ou 17h30).');
        return false;
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
            return true;
        } else {
            MessageHelper.showError('timeWindowMsg', data.message || 'Erreur lors de la sauvegarde.');
            return false;
        }
    } catch (e) {
        MessageHelper.showError('timeWindowMsg', 'Erreur de communication avec le serveur.');
        return false;
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
            
            // Mapping des préférences vers les éléments UI avec les bons IDs
            const mappings = {
                // Filtres
                'excludeKeywords': 'excludeKeywords',
                'exclude_keywords_recadrage': 'excludeKeywordsRecadrage', 
                'exclude_keywords_autorepondeur': 'excludeKeywordsAutorepondeur',
                
                // Paramètres
                'require_attachments': 'attachmentDetectionToggle',
                'max_email_size_mb': 'maxEmailSizeMB',
                'sender_priority': 'senderPriority',
                
                // Fiabilité
                'retry_count': 'retryCount',
                'retry_delay_sec': 'retryDelaySec',
                'webhook_timeout_sec': 'webhookTimeoutSec',
                'rate_limit_per_hour': 'rateLimitPerHour',
                'notify_on_failure': 'notifyOnFailureToggle'
            };
            
            Object.entries(mappings).forEach(([prefKey, elementId]) => {
                const el = document.getElementById(elementId);
                if (el && prefs[prefKey] !== undefined) {
                    if (el.type === 'checkbox') {
                        el.checked = Boolean(prefs[prefKey]);
                    } else if (el.tagName === 'TEXTAREA' && Array.isArray(prefs[prefKey])) {
                        // Convertir les tableaux en chaînes multi-lignes pour les textarea
                        el.value = prefs[prefKey].join('\n');
                    } else if (el.tagName === 'TEXTAREA' && typeof prefs[prefKey] === 'object') {
                        // Convertir les objets JSON en chaînes formatées pour les textarea
                        el.value = JSON.stringify(prefs[prefKey], null, 2);
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
        // Mapping des éléments UI vers les clés de préférences
        const mappings = {
            // Filtres
            'excludeKeywords': 'excludeKeywords',
            'excludeKeywordsRecadrage': 'exclude_keywords_recadrage', 
            'excludeKeywordsAutorepondeur': 'exclude_keywords_autorepondeur',
            
            // Paramètres
            'attachmentDetectionToggle': 'require_attachments',
            'maxEmailSizeMB': 'max_email_size_mb',
            'senderPriority': 'sender_priority',
            
            // Fiabilité
            'retryCount': 'retry_count',
            'retryDelaySec': 'retry_delay_sec',
            'webhookTimeoutSec': 'webhook_timeout_sec',
            'rateLimitPerHour': 'rate_limit_per_hour',
            'notifyOnFailureToggle': 'notify_on_failure'
        };
        
        // Collecter les préférences depuis les éléments UI
        const prefs = {};
        
        Object.entries(mappings).forEach(([elementId, prefKey]) => {
            const el = document.getElementById(elementId);
            if (el) {
                if (el.type === 'checkbox') {
                    prefs[prefKey] = el.checked;
                } else if (el.tagName === 'TEXTAREA') {
                    const value = el.value.trim();
                    if (value) {
                        // Pour les textarea de mots-clés, convertir en tableau
                        if (elementId.includes('Keywords')) {
                            prefs[prefKey] = value.split('\n').map(line => line.trim()).filter(line => line);
                        } 
                        // Pour le textarea JSON (sender_priority)
                        else if (elementId === 'senderPriority') {
                            try {
                                prefs[prefKey] = JSON.parse(value);
                            } catch (e) {
                                console.warn('Invalid JSON in senderPriority, using empty object');
                                prefs[prefKey] = {};
                            }
                        }
                        // Pour les autres textarea
                        else {
                            prefs[prefKey] = value;
                        }
                    } else {
                        // Valeur vide selon le type
                        if (elementId.includes('Keywords')) {
                            prefs[prefKey] = [];
                        } else if (elementId === 'senderPriority') {
                            prefs[prefKey] = {};
                        } else {
                            prefs[prefKey] = value;
                        }
                    }
                } else {
                    // Pour les inputs normaux
                    let value = el.value;
                    if (el.type === 'number' && value) {
                        value = parseInt(value, 10);
                    }
                    prefs[prefKey] = value || (el.type === 'number' ? 0 : '');
                }
            }
        });
        
        const data = await ApiService.post('/api/processing_prefs', { prefs });
        
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
        return false;
    }
    
    if (end && !MessageHelper.isValidTimeFormat(end)) {
        MessageHelper.showError('globalWebhookTimeMsg', 'Format d\'heure invalide (ex: 19:00 ou 19h00).');
        return false;
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
            return true;
        } else {
            MessageHelper.showError('globalWebhookTimeMsg', data.message || 'Erreur lors de la sauvegarde.');
            return false;
        }
    } catch (e) {
        MessageHelper.showError('globalWebhookTimeMsg', 'Erreur de communication avec le serveur.');
        return false;
    }
}

// -------------------- Statut Global --------------------
/**
 * Met à jour le bandeau de statut global avec les données récentes
 */
async function updateGlobalStatus() {
    try {
        // Récupérer les logs récents pour analyser le statut
        const logsResponse = await ApiService.get('/api/webhook_logs?limit=50');
        const configResponse = await ApiService.get('/api/webhooks/config');
        
        if (!logsResponse.success || !configResponse.success) {
            console.warn('Impossible de récupérer les données pour le statut global');
            return;
        }
        
        const logs = logsResponse.logs || [];
        const config = configResponse.config || {};
        
        // Analyser les logs pour déterminer le statut
        const statusData = analyzeLogsForStatus(logs);
        
        // Mettre à jour l'interface
        updateStatusBanner(statusData, config);
        
    } catch (error) {
        console.error('Erreur lors de la mise à jour du statut global:', error);
        // Afficher un statut d'erreur
        updateStatusBanner({
            lastExecution: 'Erreur',
            recentIncidents: '—',
            criticalErrors: '—',
            activeWebhooks: config?.webhook_url ? '1' : '0',
            status: 'error'
        }, {});
    }
}

/**
 * Analyse les logs pour extraire les informations de statut
 */
function analyzeLogsForStatus(logs) {
    const now = new Date();
    const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
    const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    
    let lastExecution = null;
    let recentIncidents = 0;
    let criticalErrors = 0;
    let totalWebhooks = 0;
    let successfulWebhooks = 0;
    
    logs.forEach(log => {
        const logTime = new Date(log.timestamp);
        
        // Dernière exécution
        if (!lastExecution || logTime > lastExecution) {
            lastExecution = logTime;
        }
        
        // Webhooks envoyés (dernière heure)
        if (logTime >= oneHourAgo) {
            totalWebhooks++;
            if (log.status === 'success') {
                successfulWebhooks++;
            } else if (log.status === 'error') {
                criticalErrors++;
            }
        }
        
        // Incidents récents (dernières 24h)
        if (logTime >= oneDayAgo && log.status === 'error') {
            recentIncidents++;
        }
    });
    
    // Formater la dernière exécution
    let lastExecutionText = '—';
    if (lastExecution) {
        const diffMinutes = Math.floor((now - lastExecution) / (1000 * 60));
        if (diffMinutes < 1) {
            lastExecutionText = 'À l\'instant';
        } else if (diffMinutes < 60) {
            lastExecutionText = `Il y a ${diffMinutes} min`;
        } else if (diffMinutes < 1440) {
            lastExecutionText = `Il y a ${Math.floor(diffMinutes / 60)}h`;
        } else {
            lastExecutionText = lastExecution.toLocaleDateString('fr-FR', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        }
    }
    
    // Déterminer le statut global
    let status = 'success';
    if (criticalErrors > 0) {
        status = 'error';
    } else if (recentIncidents > 0) {
        status = 'warning';
    }
    
    return {
        lastExecution: lastExecutionText,
        recentIncidents: recentIncidents.toString(),
        criticalErrors: criticalErrors.toString(),
        activeWebhooks: totalWebhooks.toString(),
        status: status
    };
}

/**
 * Met à jour l'affichage du bandeau de statut
 */
function updateStatusBanner(statusData, config) {
    // Mettre à jour les valeurs
    document.getElementById('lastExecutionTime').textContent = statusData.lastExecution;
    document.getElementById('recentIncidents').textContent = statusData.recentIncidents;
    document.getElementById('criticalErrors').textContent = statusData.criticalErrors;
    document.getElementById('activeWebhooks').textContent = statusData.activeWebhooks;
    
    // Mettre à jour l'icône de statut
    const statusIcon = document.getElementById('globalStatusIcon');
    statusIcon.className = 'status-icon ' + statusData.status;
    
    switch (statusData.status) {
        case 'success':
            statusIcon.textContent = '🟢';
            break;
        case 'warning':
            statusIcon.textContent = '🟡';
            break;
        case 'error':
            statusIcon.textContent = '🔴';
            break;
        default:
            statusIcon.textContent = '🟢';
    }
}

// -------------------- Panneaux Pliables Webhooks --------------------
/**
 * Initialise les panneaux pliables des webhooks
 */
function initializeCollapsiblePanels() {
    const panels = document.querySelectorAll('.collapsible-panel');
    
    panels.forEach(panel => {
        const header = panel.querySelector('.panel-header');
        const content = panel.querySelector('.panel-content');
        const toggleIcon = panel.querySelector('.toggle-icon');
        
        if (header && content && toggleIcon) {
            header.addEventListener('click', () => {
                const isCollapsed = content.classList.contains('collapsed');
                
                if (isCollapsed) {
                    content.classList.remove('collapsed');
                    toggleIcon.classList.remove('rotated');
                } else {
                    content.classList.add('collapsed');
                    toggleIcon.classList.add('rotated');
                }
            });
        }
    });
}

/**
 * Met à jour le statut d'un panneau
 * @param {string} panelType - Type de panneau
 * @param {boolean} success - Si la sauvegarde a réussi
 */
function updatePanelStatus(panelType, success) {
    const statusElement = document.getElementById(`${panelType}-status`);
    if (statusElement) {
        if (success) {
            statusElement.textContent = 'Sauvegardé';
            statusElement.classList.add('saved');
        } else {
            statusElement.textContent = 'Erreur';
            statusElement.classList.remove('saved');
        }
        
        // Réinitialiser après 3 secondes
        setTimeout(() => {
            statusElement.textContent = 'Sauvegarde requise';
            statusElement.classList.remove('saved');
        }, 3000);
    }
}

/**
 * Met à jour l'indicateur de dernière sauvegarde
 * @param {string} panelType - Type de panneau
 */
function updatePanelIndicator(panelType) {
    const indicator = document.getElementById(`${panelType}-indicator`);
    if (indicator) {
        const now = new Date();
        const timeString = now.toLocaleTimeString('fr-FR', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        indicator.textContent = `Dernière sauvegarde: ${timeString}`;
    }
}

/**
 * Sauvegarde un panneau de configuration webhook
 * @param {string} panelType - Type de panneau (urls-ssl, absence, time-window)
 */
async function saveWebhookPanel(panelType) {
    try {
        let data;
        let endpoint;
        let successMessage;
        
        switch (panelType) {
            case 'urls-ssl':
                data = collectUrlsData();
                endpoint = '/api/webhooks/config';
                successMessage = 'Configuration URLs & SSL enregistrée avec succès !';
                break;
                
            case 'absence':
                data = collectAbsenceData();
                endpoint = '/api/webhooks/config';
                successMessage = 'Configuration Absence Globale enregistrée avec succès !';
                break;
                
            case 'time-window':
                data = collectTimeWindowData();
                endpoint = '/api/webhooks/time-window';
                successMessage = 'Fenêtre horaire enregistrée avec succès !';
                break;
                
            default:
                console.error('Type de panneau inconnu:', panelType);
                return;
        }
        
        // Envoyer les données au serveur
        const response = await ApiService.post(endpoint, data);
        
        if (response.success) {
            MessageHelper.showSuccess(`${panelType}-msg`, successMessage);
            updatePanelStatus(panelType, true);
            updatePanelIndicator(panelType);
        } else {
            MessageHelper.showError(`${panelType}-msg`, response.message || 'Erreur lors de la sauvegarde');
            updatePanelStatus(panelType, false);
        }
        
    } catch (error) {
        console.error(`Erreur lors de la sauvegarde du panneau ${panelType}:`, error);
        MessageHelper.showError(`${panelType}-msg`, 'Erreur lors de la sauvegarde');
        updatePanelStatus(panelType, false);
    }
}

/**
 * Collecte les données du panneau URLs & SSL
 */
function collectUrlsData() {
    const webhookUrl = document.getElementById('webhookUrl')?.value || '';
    const makeWebhookUrl = document.getElementById('makeWebhookUrl')?.value || '';
    const sslToggle = document.getElementById('sslVerifyToggle');
    const sendingToggle = document.getElementById('webhookSendingToggle');
    const sslVerify = sslToggle?.checked ?? true;
    const sendingEnabled = sendingToggle?.checked ?? true;
    
    return {
        webhook_url: webhookUrl || null,
        make_webhook_url: makeWebhookUrl || null,
        webhook_ssl_verify: sslVerify,
        webhook_sending_enabled: sendingEnabled
    };
}

/**
 * Collecte les données du panneau fenêtre horaire
 */
function collectTimeWindowData() {
    const startInput = document.getElementById('webhooksTimeStart');
    const endInput = document.getElementById('webhooksTimeEnd');
    const start = startInput?.value?.trim() || '';
    const end = endInput?.value?.trim() || '';
    
    // Normaliser les formats
    const normalizedStart = start ? MessageHelper.normalizeTimeFormat(start) : '';
    const normalizedEnd = end ? MessageHelper.normalizeTimeFormat(end) : '';
    
    return {
        start: normalizedStart,
        end: normalizedEnd
    };
}

/**
 * Collecte les données du panneau d'absence
 */
function collectAbsenceData() {
    const toggle = document.getElementById('absencePauseToggle');
    const dayCheckboxes = document.querySelectorAll('input[name="absencePauseDay"]:checked');
    
    return {
        absence_pause_enabled: toggle ? toggle.checked : false,
        absence_pause_days: Array.from(dayCheckboxes).map(cb => cb.value)
    };
}

// -------------------- Déploiement Application --------------------
async function handleDeployApplication() {
    const button = document.getElementById('restartServerBtn');
    const messageId = 'restartMsg';
    
    if (!button) {
        MessageHelper.showError(messageId, 'Bouton de déploiement introuvable.');
        return;
    }
    
    const confirmed = window.confirm("Confirmez-vous le déploiement de l'application ? Elle peut être indisponible pendant quelques secondes.");
    if (!confirmed) {
        return;
    }
    
    button.disabled = true;
    MessageHelper.showInfo(messageId, 'Déploiement en cours...');
    
    try {
        const response = await ApiService.post('/api/deploy_application');
        if (response?.success) {
            MessageHelper.showSuccess(messageId, response.message || 'Déploiement planifié. Vérification du service…');
            try {
                await pollHealthCheck({ attempts: 12, intervalMs: 1500, timeoutMs: 30000 });
                window.location.reload();
            } catch (healthError) {
                console.warn('Health check failed after deployment:', healthError);
                MessageHelper.showError(messageId, "Le service ne répond pas encore. Réessayez dans quelques secondes ou rechargez la page.");
            }
        } else {
            MessageHelper.showError(messageId, response?.message || 'Échec du déploiement. Vérifiez les journaux serveur.');
        }
    } catch (error) {
        console.error('Erreur déploiement application:', error);
        MessageHelper.showError(messageId, 'Erreur de communication avec le serveur.');
    } finally {
        button.disabled = false;
    }
}

async function pollHealthCheck({ attempts = 10, intervalMs = 1200, timeoutMs = 20000 } = {}) {
    const safeAttempts = Math.max(1, Number(attempts));
    const delayMs = Math.max(250, Number(intervalMs));
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), Math.max(delayMs, Number(timeoutMs)));
    
    try {
        for (let attempt = 0; attempt < safeAttempts; attempt++) {
            try {
                const res = await fetch('/health', { cache: 'no-store', signal: controller.signal });
                if (res.ok) {
                    clearTimeout(timeoutId);
                    return true;
                }
            } catch {
                // Service peut être indisponible lors du redéploiement, ignorer
            }
            await new Promise(resolve => setTimeout(resolve, delayMs));
        }
        throw new Error('healthcheck failed');
    } finally {
        clearTimeout(timeoutId);
    }
}

// -------------------- Auto-sauvegarde Intelligente --------------------
/**
 * Initialise l'auto-sauvegarde intelligente
 */
function initializeAutoSave() {
    // Préférences qui peuvent être sauvegardées automatiquement
    const autoSaveFields = [
        'attachmentDetectionToggle',
        'retryCount', 
        'retryDelaySec',
        'webhookTimeoutSec',
        'rateLimitPerHour',
        'notifyOnFailureToggle'
    ];
    
    // Écouter les changements sur les champs d'auto-sauvegarde
    autoSaveFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.addEventListener('change', () => handleAutoSaveChange(fieldId));
            field.addEventListener('input', debounce(() => handleAutoSaveChange(fieldId), 2000));
        }
    });
    
    // Écouter les changements sur les textarea de préférences
    const preferenceTextareas = [
        'excludeKeywordsRecadrage',
        'excludeKeywordsAutorepondeur',
        'excludeKeywords',
        'senderPriority'
    ];
    
    preferenceTextareas.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.addEventListener('input', debounce(() => handleAutoSaveChange(fieldId), 3000));
        }
    });
}

/**
 * Gère les changements pour l'auto-sauvegarde
 * @param {string} fieldId - ID du champ modifié
 */
async function handleAutoSaveChange(fieldId) {
    try {
        // Marquer la section comme modifiée
        markSectionAsModified(fieldId);
        
        // Collecter les données de préférences
        const prefsData = collectPreferencesData();
        
        // Sauvegarder automatiquement
        const result = await ApiService.post('/api/processing_prefs', { prefs: prefsData });
        
        if (result.success) {
            // Marquer la section comme sauvegardée
            markSectionAsSaved(fieldId);
            showAutoSaveFeedback(fieldId, true);
        } else {
            showAutoSaveFeedback(fieldId, false, result.message);
        }
        
    } catch (error) {
        console.error('Erreur lors de l\'auto-sauvegarde:', error);
        showAutoSaveFeedback(fieldId, false, 'Erreur de connexion');
    }
}

/**
 * Collecte les données des préférences
 */
function collectPreferencesData() {
    const data = {};
    
    // Préférences de filtres (tableaux)
    const excludeKeywordsRecadrage = document.getElementById('excludeKeywordsRecadrage')?.value || '';
    const excludeKeywordsAutorepondeur = document.getElementById('excludeKeywordsAutorepondeur')?.value || '';
    const excludeKeywords = document.getElementById('excludeKeywords')?.value || '';
    
    data.exclude_keywords_recadrage = excludeKeywordsRecadrage ? 
        excludeKeywordsRecadrage.split('\n').map(line => line.trim()).filter(line => line) : [];
    data.exclude_keywords_autorepondeur = excludeKeywordsAutorepondeur ? 
        excludeKeywordsAutorepondeur.split('\n').map(line => line.trim()).filter(line => line) : [];
    data.exclude_keywords = excludeKeywords ? 
        excludeKeywords.split('\n').map(line => line.trim()).filter(line => line) : [];
    
    // Préférences de fiabilité
    data.require_attachments = document.getElementById('attachmentDetectionToggle')?.checked || false;
    data.retry_count = parseInt(document.getElementById('retryCount')?.value) || 3;
    data.retry_delay_sec = parseInt(document.getElementById('retryDelaySec')?.value) || 10;
    data.webhook_timeout_sec = parseInt(document.getElementById('webhookTimeoutSec')?.value) || 30;
    data.rate_limit_per_hour = parseInt(document.getElementById('rateLimitPerHour')?.value) || 300;
    data.notify_on_failure = document.getElementById('notifyOnFailureToggle')?.checked || false;
    
    // Préférences de priorité (JSON)
    const senderPriorityText = document.getElementById('senderPriority')?.value || '{}';
    try {
        data.sender_priority = JSON.parse(senderPriorityText);
    } catch (e) {
        data.sender_priority = {};
    }
    
    return data;
}

/**
 * Marque une section comme modifiée
 * @param {string} fieldId - ID du champ modifié
 */
function markSectionAsModified(fieldId) {
    const section = getFieldSection(fieldId);
    if (section) {
        section.classList.add('modified');
        updateSectionIndicator(section, 'Modifié');
    }
}

/**
 * Marque une section comme sauvegardée
 * @param {string} fieldId - ID du champ sauvegardé
 */
function markSectionAsSaved(fieldId) {
    const section = getFieldSection(fieldId);
    if (section) {
        section.classList.remove('modified');
        section.classList.add('saved');
        updateSectionIndicator(section, 'Sauvegardé');
        
        // Retirer la classe 'saved' après 2 secondes
        setTimeout(() => {
            section.classList.remove('saved');
            updateSectionIndicator(section, '');
        }, 2000);
    }
}

/**
 * Obtient la section d'un champ
 * @param {string} fieldId - ID du champ
 * @returns {HTMLElement|null} Section parente
 */
function getFieldSection(fieldId) {
    const field = document.getElementById(fieldId);
    if (!field) return null;
    
    // Remonter jusqu'à trouver une carte ou un panneau
    let parent = field.parentElement;
    while (parent && parent !== document.body) {
        if (parent.classList.contains('card') || parent.classList.contains('collapsible-panel')) {
            return parent;
        }
        parent = parent.parentElement;
    }
    
    return null;
}

/**
 * Met à jour l'indicateur de section
 * @param {HTMLElement} section - Section à mettre à jour
 * @param {string} status - Statut à afficher
 */
function updateSectionIndicator(section, status) {
    let indicator = section.querySelector('.section-indicator');
    
    if (!indicator) {
        // Créer l'indicateur s'il n'existe pas
        indicator = document.createElement('div');
        indicator.className = 'section-indicator';
        
        // Insérer après le titre
        const title = section.querySelector('.card-title, .panel-title');
        if (title) {
            title.appendChild(indicator);
        }
    }
    
    if (status) {
        indicator.textContent = status;
        indicator.className = `section-indicator ${status.toLowerCase()}`;
    } else {
        indicator.textContent = '';
        indicator.className = 'section-indicator';
    }
}

/**
 * Affiche un feedback d'auto-sauvegarde
 * @param {string} fieldId - ID du champ
 * @param {boolean} success - Si la sauvegarde a réussi
 * @param {string} message - Message optionnel
 */
function showAutoSaveFeedback(fieldId, success, message = '') {
    const field = document.getElementById(fieldId);
    if (!field) return;
    
    // Créer ou récupérer le conteneur de feedback
    let feedback = field.parentElement.querySelector('.auto-save-feedback');
    if (!feedback) {
        feedback = document.createElement('div');
        feedback.className = 'auto-save-feedback';
        field.parentElement.appendChild(feedback);
    }
    
    // Définir le style et le message
    feedback.style.cssText = `
        font-size: 0.7em;
        margin-top: 4px;
        padding: 2px 6px;
        border-radius: 3px;
        opacity: 0;
        transition: opacity 0.3s ease;
    `;
    
    if (success) {
        feedback.style.background = 'rgba(26, 188, 156, 0.2)';
        feedback.style.color = 'var(--cork-success)';
        feedback.textContent = '✓ Auto-sauvegardé';
    } else {
        feedback.style.background = 'rgba(231, 81, 90, 0.2)';
        feedback.style.color = 'var(--cork-danger)';
        feedback.textContent = `✗ Erreur: ${message}`;
    }
    
    // Afficher le feedback
    feedback.style.opacity = '1';
    
    // Masquer après 3 secondes
    setTimeout(() => {
        feedback.style.opacity = '0';
    }, 3000);
}

/**
 * Fonction de debounce pour limiter les appels
 * @param {Function} func - Fonction à débouncer
 * @param {number} wait - Temps d'attente en ms
 * @returns {Function} Fonction débouncée
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
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
