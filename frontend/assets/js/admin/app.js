import { api } from '../shared/api.js';
import { $, esc, beep, soundOn, setSound, toast } from '../shared/utils.js';
import * as dashboard from './dashboard.js';
import * as plats from './plats.js';
import * as categories from './categories.js';
import * as employes from './employes.js';
import * as commandes from './commandes.js';

const routes = {dashboard, commandes, plats, categories, employes};
async function route() {
  const name = (location.hash.match(/^#\/(\w+)/) || [])[1];
  const key = routes[name] ? name : 'dashboard';
  document.querySelectorAll('.side .nav').forEach(a => a.classList.toggle('on', a.getAttribute('href') === '#/' + key));
  await routes[key].render($('#view'));
}
const me = await api('/api/auth/me');
if (me.role !== 'gerant') { location.href = '/admin/login.html'; }
$('#who').innerHTML = `<b>${esc(me.prenom)} ${esc(me.nom)}</b><br><small>Gérant</small>`;
$('#out').onclick = async () => { await api('/api/auth/logout', 'POST'); location.href = '/admin/login.html'; };
addEventListener('hashchange', route); route();

// ---- nouvelles commandes : badge dans le menu + son + notification, quelle que soit la page ----
const snd = $('#snd'), lab = () => snd.textContent = soundOn() ? 'Son activé' : 'Son coupé';
lab(); snd.onclick = () => { setSound(!soundOn()); lab(); beep(); };
let lastId = null;
async function poll() {
  try {
    const r = await api('/api/admin/commandes/resume', 'GET', undefined, {quiet: true});
    $('#nbadge').textContent = r.recues; $('#nbadge').hidden = !r.recues;
    if (lastId !== null && r.derniere_id > lastId) { beep(); toast(`Nouvelle commande ${r.derniere_numero}`); }
    lastId = r.derniere_id;
  } catch {}
}
poll(); setInterval(poll, 5000);
