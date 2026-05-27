const OPEN_DEPTH_DEFAULT = 1;

function isComplexValue(value) {
    return value !== null && typeof value === 'object';
}

function formatPrimitive(value) {
    if (value === null) {
        return 'null';
    }

    if (typeof value === 'string') {
        return `"${value}"`;
    }

    if (typeof value === 'undefined') {
        return 'undefined';
    }

    return String(value);
}

function describeCollection(value) {
    if (Array.isArray(value)) {
        return `[${value.length}]`;
    }

    return `{${Object.keys(value).length}}`;
}

function getValueType(value) {
    if (value === null) {
        return 'null';
    }

    if (Array.isArray(value)) {
        return 'array';
    }

    return typeof value;
}

function createLeafNode(key, value) {
    const row = document.createElement('div');
    row.className = 'json-leaf';

    const keyEl = document.createElement('span');
    keyEl.className = 'json-key';
    keyEl.textContent = key ?? 'valeur';

    const valueEl = document.createElement('span');
    const type = getValueType(value);
    valueEl.className = `json-value json-value--${type}`;
    valueEl.textContent = formatPrimitive(value);

    row.append(keyEl, valueEl);
    return row;
}

function renderItemsChunk(container, entries, startIndex, count, depth, options) {
    const endIndex = Math.min(startIndex + count, entries.length);
    for (let i = startIndex; i < endIndex; i++) {
        const { key, val } = entries[i];
        if (isComplexValue(val)) {
            container.appendChild(createBranchNode(key, val, depth + 1, options));
        } else {
            container.appendChild(createLeafNode(key, val));
        }
    }

    if (endIndex < entries.length) {
        const remaining = entries.length - endIndex;
        const btn = document.createElement('button');
        btn.className = 'json-show-more-btn';
        btn.textContent = `Afficher plus (${remaining} restants)...`;
        btn.addEventListener('click', () => {
            btn.remove();
            renderItemsChunk(container, entries, endIndex, count, depth, options);
        });
        container.appendChild(btn);
    }
}

function createBranchNode(key, value, depth, options) {
    const node = document.createElement('details');
    node.className = 'json-node';
    const isOpenInitially = depth < (options.collapseDepth ?? OPEN_DEPTH_DEFAULT);
    if (isOpenInitially) {
        node.open = true;
    }

    const summary = document.createElement('summary');
    summary.className = 'json-node-summary';

    const keyEl = document.createElement('span');
    keyEl.className = 'json-key';
    keyEl.textContent = key ?? '(clé)';

    const metaEl = document.createElement('span');
    metaEl.className = 'json-meta';
    metaEl.textContent = describeCollection(value);

    summary.append(keyEl, metaEl);
    node.appendChild(summary);

    const childrenContainer = document.createElement('div');
    childrenContainer.className = 'json-children';
    node.appendChild(childrenContainer);

    let entries = [];
    if (Array.isArray(value)) {
        entries = value.map((val, index) => ({ key: `[${index}]`, val }));
    } else {
        entries = Object.keys(value).map(childKey => ({ key: childKey, val: value[childKey] }));
    }

    const maxItems = options.maxItemsPerNode ?? 100;

    if (isOpenInitially) {
        renderItemsChunk(childrenContainer, entries, 0, maxItems, depth, options);
    } else {
        node.addEventListener('toggle', function onToggle() {
            if (node.open && childrenContainer.children.length === 0) {
                renderItemsChunk(childrenContainer, entries, 0, maxItems, depth, options);
            }
        }, { once: true });
    }

    return node;
}

export class JsonViewer {
    static render(container, data, options = {}) {
        if (!container) {
            return;
        }

        container.classList.add('json-viewer-wrapper');
        container.replaceChildren();

        const root = document.createElement('div');
        root.className = 'json-viewer';

        if (isComplexValue(data)) {
            let entries = [];
            if (Array.isArray(data)) {
                entries = data.map((val, index) => ({ key: `[${index}]`, val }));
            } else {
                entries = Object.keys(data).map(key => ({ key, val: data[key] }));
            }
            const maxItems = options.maxItemsPerNode ?? 100;
            renderItemsChunk(root, entries, 0, maxItems, -1, options);
        } else {
            root.appendChild(createLeafNode(options.rootLabel ?? 'valeur', data));
        }

        container.appendChild(root);
    }
}
