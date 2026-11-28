import { api } from '../shared/api.js';
import { staffPage } from '../shared/staff.js';
import { esc } from '../shared/utils.js';

const { main, actions } = await staffPage('cuisinier', 'Cuisine');

actions.innerHTML = `<button class="ghost sm" id="krefresh">Actualiser</button>`;

const MODES = {
    sur_place: 'Sur place',
    a_emporter: 'À emporter',
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
            <li style="margin: 0.35rem 0;">
                <b>${l.quantite}×</b> ${esc(l.nom_plat)}
                ${l.commentaire ? `<br><small style="color:#b45309;">Note : ${esc(l.commentaire)}</small>` : ''}
            </li>`
        )
        .join('');

    const actionBtn = isNew
        ? `<button class="btn" data-id="${order.id}" data-next="en_preparation">Commencer la préparation</button>`
        : `<button class="btn" style="background:#15803d;color:#fff;" data-id="${order.id}" data-next="prete">Marquer prête</button>`;

    return `
        <article class="panel" style="border-left: 5px solid ${isNew ? '#d97706' : '#2563eb'}; display:flex; flex-direction:column; gap:0.75rem;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong>${esc(order.numero)}</strong>
                <span style="font-size:0.85rem; padding:0.2rem 0.55rem; border-radius:999px; background:${isNew ? '#fef3c7' : '#dbeafe'}; color:${isNew ? '#92400e' : '#1e40af'};">
                    ${esc(STATUTS[order.statut] || order.statut)}
                </span>
            </div>
            <div style="font-size:0.9rem; color:#555;">
                ${esc(MODES[order.mode] || order.mode)}${esc(tableInfo)} · ${esc(timeStr)}
            </div>
            ${order.note ? `<div style="padding:0.45rem 0.6rem; background:#fffbeb; border-radius:6px; font-size:0.88rem;"><b>Note commande :</b> ${esc(order.note)}</div>` : ''}
            <ul style="margin:0; padding-left:1.2rem; flex:1;">
                ${linesHtml}
            </ul>
            <div style="display:flex; justify-content:flex-end; margin-top:auto;">
                ${actionBtn}
            </div>
        </article>
    `;
}

async function loadOrders() {
    try {
        const orders = await api('/api/cuisine/commandes');
        if (!orders.length) {
            main.innerHTML = `
                <div class="panel placeholder">
                    <h2>Aucune commande en attente</h2>
                    <p class="muted">Les nouvelles commandes apparaîtront ici automatiquement.</p>
                </div>
            `;
            return;
        }

        main.innerHTML = `
            <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap:1rem;">
                ${orders.map(renderOrder).join('')}
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
                } finally {
                    btn.disabled = false;
                }
            };
        });
    } catch (err) {
        main.innerHTML = `<div class="panel"><p>Erreur de chargement : ${esc(err.message)}</p></div>`;
    }
}

document.getElementById('krefresh').onclick = loadOrders;
await loadOrders();
setInterval(loadOrders, 5000);
