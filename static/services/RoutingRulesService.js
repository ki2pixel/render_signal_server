import { ApiService } from './ApiService.js';
import { MessageHelper } from '../utils/MessageHelper.js';

const FIELD_OPTIONS = [
    { value: 'sender', label: 'Expéditeur' },
    { value: 'subject', label: 'Sujet' },
    { value: 'body', label: 'Corps' }
];

const OPERATOR_OPTIONS = [
    { value: 'contains', label: 'Contient' },
    { value: 'equals', label: 'Est égal à' },
    { value: 'regex', label: 'Regex' }
];

const PRIORITY_OPTIONS = [
    { value: 'normal', label: 'Normal' },
    { value: 'high', label: 'Haute' }
];

/**
 * Service UI pour gérer le moteur de règles de routage dynamiques.
 */
export class RoutingRulesService {
    constructor() {
        /** @type {boolean} */
        this.initialized = false;
        /** @type {Array} */
        this.rules = [];
        /** @type {HTMLElement | null} */
        this.container = null;
        /** @type {HTMLElement | null} */
        this.panel = null;
        /** @type {HTMLButtonElement | null} */
        this.addButton = null;
        /** @type {HTMLButtonElement | null} */
        this.reloadButton = null;
        /** @type {number | null} */
        this._saveTimer = null;
        /** @type {number} */
        this._saveDelayMs = 2500;
        /** @type {string} */
        this.panelId = 'routing-rules';
        /** @type {string} */
        this.messageId = 'routing-rules-msg';
        /** @type {boolean} */
        this._usingBackendFallback = false;
    }

    /**
     * Initialise le panneau des règles de routage.
     * @returns {Promise<void>}
     */
    async init() {
        if (this.initialized) return;
        this.container = document.getElementById('routingRulesList');
        this.panel = document.querySelector('.collapsible-panel[data-panel="routing-rules"]');
        this.addButton = document.getElementById('addRoutingRuleBtn');
        this.reloadButton = document.getElementById('reloadRoutingRulesBtn');

        if (!this.container) {
            return;
        }

        this._bindEvents();
        await this.loadRules(true);
        this.initialized = true;
    }

    /**
     * Charge les règles depuis l'API et rend l'UI.
     * @param {boolean} silent
     * @returns {Promise<void>}
     */
    async loadRules(silent = false) {
        try {
            const response = await ApiService.get('/api/routing_rules');
            if (!response?.success) {
                if (!silent) {
                    MessageHelper.showError(this.messageId, response?.message || 'Erreur de chargement.');
                }
                return;
            }
            const config = response?.config || {};
            const rules = Array.isArray(config.rules) ? config.rules : [];
            const fallbackRule = response?.fallback_rule;
            // Pourquoi : montrer la règle backend existante quand aucune règle UI n'est encore enregistrée.
            const hydratedRules = rules.length
                ? rules
                : (fallbackRule && typeof fallbackRule === 'object'
                    ? [{ ...fallbackRule, _isBackendFallback: true }]
                    : []);
            this._usingBackendFallback = !rules.length && Boolean(fallbackRule);
            this.rules = hydratedRules;
            this._renderRules();
            this._setPanelStatus('saved', false);
            if (!silent) {
                MessageHelper.showSuccess(this.messageId, 'Règles chargées.');
            }
        } catch (error) {
            console.error('RoutingRules load error:', error);
            if (!silent) {
                MessageHelper.showError(this.messageId, 'Erreur réseau lors du chargement.');
            }
        }
    }

    _bindEvents() {
        if (this.addButton) {
            this.addButton.addEventListener('click', () => this._handleAddRule());
        }
        if (this.reloadButton) {
            this.reloadButton.addEventListener('click', () => this.loadRules(false));
        }
        if (!this.container) return;

        this.container.addEventListener('input', () => this._markDirty());
        this.container.addEventListener('change', () => this._markDirty());

        this.container.addEventListener('click', (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            const actionButton = target.closest('[data-action]');
            if (!actionButton) return;
            event.preventDefault();
            const action = actionButton.getAttribute('data-action');
            const ruleCard = actionButton.closest('.routing-rule-card');
            if (!ruleCard) return;

            switch (action) {
                case 'add-condition':
                    this._addConditionRow(ruleCard);
                    break;
                case 'remove-rule':
                    this._removeRule(ruleCard);
                    break;
                case 'move-up':
                    this._moveRule(ruleCard, -1);
                    break;
                case 'move-down':
                    this._moveRule(ruleCard, 1);
                    break;
                case 'remove-condition':
                    this._removeCondition(actionButton);
                    break;
                default:
                    break;
            }
        });
    }

