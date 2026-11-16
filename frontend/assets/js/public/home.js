import { $, esc, da, safeUrl } from '../shared/utils.js';
import { addToCart, initCart, syncWithMenu } from './cart.js';
let menu = [], cat = 'all', q = '';
const norm = s => String(s ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const card = p => `<article class="card ${p.disponible ? '' : 'off'}">${p.disponible ? '' : '<span class="badge">Épuisé</span>'}
<div class="card-image ${safeUrl(p.photo_url) ? '' : 'empty'}">${safeUrl(p.photo_url) ? `<img src="${esc(safeUrl(p.photo_url))}" alt="${esc(p.nom)}" loading="lazy">` : ''}</div>
<div class="card-content"><h2 class="card-title">${esc(p.nom)}</h2><p class="card-description">${esc(p.description)}</p>
<small class="muted">${p.temps_preparation} min</small><div class="card-footer"><span class="price">${da(p.prix)}</span>${p.disponible ? `<button class="add-to-cart" data-add="${p.id}">Ajouter au panier</button>` : ''}</div></div></article>`;
function draw() {
  const sel = $('#category-filter'); if (sel.options.length === 1) menu.forEach(c => sel.add(new Option(c.nom, c.id)));
  const blocks = menu.filter(c => cat === 'all' || String(c.id) === cat).map(c => ({...c, plats: c.plats.filter(p => !q || norm(p.nom + ' ' + p.description).includes(q))})).filter(c => c.plats.length);
  $('#menuList').innerHTML = blocks.map(c => `<div class="category"><h2 class="category-title">${esc(c.nom)}</h2><div class="title-line"></div><div class="card-container">${c.plats.map(card).join('')}</div></div>`).join('');
  $('#no-results').style.display = blocks.length ? 'none' : 'block';
  const byId = new Map(menu.flatMap(c => c.plats).map(p => [p.id, p]));
  document.querySelectorAll('[data-add]').forEach(b => b.onclick = () => addToCart(byId.get(+b.dataset.add)));
}
$('#category-filter').onchange = e => { cat = e.target.value; draw(); };
$('#search').oninput = e => { q = norm(e.target.value.trim()); draw(); };
initCart();
fetch('/api/menu').then(r => r.json()).then(m => { menu = m; draw(); syncWithMenu(m); }).catch(() => $('#menuList').innerHTML = '<p class="err" style="text-align:center">Impossible de charger le menu.</p>');
