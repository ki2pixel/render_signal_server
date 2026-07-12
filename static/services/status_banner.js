import { ApiService } from './ApiService.js';
import { DOMHelper } from '../utils/DOMHelper.js';
import { LogService } from './LogService.js';
import { WebhookService } from './WebhookService.js';

/**
 * Analyse les logs pour extraire les informations de statut
 * @param {Array} logs - Tableau de logs webhook
 * @returns {object} Données de statut analysées
 */
export function analyzeLogsForStatus(logs) {
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
        
        if (!lastExecution || logTime > lastExecution) {
            lastExecution = logTime;
        }
        
        if (logTime >= oneHourAgo) {
            totalWebhooks++;
            if (log.status === 'success') {
                successfulWebhooks++;
            } else if (log.status === 'error') {
                criticalErrors++;
            }
        }
        
        if (logTime >= oneDayAgo && log.status === 'error') {
            recentIncidents++;
        }
    });
    
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
 * @param {object} statusData - Données de statut
 * @param {object} config - Configuration webhook
 */
export function updateStatusBanner(statusData, config) {
    const lastExecEl = DOMHelper.getElement('lastExecutionTime');
    const recentIncEl = DOMHelper.getElement('recentIncidents');
    const critErrEl = DOMHelper.getElement('criticalErrors');
    const activeWhEl = DOMHelper.getElement('activeWebhooks');

    if (lastExecEl) lastExecEl.textContent = statusData.lastExecution;
    if (recentIncEl) recentIncEl.textContent = statusData.recentIncidents;
    if (critErrEl) critErrEl.textContent = statusData.criticalErrors;
    if (activeWhEl) activeWhEl.textContent = statusData.activeWebhooks;
    
    const statusIcon = DOMHelper.getElement('globalStatusIcon');
    if (!statusIcon) return;

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

/**
 * Met à jour le bandeau de statut global avec les données récentes
 */
export async function updateGlobalStatus() {
    try {
        let logs = null;
        let config = null;

        if (LogService.isLogCacheFresh()) {
            logs = LogService.getCachedLogs();
        } else {
            const logsResponse = await ApiService.get('/api/webhook_logs?limit=50');
            if (logsResponse.success) {
                logs = logsResponse.logs || [];
            }
        }

        if (WebhookService.isConfigCacheFresh()) {
            config = WebhookService.getCachedConfig();
        } else {
            const configResponse = await ApiService.get('/api/webhooks/config');
            if (configResponse.success) {
                config = configResponse.config || {};
            }
        }

        if (!logs || !config) {
            console.warn('Impossible de récupérer les données pour le statut global');
            return;
        }

        const statusData = analyzeLogsForStatus(logs);
        updateStatusBanner(statusData, config);

    } catch (error) {
        console.error('Erreur lors de la mise à jour du statut global:', error);
        updateStatusBanner({
            lastExecution: 'Erreur',
            recentIncidents: '—',
            criticalErrors: '—',
            activeWebhooks: '0',
            status: 'error'
        }, {});
    }
}
