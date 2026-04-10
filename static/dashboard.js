import { ApiService } from './services/ApiService.js';
import { WebhookService } from './services/WebhookService.js';
import { LogService } from './services/LogService.js';
import { MessageHelper } from './utils/MessageHelper.js';
import { TabManager } from './components/TabManager.js';
import { RoutingRulesService } from './services/RoutingRulesService.js?v=20260125-routing-fallback';
import { JsonViewer } from './components/JsonViewer.js?v=20260202-json-viewer';

window.DASHBOARD_BUILD = 'modular-2026-02-02-json-viewer';

let tabManager = null;
let routingRulesService = null;

document.addEventListener('DOMContentLoaded', async () => {
    try {
        tabManager = new TabManager();
        tabManager.init();
        tabManager.enhanceAccessibility();
        
        await initializeServices();
        
        bindEvents();
        
        initializeCollapsiblePanels();
        
        initializeAutoSave();
        
        await loadInitialData();
        
        if (routingRulesService) {
            await routingRulesService.init();
        }

        LogService.startLogPolling();
        
    } catch (e) {
        console.error('Erreur lors de l\'initialisation du dashboard:', e);
        MessageHelper.showError('global', 'Erreur lors du chargement du dashboard');
    }
});

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

async function handleConfigVerification() {
    const button = document.getElementById('verifyConfigStoreBtn');
    const messageId = 'verifyConfigStoreMsg';
    const logEl = document.getElementById('verifyConfigStoreLog');
    const logViewer = document.getElementById('verifyConfigStoreViewer');
    const routingRulesMsgEl = document.getElementById('routingRulesRedisInspectMsg');
    const routingRulesLogEl = document.getElementById('routingRulesRedisInspectLog');
    const routingRulesViewer = document.getElementById('routingRulesRedisInspectViewer');
    const rawToggle = document.getElementById('verifyConfigStoreRawToggle');
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

async function initializeServices() {
    routingRulesService = new RoutingRulesService();
}

function bindEvents() {
    const magicLinkBtn = document.getElementById('generateMagicLinkBtn');
    if (magicLinkBtn) {
        magicLinkBtn.addEventListener('click', generateMagicLink);
    }
    
    const saveWebhookBtn = document.getElementById('saveConfigBtn');
    if (saveWebhookBtn) {
        saveWebhookBtn.addEventListener('click', () => WebhookService.saveConfig());
    }
    
    
    const clearLogsBtn = document.getElementById('clearLogsBtn');
    if (clearLogsBtn) {
        clearLogsBtn.addEventListener('click', () => LogService.clearLogs());
    }
    
    const exportLogsBtn = document.getElementById('exportLogsBtn');
    if (exportLogsBtn) {
        exportLogsBtn.addEventListener('click', () => LogService.exportLogs());
    }
    
    const logPeriodSelect = document.getElementById('logPeriodSelect');
    if (logPeriodSelect) {
        logPeriodSelect.addEventListener('change', (e) => {
            LogService.changeLogPeriod(parseInt(e.target.value));
        });
    }
    
    const saveTimeWindowBtn = document.getElementById('saveTimeWindowBtn');
    if (saveTimeWindowBtn) {
        saveTimeWindowBtn.addEventListener('click', saveTimeWindow);
    }
    
    const saveGlobalWebhookTimeBtn = document.getElementById('saveGlobalWebhookTimeBtn');
    if (saveGlobalWebhookTimeBtn) {
        saveGlobalWebhookTimeBtn.addEventListener('click', saveGlobalWebhookTimeWindow);
    }
    
    
    const saveRuntimeFlagsBtn = document.getElementById('runtimeFlagsSaveBtn');
    if (saveRuntimeFlagsBtn) {
        saveRuntimeFlagsBtn.addEventListener('click', saveRuntimeFlags);
    }
    
    const saveProcessingPrefsBtn = document.getElementById('processingPrefsSaveBtn');
    if (saveProcessingPrefsBtn) {
        saveProcessingPrefsBtn.addEventListener('click', saveProcessingPrefsToServer);
    }
    
    const exportConfigBtn = document.getElementById('exportConfigBtn');
    if (exportConfigBtn) {
        exportConfigBtn.addEventListener('click', exportAllConfig);
    }
    
    const importConfigBtn = document.getElementById('importConfigBtn');
    const importConfigInput = document.getElementById('importConfigFile');
    if (importConfigBtn && importConfigInput) {
        importConfigBtn.addEventListener('click', () => importConfigInput.click());
        importConfigInput.addEventListener('change', handleImportConfigFile);
    }
    
    const testWebhookUrl = document.getElementById('testWebhookUrl');
    if (testWebhookUrl) {
        testWebhookUrl.addEventListener('input', validateWebhookUrlFromInput);
    }
    
    const previewInputs = ['previewSubject', 'previewSender', 'previewBody'];
    previewInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', buildPayloadPreview);
        }
    });
    
    
    const refreshStatusBtn = document.getElementById('refreshStatusBtn');
    if (refreshStatusBtn) {
        refreshStatusBtn.addEventListener('click', updateGlobalStatus);
    }
    
    document.querySelectorAll('.panel-save-btn[data-panel]').forEach(btn => {
        btn.addEventListener('click', () => {
            const panelType = btn.dataset.panel;
            if (panelType) {
                saveWebhookPanel(panelType);
            }
        });
    });
    
    // Populate dropdowns with options
    const timeDropdowns = ['webhooksTimeStart', 'webhooksTimeEnd', 'globalWebhookTimeStart', 'globalWebhookTimeEnd'];
    timeDropdowns.forEach(id => {
        const select = document.getElementById(id);
        if (select) {
            select.innerHTML = generateTimeOptions(30);
        }
    });
    
    
    const restartBtn = document.getElementById('restartServerBtn');
    if (restartBtn) {
        restartBtn.addEventListener('click', handleDeployApplication);
    }
    
    const migrateBtn = document.getElementById('migrateConfigsBtn');
    if (migrateBtn) {
        migrateBtn.addEventListener('click', handleConfigMigration);
    }

    const verifyBtn = document.getElementById('verifyConfigStoreBtn');
    if (verifyBtn) {
        verifyBtn.addEventListener('click', handleConfigVerification);
    }
    
    // Metrics toggle event - REMOVED: Monitoring section deleted from dashboard
    // const enableMetricsToggle = document.getElementById('enableMetricsToggle');
    // if (enableMetricsToggle) {
    //     enableMetricsToggle.addEventListener('change', async () => {
    //         saveLocalPreferences();
    //         if (enableMetricsToggle.checked) {
    //             await computeAndRenderMetrics();
    //         } else {
    //             clearMetrics();
    //         }
    //     });
    // }
}

