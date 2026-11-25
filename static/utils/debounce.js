/**
 * utils/debounce.js — Debounce partagé.
 */

/**
 * Retarde l'appel de `func` jusqu'à ce que `wait` ms se soient écoulées
 * sans nouvel appel.
 * @param {Function} func - Fonction à débouncer
 * @param {number} wait - Délai en ms
 * @returns {Function} Fonction débouncée
 */
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
