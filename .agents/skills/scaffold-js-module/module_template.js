import { ApiService } from '../services/ApiService.js';
import { MessageHelper } from '../utils/MessageHelper.js';

/**
 * Exemple de composant modulaire ES6 respectant les standards UX 2026.
 */
export class NewComponent {
    constructor() {
        /** @type {boolean} */
        this.initialized = false;
        /** @type {() => void | null} */
        this._visibilityHandler = null;
        /** @type {HTMLButtonElement | null} */
        this._actionButton = null;
    }

    /**
     * Initialise le composant (idempotent, accessibilité et timer safe).
     * @returns {Promise<void>}
     */
    async init() {
        if (this.initialized) return;

        try {
            await this.loadData();
            this.bindEvents();
            this._setupVisibilityHandler();
            this.initialized = true;
        } catch (error) {
            console.error('Erreur init NewComponent:', error);
            MessageHelper.showError('global', "Erreur d'initialisation");
        }
    }

    /**
     * Charge les données depuis l'API (Always Fallback côté UI aussi).
     * @returns {Promise<void>}
     */
    async loadData() {
        try {
            const data = await ApiService.get('/api/endpoint');
            if (!data?.success) {
                MessageHelper.showError('msgContainer', data?.message ?? 'Erreur de chargement');
                return;
            }
            // TODO: Implémenter le rendu UI ici
        } catch (error) {
            MessageHelper.showError('msgContainer', 'Erreur réseau, affichage des valeurs locales.');
        }
    }

    /**
     * Attache les écouteurs d'événements avec support ARIA / clavier.
     * @returns {void}
     */
    bindEvents() {
        this._actionButton = document.getElementById('actionBtn');
        if (!this._actionButton) {
            return;
        }

        this._actionButton.setAttribute('aria-live', 'polite');
        this._actionButton.setAttribute('data-role', 'primary-action');
        this._actionButton.addEventListener('click', () => this.handleAction());
        this._actionButton.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                this.handleAction();
            }
        });
    }

    /**
     * Traite l'action principale avec feedback UI.
     * @returns {Promise<void>}
     */
    async handleAction() {
        if (!this._actionButton) return;

        MessageHelper.setButtonLoading(this._actionButton, true);

        try {
            const result = await ApiService.post('/api/action', {});
            if (result?.success) {
                MessageHelper.showSuccess('msgContainer', 'Action réussie');
            } else {
                MessageHelper.showError('msgContainer', result?.message ?? 'Erreur');
            }
        } catch (error) {
            MessageHelper.showError('msgContainer', 'Erreur serveur');
        } finally {
            MessageHelper.setButtonLoading(this._actionButton, false);
        }
    }

    /**
     * Configure la Visibility API pour suspendre les timers / polling.
     * @private
     * @returns {void}
     */
    _setupVisibilityHandler() {
        this._visibilityHandler = () => {
            const hidden = document.visibilityState === 'hidden';
            if (hidden) {
                // Arrêter les timers/polling ici
            } else {
                // Relancer les timers/polling ici
            }
        };
        document.addEventListener('visibilitychange', this._visibilityHandler);
    }

    /**
     * Nettoie les écouteurs (à appeler lors du teardown du composant).
     * @returns {void}
     */
    destroy() {
        if (this._actionButton) {
            this._actionButton.replaceWith(this._actionButton.cloneNode(true));
            this._actionButton = null;
        }
        if (this._visibilityHandler) {
            document.removeEventListener('visibilitychange', this._visibilityHandler);
            this._visibilityHandler = null;
        }
        this.initialized = false;
    }
}
