import { api } from '../shared/api.js';
import { $, esc, toast, beep, soundOn, setSound } from '../shared/utils.js';

import * as dashboard from './dashboard.js';
import * as plats from './plats.js';
import * as categories from './categories.js';
import * as employes from './employes.js';
import * as commandes from './commandes.js';

const routes = {
    dashboard,
    commandes,
    plats,
    categories,
    employes,
};

async function route() {
    const name = (location.hash.match(/^#\/(\w+)/) || [])[1];
    const key = routes[name] ? name : 'dashboard';

    document.querySelectorAll('.side .nav').forEach((link) => {
        link.classList.toggle('on', link.getAttribute('href') === `#/${key}`);
    });

    await routes[key].render($('#view'));
}

const me = await api('/api/auth/me');

if (me.role !== 'gerant') {
    location.href = '/admin/login.html';
}

$('#who').innerHTML = `
    <b>${esc(me.prenom)} ${esc(me.nom)}</b>
    <br>
    <small>Gérant</small>
`;

$('#out').onclick = async () => {
    await api('/api/auth/logout', 'POST');
    location.href = '/admin/login.html';
};

window.addEventListener('hashchange', route);
route();

const soundButton = $('#snd');

function updateSoundLabel() {
    soundButton.textContent = soundOn() ? 'Son activé' : 'Son coupé';
}

updateSoundLabel();

soundButton.onclick = () => {
    setSound(!soundOn());
    updateSoundLabel();
    beep();
};

let lastOrderId = null;

async function pollForNewOrders() {
    try {
        const summary = await api(
            '/api/admin/commandes/resume',
            'GET',
            undefined,
            { quiet: true },
        );

        $('#nbadge').textContent = summary.recues;
        $('#nbadge').hidden = !summary.recues;

        if (lastOrderId !== null && summary.derniere_id > lastOrderId) {
            beep();
            toast(`Nouvelle commande ${summary.derniere_numero}`);
        }

        lastOrderId = summary.derniere_id;
    } catch {
        // The next polling cycle retries automatically.
    }
}

pollForNewOrders();
setInterval(pollForNewOrders, 5000);
