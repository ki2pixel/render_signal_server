import { ApiService } from './ApiService.js';
import { MessageHelper } from '../utils/MessageHelper.js';

export class WebhookService {
    static ALLOWED_WEBHOOK_HOSTS = [
        /hook\.eu\d+\.make\.com/i,
        /^webhook\.kidpixel\.fr$/i
    ];
    /**
     * Charge la configuration des webhooks depuis le serveur
     * @returns {Promise<object>} Configuration des webhooks
     */
    static async loadConfig() {
        try {
            const data = await ApiService.get('/api/webhooks/config');
            
            if (data.success) {
                const config = data.config;
                
                const webhookUrlEl = document.getElementById('webhookUrl');
                if (webhookUrlEl) {
                    webhookUrlEl.placeholder = config.webhook_url || 'Non configuré';
                }
                
                const sslToggle = document.getElementById('sslVerifyToggle');
                if (sslToggle) {
                    sslToggle.checked = !!config.webhook_ssl_verify;
                }
                
                const sendingToggle = document.getElementById('webhookSendingToggle');
                if (sendingToggle) {
                    sendingToggle.checked = config.webhook_sending_enabled ?? true;
                }
                
                const absenceToggle = document.getElementById('absencePauseToggle');
                if (absenceToggle) {
                    absenceToggle.checked = !!config.absence_pause_enabled;
                }
                
                if (config.absence_pause_days && Array.isArray(config.absence_pause_days)) {
                    this.setAbsenceDayCheckboxes(config.absence_pause_days);
                }
                
                return config;
            }
        } catch (e) {
            throw e;
        }
    }

    /**
     * Sauvegarde la configuration des webhooks
     * @returns {Promise<boolean>} Succès de l'opération
     */
    static async saveConfig() {
        const webhookUrlEl = document.getElementById('webhookUrl');
        const sslToggle = document.getElementById('sslVerifyToggle');
        const sendingToggle = document.getElementById('webhookSendingToggle');
        const absenceToggle = document.getElementById('absencePauseToggle');
        
        const webhookUrl = (webhookUrlEl?.value || '').trim();
        const placeholder = webhookUrlEl?.placeholder || 'Non configuré';
        const hasNewWebhookUrl = webhookUrl.length > 0;
        
        if (hasNewWebhookUrl) {
            if (MessageHelper.isPlaceholder(webhookUrl, placeholder)) {
                MessageHelper.showError('configMsg', 'Veuillez saisir une URL webhook valide.');
                return false;
            }
            
            if (!this.isValidWebhookUrl(webhookUrl)) {
                MessageHelper.showError('configMsg', 'Format d\'URL webhook invalide.');
                return false;
            }
        }
        
        const selectedDays = this.collectAbsenceDayCheckboxes();
        
        if (absenceToggle?.checked && selectedDays.length === 0) {
            MessageHelper.showError('configMsg', 'Au moins un jour doit être sélectionné pour l\'absence globale.');
            return false;
        }
        
        const payload = {
            webhook_ssl_verify: sslToggle?.checked ?? false,
            webhook_sending_enabled: sendingToggle?.checked ?? true,
            absence_pause_enabled: absenceToggle?.checked ?? false,
            absence_pause_days: selectedDays
        };
        
        if (hasNewWebhookUrl && webhookUrl !== placeholder) {
            payload.webhook_url = webhookUrl;
        }
        
        try {
            const data = await ApiService.post('/api/webhooks/config', payload);
            
            if (data.success) {
                MessageHelper.showSuccess('configMsg', 'Configuration enregistrée avec succès !');
                
                if (webhookUrlEl) webhookUrlEl.value = '';
                
                await this.loadConfig();
                return true;
            } else {
                MessageHelper.showError('configMsg', data.message || 'Erreur lors de la sauvegarde.');
                return false;
            }
        } catch (e) {
            MessageHelper.showError('configMsg', 'Erreur de communication avec le serveur.');
            return false;
        }
    }

    /**
     * Charge les logs des webhooks
     * @param {number} days - Nombre de jours de logs à charger
     * @returns {Promise<Array>} Liste des logs
     */
    static async loadLogs(days = 7) {
        try {
            const data = await ApiService.get(`/api/webhook_logs?days=${days}`);
            return data.logs || [];
        } catch (e) {
            return [];
        }
    }

