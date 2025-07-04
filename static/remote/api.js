// static/remote/api.js

/**
 * Interroge le backend pour obtenir le statut du worker local.
 * @returns {Promise<object|null>} Les données de statut ou null en cas d'erreur.
 */
export async function fetchStatus() {
    try {
        const response = await fetch(`/api/get_local_status`);
        if (!response.ok) {
            // Gère les erreurs HTTP (4xx, 5xx) et tente de lire le corps de la réponse.
            const errorData = await response.json().catch(() => ({
                overall_status_text: `Erreur Serveur (${response.status})`,
                status_text: "Impossible de récupérer les détails de l'erreur.",
            }));
            // Renvoie un objet d'erreur structuré pour que l'UI puisse l'afficher.
            return { error: true, data: errorData };
        }
        // Renvoie les données en cas de succès.
        return { error: false, data: await response.json() };
    } catch (e) {
        // Gère les erreurs réseau (serveur inaccessible, etc.).
        console.error("Erreur de communication lors du polling:", e);
        return {
            error: true,
            data: {
                overall_status_text: "Erreur de Connexion",
                status_text: "Impossible de contacter le serveur de la télécommande.",
            }
        };
    }
}

/**
 * Envoie la commande pour déclencher le workflow sur le worker local.
 * @returns {Promise<object>} Un objet indiquant le succès ou l'échec de l'envoi.
 */
export async function triggerWorkflow() {
    try {
        const response = await fetch('/api/trigger_local_workflow', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: "start_manual_generic_from_remote_ui", source: "trigger_page_html" })
        });
        const data = await response.json();
        return { success: response.ok, data };
    } catch (e) {
        console.error("Erreur de communication lors du déclenchement:", e);
        return {
            success: false,
            data: { message: "Impossible de joindre le serveur pour le déclenchement." }
        };
    }
}

/**
 * Demande au backend de lancer la vérification des emails.
 * @returns {Promise<object>} Un objet indiquant le succès ou l'échec de la demande.
 */
export async function checkEmails() {
    try {
        const response = await fetch('/api/check_emails_and_download', { method: 'POST' });
        const data = await response.json();
        // Gère le cas où la session a expiré (401 Unauthorized)
        if (response.status === 401) {
            return { success: false, sessionExpired: true, data };
        }
        return { success: response.ok, data };
    } catch (e) {
        console.error("Erreur de communication lors de la vérification des emails:", e);
        return {
            success: false,
            data: { message: "Erreur de communication avec le serveur." }
        };
    }
}
