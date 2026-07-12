export class TabManager {
    constructor() {
        this.tabs = [];
        this.activeTab = null;
        this.tabButtons = [];
        this.tabContents = [];
        this._abortController = null;
    }

    /**
     * Initialise le système d'onglets
     */
    init() {
        this._abortController = new AbortController();
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
     * Lie les événements aux boutons d'onglets via AbortController
     */
    bindEvents() {
        const signal = this._abortController?.signal;
        this.tabButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = button.dataset.target;
                this.showTab(targetId);
            }, { signal });
        });
    }

    /**
     * Affiche l'onglet initial (premier onglet ou celui marqué comme actif)
     */
    showInitialTab() {
        const activeButton = document.querySelector('.tab-btn.active');
        if (activeButton) {
            const targetId = activeButton.dataset.target;
            this.showTab(targetId);
            return;
        }
        
        if (this.tabs.length > 0) {
            const firstTab = this.tabs[0];
            this.showTab(`#${firstTab.id}`);
        }
    }

    /**
     * Affiche un onglet spécifique
     * @param {string} targetId - ID de la cible (ex: "#sec-overview")
     */
    showTab(targetId) {
        this.tabContents.forEach(content => {
            content.classList.remove('active');
            content.style.display = 'none';
        });
        
        this.tabButtons.forEach(button => {
            button.classList.remove('active');
            button.setAttribute('aria-selected', 'false');
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
            targetButton.setAttribute('tabindex', '0');
        }
        
        this.activeTab = targetId.replace('#', '');
        
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
                    this.showTab(targetId);
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
