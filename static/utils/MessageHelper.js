// static/utils/MessageHelper.js
// Utilitaires pour les messages UI et notifications
export class MessageHelper {
    /**
     * Affiche un message temporaire dans un élément
     * @param {string} elementId - ID de l'élément cible
     * @param {string} message - Message à afficher
     * @param {string} type - Type de message (success, error, info)
     * @param {number} timeout - Durée d'affichage en ms (défaut: 5000)
     */
    static showMessage(elementId, message, type, timeout = 5000) {
        const el = document.getElementById(elementId);
        if (!el) return; // Safe-guard: element may be absent in some contexts
        
        el.textContent = message;
        el.className = 'status-msg ' + type;
        
        setTimeout(() => {
            if (!el) return;
            el.className = 'status-msg';
        }, timeout);
    }

    /**
     * Affiche un message de succès
     */
    static showSuccess(elementId, message) {
        this.showMessage(elementId, message, 'success');
    }

    /**
     * Affiche un message d'erreur
     */
    static showError(elementId, message) {
        this.showMessage(elementId, message, 'error');
    }

    /**
     * Affiche un message d'information
     */
    static showInfo(elementId, message) {
        this.showMessage(elementId, message, 'info');
    }

    /**
     * Active/désactive un bouton avec état de chargement
     * @param {HTMLElement} button - Bouton à modifier
     * @param {boolean} loading - État de chargement
     * @param {string} loadingText - Texte pendant le chargement
     */
    static setButtonLoading(button, loading = true, loadingText = '⏳ Chargement...') {
        if (!button) return;
        
        if (loading) {
            button.dataset.originalText = button.textContent;
            button.textContent = loadingText;
            button.disabled = true;
        } else {
            button.textContent = button.dataset.originalText || button.textContent;
            button.disabled = false;
            delete button.dataset.originalText;
        }
    }

    /**
     * Vérifie si une valeur est un placeholder à ignorer
     * @param {string} value - Valeur à vérifier
     * @param {string} placeholder - Placeholder attendu
     */
    static isPlaceholder(value, placeholder = 'Non configuré') {
        return !value || value.trim() === '' || value === placeholder;
    }

    /**
     * Valide le format d'une heure (HH:MM ou HHhMM)
     * @param {string} timeString - Chaîne de temps à valider
     * @returns {boolean} True si valide
     */
    static isValidTimeFormat(timeString) {
        if (!timeString || typeof timeString !== 'string') {
            return false;
        }

        const trimmed = timeString.trim();
        
        // Accepte les formats HH:MM et HHhMM
        const colonFormat = /^([01]?[0-9]|2[0-3]):[0-5][0-9]$/;
        const hFormat = /^([01]?[0-9]|2[0-3])h[0-5][0-9]$/;
        
        return colonFormat.test(trimmed) || hFormat.test(trimmed);
    }

    /**
     * Normalise une heure au format HH:MM
     * @param {string} timeString - Chaîne de temps à normaliser
     * @returns {string|null} Heure normalisée ou null si invalide
     */
    static normalizeTimeFormat(timeString) {
        if (!this.isValidTimeFormat(timeString)) {
            return null;
        }

        const trimmed = timeString.trim();
        
        // Si déjà au format HH:MM, retourner tel quel
        if (trimmed.includes(':')) {
            return trimmed;
        }
        
        // Convertir HHhMM en HH:MM
        const match = trimmed.match(/^([01]?[0-9]|2[0-3])h([0-5][0-9])$/);
        if (match) {
            const hours = match[1].padStart(2, '0');
            const minutes = match[2];
            return `${hours}:${minutes}`;
        }
        
        return null;
    }
}
