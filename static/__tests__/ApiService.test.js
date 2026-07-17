import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ApiService } from '../services/ApiService.js';

describe('ApiService', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        document.head.innerHTML = '<meta name="csrf-token" content="test-csrf-token">';
    });

    describe('_getCsrfToken', () => {
        it('should return the CSRF token from meta tag', () => {
            const token = ApiService._getCsrfToken();
            expect(token).toBe('test-csrf-token');
        });

        it('should return empty string when meta tag is missing', () => {
            document.head.innerHTML = '';
            const token = ApiService._getCsrfToken();
            expect(token).toBe('');
        });
    });

    describe('handleResponse', () => {
        it('should return the response for ok statuses', async () => {
            const res = { status: 200, ok: true };
            const result = await ApiService.handleResponse(res);
            expect(result).toBe(res);
        });

        it('should redirect to /login on 401', async () => {
            const originalLocation = window.location;
            delete window.location;
            window.location = { href: '' };

            const res = { status: 401 };
            await expect(ApiService.handleResponse(res)).rejects.toThrow('Session expirée');
            expect(window.location.href).toBe('/login');

            window.location = originalLocation;
        });

        it('should throw Access denied on 403', async () => {
            const res = { status: 403 };
            await expect(ApiService.handleResponse(res)).rejects.toThrow('Accès refusé');
        });

        it('should throw Server error on 5xx', async () => {
            const res = { status: 500 };
            await expect(ApiService.handleResponse(res)).rejects.toThrow('Erreur serveur');
        });
    });

    describe('get', () => {
        it('should make a GET request and return parsed JSON', async () => {
            const mockData = { success: true };
            globalThis.fetch = vi.fn().mockResolvedValue({
                status: 200,
                ok: true,
                json: async () => mockData,
            });

            const result = await ApiService.get('/api/test');
            expect(result).toEqual(mockData);
            expect(fetch).toHaveBeenCalledWith('/api/test', {});
        });
    });

    describe('post', () => {
        it('should make a POST request with CSRF token and JSON body', async () => {
            const mockData = { success: true };
            globalThis.fetch = vi.fn().mockResolvedValue({
                status: 200,
                ok: true,
                json: async () => mockData,
            });

            const result = await ApiService.post('/api/test', { key: 'value' });
            expect(result).toEqual(mockData);
            expect(fetch).toHaveBeenCalledWith('/api/test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': 'test-csrf-token',
                },
                body: JSON.stringify({ key: 'value' }),
            });
        });
    });
});
