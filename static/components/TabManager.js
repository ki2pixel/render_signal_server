export class TabManager {
    constructor() {
        this.tabs = [];
        this.activeTab = null;
        this.tabButtons = [];
        this.tabContents = [];
        this._abortController = null;
        this._storageKey = 'dashboard_active_tab';
    }

    /**
     * Initialise le système d'onglets
     */
    init() {
        this._abortController = new AbortController();
        this.findTabElements();
        this.bindEvents();
        this.bindHashChange();
        this.showInitialTab();
    }

    /**
     * Trouve tous les éléments d'onglets dans la page
     */
    findTabElements() {
        this.tabButtons = document.querySelectorAll('.tab-btn');
        this.tabContents = document.querySelectorAll('.section-panel');
        
        this.tabButtons.forEach((button, index) => {
            const targetId = button.dataset.target;
            const targetContent = document.querySelector(targetId);
            
            if (targetContent) {
                this.tabs.push({
                    button: button,
                    content: targetContent,
                    id: targetId.replace('#', ''),
                    index: index
                });
            }
        });
    }

    /**
     * Lie les événements aux boutons d'onglets via AbortController
     */
    bindEvents() {
        const signal = this._abortController?.signal;
        this.tabButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = button.dataset.target;
                this.showTab(targetId, { focus: true });
            }, { signal });
        });
    }

    /**
     * Affiche l'onglet initial.
     * Priorité : location.hash → sessionStorage → .active HTML → premier onglet.
     */
    showInitialTab() {
        const hashTarget = this._resolveTabSelector(globalThis.location?.hash);
        if (hashTarget) {
            this.showTab(hashTarget, { focus: false });
            return;
        }

        const stored = this._readStoredTab();
        if (stored) {
            this.showTab(stored, { focus: false });
            return;
        }

        const activeButton = document.querySelector('.tab-btn.active');
        if (activeButton) {
            this.showTab(activeButton.dataset.target, { focus: false });
            return;
        }

        if (this.tabs.length > 0) {
            this.showTab(`#${this.tabs[0].id}`, { focus: false });
        }
    }

    /**
     * Résout un sélecteur d'onglet ("#sec-x") depuis un id brut ou un hash.
     * @param {string|null} raw - Hash ou id de panneau
     * @returns {string|null} Sélecteur valide pour data-target, sinon null
     */
    _resolveTabSelector(raw) {
        if (!raw) return null;
        const selector = raw.startsWith('#') ? raw : `#${raw}`;
        const exists = Array.from(this.tabButtons).some(btn => btn.dataset.target === selector);
        return exists ? selector : null;
    }

    /**
     * Lit l'onglet mémorisé en sessionStorage.
     * @returns {string|null} Sélecteur d'onglet ou null
     */
    _readStoredTab() {
        try {
            return this._resolveTabSelector(sessionStorage.getItem(this._storageKey));
        } catch {
            return null;
        }
    }

    /**
     * Mémorise l'onglet actif et met à jour le hash sans scroll.
     * @param {string} targetId - Sélecteur d'onglet (ex: "#sec-tools")
     */
    _persistActiveTab(targetId) {
        try {
            sessionStorage.setItem(this._storageKey, targetId);
        } catch {
            // stockage indisponible — ignorer
        }
        if (globalThis.history?.replaceState && globalThis.location?.hash !== targetId) {
            globalThis.history.replaceState(null, '', targetId);
        }
    }

    /**
     * Réagit aux changements de hash (lien partagé, précédent/suivant).
     */
    bindHashChange() {
        const signal = this._abortController?.signal;
        globalThis.addEventListener('hashchange', () => {
            const targetId = this._resolveTabSelector(globalThis.location?.hash);
            if (targetId && targetId !== `#${this.activeTab}`) {
                this.showTab(targetId, { focus: false });
            }
        }, { signal });
    }

    /**
     * Affiche un onglet spécifique
     * @param {string} targetId - ID de la cible (ex: "#sec-overview")
     * @param {{focus?: boolean}} [options] - Placer le focus sur le bouton activé
     */
    showTab(targetId, options = {}) {
        this.tabContents.forEach(content => {
            content.classList.remove('active');
            content.style.display = 'none';
        });
        
        this.tabButtons.forEach(button => {
            button.classList.remove('active');
            button.setAttribute('aria-selected', 'false');
            button.setAttribute('aria-current', 'false');
            button.setAttribute('tabindex', '-1');
        });
        
        const targetContent = document.querySelector(targetId);
        if (targetContent) {
            targetContent.classList.add('active');
            targetContent.style.display = 'block';
        }
        
        const targetButton = document.querySelector(`[data-target="${targetId}"]`);
        if (targetButton) {
            targetButton.classList.add('active');
            targetButton.setAttribute('aria-selected', 'true');
            targetButton.setAttribute('aria-current', 'true');
            targetButton.setAttribute('tabindex', '0');
            if (options.focus) {
                targetButton.focus();
            }
        }
        
        this.activeTab = targetId.replace('#', '');
        this._persistActiveTab(targetId);
        
        this.dispatchTabChange(targetId);
    }

    /**
     * Déclenche un événement de changement d'onglet
     * @param {string} targetId - ID de l'onglet affiché
     */
    dispatchTabChange(targetId) {
        const event = new CustomEvent('tabchange', {
            detail: {
                tabId: targetId.replace('#', ''),
                targetId: targetId
            }
        });
        document.dispatchEvent(event);
    }

    /**
     * Obtient l'onglet actuellement actif
     * @returns {string|null} ID de l'onglet actif
     */
    getActiveTab() {
        return this.activeTab;
    }

    /**
     * Vérifie si un onglet spécifique est actif
     * @param {string} tabId - ID de l'onglet à vérifier
     * @returns {boolean} True si l'onglet est actif
     */
    isTabActive(tabId) {
        return this.activeTab === tabId;
    }

    /**
     * Ajoute des attributs ARIA pour l'accessibilité
     */
    enhanceAccessibility() {
        const tabList = this.tabButtons[0]?.parentElement;
        if (tabList) {
            tabList.setAttribute('role', 'tablist');
        }

        this.tabButtons.forEach((button) => {
            button.setAttribute('role', 'tab');
            button.setAttribute('aria-controls', button.dataset.target.replace('#', ''));
            button.setAttribute('aria-selected', String(button.classList.contains('active')));
            button.setAttribute('aria-current', String(button.classList.contains('active')));
            button.setAttribute('tabindex', button.classList.contains('active') ? '0' : '-1');
        });
        
        this.tabContents.forEach(content => {
            const contentId = content.id || content.getAttribute('id');
            if (contentId) {
                content.setAttribute('role', 'tabpanel');
                content.setAttribute('aria-labelledby', contentId.replace('sec-', 'tab-'));
            }
        });
        
        this.bindKeyboardEvents();
    }

    /**
     * Lie les événements clavier pour la navigation au clavier via AbortController
     */
    bindKeyboardEvents() {
        const signal = this._abortController?.signal;
        this.tabButtons.forEach((button, index) => {
            button.addEventListener('keydown', (e) => {
                let targetIndex = index;
                
                switch (e.key) {
                    case 'ArrowLeft':
                    case 'ArrowUp':
                        e.preventDefault();
                        targetIndex = index > 0 ? index - 1 : this.tabButtons.length - 1;
                        break;
                    case 'ArrowRight':
                    case 'ArrowDown':
                        e.preventDefault();
                        targetIndex = index < this.tabButtons.length - 1 ? index + 1 : 0;
                        break;
                    case 'Home':
                        e.preventDefault();
                        targetIndex = 0;
                        break;
                    case 'End':
                        e.preventDefault();
                        targetIndex = this.tabButtons.length - 1;
                        break;
                    default:
                        return;
                }
                
                const targetButton = this.tabButtons[targetIndex];
                if (targetButton) {
                    targetButton.focus();
                    const targetId = targetButton.dataset.target;
                    this.showTab(targetId, { focus: true });
                }
            }, { signal });
        });
    }

    /**
     * Détruit le gestionnaire d'onglets et nettoie les événements via AbortController
     */
    destroy() {
        if (this._abortController) {
            this._abortController.abort();
            this._abortController = null;
        }
        
        this.tabs = [];
        this.activeTab = null;
        this.tabButtons = [];
        this.tabContents = [];
    }
}
