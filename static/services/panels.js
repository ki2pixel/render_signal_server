import { ApiService } from './ApiService.js';
import { WebhookService } from './WebhookService.js';
import { MessageHelper } from '../utils/MessageHelper.js';
import { DOMHelper } from '../utils/DOMHelper.js';

// -------------------- Panneaux Pliables --------------------

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
            };

            header.addEventListener('click', togglePanel);
            header.addEventListener('keydown', (e) => {
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
 * Initialise le suivi des modifications pour les panneaux manuels
 */
export function initializeManualFieldsTracking() {
    const panels = document.querySelectorAll('.collapsible-panel');
    panels.forEach(panel => {
        // Ignorer le panneau de règles de routage car il gère son propre état
        if (panel.dataset.panel === 'routing-rules') return;
        
        const saveBtn = panel.querySelector('.panel-save-btn');
        if (saveBtn) {
            const inputs = panel.querySelectorAll('input, select, textarea');
            inputs.forEach(input => {
                input.addEventListener('input', () => {
                    panel.classList.add('modified');
                });
                input.addEventListener('change', () => {
                    panel.classList.add('modified');
                });
            });
        }
    });
}
