import { ApiService } from './ApiService.js';
import { WebhookService } from './WebhookService.js';
import { MessageHelper } from '../utils/MessageHelper.js';
import { DOMHelper } from '../utils/DOMHelper.js';
import { JsonViewer } from '../components/JsonViewer.js';

// -------------------- Fenêtre Horaire --------------------

/**
 * Génère les options pour les sélecteurs d'heure
 * @param {number} stepMinutes - Intervalle en minutes
 * @returns {string} HTML des options
 */
export function generateTimeOptions(stepMinutes = 30) {
    const options = ['<option value="">Sélectionner...</option>'];
    for (let hour = 0; hour < 24; hour++) {
        for (let minute = 0; minute < 60; minute += stepMinutes) {
            const timeStr = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
            options.push(`<option value="${timeStr}">${timeStr}</option>`);
        }
    }
    return options.join('');
}

/**
 * Génère les options pour les sélecteurs d'heures complètes
 * @returns {string} HTML des options
 */
export function generateHourOptions() {
    const options = ['<option value="">Sélectionner...</option>'];
    for (let hour = 0; hour < 24; hour++) {
        const label = `${hour.toString().padStart(2, '0')}h`;
        options.push(`<option value="${hour}">${label}</option>`);
    }
    return options.join('');
}

/**
 * Sélectionne une option dans un élément select
 * @param {HTMLSelectElement} selectElement - Élément select
 * @param {string} value - Valeur à sélectionner
 */
export function setSelectedOption(selectElement, value) {
    if (!selectElement) return;
    for (let i = 0; i < selectElement.options.length; i++) {
        if (selectElement.options[i].value === value || selectElement.options[i].value === value.toString()) {
            selectElement.selectedIndex = i;
            return;
        }
    }
    selectElement.selectedIndex = 0;
}

/**
 * Charge la fenêtre horaire depuis le backend
 */
export async function loadTimeWindow() {
    const applyWindowValues = (startValue = '', endValue = '') => {
        const startInput = DOMHelper.getElement('webhooksTimeStart');
        const endInput = DOMHelper.getElement('webhooksTimeEnd');
        if (startInput) setSelectedOption(startInput, startValue || '');
        if (endInput) setSelectedOption(endInput, endValue || '');
        renderTimeWindowDisplay(startValue || '', endValue || '');
    };
    
    try {
        const globalTimeResponse = await ApiService.get('/api/get_webhook_time_window');
        if (globalTimeResponse.success) {
            applyWindowValues(
                globalTimeResponse.webhooks_time_start || '',
                globalTimeResponse.webhooks_time_end || ''
            );
            return;
        }
    } catch (e) {
        console.warn('Impossible de charger la fenêtre horaire globale:', e);
    }
    
    try {
        const data = await ApiService.get('/api/get_webhook_time_window');
        if (data.success) {
            applyWindowValues(data.webhooks_time_start, data.webhooks_time_end);
        }
    } catch (e) {
        console.error('Erreur chargement fenêtre horaire (fallback):', e);
    }
}

/**
 * Sauvegarde la fenêtre horaire
 * @param {Function} updatePanelStatusFn - Callback pour le statut du panneau
 * @param {Function} updatePanelIndicatorFn - Callback pour l'indicateur
 * @returns {Promise<boolean>} Succès
 */
