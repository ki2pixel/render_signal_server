import { ApiService } from './ApiService.js';
import { MessageHelper } from '../utils/MessageHelper.js';
import { DOMHelper } from '../utils/DOMHelper.js';

/**
 * Génère un magic link et le copie dans le presse-papiers
 */

let _copiedToastTimer = null;

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
                showCopiedFeedback();
            } catch (clipboardError) {
                // Silently fail clipboard copy
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

/**
 * Affiche un toast de feedback après copie
 */
export function showCopiedFeedback() {
    if (_copiedToastTimer) {
        clearTimeout(_copiedToastTimer);
    }
    let toast = document.querySelector('.copied-feedback');
    if (!toast) {
        toast = document.createElement('div');
        toast.className = 'copied-feedback';
        toast.setAttribute('role', 'status');
        toast.setAttribute('aria-live', 'polite');
        toast.textContent = '🔗 Magic link copié dans le presse-papiers !';
        document.body.appendChild(toast);
    }
    toast.classList.add('show');
    
    _copiedToastTimer = setTimeout(() => {
        toast.classList.remove('show');
        _copiedToastTimer = null;
    }, 3000);
}