    /**
     * Affiche les logs des webhooks dans l'interface
     * @param {Array} logs - Liste des logs à afficher
     */
    static renderLogs(logs) {
        const container = document.getElementById('webhookLogs');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (!logs || logs.length === 0) {
            container.innerHTML = '<div class="log-entry">Aucun log trouvé pour cette période.</div>';
            return;
        }
        
        logs.forEach(log => {
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${log.status}`;
            
            const timeDiv = document.createElement('div');
            timeDiv.className = 'log-entry-time';
            timeDiv.textContent = this.formatTimestamp(log.timestamp);
            logEntry.appendChild(timeDiv);
            
            const statusDiv = document.createElement('div');
            statusDiv.className = 'log-entry-status';
            statusDiv.textContent = log.status.toUpperCase();
            logEntry.appendChild(statusDiv);
            
            if (log.subject) {
                const subjectDiv = document.createElement('div');
                subjectDiv.className = 'log-entry-subject';
                subjectDiv.textContent = `Sujet: ${this.escapeHtml(log.subject)}`;
                logEntry.appendChild(subjectDiv);
            }
            
            if (log.webhook_url) {
                const urlDiv = document.createElement('div');
                urlDiv.className = 'log-entry-url';
                urlDiv.textContent = `URL: ${this.escapeHtml(log.webhook_url)}`;
                logEntry.appendChild(urlDiv);
            }
            
            if (log.error_message) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'log-entry-error';
                errorDiv.textContent = `Erreur: ${this.escapeHtml(log.error_message)}`;
                logEntry.appendChild(errorDiv);
            }
            
            container.appendChild(logEntry);
        });
    }

    /**
     * Vide l'affichage des logs
     */
    static clearLogs() {
        const container = document.getElementById('webhookLogs');
        if (container) {
            container.innerHTML = '<div class="log-entry">Logs vidés.</div>';
        }
    }

    /**
     * Validation d'URL webhook (Make.com ou HTTPS générique)
     * @param {string} value - URL à valider
     * @returns {boolean} Validité de l'URL
     */
    static isValidWebhookUrl(value) {
        if (this.isValidHttpsUrl(value)) {
            try {
                const { hostname } = new URL(value);
                return this.ALLOWED_WEBHOOK_HOSTS.some((pattern) => pattern.test(hostname));
            } catch {
                return false;
            }
        }
        return /^[A-Za-z0-9_-]{10,}@[Hh]ook\.eu\d+\.make\.com$/.test(value);
    }

    /**
     * Validation d'URL HTTPS
     * @param {string} url - URL à valider
     * @returns {boolean} Validité de l'URL
     */
    static isValidHttpsUrl(url) {
        try {
            const u = new URL(url);
            return u.protocol === 'https:' && !!u.hostname;
        } catch { 
            return false; 
        }
    }

    /**
     * Échappement HTML pour éviter les XSS
     * @param {string} text - Texte à échapper
     * @returns {string} Texte échappé
     */
    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Formatage d'horodatage
     * @param {string} isoString - Timestamp ISO
     * @returns {string} Timestamp formaté
     */
    static formatTimestamp(isoString) {
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

    /**
     * Définit les cases à cocher des jours d'absence
     * @param {Array} days - Jours à cocher (monday, tuesday, ...)
     */
    static setAbsenceDayCheckboxes(days) {
        const group = document.getElementById('absencePauseDaysGroup');
        if (!group) return;
        
        const normalizedDays = new Set(
            (Array.isArray(days) ? days : []).map((day) => String(day).trim().toLowerCase())
        );
        const checkboxes = group.querySelectorAll('input[name="absencePauseDay"][type="checkbox"]');
        
        checkboxes.forEach(checkbox => {
            const dayValue = String(checkbox.value).trim().toLowerCase();
            checkbox.checked = normalizedDays.has(dayValue);
        });
    }

    /**
     * Collecte les jours d'absence cochés
     * @returns {Array} Jours cochés (monday, tuesday, ...)
     */
    static collectAbsenceDayCheckboxes() {
        const group = document.getElementById('absencePauseDaysGroup');
        if (!group) return [];
        
        const checkboxes = group.querySelectorAll('input[name="absencePauseDay"][type="checkbox"]');
        const selectedDays = [];
        
        checkboxes.forEach(checkbox => {
            if (checkbox.checked) {
                const dayValue = String(checkbox.value).trim().toLowerCase();
                if (dayValue) {
                    selectedDays.push(dayValue);
                }
            }
        });
        
        return Array.from(new Set(selectedDays));
    }
}