    _handleAddRule() {
        if (!this.container) return;
        const newRule = this._createEmptyRule();
        this.rules.push(newRule);
        const card = this._buildRuleCard(newRule, this.rules.length - 1);
        this.container.appendChild(card);
        this._markDirty();
    }

    _addConditionRow(ruleCard) {
        const conditionsContainer = ruleCard.querySelector('.routing-conditions');
        if (!conditionsContainer) return;
        const row = this._buildConditionRow({});
        conditionsContainer.appendChild(row);
        this._markDirty();
    }

    _removeCondition(button) {
        const row = button.closest('.routing-condition-row');
        if (!row || !this.container) return;
        const container = row.parentElement;
        row.remove();
        if (container && container.querySelectorAll('.routing-condition-row').length === 0) {
            const emptyRow = this._buildConditionRow({});
            container.appendChild(emptyRow);
        }
        this._markDirty();
    }

    _removeRule(ruleCard) {
        ruleCard.remove();
        this._markDirty();
    }

    _moveRule(ruleCard, direction) {
        if (!this.container) return;
        const siblings = Array.from(this.container.querySelectorAll('.routing-rule-card'));
        const index = siblings.indexOf(ruleCard);
        if (index === -1) return;
        const nextIndex = index + direction;
        if (nextIndex < 0 || nextIndex >= siblings.length) return;
        const referenceNode = direction > 0 ? siblings[nextIndex].nextSibling : siblings[nextIndex];
        this.container.insertBefore(ruleCard, referenceNode);
        this._markDirty();
    }

    _renderRules() {
        if (!this.container) return;
        while (this.container.firstChild) {
            this.container.removeChild(this.container.firstChild);
        }

        if (!this.rules.length) {
            const empty = document.createElement('div');
            empty.className = 'routing-empty';
            empty.textContent = 'Aucune règle configurée. Ajoutez une règle pour commencer.';
            this.container.appendChild(empty);
            return;
        }

        this.rules.forEach((rule, index) => {
            const card = this._buildRuleCard(rule, index);
            this.container.appendChild(card);
        });
    }

