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

const FINAL_STATUSES = new Set(['servie', 'livree', 'annulee', 'echec', 'remboursee']);
let refreshTimer = null;
let loading = false;
let cancelInProgress = false;
let finished = false;

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
    if (order.paiement_statut === 'rembourse') {
        return 'Paiement en ligne remboursé';
    }

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

async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => null);

    if (!response.ok) {
        throw new Error(data?.detail || `Erreur ${response.status}`);
    }

    return data;
}

async function loadWaitTime() {
    if (!trackingToken) {
        return null;
    }

    try {
        const result = await requestJson(
            `/api/suivi/${encodeURIComponent(trackingToken)}/temps-attente`,
        );
        return result.visible ? result.temps_attente_minutes : null;
    } catch {
        return null;
    }
}

async function cancelOrder(button) {
    if (cancelInProgress) {
        return;
    }

    if (!window.confirm('Voulez-vous vraiment annuler cette commande ?')) {
        return;
    }

    cancelInProgress = true;
    button.disabled = true;
    const feedback = trackingBox.querySelector('#cancel-feedback');

    try {
        await requestJson(
            `/api/suivi/${encodeURIComponent(trackingToken)}/annuler`,
            { method: 'POST' },
        );
        await loadTrackingPage();
    } catch (error) {
        if (feedback) {
            feedback.textContent = error.message;
        }
        button.disabled = false;
    } finally {
        cancelInProgress = false;
    }
}

async function loadTrackingPage() {
    if (loading || finished) {
        return;
    }

    loading = true;

    try {
        const order = await requestJson(
            `/api/commandes/suivi/${encodeURIComponent(trackingToken)}`,
        );
        const flow = order.mode === 'livraison'
            ? FLOWS.livraison
            : FLOWS.other;
        const finalMessage = FINAL_MESSAGES[order.statut];
        const waitTime = order.statut === 'en_preparation'
            ? await loadWaitTime()
            : null;

        const waitTimeMarkup = order.statut === 'en_preparation'
            ? `<div class="wait-time" role="status">
                    <b>Temps de préparation estimé</b>
                    <span>${waitTime === null
                        ? 'Estimation indisponible pour le moment.'
                        : `Environ ${esc(waitTime)} min`}</span>
                </div>`
            : '';

        const cancelMarkup = order.statut === 'recue'
            ? `<div class="tracking-actions">
                    <button class="danger" id="cancel-order" type="button">
                        Annuler ma commande
                    </button>
                    <p class="muted" id="cancel-feedback" aria-live="polite"></p>
                </div>`
            : '';

        trackingBox.innerHTML = `
            <h2>Commande ${esc(order.numero)}</h2>
            <p class="muted">${esc(orderModeLabel(order))}</p>

            ${finalMessage
                ? `<div class="banner">${finalMessage}</div>`
                : `<ul class="steps">${renderStatusFlow(flow, order.statut)}</ul>`}

            ${waitTimeMarkup}
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

            ${cancelMarkup}
        `;

        trackingBox.setAttribute('aria-busy', 'false');
        const cancelButton = trackingBox.querySelector('#cancel-order');
        cancelButton?.addEventListener('click', () => cancelOrder(cancelButton));

        finished = FINAL_STATUSES.has(order.statut);
    } catch (error) {
        trackingBox.setAttribute('aria-busy', 'false');
        trackingBox.innerHTML = `
            <h2>Commande introuvable</h2>
            <p class="muted">${esc(error.message || 'Vérifiez le lien de suivi.')}</p>
            <a class="btn" href="/">Retour à l'accueil</a>
        `;
        finished = true;
    } finally {
        loading = false;
        if (!finished) {
            refreshTimer = window.setTimeout(loadTrackingPage, 5000);
        } else if (refreshTimer) {
            window.clearTimeout(refreshTimer);
        }
    }
}

loadTrackingPage();

