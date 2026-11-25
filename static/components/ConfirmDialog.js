/**
 * components/ConfirmDialog.js — Boîte de confirmation accessible (modale).
 *
 * Remplace globalThis.confirm() par un modal pleinement accessible :
 *  - focus piégé dans le modal
 *  - Échap annule, Entrée confirme
 *  - le focus retourne au déclencheur à la fermeture
 *  - annonce par les lecteurs d'écran via role="alertdialog"
 */

const KEY_ESCAPE = 'Escape';
const KEY_ENTER = 'Enter';

let _trigger = null;
let _resolve = null;
let _currentDialog = null;

const backdropMarkup = `
<div class="confirm-backdrop" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-desc">
  <div class="confirm-panel">
    <h3 id="confirm-title" class="confirm-title">Confirmer l'action</h3>
    <p id="confirm-desc" class="confirm-desc"></p>
    <div class="confirm-actions">
      <button type="button" class="btn btn-secondary confirm-cancel">Annuler</button>
      <button type="button" class="btn btn-danger confirm-ok">Confirmer</button>
    </div>
  </div>
</div>
`;

const CSS = `
.confirm-backdrop {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
  z-index: 10000;
  padding: 24px;
  box-sizing: border-box;
}
.confirm-panel {
  background: var(--cork-card-bg);
  border: 1px solid var(--cork-border-color);
  border-radius: var(--radius-md);
  width: min(460px, 92vw);
  max-height: 90vh;
  overflow-y: auto;
  padding: 24px;
  box-sizing: border-box;
}
.confirm-title {
  margin: 0 0 10px 0;
  font-size: 1.1rem;
  color: var(--cork-text-primary);
}
.confirm-desc {
  margin: 0 0 20px 0;
  font-size: 0.95rem;
  color: var(--cork-text-secondary);
  line-height: 1.5;
}
.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.btn-danger {
  background: linear-gradient(to right, var(--cork-danger) 0%, #c93e47 100%);
}
.btn-danger:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-button-danger);
}
`;

function _ensureStyle() {
    if (document.getElementById('confirm-dialog-style')) return;
    const style = document.createElement('style');
    style.id = 'confirm-dialog-style';
    style.textContent = CSS;
    document.head.appendChild(style);
}

function _trapFocus(dialog) {
    const focusable = dialog.querySelectorAll('button:not([disabled]), [href], input, select, textarea');
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const handler = (e) => {
        if (e.key !== 'Tab') return;
        e.preventDefault();
        if (e.shiftKey) {
            if (document.activeElement === first || document.activeElement === dialog) {
                last.focus();
            } else {
                first.focus();
            }
        } else {
            if (document.activeElement === last) {
                first.focus();
            } else {
                last.focus();
            }
        }
    };
    dialog.addEventListener('keydown', handler, { once: false });
    return () => dialog.removeEventListener('keydown', handler);
}

export function confirm(message, title = 'Confirmer l\'action') {
    return new Promise((resolve) => {
        if (_currentDialog) {
            resolve(false);
            return;
        }
        _ensureStyle();
        _trigger = document.activeElement;
        _resolve = resolve;

        const div = document.createElement('div');
        div.innerHTML = backdropMarkup;
        const backdrop = div.firstElementChild;
        document.body.appendChild(backdrop);

        const titleEl = backdrop.querySelector('#confirm-title');
        const descEl = backdrop.querySelector('#confirm-desc');
        titleEl.textContent = title;
        descEl.textContent = message;

        const okBtn = backdrop.querySelector('.confirm-ok');
        const cancelBtn = backdrop.querySelector('.confirm-cancel');
        okBtn.focus();

        const cleanup = _trapFocus(backdrop);

        const finish = (value) => {
            cleanup();
            backdrop.remove();
            _currentDialog = null;
            _resolve = null;
            if (_trigger && typeof _trigger.focus === 'function') {
                try { _trigger.focus({ preventScroll: true }); } catch {}
            }
            _trigger = null;
            resolve(value);
        };

        const onKey = (e) => {
            if (e.key === KEY_ESCAPE) {
                e.preventDefault();
                finish(false);
            } else if (e.key === KEY_ENTER && document.activeElement === cancelBtn) {
                e.preventDefault();
                finish(false);
            }
        };
        backdrop.addEventListener('keydown', onKey);

        okBtn.addEventListener('click', () => finish(true), { once: true });
        cancelBtn.addEventListener('click', () => finish(false), { once: true });
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) finish(false);
        }, { once: true });

        _currentDialog = backdrop;
    });
}

export function destroyConfirmDialog() {
    if (_currentDialog) {
        _currentDialog.remove();
        _currentDialog = null;
    }
    if (_resolve) {
        _resolve(false);
        _resolve = null;
    }
    _trigger = null;
}