async function loadInitialData() {
    try {
        await Promise.all([
            WebhookService.loadConfig(),
            loadTimeWindow(),
            loadRuntimeFlags(),
            loadProcessingPrefsFromServer(),
            loadLocalPreferences()
        ]);

        
        await loadGlobalWebhookTimeWindow();
        
        await LogService.loadAndRenderLogs();
        
        await updateGlobalStatus();
        
        // Trigger metrics computation if toggle is enabled - REMOVED: Monitoring section deleted
        // const enableMetricsToggle = document.getElementById('enableMetricsToggle');
        // if (enableMetricsToggle && enableMetricsToggle.checked) {
        //     await computeAndRenderMetrics();
        // }
        
    } catch (e) {
        console.error('Erreur lors du chargement des données initiales:', e);
    }
}

// Metrics functions - REMOVED: Monitoring section deleted from dashboard
// async function computeAndRenderMetrics() {
//     try {
//         const res = await ApiService.get('/api/webhook_logs?days=1');
//         if (!res.ok) { 
//             if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
//                 console.warn('metrics: non-200', res.status);
//             }
//             clearMetrics(); return; 
//         }
//         const data = await res.json();
//         const logs = (data.success && Array.isArray(data.logs)) ? data.logs : [];
//         const total = logs.length;
//         const sent = logs.filter(l => l.status === 'success').length;
//         const errors = logs.filter(l => l.status === 'error').length;
//         const successRate = total ? Math.round((sent / total) * 100) : 0;
//         setMetric('metricEmailsProcessed', String(total));
//         setMetric('metricWebhooksSent', String(sent));
//         setMetric('metricErrors', String(errors));
//         setMetric('metricSuccessRate', String(successRate));
//         renderMiniChart(logs);
//     } catch (e) {
//         if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
//             console.warn('metrics error', e);
//         }
//         clearMetrics();
//     }
// }

