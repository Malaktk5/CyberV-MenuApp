import { da, esc } from '../shared/utils.js';

const trackingToken = new URLSearchParams(location.search).get('t') || '';
const trackingBox = document.getElementById('box');

const FLOWS = {
    livraison: [
        ['recue', 'Commande reçue'],
        ['en_preparation', 'En préparation'],
        ['prete', 'Prête'],
        ['en_route', 'En route'],
        ['livree', 'Livrée'],
    ],
    other: [
        ['recue', 'Commande reçue'],
        ['en_preparation', 'En préparation'],
        ['prete', 'Prête'],
        ['servie', 'Servie'],
    ],
};

const FINAL_MESSAGES = {
    annulee: 'Cette commande a été annulée.',
    echec: "La livraison n'a pas pu aboutir.",
    remboursee: 'Cette commande a été annulée et remboursée.',
};

let refreshTimer;

function orderModeLabel(order) {
    if (order.mode === 'sur_place') {
        return `Sur place · table ${order.table_numero}`;
    }

    if (order.mode === 'livraison') {
        return 'Livraison';
    }

    return 'À emporter';
}

function paymentLabel(order) {
    if (order.paiement_mode === 'en_ligne') {
        return 'Payé par carte';
    }

    if (order.paiement_statut === 'paye') {
        return 'Payé en espèces';
    }

    return 'À régler en espèces';
}

function renderStatusFlow(flow, currentStatus) {
    const currentIndex = flow.findIndex(([status]) => status === currentStatus);

    return flow
        .map(([status, label], index) => {
            const state = index < currentIndex
                ? 'done'
                : index === currentIndex
                    ? 'done now'
                    : '';

            const marker = index <= currentIndex ? '✓' : index + 1;

            return `<li class="${state}"><i>${marker}</i>${label}</li>`;
        })
        .join('');
}

function renderOrderLines(order) {
    return order.lignes
        .map((line) => `
            <div class="line">
                <span>
                    ${line.quantite}× ${esc(line.nom)}
                    ${line.commentaire
                        ? `<br><small class="muted">${esc(line.commentaire)}</small>`
                        : ''}
                </span>
                <b>${da(line.total)}</b>
            </div>
        `)
        .join('');
}

async function loadTrackingPage() {
    const response = await fetch(
        `/api/commandes/suivi/${encodeURIComponent(trackingToken)}`,
    );

    if (!response.ok) {
        trackingBox.innerHTML = `
            <h2>Commande introuvable</h2>
            <p class="muted">Vérifiez le lien de suivi.</p>
            <a class="btn" href="/">Retour à l'accueil</a>
        `;
        clearInterval(refreshTimer);
        return;
    }

    const order = await response.json();
    const flow = order.mode === 'livraison'
        ? FLOWS.livraison
        : FLOWS.other;
    const finalMessage = FINAL_MESSAGES[order.statut];

    trackingBox.innerHTML = `
        <h2>Commande ${esc(order.numero)}</h2>
        <p class="muted">${orderModeLabel(order)}</p>

        ${finalMessage
            ? `<div class="banner">${finalMessage}</div>`
            : `<ul class="steps">${renderStatusFlow(flow, order.statut)}</ul>`}

        ${renderOrderLines(order)}

        ${order.frais_livraison
            ? `<div class="line"><span>Livraison</span><b>${da(order.frais_livraison)}</b></div>`
            : ''}

        <div class="line tracking-total">
            <b>Total</b>
            <b>${da(order.total)}</b>
        </div>

        <p class="muted tracking-payment">${paymentLabel(order)}</p>

        ${order.note
            ? `<div class="note"><b>Votre note :</b> ${esc(order.note)}</div>`
            : ''}
    `;

    if (['servie', 'livree', 'annulee', 'echec', 'remboursee'].includes(order.statut)) {
        clearInterval(refreshTimer);
    }
}

loadTrackingPage();
refreshTimer = setInterval(loadTrackingPage, 5000);
