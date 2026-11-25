/**
 * utils/listenerRegistry.js — Registre de listeners pour nettoyage centralisé.
 */

/**
 * Crée un registre qui mémorise les listeners ajoutés afin de pouvoir
 * tous les retirer d'un coup (destroy / cleanup).
 * @returns {{ add: (el: EventTarget, type: string, handler: Function, options?: object) => void, removeAll: () => void }}
 */
export function createListenerRegistry() {
    const handlers = [];

    return {
        add(el, type, handler, options) {
            el.addEventListener(type, handler, options);
            handlers.push({ el, type, handler, options });
        },
        removeAll() {
            handlers.forEach(({ el, type, handler, options }) => {
                el.removeEventListener(type, handler, options);
            });
            handlers.length = 0;
        }
    };
}
