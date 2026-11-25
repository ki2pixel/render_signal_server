/**
 * dashboard.js — Orchestrateur principal du dashboard.
 *
 * Ce fichier ne contient aucune logique métier. Il importe les modules
 * spécialisés et orchestre le cycle de vie de la page (init → bind → load → cleanup).
 */
import { WebhookService } from './services/WebhookService.js';
import { LogService } from './services/LogService.js';
import { MessageHelper } from './utils/MessageHelper.js';
import { TabManager } from './components/TabManager.js';
import { RoutingRulesService } from './services/RoutingRulesService.js';
import { DOMHelper } from './utils/DOMHelper.js';

// Modules extraits
import { generateMagicLink, initMagicLinkPreference } from './services/magic_link.js';
import { handleDeployApplication, openDownloadPage } from './services/deploy.js';
import { updateGlobalStatus } from './services/status_banner.js';
import { debounce } from './utils/debounce.js';
import {
    initializeCollapsiblePanels,
    initializeManualFieldsTracking,
    updatePanelStatus,
    updatePanelIndicator,
    saveWebhookPanel,
} from './services/panels.js';
import {
    initializeAutoSave,
    initializeDataLossPrevention,
} from './services/autosave.js';
import {
    generateTimeOptions,
    loadTimeWindow,
    saveTimeWindow,
    loadGlobalWebhookTimeWindow,
    saveGlobalWebhookTimeWindow,
    loadRuntimeFlags,
    saveRuntimeFlags,
    saveRuntimeFlag,
    loadProcessingPrefsFromServer,
    saveProcessingPrefsToServer,
    loadLocalPreferences,
    saveLocalPreferences,
    exportAllConfig,
    handleImportConfigFile,
    validateWebhookUrlFromInput,
    buildPayloadPreview,
    handleConfigMigration,
    handleConfigVerification,
} from './services/config_io.js';

globalThis.DASHBOARD_BUILD = 'modular-2026-07-12-phase2';

let tabManager = null;
let routingRulesService = null;

// -------------------- Cycle de vie --------------------

document.addEventListener('DOMContentLoaded', async () => {
    try {
        tabManager = new TabManager();
        tabManager.init();
        tabManager.enhanceAccessibility();
        
        routingRulesService = new RoutingRulesService();
        
        bindEvents();
        
        initializeCollapsiblePanels();
        
        initializeAutoSave();
        
        initializeManualFieldsTracking();
        initializeDataLossPrevention(hasUnsavedChanges);
        initMagicLinkPreference();
        
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

// -------------------- Chargement des données --------------------

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
    } catch (e) {
        console.error('Erreur lors du chargement des données initiales:', e);
    }
}

// -------------------- Binding des événements --------------------

function bindEvents() {
    // Magic link
    bindElement('generateMagicLinkBtn', 'click', generateMagicLink);
    
    // Logs
    bindElement('clearLogsBtn', 'click', () => LogService.clearLogs());
    bindElement('exportLogsBtn', 'click', () => LogService.exportLogs());
    bindElement('logPeriodSelect', 'change', (e) => {
        LogService.changeLogPeriod(parseInt(e.target.value));
    });
    
    // Time window
    bindElement('saveTimeWindowBtn', 'click', () =>
        saveTimeWindow(updatePanelStatus, updatePanelIndicator)
    );
    bindElement('saveGlobalWebhookTimeBtn', 'click', () =>
        saveGlobalWebhookTimeWindow(updatePanelStatus, updatePanelIndicator)
    );
    
    // Runtime flags & processing prefs
    bindElement('runtimeFlagsSaveBtn', 'click', saveRuntimeFlags);
    bindElement('processingPrefsSaveBtn', 'click', saveProcessingPrefsToServer);

    // Ingestion Gmail Push : sauvegarde immédiate avec rollback en cas d'échec
    const gmailToggle = DOMHelper.getElement('gmailIngressEnabledToggle');
    if (gmailToggle) {
        gmailToggle.addEventListener('change', async () => {
            const previous = !gmailToggle.checked;
            const ok = await saveRuntimeFlag(
                'gmail_ingress_enabled',
                gmailToggle.checked,
                'gmailIngressMsg'
            );
            if (!ok) {
                gmailToggle.checked = previous;
            }
        });
    }
    
    // Config import/export
    bindElement('exportConfigBtn', 'click', exportAllConfig);
    const importConfigBtn = DOMHelper.getElement('importConfigBtn');
    const importConfigInput = DOMHelper.getElement('importConfigFile');
    if (importConfigBtn && importConfigInput) {
        importConfigBtn.addEventListener('click', () => importConfigInput.click());
        importConfigInput.addEventListener('change', handleImportConfigFile);
    }
    
    // Validation & preview
    bindElement('testWebhookUrl', 'input', debounce(validateWebhookUrlFromInput, 400));
    bindElement('validateWebhookUrlBtn', 'click', validateWebhookUrlFromInput);
    bindElement('buildPayloadPreviewBtn', 'click', buildPayloadPreview);
    ['previewSubject', 'previewSender', 'previewBody'].forEach(id => {
        bindElement(id, 'input', debounce(buildPayloadPreview, 200));
    });
    
    // Status
    bindElement('refreshStatusBtn', 'click', updateGlobalStatus);
    
    // Panel save buttons
    document.querySelectorAll('.panel-save-btn[data-panel]').forEach(btn => {
        btn.addEventListener('click', () => {
            const panelType = btn.dataset.panel;
            if (panelType) {
                saveWebhookPanel(panelType);
            }
        });
    });
    
    // Populate time dropdowns
    ['webhooksTimeStart', 'webhooksTimeEnd', 'globalWebhookTimeStart', 'globalWebhookTimeEnd']
        .forEach(id => {
            const select = DOMHelper.getElement(id);
            if (select) {
                select.replaceChildren(...generateTimeOptions(30));
            }
        });
    
    // Deployment & admin
    bindElement('deployApplicationBtn', 'click', handleDeployApplication);
    bindElement('migrateConfigsBtn', 'click', handleConfigMigration);
    bindElement('verifyConfigStoreBtn', 'click', handleConfigVerification);
    
    // Download page
    bindElement('openDownloadPageBtn', 'click', openDownloadPage);
}

/**
 * Helper pour binder un événement sur un élément via DOMHelper
 * @param {string} id - Identifiant data-target
 * @param {string} event - Type d'événement
 * @param {Function} handler - Callback
 */
function bindElement(id, event, handler) {
    const el = DOMHelper.getElement(id);
    if (el) {
        el.addEventListener(event, handler);
    }
}

// -------------------- État non sauvegardé --------------------

function hasUnsavedChanges() {
    const modifiedPanels = document.querySelectorAll('.modified');
    if (modifiedPanels.length > 0) {
        return true;
    }
    
    if (routingRulesService && routingRulesService.hasUnsavedChanges()) {
        return true;
    }
    
    return false;
}

// -------------------- Nettoyage --------------------

globalThis.addEventListener('beforeunload', () => {
    LogService.stopLogPolling();
    
    if (tabManager) {
        tabManager.destroy();
    }
    
    saveLocalPreferences();
});
