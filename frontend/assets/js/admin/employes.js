import { api } from '../shared/api.js';
import { esc, modal, toast } from '../shared/utils.js';
const ROLES = {gerant: 'Gérant', cuisinier: 'Cuisinier', serveur: 'Serveur', caissier: 'Caissier', livreur: 'Livreur'};

export async function render(el) {
  const d = await api('/api/admin/employes');
  el.innerHTML = `<h2>Employés <small class="muted" style="font:600 .95rem Jost">${d.total} actifs</small></h2>
  <div class="tabs">${Object.entries(d.par_role).map(([r, n]) => `<span class="tag">${ROLES[r]} : ${n}</span>`).join('')}<button class="sp" id="new" style="margin-left:auto">+ Nouveau compte</button></div>
  <div class="tbl"><table><tr><th>Nom</th><th>Email</th><th>Rôle</th><th>Actif</th><th></th></tr>${d.employes.map(e => `<tr data-id="${e.id}"><td><b>${esc(e.prenom)} ${esc(e.nom)}</b></td><td>${esc(e.email)}</td>
  <td>${ROLES[e.role]}</td><td><input type="checkbox" data-act ${e.actif ? 'checked' : ''}></td><td style="text-align:right"><button class="ghost sm" data-pw>Nouveau mot de passe</button></td></tr>`).join('')}</table></div>`;
  el.querySelector('#new').onclick = () => create(el);
  el.querySelectorAll('tr[data-id]').forEach(tr => {
    const id = tr.dataset.id;
    tr.querySelector('[data-act]').onchange = async e => { try { await api(`/api/admin/employes/${id}`, 'PATCH', {actif: e.target.checked}); render(el); } catch { e.target.checked = !e.target.checked; } };
    tr.querySelector('[data-pw]').onclick = () => modal('Nouveau mot de passe', `<label>Mot de passe (8 caractères min.)<input name="pw" type="password" minlength="8" required></label>`,
      async f => { try { await api(`/api/admin/employes/${id}`, 'PATCH', {mot_de_passe: f.pw.value}); toast('Mot de passe modifié'); } catch { return false; } });
  });
}

function create(el) {
  modal('Nouveau compte employé', `<div class="two"><label>Prénom<input name="prenom" required></label><label>Nom<input name="nom" required></label></div>
  <label>Email<input name="email" type="email" required></label><label>Téléphone<input name="telephone"></label>
  <div class="two"><label>Rôle<select name="role">${Object.entries(ROLES).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
  <label>Mot de passe<input name="mot_de_passe" type="password" minlength="8" required></label></div>`, async f => {
    const b = Object.fromEntries(new FormData(f)); b.telephone = b.telephone || null;
    try { await api('/api/admin/employes', 'POST', b); toast('Compte créé'); render(el); } catch { return false; }
  });
}
