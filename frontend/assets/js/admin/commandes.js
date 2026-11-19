import { api } from '../shared/api.js';
import { da, esc, toast } from '../shared/utils.js';

const filters = {
    statut: 'encours',
    q: '',
};

const MODES = {
    sur_place: 'Sur place',
    a_emporter: 'À emporter',
    livraison: 'Livraison',
};

const STATUSES = {
    recue: 'Reçue',
    en_preparation: 'En préparation',
    prete: 'Prête',
    servie: 'Servie',
    en_route: 'En route',
    livree: 'Livrée',
    echec: 'Échec',
    annulee: 'Annulée',
    remboursee: 'Remboursée',
};

let pollTimer;
let knownOrderIds = null;

function ago(isoDate) {
    const minutes = Math.max(
        0,
        Math.floor((Date.now() - new Date(isoDate)) / 60000),
    );

    if (minutes < 1) return "à l'instant";
    if (minutes < 60) return `il y a ${minutes} min`;

    return new Date(isoDate).toLocaleString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function paymentLabel(order) {
    if (order.paiement_mode === 'en_ligne') {
        return order.paiement_statut === 'rembourse'
            ? '<span class="tag red">Carte · remboursée</span>'
            : '<span class="tag green">Carte · payée</span>';
    }

    return order.paiement_statut === 'paye'
        ? '<span class="tag green">Espèces · payée</span>'
        : '<span class="tag">Espèces · à encaisser</span>';
}

function orderLocation(order) {
    if (order.mode === 'sur_place') {
        return `Table ${order.table_numero ?? '—'}`;
    }

    return `${esc(order.client_nom)} · ${esc(order.client_telephone)}`;
}

function orderCard(order, isNew) {
    return `
        <article class="oc s-${order.statut} ${isNew ? 'new' : ''}">
            <div class="oh">
                <b>${esc(order.numero)}</b>
                <span class="tag">${STATUSES[order.statut]}</span>
            </div>

            <div>
                <span class="tag">${MODES[order.mode]}</span>
                <b>${orderLocation(order)}</b>
                <small class="muted">· ${ago(order.created_at)}</small>
            </div>

            ${order.mode === 'livraison'
                ? `<div class="muted">${esc(order.adresse_livraison)}</div>`
                : ''}

            <ul>
                ${order.lignes.map((line) => `
                    <li>
                        <span>
                            <b>${line.quantite}×</b>
                            ${esc(line.nom)}
                            ${line.commentaire
                                ? `<br><small>${esc(line.commentaire)}</small>`
                                : ''}
                        </span>
                        <span>${da(line.total)}</span>
                    </li>
                `).join('')}
            </ul>

            ${order.note
                ? `<div class="onote"><b>Note :</b> ${esc(order.note)}</div>`
                : ''}

            ${order.frais_livraison
                ? `<div class="muted">Frais de livraison : ${da(order.frais_livraison)}</div>`
                : ''}

            <div class="ofoot">
                <div>
                    ${paymentLabel(order)}
                    <br>
                    <b class="order-total">${da(order.total)}</b>
                </div>

                ${order.statut === 'recue'
                    ? `<button class="danger sm" data-cancel="${order.id}">Annuler</button>`
                    : ''}
            </div>
        </article>
    `;
}

async function loadOrders(root) {
    const list = root.querySelector('#olist');
    if (!list) return;

    const orders = await api(
        `/api/admin/commandes?statut=${filters.statut}&q=${encodeURIComponent(filters.q)}`,
        'GET',
        undefined,
        { quiet: true },
    ).catch(() => null);

    if (!orders) return;

    const freshIds = knownOrderIds
        ? new Set(orders
            .filter((order) => !knownOrderIds.has(order.id))
            .map((order) => order.id))
        : new Set();

    knownOrderIds = new Set(orders.map((order) => order.id));

    list.innerHTML = orders
        .map((order) => orderCard(order, freshIds.has(order.id)))
        .join('') || '<p class="muted">Aucune commande.</p>';

    list.querySelectorAll('[data-cancel]').forEach((button) => {
        button.onclick = async () => {
            if (!confirm('Annuler cette commande ? (le client verra « annulée »)')) {
                return;
            }

            try {
                await api(
                    `/api/admin/commandes/${button.dataset.cancel}/annuler`,
                    'POST',
                );
                toast('Commande annulée');
                loadOrders(root);
            } catch {
                // api() displays the error.
            }
        };
    });
}

export async function render(root) {
    clearInterval(pollTimer);
    knownOrderIds = null;

    const tabs = [
        ['encours', 'En cours'],
        ['terminees', 'Terminées'],
        ['annulees', 'Annulées'],
        ['toutes', 'Toutes'],
    ];

    root.innerHTML = `
        <h2>Commandes</h2>

        <div class="tabs">
            ${tabs.map(([value, label]) => `
                <button
                    data-s="${value}"
                    class="${value === filters.statut ? 'on' : ''}"
                >${label}</button>
            `).join('')}

            <input
                id="oq"
                class="order-search"
                placeholder="N° ou nom du client…"
                value="${esc(filters.q)}"
            >
        </div>

        <div class="ocards" id="olist">
            <p class="muted">Chargement…</p>
        </div>
    `;

    root.querySelectorAll('[data-s]').forEach((button) => {
        button.onclick = () => {
            filters.statut = button.dataset.s;
            render(root);
        };
    });

    let searchTimer;

    root.querySelector('#oq').oninput = (event) => {
        filters.q = event.target.value;
        clearTimeout(searchTimer);

        searchTimer = setTimeout(() => {
            knownOrderIds = null;
            loadOrders(root);
        }, 300);
    };

    await loadOrders(root);

    pollTimer = setInterval(() => {
        if (location.hash !== '#/commandes') {
            clearInterval(pollTimer);
            return;
        }

        loadOrders(root);
    }, 5000);
}
