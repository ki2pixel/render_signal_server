export class TabManager {
    constructor() {
        this.tabs = [];
        this.activeTab = null;
        this.tabButtons = [];
        this.tabContents = [];
    }

    /**
     * Initialise le système d'onglets
     */
    init() {
        this.findTabElements();
        this.bindEvents();
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
     * Lie les événements aux boutons d'onglets
     */
    bindEvents() {
        this.tabButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = button.dataset.target;
                this.showTab(targetId);
            });
        });
    }

    /**
     * Affiche l'onglet initial (premier onglet ou celui marqué comme actif)
     */
    showInitialTab() {
        // Chercher d'abord un onglet marqué comme actif
        const activeButton = document.querySelector('.tab-btn.active');
        if (activeButton) {
            const targetId = activeButton.dataset.target;
            this.showTab(targetId);
            return;
        }
        
        // Sinon, afficher le premier onglet
        if (this.tabs.length > 0) {
            const firstTab = this.tabs[0];
            this.showTab(`#${firstTab.id}`);
        }
    }

    /**
     * Affiche un onglet spécifique avec lazy loading
     * @param {string} targetId - ID de la cible (ex: "#sec-overview")
     */
    showTab(targetId) {
        // Masquer tous les contenus d'onglets
        this.tabContents.forEach(content => {
            content.classList.remove('active');
            content.style.display = 'none';
        });
        
        // Désactiver tous les boutons
        this.tabButtons.forEach(button => {
            button.classList.remove('active');
            button.setAttribute('aria-selected', 'false');
        });
        
        // Afficher le contenu cible avec animation
        const targetContent = document.querySelector(targetId);
        if (targetContent) {
            targetContent.classList.add('active');
            targetContent.style.display = 'block';
            
            // Lazy loading: charger les données de l'onglet seulement lors du premier affichage
            this.lazyLoadTabContent(targetId.replace('#', ''));
        }
        
        // Activer le bouton cible
        const targetButton = document.querySelector(`[data-target="${targetId}"]`);
        if (targetButton) {
            targetButton.classList.add('active');
            targetButton.setAttribute('aria-selected', 'true');
        }
        
        // Mettre à jour l'onglet actif
        this.activeTab = targetId.replace('#', '');
        
        // Déclencher un événement personnalisé pour le changement d'onglet
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
     * Signale une erreur lors du chargement d'un onglet via un événement personnalisé
     * @param {string} tabId
     * @param {Error} error
     */
    dispatchTabLoadError(tabId, error) {
        document.dispatchEvent(new CustomEvent('tabloaderror', {
            detail: {
                tabId,
                error
            }
        }));
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
        this.tabButtons.forEach((button, index) => {
            button.setAttribute('role', 'tab');
            button.setAttribute('aria-controls', button.dataset.target.replace('#', ''));
            button.setAttribute('aria-selected', button.classList.contains('active'));
            button.setAttribute('tabindex', button.classList.contains('active') ? '0' : '-1');
        });
        
        this.tabContents.forEach(content => {
            const contentId = content.id || content.getAttribute('id');
            if (contentId) {
                content.setAttribute('role', 'tabpanel');
                content.setAttribute('aria-labelledby', contentId.replace('sec-', 'tab-'));
            }
        });
        
        // Gestion du clavier
        this.bindKeyboardEvents();
    }

    /**
     * Lie les événements clavier pour la navigation au clavier
     */
    bindKeyboardEvents() {
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
                    this.showTab(targetId);
                }
            });
        });
    }

    /**
     * Détruit le gestionnaire d'onglets et nettoie les événements
     */
    destroy() {
        this.tabButtons.forEach(button => {
            button.removeEventListener('click', this.handleTabClick);
            button.removeEventListener('keydown', this.handleKeyDown);
        });
        
        this.tabs = [];
        this.activeTab = null;
        this.tabButtons = [];
        this.tabContents = [];
        this.loadedTabs = null;
    }

    /**
     * Charge les données d'un onglet de manière paresseuse
     * @param {string} tabId - ID de l'onglet à charger
     */
    async lazyLoadTabContent(tabId) {
        // Vérifier si l'onglet a déjà été chargé
        if (this.isTabLoaded(tabId)) {
            return;
        }
        
        try {
            switch (tabId) {
                case 'sec-overview':
                    // Les logs sont déjà chargés via LogService
                    break;
                case 'sec-webhooks':
                    // La configuration webhooks est chargée au démarrage
                    break;
                case 'sec-email':
                    // Charger les préférences email si nécessaire
                    await this.loadEmailPreferences();
                    break;
                case 'sec-preferences':
                    // Charger les préférences de traitement si nécessaire
                    await this.loadProcessingPreferences();
                    break;
                case 'sec-tools':
                    // Les outils n'ont pas besoin de chargement supplémentaire
                    break;
            }
            
            // Marquer l'onglet comme chargé
            this.markTabAsLoaded(tabId);
        } catch (error) {
            this.dispatchTabLoadError(tabId, error);
        }
    }

    /**
     * Vérifie si un onglet a déjà été chargé
     * @param {string} tabId - ID de l'onglet
     * @returns {boolean} True si déjà chargé
     */
    isTabLoaded(tabId) {
        return this.loadedTabs && this.loadedTabs.has(tabId);
    }

    /**
     * Marque un onglet comme chargé
     * @param {string} tabId - ID de l'onglet
     */
    markTabAsLoaded(tabId) {
        if (!this.loadedTabs) {
            this.loadedTabs = new Set();
        }
        this.loadedTabs.add(tabId);
    }

    /**
     * Charge les préférences email (lazy loading)
     */
    async loadEmailPreferences() {
        // Cette fonction sera implémentée dans dashboard.js
        if (typeof window.loadPollingConfig === 'function') {
            await window.loadPollingConfig();
        }
    }

    /**
     * Charge les préférences de traitement (lazy loading)
     */
    async loadProcessingPreferences() {
        // Cette fonction sera implémentée dans dashboard.js
        if (typeof window.loadProcessingPrefsFromServer === 'function') {
            await window.loadProcessingPrefsFromServer();
        }
    }
}
