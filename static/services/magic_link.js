import { ApiService } from './ApiService.js';
import { MessageHelper } from '../utils/MessageHelper.js';
import { DOMHelper } from '../utils/DOMHelper.js';

/**
 * Génère un magic link et le copie dans le presse-papiers
 */

const _unlimitedPrefKey = 'dashboard_magic_link_unlimited';

/**
 * Persiste l'état du toggle "mode illimité" (préférence locale).
 */
export function initMagicLinkPreference() {
    const toggle = DOMHelper.getElement('magicLinkUnlimitedToggle');
    if (!toggle) return;

    try {
        toggle.checked = localStorage.getItem(_unlimitedPrefKey) === 'true';
    } catch {
        // localStorage indisponible — ignorer
    }

    toggle.addEventListener('change', () => {
        try {
            localStorage.setItem(_unlimitedPrefKey, String(toggle.checked));
        } catch {
            // ignorer
        }
    });
}

export async function generateMagicLink() {
    const btn = DOMHelper.getElement('generateMagicLinkBtn');
    const output = DOMHelper.getElement('magicLinkOutput');
    const unlimitedToggle = DOMHelper.getElement('magicLinkUnlimitedToggle');
    
    if (!btn || !output) return;
    
    output.textContent = '';
    MessageHelper.setButtonLoading(btn, true);
    
    try {
        const unlimited = unlimitedToggle?.checked ?? false;
        const data = await ApiService.post('/api/auth/magic-link', { unlimited });
        
        if (data.success && data.magic_link) {
            const expiresText = data.unlimited ? 'aucune expiration' : (data.expires_at || 'bientôt');
            output.textContent = `${data.magic_link} (exp. ${expiresText})`;
            output.className = 'status-msg success';
            
            try {
                await navigator.clipboard.writeText(data.magic_link);
                output.textContent += ' — Copié dans le presse-papiers';
                MessageHelper.showToast('Magic link copié dans le presse-papiers');
            } catch {
                MessageHelper.showToast('Magic link généré — copie manuelle requise', 'info');
            }
        } else {
            output.textContent = data.message || 'Impossible de générer le magic link.';
            output.className = 'status-msg error';
        }
    } catch (e) {
        console.error('generateMagicLink error', e);
        output.textContent = 'Erreur de génération du magic link.';
        output.className = 'status-msg error';
    } finally {
        MessageHelper.setButtonLoading(btn, false);
        setTimeout(() => {
            if (output) output.className = 'status-msg';
        }, 7000);
    }
}
