import { $, da, esc, toast } from '../shared/utils.js';
import { api } from '../shared/api.js';

const MODES = [
    ['sur_place', 'Sur place'],
    ['a_emporter', 'À emporter'],
    ['livraison', 'Livraison'],
];

function setCardFieldFormatting(dialog) {
    $('#cc-num', dialog).oninput = (event) => {
        event.target.value = event.target.value
            .replace(/\D/g, '')
            .slice(0, 19)
            .replace(/(.{4})/g, '$1 ')
            .trim();
    };

    $('#cc-exp', dialog).oninput = (event) => {
        const digits = event.target.value
            .replace(/\D/g, '')
            .slice(0, 4);

        event.target.value = digits.length > 2
            ? `${digits.slice(0, 2)}/${digits.slice(2)}`
            : digits;
    };
}

function showConfirmation(order) {
    const dialog = $('#confirm');

    dialog.innerHTML = `
        <div class="mform confirmation">
            <div class="okmark">✓</div>
            <h2>Commande envoyée !</h2>

            <p>Votre numéro de commande : <b>${esc(order.numero)}</b></p>
            <p>
                Total : <b>${da(order.total)}</b>
                · ${order.paiement_mode === 'en_ligne'
                    ? 'Payé par carte'
                    : 'Paiement en espèces'}
            </p>

            <p class="muted">
                ${order.mode === 'livraison'
                    ? 'Notre livreur vous appellera à son arrivée.'
                    : order.mode === 'a_emporter'
                        ? 'Nous vous préviendrons quand elle sera prête.'
                        : 'Nous préparons votre commande, merci de patienter à votre table.'}
            </p>

            <div class="mbtns confirmation-actions">
                <a class="btn" href="/suivi.html?t=${encodeURIComponent(order.suivi_token)}">
                    Suivre ma commande
                </a>
                <button class="ghost" id="closeConfirm">Fermer</button>
            </div>
        </div>
    `;

    $('#closeConfirm', dialog).onclick = () => dialog.close();
    dialog.showModal();
}

