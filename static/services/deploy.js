import { ApiService } from './ApiService.js';
import { MessageHelper } from '../utils/MessageHelper.js';
import { DOMHelper } from '../utils/DOMHelper.js';

/**
 * Gère le déploiement de l'application via l'API admin
 */
export async function handleDeployApplication() {
    const button = DOMHelper.getElement('restartServerBtn');
    const messageId = 'restartMsg';
    
    if (!button) {
        MessageHelper.showError(messageId, 'Bouton de déploiement introuvable.');
        return;
    }
    
    const confirmed = globalThis.confirm("Confirmez-vous le déploiement de l'application ? Elle peut être indisponible pendant quelques secondes.");
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
                globalThis.location.reload();
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

/**
 * Polling de health check après déploiement
 * @param {object} options - Configuration du polling
 * @returns {Promise<boolean>} True si le service répond
 */
export async function pollHealthCheck({ attempts = 10, intervalMs = 1200, timeoutMs = 20000 } = {}) {
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

/**
 * Ouvre une page de téléchargement dans un nouvel onglet
 */
export function openDownloadPage() {
    const urlInput = DOMHelper.getElement('downloadPageUrl');
    const msgId = 'openDownloadMsg';
    const url = (urlInput?.value || '').trim();

    if (!url) {
        MessageHelper.showError(msgId, 'Veuillez saisir une URL.');
        return;
    }

    try {
        const parsed = new URL(url);
        if (parsed.protocol !== 'https:') {
            MessageHelper.showError(msgId, 'Seules les URLs HTTPS sont autorisées.');
            return;
        }
        globalThis.open(url, '_blank', 'noopener,noreferrer');
        MessageHelper.showSuccess(msgId, 'Page ouverte dans un nouvel onglet.');
    } catch {
        MessageHelper.showError(msgId, 'URL invalide.');
    }
}
