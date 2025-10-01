// static/remote/main.js

import * as api from './api.js';
import * as ui from './ui.js';

const POLLING_INTERVAL = 3000; // 3 secondes
let pollingIntervalId = null;

/** Démarre le polling périodique du statut. */
function startPolling() {
    if (pollingIntervalId) clearInterval(pollingIntervalId);

    const poll = async () => {
        const result = await api.fetchStatus();

        if(result.error && result.data.overall_status_text.includes("Authentification")) {
            ui.updateStatusUI(result.data);
            stopPolling();
            setTimeout(() => window.location.reload(), 3000);
            return;
        }

        ui.updateStatusUI(result.data);
    };

    poll(); // Appel immédiat
    pollingIntervalId = setInterval(poll, POLLING_INTERVAL);
}

/** Arrête le polling. */
function stopPolling() {
    if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
        pollingIntervalId = null;
    }
}

/** Gère le clic sur le bouton de déclenchement du workflow. */
async function handleTriggerClick() {
    ui.setButtonsDisabled(true);
    ui.updateStatusUI({
        overall_status_text: 'Envoi de la commande...',
        status_text: 'Veuillez patienter.',
        overall_status_code_from_worker: 'progress'
    });

    const result = await api.triggerWorkflow();

    if (result.success) {
        ui.updateStatusUI({
            overall_status_text: 'Commande envoyée !',
            status_text: 'En attente de prise en charge par le worker local...',
            overall_status_code_from_worker: 'progress'
        });
        startPolling(); // S'assure que le polling est actif
    } else {
        ui.updateStatusUI({
            overall_status_text: 'Erreur Envoi Commande',
            status_text: result.data.message || 'Échec de l\'envoi de la commande.',
            overall_status_code_from_worker: 'error'
        });
        ui.setButtonsDisabled(false); // Réactive le bouton en cas d'échec
    }
}

/** Gère le clic sur le bouton de vérification des emails. */
async function handleEmailCheckClick() {
    ui.setButtonsDisabled(true);
    ui.displayEmailCheckMessage("Lancement de la vérification...", false);

    const result = await api.checkEmails();

    if (result.success) {
        ui.displayEmailCheckMessage(result.data.message || 'Opération démarrée avec succès.', false);
    } else {
        if (result.sessionExpired) {
            ui.displayEmailCheckMessage('Session expirée. Rechargez la page.', true);
            setTimeout(() => window.location.reload(), 2000);
        } else {
            ui.displayEmailCheckMessage(`Erreur : ${result.data.message || 'Échec.'}`, true);
        }
    }

    // Réactive le bouton après un court délai pour éviter le spam
    setTimeout(() => ui.setButtonsDisabled(false), 3000);
}


/** Initialise l'application sur la page distante. */
function initialize() {
    document.getElementById('triggerBtn').addEventListener('click', handleTriggerClick);
    document.getElementById('checkEmailsBtn').addEventListener('click', handleEmailCheckClick);

    console.log("🚀 Télécommande initialisée.");
    startPolling();

    // Time window UI wiring (if present)
    const startInput = document.getElementById('webhooksTimeStart');
    const endInput = document.getElementById('webhooksTimeEnd');
    const saveBtn = document.getElementById('saveTimeWindowBtn');
    const msgEl = document.getElementById('timeWindowMsg');
    if (startInput && endInput && saveBtn && msgEl) {
        // Load current values
        api.getWebhookTimeWindow().then(res => {
            if (res.success && res.data && res.data.success) {
                if (res.data.webhooks_time_start) startInput.value = res.data.webhooks_time_start;
                if (res.data.webhooks_time_end) endInput.value = res.data.webhooks_time_end;
                msgEl.textContent = `Fenêtre actuelle: ${res.data.webhooks_time_start || '—'} → ${res.data.webhooks_time_end || '—'} (${res.data.timezone || ''})`;
            } else {
                msgEl.textContent = 'Impossible de charger la fenêtre horaire.';
            }
        });

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

// Lance l'initialisation quand le DOM est prêt.
document.addEventListener('DOMContentLoaded', initialize);