export async function saveTimeWindow(updatePanelStatusFn, updatePanelIndicatorFn) {
    const startInput = DOMHelper.getElement('webhooksTimeStart');
    const endInput = DOMHelper.getElement('webhooksTimeEnd');
    if (!startInput || !endInput) return false;

    const start = startInput.value.trim();
    const end = endInput.value.trim();
    
    if (start && !/^\d{2}:\d{2}$/.test(start)) {
        MessageHelper.showError('timeWindowMsg', 'Veuillez sélectionner une heure valide.');
        return false;
    }
    
    if (end && !/^\d{2}:\d{2}$/.test(end)) {
        MessageHelper.showError('timeWindowMsg', 'Veuillez sélectionner une heure valide.');
        return false;
    }
    
    try {
        const data = await ApiService.post('/api/set_webhook_time_window', { 
            start: start, 
            end: end 
        });
        
        if (data.success) {
            MessageHelper.showSuccess('timeWindowMsg', 'Fenêtre horaire enregistrée avec succès !');
            updatePanelStatusFn('time-window', true);
            updatePanelIndicatorFn('time-window');
            
            if (startInput && Object.hasOwn(data, 'webhooks_time_start')) {
                setSelectedOption(startInput, data.webhooks_time_start || '');
            }
            if (endInput && Object.hasOwn(data, 'webhooks_time_end')) {
                setSelectedOption(endInput, data.webhooks_time_end || '');
            }
            
            renderTimeWindowDisplay(data.webhooks_time_start || start, data.webhooks_time_end || end);
            await loadTimeWindow();
            return true;
        } else {
            MessageHelper.showError('timeWindowMsg', data.message || 'Erreur lors de la sauvegarde.');
            updatePanelStatusFn('time-window', false);
            return false;
        }
    } catch (e) {
        MessageHelper.showError('timeWindowMsg', 'Erreur de communication avec le serveur.');
        updatePanelStatusFn('time-window', false);
        return false;
    }
}

/**
 * Affiche la fenêtre horaire active
 * @param {string} start - Heure de début
 * @param {string} end - Heure de fin
 */
