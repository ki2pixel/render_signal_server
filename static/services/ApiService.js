export class ApiService {
    /**
     * Gère la réponse HTTP et redirige en cas d'erreur 401/403
     * @param {Response} res - Réponse HTTP
     * @returns {Promise<Response>} - Réponse traitée
     */
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
    
    /**
     * Effectue une requête API avec gestion centralisée des erreurs
     * @param {string} url - URL de l'API
     * @param {RequestInit} options - Options de la requête
     * @returns {Promise<Response>} - Réponse HTTP
     */
    static async request(url, options = {}) {
        const res = await fetch(url, options);
        return ApiService.handleResponse(res);
    }

    /**
     * Requête GET avec parsing JSON automatique
     * @param {string} url - URL de l'API
     * @returns {Promise<any>} - Données JSON
     */
    static async get(url) {
        const res = await ApiService.request(url);
        return res.json();
    }

    /**
     * Requête POST avec envoi JSON
     * @param {string} url - URL de l'API
     * @param {object} data - Données à envoyer
     * @returns {Promise<any>} - Réponse JSON
     */
    static async post(url, data) {
        const res = await ApiService.request(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    }

    /**
     * Requête PUT avec envoi JSON
     * @param {string} url - URL de l'API
     * @param {object} data - Données à envoyer
     * @returns {Promise<any>} - Réponse JSON
     */
    static async put(url, data) {
        const res = await ApiService.request(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    }

    /**
     * Requête DELETE
     * @param {string} url - URL de l'API
     * @returns {Promise<any>} - Réponse JSON
     */
    static async delete(url) {
        const res = await ApiService.request(url, { method: 'DELETE' });
        return res.json();
    }
}
