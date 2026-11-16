import { $, esc, da, toast } from '../shared/utils.js';
import { api } from '../shared/api.js';

const MODES = [['sur_place', 'Sur place'], ['a_emporter', 'À emporter'], ['livraison', 'Livraison']];

export async function openCheckout({items, onSuccess}) {
  let opt;
  try { opt = await api('/api/options-commande', 'GET', undefined, {quiet: true}); } catch { return toast('Service momentanément indisponible, réessayez.', 'err'); }
  const preTable = +new URLSearchParams(location.search).get('table') || '';
  const sous = items.reduce((s, i) => s + i.prix * i.qty, 0);
  const d = $('#checkout');
  d.innerHTML = `<form class="mform" id="cform" novalidate><h2>Valider la commande</h2><div class="title-line" style="margin:0"></div>
  <div><b>Mode de service</b><div class="choices">${MODES.map(([k, l]) => `<label class="choice"><input type="radio" name="mode" value="${k}" ${k === 'sur_place' ? 'checked' : ''}><span>${l}</span></label>`).join('')}</div></div>
  <div id="g-table"><label>Numéro de table*<select name="table_numero"><option value="">Choisissez votre table</option>${opt.tables.map(n => `<option value="${n}" ${n === preTable ? 'selected' : ''}>Table ${n}</option>`).join('')}</select></label></div>
  <div id="g-client" hidden><div class="two"><label>Votre nom*<input name="client_nom" maxlength="100" autocomplete="name"></label><label>Téléphone*<input name="client_telephone" type="tel" maxlength="20" autocomplete="tel"></label></div></div>
  <div id="g-adr" hidden><label>Adresse de livraison*<textarea name="adresse_livraison" rows="2" maxlength="300"></textarea></label><small class="muted">Frais de livraison : ${da(opt.frais_livraison)}</small></div>
  <label>Une note pour la cuisine ? <textarea name="note" rows="3" maxlength="500" placeholder="Allergies, cuisson, précisions…"></textarea></label>
  <div><b>Paiement</b><div class="choices two-c"><label class="choice"><input type="radio" name="paiement_mode" value="especes" checked><span>Espèces</span></label><label class="choice"><input type="radio" name="paiement_mode" value="en_ligne"><span>Carte bancaire</span></label></div></div>
  <div id="g-card" hidden class="cardbox"><label>Numéro de carte<input id="cc-num" inputmode="numeric" autocomplete="off" placeholder="1234 5678 9012 3456" maxlength="23"></label>
  <div class="two"><label>Expiration<input id="cc-exp" autocomplete="off" placeholder="MM/AA" maxlength="5"></label><label>CVC<input id="cc-cvc" inputmode="numeric" autocomplete="off" placeholder="123" maxlength="4"></label></div>
  <small class="muted">Paiement simulé (mode test) : aucune donnée de carte n'est envoyée ni enregistrée.</small></div>
  <div class="recap"><div><span>Sous-total</span><b>${da(sous)}</b></div><div id="r-frais" hidden><span>Livraison</span><b>${da(opt.frais_livraison)}</b></div><div class="grand"><span>Total</span><b id="r-total">${da(sous)}</b></div></div>
  <p class="err" id="cerr"></p><div class="mbtns"><button type="button" class="ghost" id="cancel">Retour</button><button type="submit" id="csubmit">Confirmer la commande</button></div></form>`;
  const f = $('#cform', d), val = n => f.elements[n].value, mode = () => f.elements.mode.value, pay = () => f.elements.paiement_mode.value;
  const refresh = () => {
    const m = mode(); $('#g-table', d).hidden = m !== 'sur_place'; $('#g-client', d).hidden = m === 'sur_place'; $('#g-adr', d).hidden = m !== 'livraison';
    $('#g-card', d).hidden = pay() !== 'en_ligne'; $('#r-frais', d).hidden = m !== 'livraison';
    $('#r-total', d).textContent = da(sous + (m === 'livraison' ? opt.frais_livraison : 0));
  };
  f.addEventListener('change', refresh); refresh();
  $('#cc-num', d).oninput = e => e.target.value = e.target.value.replace(/\D/g, '').slice(0, 19).replace(/(.{4})/g, '$1 ').trim();
  $('#cc-exp', d).oninput = e => { let v = e.target.value.replace(/\D/g, '').slice(0, 4); e.target.value = v.length > 2 ? v.slice(0, 2) + '/' + v.slice(2) : v; };
  $('#cancel', d).onclick = () => d.close();
  f.onsubmit = async e => {
    e.preventDefault(); const err = $('#cerr', d); err.textContent = '';
    const m = mode();
    if (m === 'sur_place' && !val('table_numero')) return err.textContent = 'Choisissez votre numéro de table.';
    if (m !== 'sur_place' && !val('client_nom').trim()) return err.textContent = 'Indiquez votre nom.';
    if (m !== 'sur_place' && !/^[0-9+ ().-]{8,20}$/.test(val('client_telephone').trim())) return err.textContent = 'Numéro de téléphone invalide.';
    if (m === 'livraison' && val('adresse_livraison').trim().length < 5) return err.textContent = 'Indiquez votre adresse de livraison.';
    if (pay() === 'en_ligne') {  // validation de forme seulement ; ces champs ne sont jamais envoyés
      if (!/^\d{13,19}$/.test($('#cc-num', d).value.replace(/\s/g, ''))) return err.textContent = 'Numéro de carte invalide.';
      if (!/^(0[1-9]|1[0-2])\/\d{2}$/.test($('#cc-exp', d).value)) return err.textContent = "Date d'expiration invalide (MM/AA).";
      if (!/^\d{3,4}$/.test($('#cc-cvc', d).value)) return err.textContent = 'CVC invalide.';
    }
    const btn = $('#csubmit', d); btn.disabled = true;
    try {
      const r = await api('/api/commandes', 'POST', {
        mode: m, table_numero: m === 'sur_place' ? +val('table_numero') : null,
        client_nom: val('client_nom').trim() || null, client_telephone: m === 'sur_place' ? null : val('client_telephone').trim() || null,
        adresse_livraison: m === 'livraison' ? val('adresse_livraison').trim() : null, note: val('note').trim() || null, paiement_mode: pay(),
        lignes: items.map(i => ({plat_id: i.id, quantite: i.qty, commentaire: i.note.trim() || null}))}, {quiet: true});
      ['cc-num', 'cc-exp', 'cc-cvc'].forEach(id => $('#' + id, d).value = '');
      d.close(); onSuccess(); confirmation(r);
    } catch (x) { err.textContent = x.message; btn.disabled = false; }
  };
  d.showModal();
}

function confirmation(r) {
  const d = $('#confirm');
  d.innerHTML = `<div class="mform" style="text-align:center"><div class="okmark">✓</div><h2>Commande envoyée !</h2><p>Votre numéro de commande : <b>${esc(r.numero)}</b></p>
  <p>Total : <b>${da(r.total)}</b> · ${r.paiement_mode === 'en_ligne' ? 'Payé par carte' : 'Paiement en espèces'}</p>
  <p class="muted">${r.mode === 'livraison' ? 'Notre livreur vous appellera à son arrivée.' : r.mode === 'a_emporter' ? 'Nous vous préviendrons quand elle sera prête.' : 'Nous préparons votre commande, merci de patienter à votre table.'}</p>
  <div class="mbtns" style="justify-content:center"><a class="btn" href="/suivi.html?t=${encodeURIComponent(r.suivi_token)}">Suivre ma commande</a><button class="ghost" id="closeConfirm">Fermer</button></div></div>`;
  $('#closeConfirm', d).onclick = () => d.close();
  d.showModal();
}
