// static/services/LogService.js
// Service pour la gestion des logs et du timer de polling
import { ApiService } from './ApiService.js';
import { MessageHelper } from '../utils/MessageHelper.js';

export class LogService {
    static logPollingInterval = null;
    static currentLogDays = 7;

    /**
     * Démarre le polling automatique des logs
     * @param {number} intervalMs - Intervalle en millisecondes (défaut: 30000)
     */
    static startLogPolling(intervalMs = 30000) {
        // Arrêter le polling existant
        this.stopLogPolling();
        
        // Charger les logs immédiatement
        this.loadAndRenderLogs();
        
        // Démarrer le polling périodique
        this.logPollingInterval = setInterval(() => {
            this.loadAndRenderLogs();
        }, intervalMs);
        
        // Nettoyer le polling quand la page n'est plus visible
        document.addEventListener('visibilitychange', this.handleVisibilityChange);
    }

    /**
     * Arrête le polling des logs
     */
    static stopLogPolling() {
        if (this.logPollingInterval) {
            clearInterval(this.logPollingInterval);
            this.logPollingInterval = null;
        }
        
        document.removeEventListener('visibilitychange', this.handleVisibilityChange);
    }

    /**
     * Gère les changements de visibilité de la page
     */
    static handleVisibilityChange() {
        if (document.hidden) {
            // Mettre en pause le polling quand la page est cachée
            LogService.stopLogPolling();
        } else {
            // Reprendre le polling quand la page redevient visible
            LogService.startLogPolling();
        }
    }

    /**
     * Charge et affiche les logs
     * @param {number} days - Nombre de jours de logs à charger
     */
    static async loadAndRenderLogs(days = null) {
        const daysToLoad = days || this.currentLogDays;
        
        try {
            const logs = await ApiService.get(`/api/webhook_logs?days=${daysToLoad}`);
            this.renderLogs(logs.logs || []);
        } catch (e) {
            console.error('Erreur chargement logs:', e);
            this.renderLogs([]);
        }
    }

    /**
     * Affiche les logs dans l'interface
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
     * Change la période des logs et recharge
     * @param {number} days - Nouvelle période en jours
     */
    static changeLogPeriod(days) {
        this.currentLogDays = days;
        this.loadAndRenderLogs(days);
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
     * Exporte les logs au format JSON
     * @param {number} days - Nombre de jours à exporter
     */
    static async exportLogs(days = null) {
        const daysToExport = days || this.currentLogDays;
        
        try {
            const data = await ApiService.get(`/api/webhook_logs?days=${daysToExport}`);
            const logs = data.logs || [];
            
            const exportObj = {
                exported_at: new Date().toISOString(),
                period_days: daysToExport,
                count: logs.length,
                logs: logs
            };
            
            const blob = new Blob([JSON.stringify(exportObj, null, 2)], { 
                type: 'application/json' 
            });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `webhook_logs_${daysToExport}days_${new Date().toISOString().split('T')[0]}.json`;
            a.click();
            URL.revokeObjectURL(url);
            
            MessageHelper.showSuccess('logMsg', `Exporté ${logs.length} logs sur ${daysToExport} jours.`);
        } catch (e) {
            MessageHelper.showError('logMsg', 'Erreur lors de l\'export des logs.');
        }
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
     * Obtient des statistiques sur les logs
     * @param {number} days - Période en jours
     * @returns {Promise<object>} Statistiques des logs
     */
    static async getLogStats(days = null) {
        const daysToAnalyze = days || this.currentLogDays;
        
        try {
            const data = await ApiService.get(`/api/webhook_logs?days=${daysToAnalyze}`);
            const logs = data.logs || [];
            
            const stats = {
                total: logs.length,
                success: 0,
                error: 0,
                by_status: {},
                latest_error: null,
                period_days: daysToAnalyze
            };
            
            logs.forEach(log => {
                stats.by_status[log.status] = (stats.by_status[log.status] || 0) + 1;
                
                if (log.status === 'success') {
                    stats.success++;
                } else if (log.status === 'error') {
                    stats.error++;
                    if (!stats.latest_error || new Date(log.timestamp) > new Date(stats.latest_error.timestamp)) {
                        stats.latest_error = log;
                    }
                }
            });
            
            return stats;
        } catch (e) {
            return {
                total: 0,
                success: 0,
                error: 0,
                by_status: {},
                latest_error: null,
                period_days: daysToAnalyze
            };
        }
    }
}
