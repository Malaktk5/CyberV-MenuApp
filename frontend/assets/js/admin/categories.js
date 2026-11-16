import { api } from '../shared/api.js';
import { esc, modal, toast } from '../shared/utils.js';

export async function render(el) {
  const cats = await api('/api/admin/categories');
  el.innerHTML = `<h2>Catégories</h2><div class="toolbar"><button class="sp" id="new">+ Nouvelle catégorie</button></div>
  <div class="tbl"><table><tr><th>Ordre</th><th>Nom</th><th>Plats</th><th></th></tr>${cats.map(c => `<tr data-id="${c.id}"><td>${c.ordre}</td><td><b>${esc(c.nom)}</b></td><td>${c.nb_plats}</td>
  <td style="text-align:right"><button class="ghost sm" data-edit>Modifier</button> <button class="danger sm" data-del>Supprimer</button></td></tr>`).join('') || '<tr><td colspan="4" class="muted">Aucune catégorie</td></tr>'}</table></div>`;
  el.querySelector('#new').onclick = () => form(el);
  el.querySelectorAll('tr[data-id]').forEach(tr => {
    const c = cats.find(x => x.id == tr.dataset.id);
    tr.querySelector('[data-edit]').onclick = () => form(el, c);
    tr.querySelector('[data-del]').onclick = async () => { if (!confirm(`Supprimer la catégorie « ${c.nom} » ?`)) return; try { await api(`/api/admin/categories/${c.id}`, 'DELETE'); toast('Catégorie supprimée'); render(el); } catch {} };
  });
}

function form(el, c = null) {
  modal(c ? 'Modifier la catégorie' : 'Nouvelle catégorie', `<label>Nom<input name="nom" required maxlength="100" value="${esc(c?.nom)}"></label>
  <label>Ordre d'affichage<input name="ordre" type="number" value="${c?.ordre ?? 0}"></label>`, async f => {
    try { await api(c ? `/api/admin/categories/${c.id}` : '/api/admin/categories', c ? 'PUT' : 'POST', {nom: f.nom.value, ordre: +f.ordre.value || 0}); toast('Catégorie enregistrée'); render(el); } catch { return false; }
  });
}
