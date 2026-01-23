export class ApiService {
    /** Gère la réponse HTTP et redirige en cas d'erreur 401/403 */
    static async handleResponse(res) {
        if (res.status === 401) {
            window.location.href = '/login';
            throw new Error('Session expirée');
        }
        if (res.status === 403) {
            throw new Error('Accès refusé');
        }
        if (res.status >= 500) {
            throw new Error('Erreur serveur');
        }
        return res;
    }
    
    /** Effectue une requête API avec gestion centralisée des erreurs */
    static async request(url, options = {}) {
        const res = await fetch(url, options);
        return ApiService.handleResponse(res);
    }

    /** Requête GET avec parsing JSON automatique */
    static async get(url) {
        const res = await ApiService.request(url);
        return res.json();
    }

    /** Requête POST avec envoi JSON */
    static async post(url, data) {
        const res = await ApiService.request(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    }

    /** Requête PUT avec envoi JSON */
    static async put(url, data) {
        const res = await ApiService.request(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    }

    /** Requête DELETE */
    static async delete(url) {
        const res = await ApiService.request(url, { method: 'DELETE' });
        return res.json();
    }
}
