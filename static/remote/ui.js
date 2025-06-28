// static/remote/ui.js

// Références aux éléments du DOM pour un accès facile
const dom = {
    triggerButton: document.getElementById('triggerBtn'),
    statusContainer: document.getElementById('statusContainer'),
    overallStatusText: document.getElementById('overallStatusText'),
    statusTextDetail: document.getElementById('statusTextDetail'),
    progressBarContainer: document.getElementById('progress-bar-remote-container'),
    progressBar: document.getElementById('progress-bar-remote'),
    progressText: document.getElementById('progressTextRemote'),
    downloadsTitle: document.getElementById('downloadsTitle'),
    downloadsList: document.getElementById('recentDownloadsList'),
    checkEmailsButton: document.getElementById('checkEmailsBtn'),
    emailStatusMsg: document.getElementById('emailCheckStatusMsg'),
    summaryTitle: document.getElementById('sequenceSummaryTitleRemote'),
    summaryContent: document.getElementById('sequenceSummaryRemote'),
};

/** Met à jour l'ensemble de l'interface de statut avec les données reçues. */
export function updateStatusUI(data) {
    if (!data) return;

    dom.statusContainer.style.display = 'block';

    // --- Mise à jour du texte de statut principal ---
    dom.overallStatusText.textContent = data.overall_status_text || "Inconnu";
    dom.statusTextDetail.textContent = data.status_text || "Aucun détail.";

    const workerStatusCode = (data.overall_status_code_from_worker || "idle").toLowerCase();
    dom.overallStatusText.className = ''; // Reset
    if (workerStatusCode.includes("success")) dom.overallStatusText.classList.add('status-success');
    else if (workerStatusCode.includes("error")) dom.overallStatusText.classList.add('status-error');
    else if (workerStatusCode.includes("running")) dom.overallStatusText.classList.add('status-progress');
    else if (workerStatusCode.includes("warning")) dom.overallStatusText.classList.add('status-warning');
    else dom.overallStatusText.classList.add('status-idle');

    // --- Barre de progression ---
    updateProgressBar(data, workerStatusCode);

    // --- Liste des téléchargements récents ---
    updateDownloadsList(data.recent_downloads);

    // --- Résumé de la dernière séquence ---
    updateLastSequenceSummary(data, workerStatusCode);

    // --- État du bouton de déclenchement ---
    const isSystemIdle = workerStatusCode.includes("idle") || workerStatusCode.includes("completed") || workerStatusCode.includes("unavailable") || workerStatusCode.includes("error");
    dom.triggerButton.disabled = !isSystemIdle;
}

/** Met à jour la barre de progression. */
function updateProgressBar(data, workerStatusCode) {
    if (data.progress_total > 0 && workerStatusCode.includes("running")) {
        const percentage = Math.round((data.progress_current / data.progress_total) * 100);
        dom.progressBar.style.width = `${percentage}%`;
        dom.progressBar.style.backgroundColor = 'var(--cork-primary-accent)';

        const stepName = (data.current_step_name || '').split(":")[1]?.trim() || data.current_step_name || '';
        dom.progressText.textContent = `${stepName} ${percentage}% (${data.progress_current}/${data.progress_total})`;
        dom.progressBarContainer.style.display = 'block';
    } else {
        dom.progressBarContainer.style.display = 'none';
    }
}

/** Met à jour la liste des téléchargements. */
function updateDownloadsList(downloads) {
    if (downloads && downloads.length > 0) {
        dom.downloadsTitle.style.display = 'block';
        dom.downloadsList.innerHTML = '';
        downloads.forEach(dl => {
            const li = document.createElement('li');
            const status = (dl.status || "").toLowerCase();
            let color = 'var(--cork-text-secondary)';
            if (status === 'completed') color = 'var(--cork-success)';
            else if (status === 'failed') color = 'var(--cork-danger)';
            else if (['downloading', 'starting'].includes(status)) color = 'var(--cork-info)';

            li.innerHTML = `<span style="color:${color}; font-weight:bold;">[${dl.status || 'N/A'}]</span> ${dl.filename || 'N/A'}`;
            dom.downloadsList.appendChild(li);
        });
    } else {
        dom.downloadsTitle.style.display = 'none';
        dom.downloadsList.innerHTML = '';
    }
}

/** Affiche le résumé de la dernière séquence si pertinent. */
function updateLastSequenceSummary(data, workerStatusCode) {
    // Cette fonction reste complexe, on la garde telle quelle pour l'instant
    // car elle dépend de la logique métier (récence, etc.)
    dom.summaryTitle.style.display = 'none';
    dom.summaryContent.style.display = 'none';
    // Le code existant pour vérifier la récence du résumé peut être inséré ici
}


/** Affiche un message sous le bouton de vérification des emails. */
export function displayEmailCheckMessage(message, isError = false) {
    dom.emailStatusMsg.textContent = message;
    dom.emailStatusMsg.className = isError ? 'status-error' : 'status-success';
}

/** Gère l'état (activé/désactivé) des boutons d'action. */
export function setButtonsDisabled(disabled) {
    dom.triggerButton.disabled = disabled;
    dom.checkEmailsButton.disabled = disabled;
}
