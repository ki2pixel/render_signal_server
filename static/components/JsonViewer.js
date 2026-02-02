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

function createBranchNode(key, value, depth, options) {
    const node = document.createElement('details');
    node.className = 'json-node';
    if (depth < (options.collapseDepth ?? OPEN_DEPTH_DEFAULT)) {
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

    if (Array.isArray(value)) {
        value.forEach((childValue, index) => {
            if (isComplexValue(childValue)) {
                childrenContainer.appendChild(
                    createBranchNode(`[${index}]`, childValue, depth + 1, options)
                );
            } else {
                childrenContainer.appendChild(createLeafNode(`[${index}]`, childValue));
            }
        });
    } else {
        Object.keys(value).forEach((childKey) => {
            const childValue = value[childKey];
            if (isComplexValue(childValue)) {
                childrenContainer.appendChild(
                    createBranchNode(childKey, childValue, depth + 1, options)
                );
            } else {
                childrenContainer.appendChild(createLeafNode(childKey, childValue));
            }
        });
    }

    node.appendChild(childrenContainer);
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

        if (Array.isArray(data)) {
            data.forEach((value, index) => {
                if (isComplexValue(value)) {
                    root.appendChild(createBranchNode(`[${index}]`, value, 0, options));
                } else {
                    root.appendChild(createLeafNode(`[${index}]`, value));
                }
            });
        } else if (isComplexValue(data)) {
            Object.keys(data).forEach((key) => {
                const value = data[key];
                if (isComplexValue(value)) {
                    root.appendChild(createBranchNode(key, value, 0, options));
                } else {
                    root.appendChild(createLeafNode(key, value));
                }
            });
        } else {
            root.appendChild(createLeafNode(options.rootLabel ?? 'valeur', data));
        }

        container.appendChild(root);
    }
}
