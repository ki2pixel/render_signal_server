import { ApiService } from './ApiService.js';
import { DOMHelper } from '../utils/DOMHelper.js';

const _registeredHandlers = [];

/**
 * Fonction de debounce pour limiter les appels
 * @param {Function} func - Fonction à débouncer
 * @param {number} wait - Temps d'attente en ms
 * @returns {Function} Fonction débouncée
 */
export function debounce(func, wait) {
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

/**
 * Enregistre un gestionnaire d'événement traçable
 * @param {Element} el
 * @param {string} type
 * @param {Function} handler
 */
function _addTrackedListener(el, type, handler) {
    el.addEventListener(type, handler);
    _registeredHandlers.push({ el, type, handler });
}

/**
 * Initialise l'auto-sauvegarde intelligente
 */
export function initializeAutoSave() {
    const autoSaveFields = [
        'attachmentDetectionToggle',
        'retryCount', 
        'retryDelaySec',
        'webhookTimeoutSec',
        'rateLimitPerHour',
        'notifyOnFailureToggle'
    ];
    
    autoSaveFields.forEach(fieldId => {
        const field = DOMHelper.getElement(fieldId);
        if (field) {
            _addTrackedListener(field, 'change', () => {
                markSectionAsModified(fieldId);
                handleAutoSaveChange(fieldId);
            });
            _addTrackedListener(field, 'input', () => markSectionAsModified(fieldId));
            _addTrackedListener(field, 'input', debounce(() => handleAutoSaveChange(fieldId), 2000));
        }
    });
    
    const preferenceTextareas = [
        'excludeKeywordsRecadrage',
        'excludeKeywordsAutorepondeur',
        'excludeKeywords',
        'senderPriority'
    ];
    
    preferenceTextareas.forEach(fieldId => {
        const field = DOMHelper.getElement(fieldId);
        if (field) {
            _addTrackedListener(field, 'input', () => markSectionAsModified(fieldId));
            _addTrackedListener(field, 'input', debounce(() => handleAutoSaveChange(fieldId), 3000));
        }
    });
}

/**
 * Gère les changements pour l'auto-sauvegarde
 * @param {string} fieldId - ID du champ modifié
 */
async function handleAutoSaveChange(fieldId) {
    try {
        markSectionAsModified(fieldId);
        
        const prefsData = collectPreferencesData();
        const result = await ApiService.post('/api/processing_prefs', prefsData);
        
        if (result.success) {
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
 * @returns {object} Données de préférences
 */
export function collectPreferencesData() {
    const data = {};
    
    const excludeKeywordsRecadrage = DOMHelper.getElement('excludeKeywordsRecadrage')?.value || '';
    const excludeKeywordsAutorepondeur = DOMHelper.getElement('excludeKeywordsAutorepondeur')?.value || '';
    const excludeKeywords = DOMHelper.getElement('excludeKeywords')?.value || '';
    
    data.exclude_keywords_recadrage = excludeKeywordsRecadrage ? 
        excludeKeywordsRecadrage.split('\n').map(line => line.trim()).filter(line => line) : [];
    data.exclude_keywords_autorepondeur = excludeKeywordsAutorepondeur ? 
        excludeKeywordsAutorepondeur.split('\n').map(line => line.trim()).filter(line => line) : [];
    data.exclude_keywords = excludeKeywords ? 
        excludeKeywords.split('\n').map(line => line.trim()).filter(line => line) : [];
    
    data.require_attachments = DOMHelper.getElement('attachmentDetectionToggle')?.checked || false;

    const retryCountRaw = DOMHelper.getElement('retryCount')?.value;
    if (retryCountRaw !== undefined && String(retryCountRaw).trim() !== '') {
        data.retry_count = parseInt(String(retryCountRaw).trim(), 10);
    }

    const retryDelayRaw = DOMHelper.getElement('retryDelaySec')?.value;
    if (retryDelayRaw !== undefined && String(retryDelayRaw).trim() !== '') {
        data.retry_delay_sec = parseInt(String(retryDelayRaw).trim(), 10);
    }

    const webhookTimeoutRaw = DOMHelper.getElement('webhookTimeoutSec')?.value;
    if (webhookTimeoutRaw !== undefined && String(webhookTimeoutRaw).trim() !== '') {
        data.webhook_timeout_sec = parseInt(String(webhookTimeoutRaw).trim(), 10);
    }

    const rateLimitRaw = DOMHelper.getElement('rateLimitPerHour')?.value;
    if (rateLimitRaw !== undefined && String(rateLimitRaw).trim() !== '') {
        data.rate_limit_per_hour = parseInt(String(rateLimitRaw).trim(), 10);
    }

    data.notify_on_failure = DOMHelper.getElement('notifyOnFailureToggle')?.checked || false;
    
    const senderPriorityText = DOMHelper.getElement('senderPriority')?.value || '{}';
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
    const field = DOMHelper.getElement(fieldId);
    if (!field) return null;
    
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
        indicator = document.createElement('div');
        indicator.className = 'section-indicator';
        
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
export function showAutoSaveFeedback(fieldId, success, message = '') {
    const field = DOMHelper.getElement(fieldId);
    if (!field) return;
    
    let feedback = field.parentElement.querySelector('.auto-save-feedback');
    if (!feedback) {
        feedback = document.createElement('div');
        feedback.className = 'auto-save-feedback';
        feedback.setAttribute('role', 'status');
        feedback.setAttribute('aria-live', 'polite');
        field.parentElement.appendChild(feedback);
    }
    
    // Utilise des classes CSS plutôt que des styles inline
    feedback.classList.remove('auto-save-feedback--success', 'auto-save-feedback--error');
    
    if (success) {
        feedback.classList.add('auto-save-feedback--success');
        feedback.textContent = '✓ Auto-sauvegardé';
    } else {
        feedback.classList.add('auto-save-feedback--error');
        feedback.textContent = `✗ Erreur: ${message}`;
    }
    
    feedback.classList.add('auto-save-feedback--visible');
    
    setTimeout(() => {
        feedback.classList.remove('auto-save-feedback--visible');
    }, 3000);
}

/**
 * Prévention de la perte de données (alerte avant fermeture)
 * @param {Function} hasUnsavedChangesFn - Vérifie les changements non sauvegardés
 */
export function initializeDataLossPrevention(hasUnsavedChangesFn) {
    const handler = (e) => {
        if (hasUnsavedChangesFn()) {
            e.preventDefault();
            e.returnValue = '';
        }
    };
    globalThis.addEventListener('beforeunload', handler);
    _registeredHandlers.push({ el: globalThis, type: 'beforeunload', handler });
}

/**
 * Nettoie tous les listeners d'auto-sauvegarde enregistrés.
 */
export function destroy() {
    _registeredHandlers.forEach(({ el, type, handler }) => {
        el.removeEventListener(type, handler);
    });
    _registeredHandlers.length = 0;
}
