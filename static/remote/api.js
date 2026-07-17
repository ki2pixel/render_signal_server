import { ApiService } from '../services/ApiService.js';

export async function fetchStatus() {
    try {
        const response = await fetch('/api/get_local_status');
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({
                overall_status_text: `Erreur Serveur (${response.status})`,
                status_text: "Impossible de récupérer les détails de l'erreur.",
            }));
            return { error: true, data: errorData };
        }
        return { error: false, data: await response.json() };
    } catch (e) {
        return {
            error: true,
            data: {
                overall_status_text: "Erreur de Connexion",
                status_text: "Impossible de contacter le serveur de la télécommande.",
            }
        };
    }
}

export async function getWebhookTimeWindow() {
    try {
        const res = await fetch('/api/get_webhook_time_window');
        const data = await res.json();
        return { success: res.ok, data };
    } catch (e) {
        return { success: false, data: { message: 'Erreur de communication.' } };
    }
}

export async function setWebhookTimeWindow(start, end) {
    try {
        const res = await fetch('/api/set_webhook_time_window', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': ApiService._getCsrfToken() },
            body: JSON.stringify({ start, end })
        });
        const data = await res.json();
        return { success: res.ok, data };
    } catch (e) {
        return { success: false, data: { message: 'Erreur de communication.' } };
    }
}

export async function triggerWorkflow() {
    try {
        const response = await fetch('/api/trigger_local_workflow', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': ApiService._getCsrfToken() },
            body: JSON.stringify({ command: "start_manual_generic_from_remote_ui", source: "trigger_page_html" })
        });
        const data = await response.json();
        return { success: response.ok, data };
    } catch (e) {
        return {
            success: false,
            data: { message: "Impossible de joindre le serveur pour le déclenchement." }
        };
    }
}

export async function checkEmails() {
    try {
        const response = await fetch('/api/check_emails_and_download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': ApiService._getCsrfToken() }
        });
        const data = await response.json();
        if (response.status === 401) {
            return { success: false, sessionExpired: true, data };
        }
        return { success: response.ok, data };
    } catch (e) {
        return {
            success: false,
            data: { message: "Erreur de communication avec le serveur." }
        };
    }
}
