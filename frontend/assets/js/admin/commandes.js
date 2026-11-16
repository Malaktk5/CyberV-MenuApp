import { api } from '../shared/api.js';
import { esc, da, toast } from '../shared/utils.js';

const F = {statut: 'encours', q: ''};
const MODES = {sur_place: 'Sur place', a_emporter: 'À emporter', livraison: 'Livraison'};
const STATUTS = {recue: 'Reçue', en_preparation: 'En préparation', prete: 'Prête', servie: 'Servie', en_route: 'En route', livree: 'Livrée', echec: 'Échec', annulee: 'Annulée', remboursee: 'Remboursée'};
let timer, known = null;

const ago = iso => { const m = Math.max(0, Math.floor((Date.now() - new Date(iso)) / 60000)); return m < 1 ? "à l'instant" : m < 60 ? `il y a ${m} min` : new Date(iso).toLocaleString('fr-FR', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'}); };
const pay = o => o.paiement_mode === 'en_ligne' ? (o.paiement_statut === 'rembourse' ? '<span class="tag red">Carte · remboursée</span>' : '<span class="tag green">Carte · payée</span>') : (o.paiement_statut === 'paye' ? '<span class="tag green">Espèces · payée</span>' : '<span class="tag">Espèces · à encaisser</span>');
const where = o => o.mode === 'sur_place' ? `Table ${o.table_numero ?? '—'}` : `${esc(o.client_nom)} · ${esc(o.client_telephone)}`;

function card(o, isNew) {
  return `<article class="oc s-${o.statut} ${isNew ? 'new' : ''}"><div class="oh"><b>${esc(o.numero)}</b><span class="tag">${STATUTS[o.statut]}</span></div>
  <div><span class="tag">${MODES[o.mode]}</span> <b>${where(o)}</b> <small class="muted">· ${ago(o.created_at)}</small></div>
  ${o.mode === 'livraison' ? `<div class="muted">${esc(o.adresse_livraison)}</div>` : ''}
  <ul>${o.lignes.map(l => `<li><span><b>${l.quantite}×</b> ${esc(l.nom)}${l.commentaire ? `<br><small>${esc(l.commentaire)}</small>` : ''}</span><span>${da(l.total)}</span></li>`).join('')}</ul>
  ${o.note ? `<div class="onote"><b>Note :</b> ${esc(o.note)}</div>` : ''}
  ${o.frais_livraison ? `<div class="muted">Frais de livraison : ${da(o.frais_livraison)}</div>` : ''}
  <div class="ofoot"><div>${pay(o)}<br><b style="font-size:1.15rem">${da(o.total)}</b></div>${o.statut === 'recue' ? `<button class="danger sm" data-cancel="${o.id}">Annuler</button>` : ''}</div></article>`;
}

async function load(el) {
  const list = el.querySelector('#olist'); if (!list) return;
  const os = await api(`/api/admin/commandes?statut=${F.statut}&q=${encodeURIComponent(F.q)}`, 'GET', undefined, {quiet: true}).catch(() => null);
  if (!os) return;
  const fresh = known ? new Set(os.filter(o => !known.has(o.id)).map(o => o.id)) : new Set(); known = new Set(os.map(o => o.id));
  list.innerHTML = os.map(o => card(o, fresh.has(o.id))).join('') || '<p class="muted">Aucune commande.</p>';
  list.querySelectorAll('[data-cancel]').forEach(b => b.onclick = async () => {
    if (!confirm('Annuler cette commande ? (le client verra « annulée »)')) return;
    try { await api(`/api/admin/commandes/${b.dataset.cancel}/annuler`, 'POST'); toast('Commande annulée'); load(el); } catch {}
  });
}

export async function render(el) {
  clearInterval(timer); known = null;
  el.innerHTML = `<h2>Commandes</h2><div class="tabs">${[['encours', 'En cours'], ['terminees', 'Terminées'], ['annulees', 'Annulées'], ['toutes', 'Toutes']].map(([k, l]) => `<button data-s="${k}" class="${k === F.statut ? 'on' : ''}">${l}</button>`).join('')}
  <input id="oq" placeholder="N° ou nom du client…" value="${esc(F.q)}" style="max-width:240px;margin-left:auto"></div><div class="ocards" id="olist"><p class="muted">Chargement…</p></div>`;
  el.querySelectorAll('[data-s]').forEach(b => b.onclick = () => { F.statut = b.dataset.s; render(el); });
  let t; el.querySelector('#oq').oninput = e => { F.q = e.target.value; clearTimeout(t); t = setTimeout(() => { known = null; load(el); }, 300); };
  await load(el);
  timer = setInterval(() => { if (location.hash !== '#/commandes') return clearInterval(timer); load(el); }, 5000);  // actualisation automatique
}
