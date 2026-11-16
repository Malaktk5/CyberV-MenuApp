import { api } from '../shared/api.js';
import { esc, da, attrUrl, modal, toast } from '../shared/utils.js';
const F = {cat: '', q: '', archives: false};

export async function render(el) {
  const [cats, plats] = await Promise.all([api('/api/admin/categories'), api(`/api/admin/plats?archives=${F.archives}`)]);
  const list = plats.filter(p => (!F.cat || String(p.categorie_id) === F.cat) && (!F.q || p.nom.toLowerCase().includes(F.q.toLowerCase())));
  el.innerHTML = `<h2>Plats</h2><div class="toolbar"><input id="q" placeholder="Rechercher un plat…" value="${esc(F.q)}">
  <select id="fc"><option value="">Toutes les catégories</option>${cats.map(c => `<option value="${c.id}" ${String(c.id) === F.cat ? 'selected' : ''}>${esc(c.nom)}</option>`).join('')}</select>
  <label><input type="checkbox" id="fa" ${F.archives ? 'checked' : ''}> Afficher les archivés</label><button class="sp" id="new">+ Nouveau plat</button></div>
  <div class="pgrid">${list.map(p => `<div class="pcard ${p.disponible ? '' : 'off'} ${p.archive ? 'arch' : ''}" data-id="${p.id}">
   <div class="pimg ${attrUrl(p.photo_url) ? 'has' : ''}" ${attrUrl(p.photo_url) ? `style="background-image:url('${attrUrl(p.photo_url)}')"` : ''}>${p.archive ? '<span class="tag">Archivé</span>' : ''}${!p.disponible && !p.archive ? '<span class="tag">Épuisé</span>' : ''}</div>
   <div class="pmain"><div class="ptop"><h3>${esc(p.nom)}</h3><b>${da(p.prix)}</b></div><small class="muted">${esc(p.categorie)} · ${p.temps_preparation} min</small><p>${esc(p.description)}</p></div>
   <div class="pact"><label><input type="checkbox" data-av ${p.disponible ? 'checked' : ''} ${p.archive ? 'disabled' : ''}> Disponible</label>
   <button class="ghost sm" data-edit>Modifier</button><button class="ghost sm" data-arch>${p.archive ? 'Restaurer' : 'Archiver'}</button><button class="danger sm" data-del>Supprimer</button></div></div>`).join('') || '<p class="muted">Aucun plat.</p>'}</div>`;
  el.querySelector('#q').oninput = e => { F.q = e.target.value; clearTimeout(render.t); render.t = setTimeout(() => render(el), 250); };
  el.querySelector('#fc').onchange = e => { F.cat = e.target.value; render(el); };
  el.querySelector('#fa').onchange = e => { F.archives = e.target.checked; render(el); };
  el.querySelector('#new').onclick = () => form(el, cats);
  el.querySelectorAll('.pcard').forEach(card => {
    const p = plats.find(x => x.id == card.dataset.id);
    card.querySelector('[data-av]').onchange = async e => {   // case à cocher : décochée => plat grisé
      card.classList.toggle('off', !e.target.checked);
      try { await api(`/api/staff/plats/${p.id}/disponibilite`, 'PATCH', {disponible: e.target.checked}); }
      catch { e.target.checked = !e.target.checked; card.classList.toggle('off', !e.target.checked); }
    };
    card.querySelector('[data-edit]').onclick = () => form(el, cats, p);
    card.querySelector('[data-arch]').onclick = async () => { await api(`/api/admin/plats/${p.id}/${p.archive ? 'restaurer' : 'archiver'}`, 'POST'); toast(p.archive ? 'Plat restauré' : 'Plat archivé'); render(el); };
    card.querySelector('[data-del]').onclick = async () => { if (!confirm(`Supprimer définitivement « ${p.nom} » ?`)) return; try { await api(`/api/admin/plats/${p.id}`, 'DELETE'); toast('Plat supprimé'); render(el); } catch {} };
  });
}

function form(el, cats, p = null) {
  if (!cats.length) return toast("Créez d'abord une catégorie", 'err');
  const f = modal(p ? 'Modifier le plat' : 'Nouveau plat', `
    <label>Nom<input name="nom" required maxlength="150" value="${esc(p?.nom)}"></label>
    <div class="two"><label>Catégorie<select name="categorie_id">${cats.map(c => `<option value="${c.id}" ${p?.categorie_id === c.id ? 'selected' : ''}>${esc(c.nom)}</option>`).join('')}</select></label>
    <label>Prix (DA)<input name="prix" type="number" min="0" step="any" required value="${p?.prix ?? ''}"></label></div>
    <div class="two"><label>Temps de préparation (min)<input name="temps_preparation" type="number" min="0" value="${p?.temps_preparation ?? 10}"></label>
    <label class="row" style="margin-top:1.5rem"><input type="checkbox" name="disponible" ${p?.disponible === false ? '' : 'checked'}> Disponible</label></div>
    <label>Description<textarea name="description">${esc(p?.description)}</textarea></label>
    <label>Photo<input type="file" name="file" accept="image/png,image/jpeg,image/webp"></label><div class="prev" id="prev" style="background-image:url('${attrUrl(p?.photo_url)}')"></div><input type="hidden" name="photo_url" value="${esc(p?.photo_url)}">`,
  async f => {
    const d = new FormData(f);
    const body = {nom: d.get('nom'), categorie_id: +d.get('categorie_id'), prix: +d.get('prix'), temps_preparation: +d.get('temps_preparation') || 0,
      disponible: f.disponible.checked, description: d.get('description') || null, photo_url: d.get('photo_url') || null};
    try { await api(p ? `/api/admin/plats/${p.id}` : '/api/admin/plats', p ? 'PUT' : 'POST', body); toast(p ? 'Plat modifié' : 'Plat créé'); render(el); } catch { return false; }
  });
  f.file.onchange = async () => {
    const file = f.file.files[0]; if (!file) return;
    try { const r = await api('/api/admin/upload', 'POST', file); f.photo_url.value = r.url; f.querySelector('#prev').style.backgroundImage = `url('${attrUrl(r.url)}')`; } catch { f.file.value = ''; }
  };
}
