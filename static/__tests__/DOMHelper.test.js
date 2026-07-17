import { describe, it, expect, beforeEach } from 'vitest';
import { DOMHelper } from '../utils/DOMHelper.js';

describe('DOMHelper', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <div id="testId">By ID</div>
            <div data-target="testTarget">By Target</div>
            <div data-action="testAction">By Action</div>
            <div class="testClass">By Class</div>
            <div data-target="multiTarget">Multi 1</div>
            <div data-target="multiTarget">Multi 2</div>
        `;
    });

    describe('getElement', () => {
        it('should find element by ID', () => {
            const el = DOMHelper.getElement('testId');
            expect(el).not.toBeNull();
            expect(el.textContent).toBe('By ID');
        });

        it('should find element by data-target attribute', () => {
            const el = DOMHelper.getElement('testTarget');
            expect(el).not.toBeNull();
            expect(el.textContent).toBe('By Target');
        });

        it('should find element by data-action attribute', () => {
            const el = DOMHelper.getElement('testAction');
            expect(el).not.toBeNull();
            expect(el.textContent).toBe('By Action');
        });

        it('should find element by CSS selector (.class)', () => {
            const el = DOMHelper.getElement('.testClass');
            expect(el).not.toBeNull();
            expect(el.textContent).toBe('By Class');
        });

        it('should return null for non-existent element', () => {
            const el = DOMHelper.getElement('nonexistent');
            expect(el).toBeNull();
        });

        it('should return null for empty string', () => {
            expect(DOMHelper.getElement('')).toBeNull();
        });

        it('should return null for non-string input', () => {
            expect(DOMHelper.getElement(null)).toBeNull();
            expect(DOMHelper.getElement(undefined)).toBeNull();
        });
    });

    describe('getElements', () => {
        it('should return multiple elements by data-target', () => {
            const els = DOMHelper.getElements('multiTarget');
            expect(els).toHaveLength(2);
        });

        it('should return empty array for non-existent selector', () => {
            const els = DOMHelper.getElements('nonexistent');
            expect(els).toHaveLength(0);
        });

        it('should return single element wrapped in array by ID', () => {
            const els = DOMHelper.getElements('testId');
            expect(els).toHaveLength(1);
            expect(els[0].textContent).toBe('By ID');
        });
    });
});