// function clearMetrics() {
//     setMetric('metricEmailsProcessed', '—');
//     setMetric('metricWebhooksSent', '—');
//     setMetric('metricErrors', '—');
//     setMetric('metricSuccessRate', '—');
//     const chart = document.getElementById('metricsMiniChart');
//     if (chart) chart.innerHTML = '';
// }

// function setMetric(id, text) {
//     const el = document.getElementById(id);
//     if (el) el.textContent = text;
// }

// function renderMiniChart(logs) {
//     const chart = document.getElementById('metricsMiniChart');
//     if (!chart) return;
//     chart.innerHTML = '';
//     const width = chart.clientWidth || 300;
//     const height = chart.clientHeight || 60;
//     const canvas = document.createElement('canvas');
//     canvas.width = width; canvas.height = height;
//     const ctx = canvas.getContext('2d');
    
//     // Simple line chart implementation
//     const padding = 5;
//     const chartWidth = width - 2 * padding;
//     const chartHeight = height - 2 * padding;
    
//     // Group logs by hour
//     const hourlyData = new Array(24).fill(0);
//     logs.forEach(log => {
//         const hour = new Date(log.timestamp).getHours();
//         hourlyData[hour]++;
//     });
    
//     const maxCount = Math.max(...hourlyData, 1);
//     const stepX = chartWidth / 23;
    
//     ctx.strokeStyle = '#4CAF50';
//     ctx.lineWidth = 2;
//     ctx.beginPath();
    
//     hourlyData.forEach((count, i) => {
//         const x = padding + i * stepX;
//         const y = padding + chartHeight - (count / maxCount) * chartHeight;
        
//         if (i === 0) {
//             ctx.moveTo(x, y);
//         } else {
//             ctx.lineTo(x, y);
//         }
//     });
    
//     ctx.stroke();
//     chart.appendChild(canvas);
// }