    _buildRuleCard(rule, index) {
        const normalizedRule = this._normalizeRule(rule, index);
        const card = document.createElement('div');
        card.className = 'routing-rule-card';
        card.dataset.ruleId = normalizedRule.id;

        const header = document.createElement('div');
        header.className = 'routing-rule-header';

        const titleWrap = document.createElement('div');
        titleWrap.className = 'routing-rule-title';

        const nameLabel = document.createElement('label');
        nameLabel.textContent = 'Nom de règle';
        nameLabel.setAttribute('for', `${normalizedRule.id}-name`);

        const nameInput = document.createElement('input');
        nameInput.className = 'routing-input';
        nameInput.type = 'text';
        nameInput.value = normalizedRule.name;
        nameInput.id = `${normalizedRule.id}-name`;
        nameInput.setAttribute('data-field', 'rule-name');
        nameInput.setAttribute('aria-label', 'Nom de règle');

        const badgeWrap = document.createElement('div');
        badgeWrap.className = 'routing-rule-badges';
        if (rule._isBackendFallback) {
            const badge = document.createElement('span');
            badge.className = 'routing-badge backend-fallback';
            badge.textContent = 'Règle backend par défaut';
            badge.setAttribute('title', 'Renvoyée depuis la configuration backend tant qu’aucune règle personnalisée n’est sauvegardée.');
            badgeWrap.appendChild(badge);
        }

        titleWrap.appendChild(nameLabel);
        titleWrap.appendChild(nameInput);
        if (badgeWrap.children.length) {
            titleWrap.appendChild(badgeWrap);
        }

        const controls = document.createElement('div');
        controls.className = 'routing-rule-controls';

        const moveUp = this._buildIconButton('⬆️', 'Déplacer vers le haut', 'move-up');
        const moveDown = this._buildIconButton('⬇️', 'Déplacer vers le bas', 'move-down');
        const remove = this._buildIconButton('🗑️', 'Supprimer la règle', 'remove-rule');

        controls.appendChild(moveUp);
        controls.appendChild(moveDown);
        controls.appendChild(remove);

        header.appendChild(titleWrap);
        header.appendChild(controls);

        const conditionsTitle = document.createElement('div');
        conditionsTitle.className = 'routing-section-title';
        conditionsTitle.textContent = 'Conditions';

        const conditionsContainer = document.createElement('div');
        conditionsContainer.className = 'routing-conditions';

        normalizedRule.conditions.forEach((condition) => {
            const row = this._buildConditionRow(condition);
            conditionsContainer.appendChild(row);
        });

        const addConditionBtn = document.createElement('button');
        addConditionBtn.type = 'button';
        addConditionBtn.className = 'btn btn-secondary btn-small routing-add-btn';
        addConditionBtn.textContent = '➕ Ajouter une condition';
        addConditionBtn.setAttribute('data-action', 'add-condition');

        const actionsTitle = document.createElement('div');
        actionsTitle.className = 'routing-section-title';
        actionsTitle.textContent = 'Actions';

        const actionsContainer = document.createElement('div');
        actionsContainer.className = 'routing-actions';

        const webhookLabel = document.createElement('label');
        webhookLabel.textContent = 'Webhook cible (HTTPS ou token Make)';
        webhookLabel.setAttribute('for', `${normalizedRule.id}-webhook`);

        const webhookInput = document.createElement('input');
        webhookInput.type = 'text';
        webhookInput.className = 'routing-input';
        webhookInput.value = normalizedRule.actions.webhook_url;
        webhookInput.id = `${normalizedRule.id}-webhook`;
        webhookInput.setAttribute('data-field', 'webhook-url');
        webhookInput.setAttribute('placeholder', 'https://hook.eu2.make.com/xxx');
        webhookInput.setAttribute('aria-label', 'URL webhook');

        const priorityWrap = document.createElement('div');
        priorityWrap.className = 'routing-inline';

        const priorityLabel = document.createElement('label');
        priorityLabel.textContent = 'Priorité';
        priorityLabel.setAttribute('for', `${normalizedRule.id}-priority`);

        const prioritySelect = this._buildSelect(PRIORITY_OPTIONS, normalizedRule.actions.priority);
        prioritySelect.id = `${normalizedRule.id}-priority`;
        prioritySelect.setAttribute('data-field', 'priority');
        prioritySelect.setAttribute('aria-label', 'Priorité');

        priorityWrap.appendChild(priorityLabel);
        priorityWrap.appendChild(prioritySelect);

        const stopWrap = document.createElement('div');
        stopWrap.className = 'routing-inline';

        const stopLabel = document.createElement('label');
        stopLabel.textContent = 'Stop après correspondance';
        stopLabel.setAttribute('for', `${normalizedRule.id}-stop`);

        const stopToggle = document.createElement('input');
        stopToggle.type = 'checkbox';
        stopToggle.id = `${normalizedRule.id}-stop`;
        stopToggle.checked = normalizedRule.actions.stop_processing;
        stopToggle.setAttribute('data-field', 'stop-processing');
        stopToggle.setAttribute('aria-label', 'Stop après correspondance');

        stopWrap.appendChild(stopLabel);
        stopWrap.appendChild(stopToggle);

        actionsContainer.appendChild(webhookLabel);
        actionsContainer.appendChild(webhookInput);
        actionsContainer.appendChild(priorityWrap);
        actionsContainer.appendChild(stopWrap);

        card.appendChild(header);
        card.appendChild(conditionsTitle);
        card.appendChild(conditionsContainer);
        card.appendChild(addConditionBtn);
        card.appendChild(actionsTitle);
        card.appendChild(actionsContainer);

        return card;
    }

