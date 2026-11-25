import { ApiService } from './ApiService.js';
import { MessageHelper } from '../utils/MessageHelper.js';
import { DOMHelper } from '../utils/DOMHelper.js';
import { createListenerRegistry } from '../utils/listenerRegistry.js';

const _listeners = createListenerRegistry();

function _addTrackedListener(el, type, handler) {
    _listeners.add(el, type, handler);
}

// -------------------- Panneaux Pliables --------------------

const _panelStateKey = (panelName) => `dashboard_panel_state_${panelName}`;

/**
 * Mémorise l'état ouvert/replié d'un panneau (localStorage, best-effort).
 * @param {string} panelName - Nom du panneau (data-panel)
 * @param {boolean} collapsed - Vrai si replié
 */
function _persistPanelState(panelName, collapsed) {
    try {
        localStorage.setItem(_panelStateKey(panelName), collapsed ? 'collapsed' : 'expanded');
    } catch {
        // localStorage indisponible (mode privé, quota) — ignorer
    }
}

/**
 * Restaure l'état mémorisé d'un panneau. Sans mémorisation, conserve
 * la classe .collapsed définie dans le HTML.
 * @param {Element} panel - Élément .collapsible-panel
 * @returns {boolean|null} true = replié, false = ouvert, null = pas de préférence
 */
function _restorePanelState(panel) {
    try {
        const saved = localStorage.getItem(_panelStateKey(panel.dataset.panel));
        if (saved === 'collapsed') return true;
        if (saved === 'expanded') return false;
    } catch {
        // ignorer
    }
    return null;
}

/**
 * Initialise les panneaux pliables des webhooks avec accessibilité clavier
 */
export function initializeCollapsiblePanels() {
    const panels = document.querySelectorAll('.collapsible-panel');
    
    panels.forEach(panel => {
        const header = panel.querySelector('.panel-header');
        const content = panel.querySelector('.panel-content');
        const toggleIcon = panel.querySelector('.toggle-icon');
        
        if (header && content && toggleIcon) {
            const remembered = _restorePanelState(panel);
            if (remembered === true) {
                content.classList.add('collapsed');
                toggleIcon.classList.add('rotated');
            } else if (remembered === false) {
                content.classList.remove('collapsed');
                toggleIcon.classList.remove('rotated');
            }

            // Accessibilité WCAG AA
            header.setAttribute('role', 'button');
            header.setAttribute('tabindex', '0');
            header.setAttribute('aria-expanded', String(!content.classList.contains('collapsed')));

            const togglePanel = () => {
                const isCollapsed = content.classList.contains('collapsed');
                
                if (isCollapsed) {
                    content.classList.remove('collapsed');
                    toggleIcon.classList.remove('rotated');
                    header.setAttribute('aria-expanded', 'true');
                } else {
                    content.classList.add('collapsed');
                    toggleIcon.classList.add('rotated');
                    header.setAttribute('aria-expanded', 'false');
                }
                _persistPanelState(panel.dataset.panel, content.classList.contains('collapsed'));
            };

            _addTrackedListener(header, 'click', togglePanel);
            _addTrackedListener(header, 'keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    togglePanel();
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
export function updatePanelStatus(panelType, success) {
    const statusElement = DOMHelper.getElement(`${panelType}-status`);
    const panelElement = document.querySelector(`.collapsible-panel[data-panel="${panelType}"]`);
    
    if (statusElement) {
        if (success) {
            statusElement.textContent = 'Sauvegardé';
            statusElement.classList.add('saved');
            if (panelElement) {
                panelElement.classList.remove('modified');
            }
        } else {
            statusElement.textContent = 'Erreur';
            statusElement.classList.remove('saved');
        }
        
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
export function updatePanelIndicator(panelType) {
    const indicator = DOMHelper.getElement(`${panelType}-indicator`);
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
 * Collecte les données du panneau URLs & SSL
 * @returns {object} Données collectées
 */
export function collectUrlsData() {
    const webhookUrl = DOMHelper.getElement('webhookUrl')?.value || '';
    const webhookUrlPlaceholder = DOMHelper.getElement('webhookUrl')?.placeholder || '';
    const sslToggle = DOMHelper.getElement('sslVerifyToggle');
    const sendingToggle = DOMHelper.getElement('webhookSendingToggle');
    const deliveryModeSelect = DOMHelper.getElement('webhookDeliveryMode');
    const fallbackOn415Toggle = DOMHelper.getElement('webhookFallbackOn415Toggle');
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
 * @returns {object} Données collectées
 */
export function collectTimeWindowData() {
    const startInput = DOMHelper.getElement('globalWebhookTimeStart');
    const endInput = DOMHelper.getElement('globalWebhookTimeEnd');
    const start = startInput?.value?.trim() || '';
    const end = endInput?.value?.trim() || '';
    
    const normalizedStart = start ? (MessageHelper.normalizeTimeFormat(start) || '') : '';
    const normalizedEnd = end ? (MessageHelper.normalizeTimeFormat(end) || '') : '';
    
    return {
        start: normalizedStart,
        end: normalizedEnd
    };
}

/**
 * Collecte les données du panneau d'absence
 * @returns {object} Données collectées
 */
export function collectAbsenceData() {
    const toggle = DOMHelper.getElement('absencePauseToggle');
    const dayCheckboxes = document.querySelectorAll('input[name="absencePauseDay"]:checked');
    
    return {
        absence_pause_enabled: toggle ? toggle.checked : false,
        absence_pause_days: Array.from(dayCheckboxes).map(cb => cb.value)
    };
}

/**
 * Sauvegarde un panneau de configuration webhook
 * @param {string} panelType - Type de panneau (urls-ssl, absence, time-window)
 */
export async function saveWebhookPanel(panelType) {
    const saveBtn = document.querySelector(`.panel-save-btn[data-panel="${panelType}"]`);
    if (saveBtn?.disabled) return; // garde anti double-soumis

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
        
        MessageHelper.setButtonLoading(saveBtn, true, '⏳ Enregistrement...');
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
        MessageHelper.showError(`${panelType}-msg`, MessageHelper.describeError(error, 'Erreur lors de la sauvegarde'));
        updatePanelStatus(panelType, false);
    } finally {
        MessageHelper.setButtonLoading(saveBtn, false);
    }
}

/**
 * Initialise le suivi des modifications pour les panneaux manuels
 */
export function initializeManualFieldsTracking() {
    const panels = document.querySelectorAll('.collapsible-panel');
    panels.forEach(panel => {
        if (panel.dataset.panel === 'routing-rules') return;
        
        const saveBtn = panel.querySelector('.panel-save-btn');
        if (saveBtn) {
            const inputs = panel.querySelectorAll('input, select, textarea');
            inputs.forEach(input => {
                _addTrackedListener(input, 'input', () => {
                    panel.classList.add('modified');
                });
                _addTrackedListener(input, 'change', () => {
                    panel.classList.add('modified');
                });
            });
        }
    });
}

/**
 * Nettoie tous les listeners enregistrés pour les panneaux.
 */
export function destroy() {
    _listeners.removeAll();
}
