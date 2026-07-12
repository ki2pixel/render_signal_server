import { ApiService } from './ApiService.js';
import { MessageHelper } from '../utils/MessageHelper.js';
import { DOMHelper } from '../utils/DOMHelper.js';

export class LogService {
    static logPollingInterval = null;
    static currentLogDays = 7;
    static _cachedLogs = null;
    static _logsCacheTime = null;

    /**
     * Démarre le polling automatique des logs
     * @param {number} intervalMs - Intervalle en millisecondes (défaut: 30000)
     */
    static startLogPolling(intervalMs = 30000) {
        this.stopLogPolling();
        
        this.loadAndRenderLogs();
        
        this.logPollingInterval = setInterval(() => {
            this.loadAndRenderLogs();
        }, intervalMs);
        
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
            LogService.stopLogPolling();
        } else {
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
            const data = await ApiService.get(`/api/webhook_logs?days=${daysToLoad}`);
            const logs = data.logs || [];
            this._cachedLogs = logs;
            this._logsCacheTime = Date.now();
            this.renderLogs(logs);
        } catch (e) {
            MessageHelper.showError('logMsg', 'Erreur lors du chargement des logs.');
            this.renderLogs([]);
        }
    }

    /**
     * Affiche les logs dans l'interface
     * @param {Array} logs - Liste des logs à afficher
     */
    static renderLogs(logs) {
        const container = DOMHelper.getElement('webhookLogs');
        if (!container) return;
        
        container.replaceChildren();
        
        if (!logs || logs.length === 0) {
            const emptyItem = document.createElement('div');
            emptyItem.className = 'timeline-item';
            const emptyContent = document.createElement('div');
            emptyContent.className = 'timeline-content';
            emptyContent.textContent = 'Aucun log trouvé pour cette période.';
            emptyItem.appendChild(emptyContent);
            container.appendChild(emptyItem);
            return;
        }
        
        const timelineContainer = document.createElement('div');
        timelineContainer.className = 'timeline-container';
        
        const timelineLine = document.createElement('div');
        timelineLine.className = 'timeline-line';
        timelineContainer.appendChild(timelineLine);
        
        const sparkline = this.createSparkline(logs);
        if (sparkline) {
            timelineContainer.appendChild(sparkline);
        }
        
        logs.forEach((log, index) => {
            const timelineItem = document.createElement('div');
            timelineItem.className = 'timeline-item';
            timelineItem.style.animationDelay = `${index * 0.1}s`;
            
            const marker = document.createElement('div');
            marker.className = `timeline-marker ${log.status}`;
            marker.textContent = log.status === 'success' ? '✓' : '⚠';
            timelineItem.appendChild(marker);
            
            const content = document.createElement('div');
            content.className = 'timeline-content';
            
            const header = document.createElement('div');
            header.className = 'timeline-header';
            
            const timeDiv = document.createElement('div');
            timeDiv.className = 'timeline-time';
            timeDiv.textContent = this.formatTimestamp(log.timestamp);
            header.appendChild(timeDiv);
            
            const statusDiv = document.createElement('div');
            statusDiv.className = `timeline-status ${log.status}`;
            statusDiv.textContent = log.status.toUpperCase();
            header.appendChild(statusDiv);
            
            content.appendChild(header);
            
            const details = document.createElement('div');
            details.className = 'timeline-details';
            
            if (log.subject) {
                const subjectDiv = document.createElement('div');
                subjectDiv.textContent = `Sujet: ${log.subject}`;
                details.appendChild(subjectDiv);
            }
            
            if (log.webhook_url) {
                const urlDiv = document.createElement('div');
                urlDiv.textContent = `URL: ${log.webhook_url}`;
                details.appendChild(urlDiv);
            }
            
            if (log.error_message) {
                const errorDiv = document.createElement('div');
                errorDiv.style.color = 'var(--cork-danger)';
                errorDiv.textContent = `Erreur: ${log.error_message}`;
                details.appendChild(errorDiv);
            }
            
            content.appendChild(details);
            timelineItem.appendChild(content);
            timelineContainer.appendChild(timelineItem);
        });
        
        container.replaceChildren(timelineContainer);
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
        const container = DOMHelper.getElement('webhookLogs');
        if (container) {
            container.replaceChildren();
            const clearedEntry = document.createElement('div');
            clearedEntry.className = 'log-entry';
            clearedEntry.textContent = 'Logs vidés.';
            container.appendChild(clearedEntry);
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
    
    /**
     * Crée une sparkline pour visualiser les tendances des logs
     * @param {Array} logs - Liste des logs
     * @returns {HTMLElement|null} Élément DOM de la sparkline
     */
    static createSparkline(logs) {
        if (!logs || logs.length < 2) return null;
        
        const hourlyData = {};
        const now = new Date();
        
        logs.forEach(log => {
            const logTime = new Date(log.timestamp);
            const hourKey = new Date(logTime.getFullYear(), logTime.getMonth(), logTime.getDate(), logTime.getHours()).getTime();
            
            if (!hourlyData[hourKey]) {
                hourlyData[hourKey] = { success: 0, error: 0, total: 0 };
            }
            
            hourlyData[hourKey].total++;
            if (log.status === 'success') {
                hourlyData[hourKey].success++;
            } else if (log.status === 'error') {
                hourlyData[hourKey].error++;
            }
        });
        
        const sparklineContainer = document.createElement('div');
        sparklineContainer.className = 'timeline-sparkline';
        
        const canvas = document.createElement('canvas');
        canvas.className = 'sparkline-canvas';
        const dpr = globalThis.devicePixelRatio || 1;
        canvas.width = 200 * dpr;
        canvas.height = 40 * dpr;
        canvas.style.width = '200px';
        canvas.style.height = '40px';
        
        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
        
        const hours = 24;
        const data = [];
        const maxCount = Math.max(...Object.values(hourlyData).map(d => d.total), 1);
        
        for (let i = hours - 1; i >= 0; i--) {
            const hourTime = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours() - i).getTime();
            const hourData = hourlyData[hourTime] || { success: 0, error: 0, total: 0 };
            data.push(hourData.total);
        }
        
        // Dessiner la sparkline
        ctx.strokeStyle = '#4361ee';
        ctx.lineWidth = 2;
        ctx.fillStyle = 'rgba(67, 97, 238, 0.1)';
        
        const width = canvas.width;
        const height = canvas.height;
        const stepX = width / (data.length - 1);
        
        ctx.beginPath();
        data.forEach((value, index) => {
            const x = index * stepX;
            const y = height - (value / maxCount) * height * 0.8 - 5;
            
            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.stroke();
        
        ctx.lineTo(width, height);
        ctx.lineTo(0, height);
        ctx.closePath();
        ctx.fill();
        
        sparklineContainer.appendChild(canvas);
        
        const legend = document.createElement('div');
        legend.className = 'sparkline-legend';
        legend.textContent = `24h - Max: ${maxCount}`;
        sparklineContainer.appendChild(legend);
        
        return sparklineContainer;
    }

    /**
     * Retourne les logs en cache (dernier fetch réussi)
     * @returns {Array|null} Logs en cache ou null
     */
    static getCachedLogs() {
        return this._cachedLogs;
    }

    /**
     * Vérifie si le cache des logs est encore frais
     * @param {number} maxAgeMs - Âge maximum en ms (défaut: 30000)
     * @returns {boolean} True si le cache est frais
     */
    static isLogCacheFresh(maxAgeMs = 30000) {
        return this._cachedLogs !== null &&
               this._logsCacheTime !== null &&
               (Date.now() - this._logsCacheTime) < maxAgeMs;
    }
}
