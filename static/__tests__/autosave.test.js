import { describe, it, expect } from 'vitest';
import { debounce } from '../services/autosave.js';

describe('debounce', () => {
    it('should delay execution by the specified wait time', async () => {
        // Given
        let callCount = 0;
        const fn = debounce(() => { callCount++; }, 50);

        // When
        fn();
        fn();
        fn();

        // Then — not yet called
        expect(callCount).toBe(0);

        // Wait for debounce to fire
        await new Promise((resolve) => setTimeout(resolve, 100));

        // Then — called exactly once
        expect(callCount).toBe(1);
    });

    it('should pass arguments to the debounced function', async () => {
        // Given
        let receivedArgs = null;
        const fn = debounce((...args) => { receivedArgs = args; }, 50);

        // When
        fn('a', 'b');

        // Then
        await new Promise((resolve) => setTimeout(resolve, 100));
        expect(receivedArgs).toEqual(['a', 'b']);
    });

    it('should reset the timer on each call', async () => {
        // Given
        let callCount = 0;
        const fn = debounce(() => { callCount++; }, 100);

        // When — call twice with a 60ms gap (less than 100ms wait)
        fn();
        await new Promise((resolve) => setTimeout(resolve, 60));
        fn();

        // Then — after 80ms from second call, still not fired
        await new Promise((resolve) => setTimeout(resolve, 80));
        expect(callCount).toBe(0);

        // Then — after full wait, fired exactly once
        await new Promise((resolve) => setTimeout(resolve, 50));
        expect(callCount).toBe(1);
    });
});