export function renderTimeWindowDisplay(start, end) {
    const displayEl = DOMHelper.getElement('timeWindowDisplay');
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

// -------------------- Fenêtre Horaire Globale Webhook --------------------

/**
 * Charge la fenêtre horaire globale webhook
 */
export async function loadGlobalWebhookTimeWindow() {
    const applyGlobalWindowValues = (startValue = '', endValue = '') => {
        const startInput = DOMHelper.getElement('globalWebhookTimeStart');
        const endInput = DOMHelper.getElement('globalWebhookTimeEnd');
        if (startInput) setSelectedOption(startInput, startValue || '');
        if (endInput) setSelectedOption(endInput, endValue || '');
    };
    
    try {
        const timeWindowResponse = await ApiService.get('/api/webhooks/time-window');
        if (timeWindowResponse.success) {
            applyGlobalWindowValues(
                timeWindowResponse.webhooks_time_start || '',
                timeWindowResponse.webhooks_time_end || ''
            );
            return;
        }
    } catch (e) {
        console.warn('Impossible de charger la fenêtre horaire webhook globale:', e);
    }
}

/**
 * Sauvegarde la fenêtre horaire globale
 * @param {Function} updatePanelStatusFn - Callback pour le statut du panneau
 * @param {Function} updatePanelIndicatorFn - Callback pour l'indicateur
 * @returns {Promise<boolean>} Succès
 */
export async function saveGlobalWebhookTimeWindow(updatePanelStatusFn, updatePanelIndicatorFn) {
    const startInput = DOMHelper.getElement('globalWebhookTimeStart');
    const endInput = DOMHelper.getElement('globalWebhookTimeEnd');
    if (!startInput || !endInput) return false;

    const start = startInput.value.trim();
    const end = endInput.value.trim();
    
    if (start && !/^\d{2}:\d{2}$/.test(start)) {
        MessageHelper.showError('globalWebhookTimeMsg', 'Veuillez sélectionner une heure valide.');
        return false;
    }
    
    if (end && !/^\d{2}:\d{2}$/.test(end)) {
        MessageHelper.showError('globalWebhookTimeMsg', 'Veuillez sélectionner une heure valide.');
        return false;
    }
    
    try {
        const data = await ApiService.post('/api/webhooks/time-window', { 
            start: start, 
            end: end 
        });
        
        if (data.success) {
            MessageHelper.showSuccess('globalWebhookTimeMsg', 'Fenêtre horaire webhook enregistrée avec succès !');
            updatePanelStatusFn('time-window', true);
            updatePanelIndicatorFn('time-window');
            
            if (startInput && Object.hasOwn(data, 'webhooks_time_start')) {
                setSelectedOption(startInput, data.webhooks_time_start || '');
            }
            if (endInput && Object.hasOwn(data, 'webhooks_time_end')) {
                setSelectedOption(endInput, data.webhooks_time_end || '');
            }
            await loadGlobalWebhookTimeWindow();
            return true;
        } else {
            MessageHelper.showError('globalWebhookTimeMsg', data.message || 'Erreur lors de la sauvegarde.');
            updatePanelStatusFn('time-window', false);
            return false;
        }
    } catch (e) {
        MessageHelper.showError('globalWebhookTimeMsg', 'Erreur de communication avec le serveur.');
        updatePanelStatusFn('time-window', false);
        return false;
    }
}

// -------------------- Runtime Flags --------------------

/**
 * Charge les flags de runtime depuis le backend
 */
export async function loadRuntimeFlags() {
    try {
        const data = await ApiService.get('/api/get_runtime_flags');
        
        if (data.success) {
            const flags = data.flags || {};

            const disableDedup = DOMHelper.getElement('disableEmailIdDedupToggle');
            if (disableDedup && Object.hasOwn(flags, 'disable_email_id_dedup')) {
                disableDedup.checked = !!flags.disable_email_id_dedup;
            }

            const allowCustom = DOMHelper.getElement('allowCustomWithoutLinksToggle');
            if (
                allowCustom
                && Object.hasOwn(flags, 'allow_custom_webhook_without_links')
            ) {
                allowCustom.checked = !!flags.allow_custom_webhook_without_links;
            }

            const gmailIngressEnabled = DOMHelper.getElement('gmailIngressEnabledToggle');
            if (
                gmailIngressEnabled
                && Object.hasOwn(flags, 'gmail_ingress_enabled')
            ) {
                gmailIngressEnabled.checked = !!flags.gmail_ingress_enabled;
            }
        }
    } catch (e) {
        console.error('loadRuntimeFlags error', e);
    }
}

/**
 * Sauvegarde les flags de runtime
 */
export async function saveRuntimeFlags() {
    const msgId = 'runtimeFlagsMsg';
    const btn = DOMHelper.getElement('runtimeFlagsSaveBtn');
    
    MessageHelper.setButtonLoading(btn, true);
    
    try {
        const disableDedup = DOMHelper.getElement('disableEmailIdDedupToggle');
        const allowCustom = DOMHelper.getElement('allowCustomWithoutLinksToggle');
        const gmailIngressEnabled = DOMHelper.getElement('gmailIngressEnabledToggle');

        const payload = {
            disable_email_id_dedup: disableDedup?.checked ?? false,
            allow_custom_webhook_without_links: allowCustom?.checked ?? false,
            gmail_ingress_enabled: gmailIngressEnabled?.checked ?? true,
        };

        const data = await ApiService.post('/api/update_runtime_flags', payload);
        
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

/**
 * Charge les préférences de traitement depuis le backend
 */
export async function loadProcessingPrefsFromServer() {
    try {
        const data = await ApiService.get('/api/processing_prefs');
        
        if (data.success) {
            const prefs = data.prefs || {};
            
            const mappings = {
                'exclude_keywords': 'excludeKeywords',
                'exclude_keywords_recadrage': 'excludeKeywordsRecadrage', 
                'exclude_keywords_autorepondeur': 'excludeKeywordsAutorepondeur',
                'require_attachments': 'attachmentDetectionToggle',
                'max_email_size_mb': 'maxEmailSizeMB',
                'sender_priority': 'senderPriority',
                'retry_count': 'retryCount',
                'retry_delay_sec': 'retryDelaySec',
                'webhook_timeout_sec': 'webhookTimeoutSec',
                'rate_limit_per_hour': 'rateLimitPerHour',
                'notify_on_failure': 'notifyOnFailureToggle'
            };
            
            Object.entries(mappings).forEach(([prefKey, elementId]) => {
                const el = DOMHelper.getElement(elementId);
                if (el && prefs[prefKey] !== undefined) {
                    if (el.type === 'checkbox') {
                        el.checked = Boolean(prefs[prefKey]);
                    } else if (el.tagName === 'TEXTAREA' && Array.isArray(prefs[prefKey])) {
                        el.value = prefs[prefKey].join('\n');
                    } else if (el.tagName === 'TEXTAREA' && typeof prefs[prefKey] === 'object') {
                        el.value = JSON.stringify(prefs[prefKey], null, 2);
                    } else if (el.type === 'number' && prefs[prefKey] === null) {
                        el.value = '';
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

/**
 * Sauvegarde les préférences de traitement
 */
export async function saveProcessingPrefsToServer() {
    const btn = DOMHelper.getElement('processingPrefsSaveBtn');
    const msgId = 'processingPrefsMsg';
    
    MessageHelper.setButtonLoading(btn, true);
    
    try {
        const mappings = {
            'excludeKeywords': 'exclude_keywords',
            'excludeKeywordsRecadrage': 'exclude_keywords_recadrage', 
            'excludeKeywordsAutorepondeur': 'exclude_keywords_autorepondeur',
            'attachmentDetectionToggle': 'require_attachments',
            'maxEmailSizeMB': 'max_email_size_mb',
            'senderPriority': 'sender_priority',
            'retryCount': 'retry_count',
            'retryDelaySec': 'retry_delay_sec',
            'webhookTimeoutSec': 'webhook_timeout_sec',
            'rateLimitPerHour': 'rate_limit_per_hour',
            'notifyOnFailureToggle': 'notify_on_failure'
        };
        
        const prefs = {};
        
        Object.entries(mappings).forEach(([elementId, prefKey]) => {
            const el = DOMHelper.getElement(elementId);
            if (el) {
                if (el.type === 'checkbox') {
                    prefs[prefKey] = el.checked;
                } else if (el.tagName === 'TEXTAREA') {
                    const value = el.value.trim();
                    if (value) {
                        if (elementId.includes('Keywords')) {
                            prefs[prefKey] = value.split('\n').map(line => line.trim()).filter(line => line);
                        } 
                        else if (elementId === 'senderPriority') {
                            try {
                                prefs[prefKey] = JSON.parse(value);
                            } catch (e) {
                                console.warn('Invalid JSON in senderPriority, using empty object');
                                prefs[prefKey] = {};
                            }
                        }
                        else {
                            prefs[prefKey] = value;
                        }
                    } else {
                        if (elementId.includes('Keywords')) {
                            prefs[prefKey] = [];
                        } else if (elementId === 'senderPriority') {
                            prefs[prefKey] = {};
                        } else {
                            prefs[prefKey] = value;
                        }
                    }
                } else {
                    const value = (el.value ?? '').toString().trim();
                    if (el.type === 'number') {
                        if (value === '') {
                            if (elementId === 'maxEmailSizeMB') {
                                prefs[prefKey] = null;
                            }
                            return;
                        }
                        prefs[prefKey] = parseInt(value, 10);
                        return;
                    }
                    prefs[prefKey] = value;
                }
            }
        });
        
        const data = await ApiService.post('/api/processing_prefs', prefs);
        
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

/**
 * Charge les préférences locales depuis le localStorage
 */
export function loadLocalPreferences() {
    try {
        const raw = localStorage.getItem('dashboard_prefs_v1');
        if (!raw) return;
        
        const prefs = JSON.parse(raw);
        
        Object.keys(prefs).forEach(key => {
            const el = DOMHelper.getElement(key);
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

/**
 * Sauvegarde les préférences locales dans le localStorage
 */
export function saveLocalPreferences() {
    try {
        const prefs = {};
        
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

// -------------------- Import / Export --------------------

/**
 * Exporte toute la configuration en JSON
 */
export async function exportAllConfig() {
    try {
        const [webhookCfg, timeWin, processingPrefs] = await Promise.all([
            ApiService.get('/api/webhooks/config'),
            ApiService.get('/api/get_webhook_time_window'),
            ApiService.get('/api/processing_prefs')
        ]);
        
        const prefsRaw = localStorage.getItem('dashboard_prefs_v1');
        const exportObj = {
            exported_at: new Date().toISOString(),
            webhook_config: webhookCfg,
            time_window: timeWin,
            processing_prefs: processingPrefs,
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

/**
 * Gère l'import d'un fichier de configuration
 * @param {Event} evt - Événement change du input file
 */
export function handleImportConfigFile(evt) {
    const file = evt.target.files && evt.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = async () => {
        try {
            const obj = JSON.parse(String(reader.result || '{}'));
            
            await applyImportedServerConfig(obj);
            
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
    
    evt.target.value = '';
}

/**
 * Applique la configuration serveur importée
 * @param {object} obj - Objet de configuration importé
 */
async function applyImportedServerConfig(obj) {
    // Webhook config
    if (obj?.webhook_config?.config) {
        const cfg = obj.webhook_config.config;
        const payload = {};

        if (
            cfg.webhook_url
            && typeof cfg.webhook_url === 'string'
            && !cfg.webhook_url.includes('***')
        ) {
            payload.webhook_url = cfg.webhook_url;
        }
        if (typeof cfg.webhook_ssl_verify === 'boolean') payload.webhook_ssl_verify = cfg.webhook_ssl_verify;
        if (typeof cfg.webhook_sending_enabled === 'boolean') {
            payload.webhook_sending_enabled = cfg.webhook_sending_enabled;
        }
        if (typeof cfg.absence_pause_enabled === 'boolean') {
            payload.absence_pause_enabled = cfg.absence_pause_enabled;
        }
        if (Array.isArray(cfg.absence_pause_days)) {
            payload.absence_pause_days = cfg.absence_pause_days;
        }
        
        if (Object.keys(payload).length) {
            await ApiService.post('/api/webhooks/config', payload);
            await WebhookService.loadConfig();
        }
    }
    
    // Time window
    if (obj?.time_window) {
        const start = obj.time_window?.webhooks_time_start ?? '';
        const end = obj.time_window?.webhooks_time_end ?? '';
        await ApiService.post('/api/set_webhook_time_window', { start, end });
        await loadTimeWindow();
    }

    // Processing prefs
    if (obj?.processing_prefs?.prefs && typeof obj.processing_prefs.prefs === 'object') {
        await ApiService.post('/api/processing_prefs', obj.processing_prefs.prefs);
        await loadProcessingPrefsFromServer();
    }
}

// -------------------- Validation --------------------

/**
 * Valide le format de l'URL webhook saisie
 */
export function validateWebhookUrlFromInput() {
    const inp = DOMHelper.getElement('testWebhookUrl');
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

/**
 * Construit l'aperçu du payload webhook
 */
export function buildPayloadPreview() {
    const subject = (DOMHelper.getElement('previewSubject')?.value || '').trim();
    const sender = (DOMHelper.getElement('previewSender')?.value || '').trim();
    const body = (DOMHelper.getElement('previewBody')?.value || '').trim();
    
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
    
    const pre = DOMHelper.getElement('payloadPreview');
    if (pre) pre.textContent = JSON.stringify(payload, null, 2);
}

// -------------------- Config Migration & Verification --------------------

/**
 * Gère la migration des configs vers Redis
 */
export async function handleConfigMigration() {
    const button = DOMHelper.getElement('migrateConfigsBtn');
    const messageId = 'migrateConfigsMsg';
    const logEl = DOMHelper.getElement('migrateConfigsLog');

    if (!button) {
        MessageHelper.showError(messageId, 'Bouton de migration introuvable.');
        return;
    }

    const confirmed = globalThis.confirm('Lancer la migration des configurations vers Redis ?');
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

/**
 * Gère la vérification du config store
 */
export async function handleConfigVerification() {
    const button = DOMHelper.getElement('verifyConfigStoreBtn');
    const messageId = 'verifyConfigStoreMsg';
    const logEl = DOMHelper.getElement('verifyConfigStoreLog');
    const logViewer = DOMHelper.getElement('verifyConfigStoreViewer');
    const routingRulesMsgEl = DOMHelper.getElement('routingRulesRedisInspectMsg');
    const routingRulesLogEl = DOMHelper.getElement('routingRulesRedisInspectLog');
    const routingRulesViewer = DOMHelper.getElement('routingRulesRedisInspectViewer');
    const rawToggle = DOMHelper.getElement('verifyConfigStoreRawToggle');
    const includeRaw = Boolean(rawToggle?.checked);

    if (!button) {
        MessageHelper.showError(messageId, 'Bouton de vérification introuvable.');
        return;
    }

    MessageHelper.setButtonLoading(button, true, '⏳ Vérification en cours...');
    MessageHelper.showInfo(messageId, 'Vérification des données Redis en cours...');
    if (logEl) {
        logEl.style.display = 'none';
        logEl.textContent = '';
    }
    if (logViewer) {
        logViewer.style.display = 'none';
        logViewer.textContent = '';
    }
    if (routingRulesMsgEl) {
        routingRulesMsgEl.textContent = '';
        routingRulesMsgEl.className = 'status-msg';
    }
    if (routingRulesLogEl) {
        routingRulesLogEl.style.display = 'none';
        routingRulesLogEl.textContent = '';
    }
    if (routingRulesViewer) {
        routingRulesViewer.style.display = 'none';
        routingRulesViewer.textContent = '';
    }

    try {
        const response = await ApiService.post('/api/verify_config_store', { raw: includeRaw });
        if (response?.success) {
            MessageHelper.showSuccess(messageId, 'Toutes les configurations sont conformes.');
        } else {
            MessageHelper.showError(
                messageId,
                response?.message || 'Des incohérences ont été détectées.'
            );
        }

        if (logEl && !includeRaw) {
            const lines = (response?.results || []).map((entry) => {
                const status = entry.valid ? 'OK' : `INVALID (${entry.message})`;
                const summary = entry.summary || '';
                return [ `${entry.key}: ${status}`, summary ].filter(Boolean).join('\n');
            });
            logEl.textContent = lines.length ? lines.join('\n\n') : 'Aucun résultat renvoyé.';
            logEl.style.display = 'block';
        }

        if (logViewer && includeRaw) {
            JsonViewer.render(logViewer, response?.results || [], { collapseDepth: 1 });
            logViewer.style.display = 'block';
        }

        const routingEntry = (response?.results || []).find(
            (entry) => entry && entry.key === 'routing_rules'
        );

        if (routingRulesMsgEl) {
            if (!routingEntry) {
                MessageHelper.showInfo(
                    'routingRulesRedisInspectMsg',
                    'Routage Dynamique: aucune entrée trouvée dans la vérification (clé routing_rules absente).'
                );
            } else if (routingEntry.valid) {
                MessageHelper.showSuccess(
                    'routingRulesRedisInspectMsg',
                    'Routage Dynamique: configuration persistée OK.'
                );
            } else {
                MessageHelper.showError(
                    'routingRulesRedisInspectMsg',
                    `Routage Dynamique: INVALID (${routingEntry.message || 'inconnu'}).`
                );
            }
        }

        if (routingRulesLogEl && !includeRaw) {
            if (!routingEntry) {
                routingRulesLogEl.textContent = '';
                routingRulesLogEl.style.display = 'none';
            } else {
                routingRulesLogEl.textContent = routingEntry.summary || '<vide>';
                routingRulesLogEl.style.display = 'block';
            }
        }

        if (routingRulesViewer) {
            if (!routingEntry || !includeRaw || !routingEntry.payload) {
                routingRulesViewer.textContent = '';
                routingRulesViewer.style.display = 'none';
            } else {
                JsonViewer.render(routingRulesViewer, routingEntry.payload, { collapseDepth: 1 });
                routingRulesViewer.style.display = 'block';
            }
        }
    } catch (error) {
        console.error('Erreur vérification config store:', error);
        MessageHelper.showError(messageId, 'Erreur de communication avec le serveur.');

        if (routingRulesMsgEl) {
            MessageHelper.showError('routingRulesRedisInspectMsg', 'Erreur de communication avec le serveur.');
        }
    } finally {
        MessageHelper.setButtonLoading(button, false);
    }
}
