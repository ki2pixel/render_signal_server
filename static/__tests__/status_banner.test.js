import { describe, it, expect } from 'vitest';
import { analyzeLogsForStatus } from '../services/status_banner.js';

describe('analyzeLogsForStatus', () => {
    // Given
    const now = new Date();
    const thirtyMinutesAgo = new Date(now.getTime() - 30 * 60 * 1000).toISOString();
    const twoHoursAgo = new Date(now.getTime() - 2 * 60 * 60 * 1000).toISOString();
    const twoDaysAgo = new Date(now.getTime() - 48 * 60 * 60 * 1000).toISOString();

    it('should return success status for all-success recent logs', () => {
        // Given
        const logs = [
            { timestamp: thirtyMinutesAgo, status: 'success' },
            { timestamp: thirtyMinutesAgo, status: 'success' },
        ];

        // When
        const result = analyzeLogsForStatus(logs);

        // Then
        expect(result.status).toBe('success');
        expect(result.criticalErrors).toBe('0');
        expect(result.recentIncidents).toBe('0');
        expect(result.activeWebhooks).toBe('2');
    });

    it('should return error status when there are recent critical errors', () => {
        // Given
        const logs = [
            { timestamp: thirtyMinutesAgo, status: 'error' },
            { timestamp: thirtyMinutesAgo, status: 'success' },
        ];

        // When
        const result = analyzeLogsForStatus(logs);

        // Then
        expect(result.status).toBe('error');
        expect(result.criticalErrors).toBe('1');
    });

    it('should return warning status for recent incidents outside the last hour', () => {
        // Given
        const logs = [
            { timestamp: twoHoursAgo, status: 'error' },
        ];

        // When
        const result = analyzeLogsForStatus(logs);

        // Then
        expect(result.status).toBe('warning');
        expect(result.criticalErrors).toBe('0');
        expect(result.recentIncidents).toBe('1');
    });

    it('should handle empty logs array', () => {
        // Given
        const logs = [];

        // When
        const result = analyzeLogsForStatus(logs);

        // Then
        expect(result.status).toBe('success');
        expect(result.lastExecution).toBe('—');
        expect(result.activeWebhooks).toBe('0');
    });

    it('should not count errors older than 24h as incidents', () => {
        // Given
        const logs = [
            { timestamp: twoDaysAgo, status: 'error' },
        ];

        // When
        const result = analyzeLogsForStatus(logs);

        // Then
        expect(result.status).toBe('success');
        expect(result.recentIncidents).toBe('0');
    });

    it('should format lastExecution as relative time for recent logs', () => {
        // Given
        const fiveMinutesAgo = new Date(now.getTime() - 5 * 60 * 1000).toISOString();
        const logs = [
            { timestamp: fiveMinutesAgo, status: 'success' },
        ];

        // When
        const result = analyzeLogsForStatus(logs);

        // Then
        expect(result.lastExecution).toMatch(/Il y a \d+ min/);
    });
});
