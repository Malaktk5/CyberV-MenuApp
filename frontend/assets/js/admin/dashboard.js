import { api } from '../shared/api.js';
import { esc, da } from '../shared/utils.js';
const S = {period: 'day', date: new Date().toISOString().slice(0, 10)};
const MODES = {sur_place: 'Sur place', a_emporter: 'À emporter', livraison: 'Livraison'};
const STATUTS = {recue: 'Reçue', en_preparation: 'En préparation', prete: 'Prête', servie: 'Servie', en_route: 'En route', livree: 'Livrée', echec: 'Échec', annulee: 'Annulée', remboursee: 'Remboursée'};

export async function render(el) {
  const s = await api(`/api/admin/stats?period=${S.period}&date=${S.date}`);
  const k = (t, v) => `<div class="card kpi"><small>${t}</small><b>${v}</b></div>`;
  const mx = Math.max(1, ...s.serie.map(x => x.ca)), step = Math.ceil(s.serie.length / 12), topMax = s.top_plats[0]?.quantite || 1;
  el.innerHTML = `<h2>Tableau de bord <small class="muted" style="font:600 .95rem Jost">${s.debut} → ${s.fin}</small></h2>
  <div class="tabs">${[['day', 'Jour'], ['week', 'Semaine'], ['month', 'Mois'], ['year', 'Année']].map(([p, l]) => `<button data-p="${p}" class="${p === S.period ? 'on' : ''}">${l}</button>`).join('')}<input type="date" id="d" value="${S.date}"></div>
  <div class="grid">${k('Recette', da(s.ca))}${k('Clients (commandes)', s.commandes)}${k('Panier moyen', da(s.panier_moyen))}${k('Plats vendus', s.plats_vendus)}
  ${k('Temps moyen de préparation', s.temps_prep_moyen != null ? s.temps_prep_moyen + ' min' : '—')}${k('Annulations', `${s.annulees} (${s.taux_annulation} %)`)}${k('Commandes en cours', s.en_cours)}</div>
  <h3>Recette</h3><div class="bars">${s.serie.map((x, i) => `<div class="col" title="${esc(x.label)} : ${da(x.ca)} · ${x.commandes} cmd"><i style="height:${Math.round(100 * x.ca / mx)}%"></i><span>${i % step ? '' : esc(x.label)}</span></div>`).join('') || '<p class="muted">Aucune donnée sur cette période</p>'}</div>
  <div class="grid two"><div class="card"><h3>Plats les plus vendus</h3>${s.top_plats.map(p => `<div><b>${esc(p.nom)}</b> <span class="muted">— ${p.quantite}</span><div class="hbar" style="width:${Math.round(100 * p.quantite / topMax)}%"></div></div>`).join('') || '<p class="muted">—</p>'}</div>
  <div class="card"><h3>Heures de pointe</h3>${s.heures_de_pointe.map(h => `<p style="margin:.2rem 0"><b>${h.h}h</b> — ${h.n} commandes</p>`).join('') || '<p class="muted">—</p>'}
  <h3 style="margin-top:1rem">Mode de service</h3>${Object.entries(s.modes).map(([m, n]) => `<p style="margin:.2rem 0">${MODES[m] || m} : <b>${n}</b></p>`).join('') || '<p class="muted">—</p>'}</div></div>
  <h3>Dernières commandes</h3><div class="tbl"><table><tr><th>N°</th><th>Mode</th><th>Statut</th><th>Total</th><th>Date</th></tr>${s.recentes.map(o => `<tr><td>${esc(o.numero)}</td><td>${MODES[o.mode]}</td><td><span class="tag">${STATUTS[o.statut]}</span></td><td>${da(o.total)}</td><td>${new Date(o.created_at).toLocaleString('fr-FR')}</td></tr>`).join('') || '<tr><td colspan="5" class="muted">Aucune commande</td></tr>'}</table></div>`;
  el.querySelectorAll('[data-p]').forEach(b => b.onclick = () => { S.period = b.dataset.p; render(el); });
  el.querySelector('#d').onchange = e => { S.date = e.target.value || S.date; render(el); };
}
