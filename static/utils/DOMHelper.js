export class DOMHelper {
    /**
     * Resolves a DOM element trying multiple strategies in order:
     * 1. Data-target attribute (e.g. data-target="myId")
     * 2. Data-action attribute (e.g. data-action="myId")
     * 3. CSS Selector (if identifier starts with # or .)
     * 4. Traditional ID (getElementById)
     * 
     * @param {string} identifier - The identifier to look for
     * @param {Element|Document} root - Optional root element to search within
     * @returns {Element|null} The resolved element or null
     */
    static getElement(identifier, root = document) {
        if (!identifier || typeof identifier !== 'string') return null;

        let el = root.querySelector(`[data-target="${identifier}"]`);
        if (el) return el;

        el = root.querySelector(`[data-action="${identifier}"]`);
        if (el) return el;

        if (identifier.startsWith('#') || identifier.startsWith('.')) {
            try {
                el = root.querySelector(identifier);
                if (el) return el;
            } catch (e) {
                // Invalid selector, ignore
            }
        }

        // Fallback for document.getElementById
        if (root === document) {
            return document.getElementById(identifier);
        }

        try {
            return root.querySelector(`#${identifier}`);
        } catch (e) {
            return null;
        }
    }

    /**
     * Resolves multiple DOM elements using the same strategies as getElement.
     * 
     * @param {string} identifier - The identifier to look for
     * @param {Element|Document} root - Optional root element to search within
     * @returns {NodeList|Array} The resolved elements list
     */
    static getElements(identifier, root = document) {
        if (!identifier || typeof identifier !== 'string') return [];

        let elements = root.querySelectorAll(`[data-target="${identifier}"]`);
        if (elements.length > 0) return elements;

        elements = root.querySelectorAll(`[data-action="${identifier}"]`);
        if (elements.length > 0) return elements;

        if (identifier.startsWith('#') || identifier.startsWith('.')) {
            try {
                elements = root.querySelectorAll(identifier);
                if (elements.length > 0) return elements;
            } catch (e) {
                // Invalid selector
            }
        }

        let el;
        if (root === document) {
            el = document.getElementById(identifier);
        } else {
            try {
                el = root.querySelector(`#${identifier}`);
            } catch (e) {
                el = null;
            }
        }
        
        return el ? [el] : [];
    }
}
