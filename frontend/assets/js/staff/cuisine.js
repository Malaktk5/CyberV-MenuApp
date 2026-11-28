import { api } from '../shared/api.js';
import { staffPage } from '../shared/staff.js';
import { esc } from '../shared/utils.js';

const { main, actions } = await staffPage('cuisinier', 'Cuisine');

actions.innerHTML = `<button class="ghost sm" id="krefresh">Actualiser</button>`;

const MODES = {
    sur_place: 'Sur place',
    a_emporter: 'À emporter',
    livraison: 'Livraison',
};

const STATUTS = {
    recue: 'Reçue',
    en_preparation: 'En préparation',
};

function renderOrder(order) {
    const isNew = order.statut === 'recue';
    const tableInfo = order.table_numero ? ` · Table ${order.table_numero}` : '';
    const timeStr = new Date(order.created_at).toLocaleTimeString('fr-FR', {
        hour: '2-digit',
        minute: '2-digit',
    });

    const linesHtml = (order.lignes || [])
        .map(
            (l) => `
            <li>
                <span class="kticket-qty">${l.quantite}×</span>
                <div>
                    <strong>${esc(l.nom_plat)}</strong>
                    ${l.commentaire ? `<div style="color:#b45309;font-size:0.82rem;margin-top:2px;">Note : ${esc(l.commentaire)}</div>` : ''}
                </div>
            </li>`
        )
        .join('');

    const actionBtn = isNew
        ? `<button class="btn" data-id="${order.id}" data-next="en_preparation">Commencer la préparation</button>`
        : `<button class="btn" data-id="${order.id}" data-next="prete">Marquer prête</button>`;

    return `
        <article class="kticket ${isNew ? 'is-new' : 'is-prep'}">
            <div class="kticket-head">
                <span class="kticket-num">${esc(order.numero)}</span>
                <span class="kticket-badge">${esc(STATUTS[order.statut] || order.statut)}</span>
            </div>
            <div class="kticket-meta">
                ${esc(MODES[order.mode] || order.mode)}${esc(tableInfo)} · ${esc(timeStr)}
            </div>
            ${order.note ? `<div style="margin:0.85rem 1.25rem 0;padding:0.55rem 0.75rem;background:#fdf5f2;border-left:3px solid var(--gold);border-radius:8px;font-size:0.85rem;"><b>Note :</b> ${esc(order.note)}</div>` : ''}
            <ul class="kticket-items">
                ${linesHtml}
            </ul>
            <div class="kticket-foot">
                ${actionBtn}
            </div>
        </article>
    `;
}

async function loadOrders() {
    try {
        const orders = await api('/api/cuisine/commandes');
        const newOrders = orders.filter((o) => o.statut === 'recue');
        const prepOrders = orders.filter((o) => o.statut === 'en_preparation');

        main.innerHTML = `
            <div class="kstats">
                <div class="kstat-pill"><span class="kdot new"></span> À préparer : ${newOrders.length}</div>
                <div class="kstat-pill"><span class="kdot prep"></span> En préparation : ${prepOrders.length}</div>
            </div>
            <div class="kboard">
                <section class="kcol">
                    <div class="kcol-head">
                        <h2>1 · À préparer</h2>
                        <span class="kcol-count">${newOrders.length}</span>
                    </div>
                    <div class="kcol-list">
                        ${newOrders.length ? newOrders.map(renderOrder).join('') : '<div class="kcol-empty">Aucune nouvelle commande</div>'}
                    </div>
                </section>
                <section class="kcol">
                    <div class="kcol-head">
                        <h2>2 · En préparation</h2>
                        <span class="kcol-count">${prepOrders.length}</span>
                    </div>
                    <div class="kcol-list">
                        ${prepOrders.length ? prepOrders.map(renderOrder).join('') : '<div class="kcol-empty">Aucune commande en cours</div>'}
                    </div>
                </section>
            </div>
        `;

        main.querySelectorAll('button[data-id]').forEach((btn) => {
            btn.onclick = async () => {
                btn.disabled = true;
                try {
                    await api(`/api/cuisine/commandes/${btn.dataset.id}/statut`, 'POST', {
                        statut: btn.dataset.next,
                    });
                    await loadOrders();
                } catch (err) {
                    btn.disabled = false;
                    alert(err.message);
                }
            };
        });
    } catch (err) {
        main.innerHTML = `<div class="panel"><p>Erreur de chargement : ${esc(err.message)}</p></div>`;
    }
}

document.getElementById('krefresh').onclick = loadOrders;
loadOrders();
setInterval(loadOrders, 10000);