    _buildConditionRow(condition) {
        const row = document.createElement('div');
        row.className = 'routing-condition-row';

        const fieldSelect = this._buildSelect(FIELD_OPTIONS, condition.field || 'sender');
        fieldSelect.setAttribute('data-field', 'condition-field');
        fieldSelect.setAttribute('aria-label', 'Champ de condition');

        const operatorSelect = this._buildSelect(OPERATOR_OPTIONS, condition.operator || 'contains');
        operatorSelect.setAttribute('data-field', 'condition-operator');
        operatorSelect.setAttribute('aria-label', 'Opérateur');

        const valueInput = document.createElement('input');
        valueInput.type = 'text';
        valueInput.className = 'routing-input';
        valueInput.value = condition.value || '';
        valueInput.setAttribute('data-field', 'condition-value');
        valueInput.setAttribute('aria-label', 'Valeur');
        valueInput.setAttribute('placeholder', 'ex: facture');

        const caseWrap = document.createElement('label');
        caseWrap.className = 'routing-checkbox';

        const caseToggle = document.createElement('input');
        caseToggle.type = 'checkbox';
        caseToggle.checked = Boolean(condition.case_sensitive);
        caseToggle.setAttribute('data-field', 'condition-case');
        caseToggle.setAttribute('aria-label', 'Sensible à la casse');

        const caseText = document.createElement('span');
        caseText.textContent = 'Casse';

        caseWrap.appendChild(caseToggle);
        caseWrap.appendChild(caseText);

        const removeBtn = this._buildIconButton('✖', 'Supprimer condition', 'remove-condition');

        row.appendChild(fieldSelect);
        row.appendChild(operatorSelect);
        row.appendChild(valueInput);
        row.appendChild(caseWrap);
        row.appendChild(removeBtn);

        return row;
    }

    _buildSelect(options, value) {
        const select = document.createElement('select');
        select.className = 'routing-select';
        options.forEach((option) => {
            const opt = document.createElement('option');
            opt.value = option.value;
            opt.textContent = option.label;
            if (option.value === value) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });
        return select;
    }