export async function openCheckout({ items, onSuccess }) {
    let options;

    try {
        options = await api('/api/options-commande', 'GET', undefined, {
            quiet: true,
        });
    } catch {
        toast('Service momentanément indisponible, réessayez.', 'err');
        return;
    }

    const preselectedTable = (
        Number(new URLSearchParams(location.search).get('table')) || ''
    );

    const subtotal = items.reduce(
        (sum, item) => sum + item.prix * item.qty,
        0,
    );

    const dialog = $('#checkout');

    dialog.innerHTML = `
        <form class="mform" id="cform" novalidate>
            <h2>Valider la commande</h2>
            <div class="title-line checkout-title-line"></div>

            <div>
                <b>Mode de service</b>

                <div class="choices">
                    ${MODES.map(([value, label]) => `
                        <label class="choice">
                            <input
                                type="radio"
                                name="mode"
                                value="${value}"
                                ${value === 'sur_place' ? 'checked' : ''}
                            >
                            <span>${label}</span>
                        </label>
                    `).join('')}
                </div>
            </div>

            <div id="g-table">
                <label>
                    Numéro de table*
                    <select name="table_numero">
                        <option value="">Choisissez votre table</option>
                        ${options.tables.map((tableNumber) => `
                            <option
                                value="${tableNumber}"
                                ${tableNumber === preselectedTable ? 'selected' : ''}
                            >Table ${tableNumber}</option>
                        `).join('')}
                    </select>
                </label>
            </div>

            <div id="g-client" hidden>
                <div class="two">
                    <label>
                        Votre nom*
                        <input name="client_nom" maxlength="100" autocomplete="name">
                    </label>

                    <label>
                        Téléphone*
                        <input
                            name="client_telephone"
                            type="tel"
                            maxlength="20"
                            autocomplete="tel"
                        >
                    </label>
                </div>
            </div>

            <div id="g-adr" hidden>
                <label>
                    Adresse de livraison*
                    <textarea name="adresse_livraison" rows="2" maxlength="300"></textarea>
                </label>

                <small class="muted">
                    Frais de livraison : ${da(options.frais_livraison)}
                </small>
            </div>

            <label>
                Une note pour la cuisine ?
                <textarea
                    name="note"
                    rows="3"
                    maxlength="500"
                    placeholder="Allergies, cuisson, précisions…"
                ></textarea>
            </label>

            <div>
                <b>Paiement</b>

                <div class="choices two-c">
                    <label class="choice">
                        <input type="radio" name="paiement_mode" value="especes" checked>
                        <span>Espèces</span>
                    </label>

                    <label class="choice">
                        <input type="radio" name="paiement_mode" value="en_ligne">
                        <span>Carte bancaire</span>
                    </label>
                </div>
            </div>

            <div id="g-card" hidden class="cardbox">
                <label>
                    Numéro de carte
                    <input
                        id="cc-num"
                        inputmode="numeric"
                        autocomplete="off"
                        placeholder="1234 5678 9012 3456"
                        maxlength="23"
                    >
                </label>

                <div class="two">
                    <label>
                        Expiration
                        <input
                            id="cc-exp"
                            autocomplete="off"
                            placeholder="MM/AA"
                            maxlength="5"
                        >
                    </label>

                    <label>
                        CVC
                        <input
                            id="cc-cvc"
                            inputmode="numeric"
                            autocomplete="off"
                            placeholder="123"
                            maxlength="4"
                        >
                    </label>
                </div>

                <small class="muted">
                    Paiement simulé (mode test) : aucune donnée de carte n'est envoyée ni enregistrée.
                </small>
            </div>

            <div class="recap">
                <div><span>Sous-total</span><b>${da(subtotal)}</b></div>

                <div id="r-frais" hidden>
                    <span>Livraison</span>
                    <b>${da(options.frais_livraison)}</b>
                </div>

                <div class="grand">
                    <span>Total</span>
                    <b id="r-total">${da(subtotal)}</b>
                </div>
            </div>

            <p class="err" id="cerr"></p>

            <div class="mbtns">
                <button type="button" class="ghost" id="cancel">Retour</button>
                <button type="submit" id="csubmit">Confirmer la commande</button>
            </div>
        </form>
    `;

    const form = $('#cform', dialog);

    const getFieldValue = (name) => form.elements[name].value;
    const getMode = () => form.elements.mode.value;
    const getPaymentMode = () => form.elements.paiement_mode.value;

    const refreshCheckout = () => {
        const mode = getMode();
        const paymentMode = getPaymentMode();

        $('#g-table', dialog).hidden = mode !== 'sur_place';
        $('#g-client', dialog).hidden = mode === 'sur_place';
        $('#g-adr', dialog).hidden = mode !== 'livraison';
        $('#g-card', dialog).hidden = paymentMode !== 'en_ligne';
        $('#r-frais', dialog).hidden = mode !== 'livraison';

        const deliveryFee = mode === 'livraison'
            ? options.frais_livraison
            : 0;

        $('#r-total', dialog).textContent = da(subtotal + deliveryFee);
    };

    form.addEventListener('change', refreshCheckout);
    refreshCheckout();
    setCardFieldFormatting(dialog);

    $('#cancel', dialog).onclick = () => dialog.close();

    form.onsubmit = async (event) => {
        event.preventDefault();

        const error = $('#cerr', dialog);
        error.textContent = '';

        const mode = getMode();
        const paymentMode = getPaymentMode();

        if (mode === 'sur_place' && !getFieldValue('table_numero')) {
            error.textContent = 'Choisissez votre numéro de table.';
            return;
        }

        if (mode !== 'sur_place' && !getFieldValue('client_nom').trim()) {
            error.textContent = 'Indiquez votre nom.';
            return;
        }

        if (
            mode !== 'sur_place'
            && !/^[0-9+ ().-]{8,20}$/.test(getFieldValue('client_telephone').trim())
        ) {
            error.textContent = 'Numéro de téléphone invalide.';
            return;
        }

        if (
            mode === 'livraison'
            && getFieldValue('adresse_livraison').trim().length < 5
        ) {
            error.textContent = 'Indiquez votre adresse de livraison.';
            return;
        }

        if (paymentMode === 'en_ligne') {
            if (!/^\d{13,19}$/.test($('#cc-num', dialog).value.replace(/\s/g, ''))) {
                error.textContent = 'Numéro de carte invalide.';
                return;
            }

            if (!/^(0[1-9]|1[0-2])\/\d{2}$/.test($('#cc-exp', dialog).value)) {
                error.textContent = "Date d'expiration invalide (MM/AA).";
                return;
            }

            if (!/^\d{3,4}$/.test($('#cc-cvc', dialog).value)) {
                error.textContent = 'CVC invalide.';
                return;
            }
        }

        const submitButton = $('#csubmit', dialog);
        submitButton.disabled = true;

        try {
            const order = await api('/api/commandes', 'POST', {
                mode,
                table_numero: mode === 'sur_place'
                    ? Number(getFieldValue('table_numero'))
                    : null,
                client_nom: getFieldValue('client_nom').trim() || null,
                client_telephone: mode === 'sur_place'
                    ? null
                    : getFieldValue('client_telephone').trim() || null,
                adresse_livraison: mode === 'livraison'
                    ? getFieldValue('adresse_livraison').trim()
                    : null,
                note: getFieldValue('note').trim() || null,
                paiement_mode: paymentMode,
                lignes: items.map((item) => ({
                    plat_id: item.id,
                    quantite: item.qty,
                    commentaire: item.note.trim() || null,
                })),
            }, { quiet: true });

            ['cc-num', 'cc-exp', 'cc-cvc'].forEach((id) => {
                $(`#${id}`, dialog).value = '';
            });

            dialog.close();
            onSuccess();
            showConfirmation(order);
        } catch (submitError) {
            error.textContent = submitError.message;
            submitButton.disabled = false;
        }
    };

    dialog.showModal();
}
