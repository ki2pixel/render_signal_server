import { describe, it, expect, beforeEach, vi } from 'vitest';
import { WebhookService } from '../services/WebhookService.js';

describe('WebhookService', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        document.body.innerHTML = `
            <input id="webhookUrl" data-target="webhookUrl" placeholder="https://hook.example.com">
            <input id="sslVerifyToggle" data-target="sslVerifyToggle" type="checkbox">
            <input id="webhookSendingToggle" data-target="webhookSendingToggle" type="checkbox" checked>
        `;
        WebhookService._cachedConfig = null;
        WebhookService._configCacheTime = null;
    });

    describe('isValidHttpsUrl', () => {
        it('should accept valid HTTPS URLs', () => {
            expect(WebhookService.isValidHttpsUrl('https://example.com/path')).toBe(true);
        });

        it('should reject HTTP URLs', () => {
            expect(WebhookService.isValidHttpsUrl('http://example.com')).toBe(false);
        });

        it('should reject invalid URLs', () => {
            expect(WebhookService.isValidHttpsUrl('not-a-url')).toBe(false);
        });

        it('should reject empty string', () => {
            expect(WebhookService.isValidHttpsUrl('')).toBe(false);
        });
    });

    describe('isValidWebhookUrl', () => {
        it('should accept Make.com token format', () => {
            expect(WebhookService.isValidWebhookUrl('abc123def456@Hook.eu2.make.com')).toBe(true);
        });

        it('should reject short tokens', () => {
            expect(WebhookService.isValidWebhookUrl('abc@Hook.eu2.make.com')).toBe(false);
        });

        it('should accept allowed HTTPS hosts', () => {
            expect(WebhookService.isValidWebhookUrl('https://hook.eu2.make.com/xxxx')).toBe(true);
        });

        it('should reject disallowed HTTPS hosts', () => {
            expect(WebhookService.isValidWebhookUrl('https://evil.com/hook')).toBe(false);
        });
    });

    describe('config cache', () => {
        it('should return null when no config cached', () => {
            expect(WebhookService.getCachedConfig()).toBeNull();
        });

        it('should consider cache stale after maxAge', () => {
            WebhookService._cachedConfig = { test: true };
            WebhookService._configCacheTime = Date.now() - 120000;
            expect(WebhookService.isConfigCacheFresh(60000)).toBe(false);
        });

        it('should consider cache fresh within maxAge', () => {
            WebhookService._cachedConfig = { test: true };
            WebhookService._configCacheTime = Date.now() - 10000;
            expect(WebhookService.isConfigCacheFresh(60000)).toBe(true);
        });
    });
});