function showCopiedFeedback() {
    let toast = document.querySelector('.copied-feedback');
    if (!toast) {
        toast = document.createElement('div');
        toast.className = 'copied-feedback';
        toast.textContent = '🔗 Magic link copié dans le presse-papiers !';
        document.body.appendChild(toast);
    }
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

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


// Time window helpers
function generateTimeOptions(stepMinutes = 30) {
    const options = ['<option value="">Sélectionner...</option>'];
    for (let hour = 0; hour < 24; hour++) {
        for (let minute = 0; minute < 60; minute += stepMinutes) {
            const timeStr = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
            options.push(`<option value="${timeStr}">${timeStr}</option>`);
        }
    }
    return options.join('');
}

function generateHourOptions() {
    const options = ['<option value="">Sélectionner...</option>'];
    for (let hour = 0; hour < 24; hour++) {
        const label = `${hour.toString().padStart(2, '0')}h`;
        options.push(`<option value="${hour}">${label}</option>`);
    }
    return options.join('');
}

function setSelectedOption(selectElement, value) {
    if (!selectElement) return;
    // Try to find exact match first
    for (let i = 0; i < selectElement.options.length; i++) {
        if (selectElement.options[i].value === value || selectElement.options[i].value === value.toString()) {
            selectElement.selectedIndex = i;
            return;
        }
    }
    // If no match, select first (empty) option
    selectElement.selectedIndex = 0;
}

// Time window
async function loadTimeWindow() {
    const applyWindowValues = (startValue = '', endValue = '') => {
        const startInput = document.getElementById('webhooksTimeStart');
        const endInput = document.getElementById('webhooksTimeEnd');
        if (startInput) setSelectedOption(startInput, startValue || '');
        if (endInput) setSelectedOption(endInput, endValue || '');
        renderTimeWindowDisplay(startValue || '', endValue || '');
    };
    
    try {
        // 0) Source principale : fenêtre horaire globale (ancien endpoint)
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
        // 2) Fallback: ancienne source (time window override)
        const data = await ApiService.get('/api/get_webhook_time_window');
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
    
    // For dropdowns, validation is simpler - format is guaranteed HH:MM
    if (start && !/^\d{2}:\d{2}$/.test(start)) {
        MessageHelper.showError('timeWindowMsg', 'Veuillez sélectionner une heure valide.');
        return false;
    }
    
    if (end && !/^\d{2}:\d{2}$/.test(end)) {
        MessageHelper.showError('timeWindowMsg', 'Veuillez sélectionner une heure valide.');
        return false;
    }
    
    // No normalization needed for dropdowns - format is already HH:MM
    
    try {
        const data = await ApiService.post('/api/set_webhook_time_window', { 
            start: start, 
            end: end 
        });
        
        if (data.success) {
            MessageHelper.showSuccess('timeWindowMsg', 'Fenêtre horaire enregistrée avec succès !');
            updatePanelStatus('time-window', true);
            updatePanelIndicator('time-window');
            
            // Mettre à jour les inputs selon la normalisation renvoyée par le backend
            if (startInput && Object.prototype.hasOwnProperty.call(data, 'webhooks_time_start')) {
                setSelectedOption(startInput, data.webhooks_time_start || '');
            }
            if (endInput && Object.prototype.hasOwnProperty.call(data, 'webhooks_time_end')) {
                setSelectedOption(endInput, data.webhooks_time_end || '');
            }
            
            renderTimeWindowDisplay(data.webhooks_time_start || start, data.webhooks_time_end || end);
            
            // S'assurer que la source persistée est rechargée
            await loadTimeWindow();
            return true;
        } else {
            MessageHelper.showError('timeWindowMsg', data.message || 'Erreur lors de la sauvegarde.');
            updatePanelStatus('time-window', false);
            return false;
        }
    } catch (e) {
        MessageHelper.showError('timeWindowMsg', 'Erreur de communication avec le serveur.');
        updatePanelStatus('time-window', false);
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


// Runtime flags
async function loadRuntimeFlags() {
    try {
        const data = await ApiService.get('/api/get_runtime_flags');
        
        if (data.success) {
            const flags = data.flags || {};

            const disableDedup = document.getElementById('disableEmailIdDedupToggle');
            if (disableDedup && Object.prototype.hasOwnProperty.call(flags, 'disable_email_id_dedup')) {
                disableDedup.checked = !!flags.disable_email_id_dedup;
            }

            const allowCustom = document.getElementById('allowCustomWithoutLinksToggle');
            if (
                allowCustom
                && Object.prototype.hasOwnProperty.call(flags, 'allow_custom_webhook_without_links')
            ) {
                allowCustom.checked = !!flags.allow_custom_webhook_without_links;
            }

            const gmailIngressEnabled = document.getElementById('gmailIngressEnabledToggle');
            if (
                gmailIngressEnabled
                && Object.prototype.hasOwnProperty.call(flags, 'gmail_ingress_enabled')
            ) {
                gmailIngressEnabled.checked = !!flags.gmail_ingress_enabled;
            }
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
        const disableDedup = document.getElementById('disableEmailIdDedupToggle');
        const allowCustom = document.getElementById('allowCustomWithoutLinksToggle');
        const gmailIngressEnabled = document.getElementById('gmailIngressEnabledToggle');

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

// Processing preferences
async function loadProcessingPrefsFromServer() {
    try {
        const data = await ApiService.get('/api/processing_prefs');
        
        if (data.success) {
            const prefs = data.prefs || {};
            
            // Mapping des préférences vers les éléments UI avec les bons IDs
            const mappings = {
                // Filtres
                'exclude_keywords': 'excludeKeywords',
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

async function saveProcessingPrefsToServer() {
    const btn = document.getElementById('processingPrefsSaveBtn');
    const msgId = 'processingPrefsMsg';
    
    MessageHelper.setButtonLoading(btn, true);
    
    try {
        // Mapping des éléments UI vers les clés de préférences
        const mappings = {
            // Filtres
            'excludeKeywords': 'exclude_keywords',
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

// Local preferences
function loadLocalPreferences() {
    try {
        const raw = localStorage.getItem('dashboard_prefs_v1');
        if (!raw) {
            // Default preferences - REMOVED: enableMetricsToggle default
            // const enableMetricsToggle = document.getElementById('enableMetricsToggle');
            // if (enableMetricsToggle) {
            //     enableMetricsToggle.checked = true;
            // }
            return;
        }
        
        const prefs = JSON.parse(raw);
        
        // Apply metrics preference if exists - REMOVED: Monitoring section deleted
        // if (prefs.hasOwnProperty('enableMetricsToggle')) {
        //     const enableMetricsToggle = document.getElementById('enableMetricsToggle');
        //     if (enableMetricsToggle) {
        //         enableMetricsToggle.checked = prefs.enableMetricsToggle;
        //     }
        // }
        
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
        
        // Always save enableMetricsToggle preference - REMOVED: Monitoring section deleted
        // const enableMetricsToggle = document.getElementById('enableMetricsToggle');
        // if (enableMetricsToggle) {
        //     prefs.enableMetricsToggle = enableMetricsToggle.checked;
        // }
        
        localStorage.setItem('dashboard_prefs_v1', JSON.stringify(prefs));
    } catch (e) {
        console.warn('Erreur sauvegarde préférences locales:', e);
    }
}

// Configuration management
async function exportAllConfig() {
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
        const start = obj.time_window.webhooks_time_start ?? '';
        const end = obj.time_window.webhooks_time_end ?? '';
        await ApiService.post('/api/set_webhook_time_window', { start, end });
        await loadTimeWindow();
    }

    // Processing prefs
    if (obj?.processing_prefs?.prefs && typeof obj.processing_prefs.prefs === 'object') {
        await ApiService.post('/api/processing_prefs', obj.processing_prefs.prefs);
        await loadProcessingPrefsFromServer();
    }
}

// Validation
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


// Fenêtre horaire global webhook
async function loadGlobalWebhookTimeWindow() {
    const applyGlobalWindowValues = (startValue = '', endValue = '') => {
        const startInput = document.getElementById('globalWebhookTimeStart');
        const endInput = document.getElementById('globalWebhookTimeEnd');
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

async function saveGlobalWebhookTimeWindow() {
    const startInput = document.getElementById('globalWebhookTimeStart');
    const endInput = document.getElementById('globalWebhookTimeEnd');
    const start = startInput.value.trim();
    const end = endInput.value.trim();
    
    // Validation des formats - dropdowns guarantee HH:MM format
    if (start && !/^\d{2}:\d{2}$/.test(start)) {
        MessageHelper.showError('globalWebhookTimeMsg', 'Veuillez sélectionner une heure valide.');
        return false;
    }
    
    if (end && !/^\d{2}:\d{2}$/.test(end)) {
        MessageHelper.showError('globalWebhookTimeMsg', 'Veuillez sélectionner une heure valide.');
        return false;
    }
    
    // No normalization needed for dropdowns - format is already HH:MM
    
    try {
        const data = await ApiService.post('/api/webhooks/time-window', { 
            start: start, 
            end: end 
        });
        
        if (data.success) {
            MessageHelper.showSuccess('globalWebhookTimeMsg', 'Fenêtre horaire webhook enregistrée avec succès !');
            updatePanelStatus('time-window', true);
            updatePanelIndicator('time-window');
            
            // Mettre à jour les inputs selon la normalisation renvoyée par le backend
            if (startInput && Object.prototype.hasOwnProperty.call(data, 'webhooks_time_start')) {
                setSelectedOption(startInput, data.webhooks_time_start || '');
            }
            if (endInput && Object.prototype.hasOwnProperty.call(data, 'webhooks_time_end')) {
                setSelectedOption(endInput, data.webhooks_time_end || '');
            }
            await loadGlobalWebhookTimeWindow();
            return true;
        } else {
            MessageHelper.showError('globalWebhookTimeMsg', data.message || 'Erreur lors de la sauvegarde.');
            updatePanelStatus('time-window', false);
            return false;
        }
    } catch (e) {
        MessageHelper.showError('globalWebhookTimeMsg', 'Erreur de communication avec le serveur.');
        updatePanelStatus('time-window', false);
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
    const webhookUrlPlaceholder = document.getElementById('webhookUrl')?.placeholder || '';
    const sslToggle = document.getElementById('sslVerifyToggle');
    const sendingToggle = document.getElementById('webhookSendingToggle');
    const deliveryModeSelect = document.getElementById('webhookDeliveryMode');
    const fallbackOn415Toggle = document.getElementById('webhookFallbackOn415Toggle');
    const sslVerify = sslToggle?.checked ?? true;
    const sendingEnabled = sendingToggle?.checked ?? true;
    const deliveryMode = deliveryModeSelect?.value || 'json';

    const payload = {
        webhook_ssl_verify: sslVerify,
        webhook_sending_enabled: sendingEnabled,
        webhook_delivery_mode: deliveryMode,
        webhook_fallback_on_415: fallbackOn415Toggle?.checked ?? true,
    };

    const trimmedWebhookUrl = webhookUrl.trim();
    if (trimmedWebhookUrl && !MessageHelper.isPlaceholder(trimmedWebhookUrl, webhookUrlPlaceholder)) {
        payload.webhook_url = trimmedWebhookUrl;
    }

    return payload;
}

/**
 * Collecte les données du panneau fenêtre horaire
 */
function collectTimeWindowData() {
    const startInput = document.getElementById('globalWebhookTimeStart');
    const endInput = document.getElementById('globalWebhookTimeEnd');
    const start = startInput?.value?.trim() || '';
    const end = endInput?.value?.trim() || '';
    
    // Normaliser les formats
    const normalizedStart = start ? (MessageHelper.normalizeTimeFormat(start) || '') : '';
    const normalizedEnd = end ? (MessageHelper.normalizeTimeFormat(end) || '') : '';
    
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
        const result = await ApiService.post('/api/processing_prefs', prefsData);
        
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

    const retryCountRaw = document.getElementById('retryCount')?.value;
    if (retryCountRaw !== undefined && String(retryCountRaw).trim() !== '') {
        data.retry_count = parseInt(String(retryCountRaw).trim(), 10);
    }

    const retryDelayRaw = document.getElementById('retryDelaySec')?.value;
    if (retryDelayRaw !== undefined && String(retryDelayRaw).trim() !== '') {
        data.retry_delay_sec = parseInt(String(retryDelayRaw).trim(), 10);
    }

    const webhookTimeoutRaw = document.getElementById('webhookTimeoutSec')?.value;
    if (webhookTimeoutRaw !== undefined && String(webhookTimeoutRaw).trim() !== '') {
        data.webhook_timeout_sec = parseInt(String(webhookTimeoutRaw).trim(), 10);
    }

    const rateLimitRaw = document.getElementById('rateLimitPerHour')?.value;
    if (rateLimitRaw !== undefined && String(rateLimitRaw).trim() !== '') {
        data.rate_limit_per_hour = parseInt(String(rateLimitRaw).trim(), 10);
    }

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