    _buildIconButton(symbol, label, action) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'routing-icon-btn';
        button.textContent = symbol;
        button.setAttribute('aria-label', label);
        button.setAttribute('data-action', action);
        return button;
    }

    _normalizeRule(rule, index) {
        const id = String(rule?.id || '').trim() || this._generateRuleId(index);
        const name = String(rule?.name || '').trim() || `Règle ${index + 1}`;
        const conditions = Array.isArray(rule?.conditions) && rule.conditions.length
            ? rule.conditions
            : [this._createEmptyCondition()];
        const actions = rule?.actions || {};
        return {
            id,
            name,
            conditions,
            actions: {
                webhook_url: String(actions.webhook_url || '').trim(),
                priority: String(actions.priority || 'normal').trim().toLowerCase(),
                stop_processing: Boolean(actions.stop_processing)
            }
        };
    }

    _createEmptyRule() {
        return {
            id: this._generateRuleId(this.rules.length),
            name: `Règle ${this.rules.length + 1}`,
            conditions: [this._createEmptyCondition()],
            actions: {
                webhook_url: '',
                priority: 'normal',
                stop_processing: false
            }
        };
    }

    _createEmptyCondition() {
        return {
            field: 'sender',
            operator: 'contains',
            value: '',
            case_sensitive: false
        };
    }

    _generateRuleId(index) {
        return `rule-${Date.now()}-${index}`;
    }

    _markDirty() {
        this._setPanelStatus('dirty');
        this._setPanelClass('modified');
        this._scheduleSave();
    }

    _scheduleSave() {
        if (this._saveTimer) {
            window.clearTimeout(this._saveTimer);
        }
        this._setPanelStatus('saving');
        this._saveTimer = window.setTimeout(() => {
            this.saveRules();
        }, this._saveDelayMs);
    }

    async saveRules() {
        const { rules, errors } = this._collectRulesFromDom();
        if (errors.length) {
            MessageHelper.showError(this.messageId, errors[0]);
            this._setPanelStatus('error');
            return;
        }

        try {
            const response = await ApiService.post('/api/routing_rules', { rules });
            if (!response?.success) {
                MessageHelper.showError(this.messageId, response?.message || 'Erreur lors de la sauvegarde.');
                this._setPanelStatus('error');
                return;
            }
            const config = response?.config || {};
            this.rules = Array.isArray(config.rules) ? config.rules : rules;
            this._renderRules();
            this._setPanelStatus('saved');
            this._setPanelClass('saved');
            this._updatePanelIndicator();
            MessageHelper.showSuccess(this.messageId, 'Règles enregistrées.');
        } catch (error) {
            console.error('RoutingRules save error:', error);
            MessageHelper.showError(this.messageId, 'Erreur réseau lors de la sauvegarde.');
            this._setPanelStatus('error');
        }
    }

    _collectRulesFromDom() {
        const errors = [];
        const rules = [];
        if (!this.container) {
            return { rules, errors };
        }
        this._clearInvalidMarkers();
        const cards = Array.from(this.container.querySelectorAll('.routing-rule-card'));

        cards.forEach((card, index) => {
            const nameInput = card.querySelector('[data-field="rule-name"]');
            const webhookInput = card.querySelector('[data-field="webhook-url"]');
            const prioritySelect = card.querySelector('[data-field="priority"]');
            const stopToggle = card.querySelector('[data-field="stop-processing"]');
            const nameValue = (nameInput?.value || '').trim();
            const webhookValue = (webhookInput?.value || '').trim();

            if (!nameValue) {
                errors.push('Le nom de la règle est requis.');
                nameInput?.classList.add('routing-invalid');
            }

            const webhookCheck = this._validateWebhookUrl(webhookValue);
            if (!webhookCheck.ok) {
                errors.push(webhookCheck.message);
                webhookInput?.classList.add('routing-invalid');
            }

            const conditions = [];
            const conditionRows = Array.from(card.querySelectorAll('.routing-condition-row'));
            conditionRows.forEach((row) => {
                const fieldSelect = row.querySelector('[data-field="condition-field"]');
                const operatorSelect = row.querySelector('[data-field="condition-operator"]');
                const valueInput = row.querySelector('[data-field="condition-value"]');
                const caseToggle = row.querySelector('[data-field="condition-case"]');
                const fieldValue = String(fieldSelect?.value || '').trim();
                const operatorValue = String(operatorSelect?.value || '').trim();
                const valueValue = String(valueInput?.value || '').trim();

                if (!fieldValue || !operatorValue || !valueValue) {
                    if (!valueValue) {
                        valueInput?.classList.add('routing-invalid');
                    }
                    return;
                }

                conditions.push({
                    field: fieldValue,
                    operator: operatorValue,
                    value: valueValue,
                    case_sensitive: Boolean(caseToggle?.checked)
                });
            });

            if (!conditions.length) {
                errors.push('Chaque règle doit contenir au moins une condition.');
            }

            if (!errors.length) {
                rules.push({
                    id: card.dataset.ruleId || this._generateRuleId(index),
                    name: nameValue,
                    conditions,
                    actions: {
                        webhook_url: webhookValue,
                        priority: String(prioritySelect?.value || 'normal').trim(),
                        stop_processing: Boolean(stopToggle?.checked)
                    }
                });
            }
        });

        return { rules, errors };
    }

    _validateWebhookUrl(value) {
        if (!value) {
            return { ok: false, message: 'Webhook cible requis pour chaque règle.' };
        }
        if (value.startsWith('https://')) {
            return { ok: true, message: '' };
        }
        if (value.startsWith('http://')) {
            return { ok: false, message: 'Utilisez HTTPS pour le webhook cible.' };
        }
        const tokenLike = /^[A-Za-z0-9_-]+(@hook\.eu\d+\.make\.com)?$/.test(value);
        if (tokenLike) {
            return { ok: true, message: '' };
        }
        return { ok: false, message: 'Format de webhook invalide (HTTPS ou token Make).' };
    }

    _setPanelStatus(state, autoReset = true) {
        const statusEl = document.getElementById(`${this.panelId}-status`);
        if (!statusEl) return;
        const states = {
            dirty: 'Sauvegarde requise',
            saving: 'Sauvegarde…',
            saved: 'Sauvegardé',
            error: 'Erreur'
        };
        statusEl.textContent = states[state] || states.dirty;
        if (state === 'saved') {
            statusEl.classList.add('saved');
        } else {
            statusEl.classList.remove('saved');
        }
        if (state === 'saved' && autoReset) {
            window.setTimeout(() => {
                statusEl.textContent = states.dirty;
                statusEl.classList.remove('saved');
            }, 3000);
        }
    }

    _setPanelClass(state) {
        if (!this.panel) return;
        this.panel.classList.remove('modified', 'saved');
        if (state === 'modified') {
            this.panel.classList.add('modified');
        }
        if (state === 'saved') {
            this.panel.classList.add('saved');
            window.setTimeout(() => {
                this.panel?.classList.remove('saved');
            }, 2000);
        }
    }

    _updatePanelIndicator() {
        const indicator = document.getElementById(`${this.panelId}-indicator`);
        if (!indicator) return;
        const now = new Date();
        indicator.textContent = `Dernière sauvegarde: ${now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`;
    }

    _clearInvalidMarkers() {
        if (!this.container) return;
        this.container.querySelectorAll('.routing-invalid').forEach((el) => {
            el.classList.remove('routing-invalid');
        });
    }
}
