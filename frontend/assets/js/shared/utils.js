export const $ = (s, r = document) => r.querySelector(s);
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const da = n => new Intl.NumberFormat('fr-FR', {maximumFractionDigits: 0}).format(n ?? 0) + ' DA';
export const safeUrl = u => /^(\/uploads\/|\/assets\/|https?:\/\/)/.test(u || '') ? u : '';
export const attrUrl = u => safeUrl(u).replace(/['"()\\\s]/g, encodeURIComponent);
export function toast(msg, kind = '') {
  let box = $('#toast'); if (!box) { box = document.createElement('div'); box.id = 'toast'; document.body.append(box); }
  const t = document.createElement('div'); t.textContent = msg; if (kind) t.className = kind; box.append(t); setTimeout(() => t.remove(), 3500);
}
/** Ouvre la boîte de dialogue partagée (<dialog id="dlg">) avec un formulaire. */
export function modal(title, body, onSubmit) {
  const d = $('#dlg');
  d.innerHTML = `<form class="mform"><h3>${title}</h3>${body}<div class="mbtns"><button type="button" class="ghost" data-close>Annuler</button><button>Enregistrer</button></div></form>`;
  d.querySelector('[data-close]').onclick = () => d.close();
  const f = d.querySelector('form');
  f.onsubmit = async e => { e.preventDefault(); if ((await onSubmit(f)) !== false) d.close(); };
  d.showModal(); return f;
}

// ---- son (nouvelle commande) : le navigateur exige un premier clic sur la page pour l'autoriser ----
let AC = null;
const unlock = () => { try { AC = AC || new (window.AudioContext || window.webkitAudioContext)(); AC.resume(); } catch {} };
document.addEventListener('click', unlock);
export const soundOn = () => { try { return localStorage.getItem('sound') !== '0'; } catch { return true; } };
export const setSound = v => { try { localStorage.setItem('sound', v ? '1' : '0'); } catch {} unlock(); };
export function beep() {
  if (!soundOn() || !AC) return;
  [880, 1175, 1568].forEach((f, i) => { const o = AC.createOscillator(), g = AC.createGain(), t = AC.currentTime + i * .18;
    o.frequency.value = f; g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(.3, t + .03); g.gain.exponentialRampToValueAtTime(.0001, t + .35);
    o.connect(g); g.connect(AC.destination); o.start(t); o.stop(t + .4); });
}
