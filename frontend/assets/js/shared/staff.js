import { api } from './api.js';
import { $, esc } from './utils.js';

export const LOGIN = '/admin/login.html';
export const ROLES = {gerant: 'Gérant', cuisinier: 'Cuisinier', serveur: 'Serveur', caissier: 'Caissier', livreur: 'Livreur'};

/** Écran d'accueil de chaque rôle. C'est le SEUL endroit à modifier pour déplacer un écran
 *  (la page de connexion et le cadre ci-dessous s'en servent). */
export const ROLE_HOME = {
  gerant: '/admin/',
  cuisinier: '/staff/cuisine.html',
  serveur: '/staff/salle.html',
  caissier: '/staff/caisse.html',
  livreur: '/staff/livraison.html',
};

export async function logout() {
  try { await api('/api/auth/logout', 'POST', undefined, {quiet: true}); } catch {}
  location.href = LOGIN;
}

/**
 * Cadre commun des écrans du personnel : vérifie la session et le rôle, puis affiche l'en-tête
 * (nom de l'utilisateur, rôle, déconnexion) et une zone de contenu.
 *
 *   const { me, main, actions } = await staffPage('cuisinier', 'Cuisine');
 *   main.innerHTML = '…';                  // l'écran se dessine ici
 *   actions.append(monBouton);             // boutons à droite de l'en-tête (ex. son activé / coupé)
 *
 * - pas connecté : api.js renvoie vers la page de connexion ;
 * - connecté avec un autre rôle : redirigé vers SON écran (la page ne s'affiche jamais) ;
 * - la vraie sécurité reste côté serveur (require_role sur chaque route) : ce contrôle ne sert qu'à bien guider.
 */
export async function staffPage(role, title) {
  const me = await api('/api/auth/me');
  if (me.role !== role) {
    location.replace(ROLE_HOME[me.role] || LOGIN);
    return new Promise(() => {});  // la redirection est en cours : le script de la page s'arrête ici
  }
  document.title = `${title} · Yummy`;
  const root = $('#staff-root');
  root.innerHTML = `<header class="sbar"><a href="${ROLE_HOME[role]}"><img class="logo" src="/assets/img/logo.png" alt="Yummy"></a>
    <h1>${esc(title)}</h1><div class="sright"><span class="sactions"></span>
    <span class="swho"><b>${esc(me.prenom)} ${esc(me.nom)}</b><small>${esc(ROLES[me.role] || me.role)}</small></span>
    <button class="ghost sm" id="slogout">Déconnexion</button></div></header><main class="smain" id="screen"></main>`;
  $('#slogout', root).onclick = logout;
  if (!$('#dlg')) document.body.append(Object.assign(document.createElement('dialog'), {id: 'dlg'}));  // pour modal() de utils.js
  return {me, main: $('#screen', root), actions: $('.sactions', root)};
}
