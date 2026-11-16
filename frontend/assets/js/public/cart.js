import { $, esc, da, toast } from '../shared/utils.js';
import { openCheckout } from './checkout.js';

const KEY = 'yummy_cart';
let items = [];
try { items = JSON.parse(localStorage.getItem(KEY) || '[]').filter(i => i && Number.isInteger(i.id) && i.qty > 0 && i.qty <= 20); } catch { items = []; }
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(items)); } catch {} };
export const total = () => items.reduce((s, i) => s + i.prix * i.qty, 0);
export const getItems = () => items;
export function clearCart() { items = []; save(); render(); }

export function addToCart(p) {
  const i = items.find(x => x.id === p.id);
  if (i) i.qty = Math.min(20, i.qty + 1); else items.push({id: p.id, nom: p.nom, prix: p.prix, qty: 1, note: ''});
  save(); render(); toast(`${p.nom} ajouté au panier`);
}

/** Aligne le panier mémorisé avec le menu actuel (prix, plats épuisés ou supprimés). */
export function syncWithMenu(menu) {
  const all = new Map(menu.flatMap(c => c.plats).map(p => [p.id, p])), n = items.length;
  items = items.filter(i => all.get(i.id)?.disponible);
  items.forEach(i => { const p = all.get(i.id); i.nom = p.nom; i.prix = p.prix; });
  if (items.length !== n) toast("Certains plats de votre panier ne sont plus disponibles", 'err');
  save(); render();
}

function render() {
  $('#cart-count').textContent = items.reduce((n, i) => n + i.qty, 0);
  $('#cart-total').textContent = da(total());
  $('#checkoutBtn').disabled = !items.length;
  $('#cart-items').innerHTML = items.map(i => `<li data-id="${i.id}"><div class="ci-top"><b>${esc(i.nom)}</b><span>${da(i.prix * i.qty)}</span></div>
    <div class="ci-ctl"><button class="sm ghost" data-m aria-label="Moins">−</button><b>${i.qty}</b><button class="sm ghost" data-p aria-label="Plus">+</button><button class="sm danger" data-x>Retirer</button></div>
    <input class="ci-note" maxlength="200" placeholder="Remarque (ex : sans oignons)" value="${esc(i.note)}"></li>`).join('') || '<li class="muted">Votre panier est vide.</li>';
  document.querySelectorAll('#cart-items li[data-id]').forEach(li => {
    const it = items.find(x => x.id == li.dataset.id);
    li.querySelector('[data-m]').onclick = () => { it.qty--; if (it.qty < 1) items = items.filter(x => x !== it); save(); render(); };
    li.querySelector('[data-p]').onclick = () => { it.qty = Math.min(20, it.qty + 1); save(); render(); };
    li.querySelector('[data-x]').onclick = () => { items = items.filter(x => x !== it); save(); render(); };
    li.querySelector('.ci-note').oninput = e => { it.note = e.target.value; save(); };
  });
}

export function initCart() {
  const panel = $('#cart');
  $('#cartBtn').onclick = () => panel.classList.toggle('open');
  document.addEventListener('keydown', e => { if (e.key === 'Escape') panel.classList.remove('open'); });
  $('#checkoutBtn').onclick = () => { if (items.length) { panel.classList.remove('open'); openCheckout({items, onSuccess: clearCart}); } };
  render();
}
