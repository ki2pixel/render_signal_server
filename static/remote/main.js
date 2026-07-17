import * as api from './api.js';
import { updateStatusUI, displayEmailCheckMessage, setButtonsDisabled } from './ui.js';

const POLLING_INTERVAL = 3000;
let pollingIntervalId = null;

function waitFor(predicateFn, { timeoutMs = 8000, intervalMs = 100 } = {}) {
    return new Promise((resolve, reject) => {
        const start = Date.now();
        const timer = setInterval(() => {
            try {
                if (predicateFn()) {
                    clearInterval(timer);
                    resolve(true);
                } else if (Date.now() - start > timeoutMs) {
                    clearInterval(timer);
                    resolve(false);
                }
            } catch (e) {
                clearInterval(timer);
                reject(e);
            }
        }, intervalMs);
    });
}

function startPolling() {
    if (pollingIntervalId) clearInterval(pollingIntervalId);

    const poll = async () => {
        const result = await api.fetchStatus();

        if (result.error && result.data.overall_status_text.includes("Authentification")) {
            updateStatusUI(result.data);
            stopPolling();
            setTimeout(() => window.location.reload(), 3000);
            return;
        }

        updateStatusUI(result.data);
    };

    poll();
    pollingIntervalId = setInterval(poll, POLLING_INTERVAL);
}

function stopPolling() {
    if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
        pollingIntervalId = null;
    }
}

async function handleTriggerClick() {
    setButtonsDisabled(true);
    updateStatusUI({
        overall_status_text: 'Envoi de la commande...',
        status_text: 'Veuillez patienter.',
        overall_status_code_from_worker: 'progress'
    });

    const result = await api.triggerWorkflow();

    if (result.success) {
        updateStatusUI({
            overall_status_text: 'Commande envoyée !',
            status_text: 'En attente de prise en charge par le worker local...',
            overall_status_code_from_worker: 'progress'
        });
        startPolling();
    } else {
        updateStatusUI({
            overall_status_text: 'Erreur Envoi Commande',
            status_text: result.data.message || 'Échec de l\'envoi de la commande.',
            overall_status_code_from_worker: 'error'
        });
        setButtonsDisabled(false);
    }
}

async function handleEmailCheckClick() {
    setButtonsDisabled(true);
    displayEmailCheckMessage("Lancement de la vérification...", false);

    const result = await api.checkEmails();

    if (result.success) {
        displayEmailCheckMessage(result.data.message || 'Opération démarrée avec succès.', false);
    } else {
        if (result.sessionExpired) {
            displayEmailCheckMessage('Session expirée. Rechargez la page.', true);
            setTimeout(() => window.location.reload(), 2000);
        } else {
            displayEmailCheckMessage(`Erreur : ${result.data.message || 'Échec.'}`, true);
        }
    }

    setTimeout(() => setButtonsDisabled(false), 3000);
}

function initialize() {
    document.getElementById('triggerBtn').addEventListener('click', handleTriggerClick);
    document.getElementById('checkEmailsBtn').addEventListener('click', handleEmailCheckClick);

    startPolling();

    const startInput = document.getElementById('webhooksTimeStart');
    const endInput = document.getElementById('webhooksTimeEnd');
    const saveBtn = document.getElementById('saveTimeWindowBtn');
    const msgEl = document.getElementById('timeWindowMsg');
    if (startInput && endInput && saveBtn && msgEl) {
        (async () => {
            let ready = (api && typeof api.getWebhookTimeWindow === 'function');
            if (!ready) {
                ready = await waitFor(() => (api && typeof api.getWebhookTimeWindow === 'function'), { timeoutMs: 5000 });
            }
            try {
                if (!ready) {
                    msgEl.textContent = 'API non prête. Rechargez la page (Ctrl+Shift+R).';
                    return;
                }
                const res = await api.getWebhookTimeWindow();
                if (res.success && res.data && res.data.success) {
                    if (res.data.webhooks_time_start) startInput.value = res.data.webhooks_time_start;
                    if (res.data.webhooks_time_end) endInput.value = res.data.webhooks_time_end;
                    msgEl.textContent = `Fenêtre actuelle: ${res.data.webhooks_time_start || '—'} → ${res.data.webhooks_time_end || '—'} (${res.data.timezone || ''})`;
                } else {
                    msgEl.textContent = 'Impossible de charger la fenêtre horaire.';
                }
            } catch (e) {
                msgEl.textContent = 'Erreur de chargement de la fenêtre horaire.';
            }
        })();

        saveBtn.addEventListener('click', async () => {
            const s = startInput.value.trim();
            const e = endInput.value.trim();
            const res = await api.setWebhookTimeWindow(s, e);
            if (res.success && res.data && res.data.success) {
                msgEl.textContent = `Sauvegardé. Fenêtre: ${res.data.webhooks_time_start || '—'} → ${res.data.webhooks_time_end || '—'}`;
                msgEl.className = 'status-success';
            } else {
                msgEl.textContent = res.data && res.data.message ? res.data.message : 'Erreur de sauvegarde.';
                msgEl.className = 'status-error';
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', initialize);
