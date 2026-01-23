// static/remote/main.js

// Les APIs sont disponibles via window.appAPI (défini dans api.js)

const POLLING_INTERVAL = 3000; // 3 secondes
let pollingIntervalId = null;

// Attends jusqu'à ce qu'une condition soit vraie (ou timeout)
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

function loadScriptOnce(src) {
    return new Promise((resolve, reject) => {
        // Already loaded?
        const existing = Array.from(document.scripts).find(s => s.src && s.src.includes(src));
        if (existing) {
            if (existing.dataset.loaded === 'true') return resolve(true);
            existing.addEventListener('load', () => resolve(true));
            existing.addEventListener('error', () => resolve(false));
            return;
        }
        const s = document.createElement('script');
        s.src = src;
        s.async = false; // preserve order
        s.dataset.loaded = 'false';
        s.onload = () => { s.dataset.loaded = 'true'; resolve(true); };
        s.onerror = () => resolve(false);
        document.head.appendChild(s);
    });
}

/** Démarre le polling périodique du statut. */
function startPolling() {
    if (pollingIntervalId) clearInterval(pollingIntervalId);

    const poll = async () => {
        const result = await window.appAPI.fetchStatus();

        if(result.error && result.data.overall_status_text.includes("Authentification")) {
            window.ui.updateStatusUI(result.data);
            stopPolling();
            setTimeout(() => window.location.reload(), 3000);
            return;
        }

        window.ui.updateStatusUI(result.data);
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
    window.ui.setButtonsDisabled(true);
    window.ui.updateStatusUI({
        overall_status_text: 'Envoi de la commande...',
        status_text: 'Veuillez patienter.',
        overall_status_code_from_worker: 'progress'
    });

    const result = await window.appAPI.triggerWorkflow();

    if (result.success) {
        window.ui.updateStatusUI({
            overall_status_text: 'Commande envoyée !',
            status_text: 'En attente de prise en charge par le worker local...',
            overall_status_code_from_worker: 'progress'
        });
        startPolling(); // S'assure que le polling est actif
    } else {
        window.ui.updateStatusUI({
            overall_status_text: 'Erreur Envoi Commande',
            status_text: result.data.message || 'Échec de l\'envoi de la commande.',
            overall_status_code_from_worker: 'error'
        });
        window.ui.setButtonsDisabled(false); // Réactive le bouton en cas d'échec
    }
}

/** Gère le clic sur le bouton de vérification des emails. */
async function handleEmailCheckClick() {
    window.ui.setButtonsDisabled(true);
    window.ui.displayEmailCheckMessage("Lancement de la vérification...", false);

    const result = await window.appAPI.checkEmails();

    if (result.success) {
        window.ui.displayEmailCheckMessage(result.data.message || 'Opération démarrée avec succès.', false);
    } else {
        if (result.sessionExpired) {
            window.ui.displayEmailCheckMessage('Session expirée. Rechargez la page.', true);
            setTimeout(() => window.location.reload(), 2000);
        } else {
            window.ui.displayEmailCheckMessage(`Erreur : ${result.data.message || 'Échec.'}`, true);
        }
    }

    // Réactive le bouton après un court délai pour éviter le spam
    setTimeout(() => window.ui.setButtonsDisabled(false), 3000);
}


/** Initialise l'application sur la page distante. */
function initialize() {
    document.getElementById('triggerBtn').addEventListener('click', handleTriggerClick);
    document.getElementById('checkEmailsBtn').addEventListener('click', handleEmailCheckClick);

    startPolling();

    // Time window UI wiring (if present)
    const startInput = document.getElementById('webhooksTimeStart');
    const endInput = document.getElementById('webhooksTimeEnd');
    const saveBtn = document.getElementById('saveTimeWindowBtn');
    const msgEl = document.getElementById('timeWindowMsg');
    if (startInput && endInput && saveBtn && msgEl) {
        (async () => {
            let ready = (window.appAPI && typeof window.appAPI.getWebhookTimeWindow === 'function');
            if (!ready) {
                // Essaie de charger api.js dynamiquement si indisponible
                await loadScriptOnce('/static/remote/api.js');
                ready = (window.appAPI && typeof window.appAPI.getWebhookTimeWindow === 'function');
                if (!ready) {
                    // Patiente un peu plus si nécessaire
                    ready = await waitFor(() => (window.appAPI && typeof window.appAPI.getWebhookTimeWindow === 'function'), { timeoutMs: 5000 });
                }
            }
            try {
                if (!ready) {
                    msgEl.textContent = 'API non prête. Rechargez la page (Ctrl+Shift+R).';
                    return;
                }
                const res = await window.appAPI.getWebhookTimeWindow();
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
            if (!(window.appAPI && typeof window.appAPI.setWebhookTimeWindow === 'function')) {
                msgEl.textContent = 'API non prête. Rechargez la page (Ctrl+Shift+R).';
                msgEl.className = 'status-error';
                return;
            }
            const res = await window.appAPI.setWebhookTimeWindow(s, e);
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
