import { api } from './api.js';
import { $, esc } from './utils.js';

export const LOGIN = '/admin/login.html';

export const ROLES = {
    gerant: 'Gérant',
    cuisinier: 'Cuisinier',
    serveur: 'Serveur',
    caissier: 'Caissier',
    livreur: 'Livreur',
};

export const ROLE_HOME = {
    gerant: '/admin/',
    cuisinier: '/staff/cuisine.html',
    serveur: '/staff/salle.html',
    caissier: '/staff/caisse.html',
    livreur: '/staff/livraison.html',
};

export async function logout() {
    try {
        await api('/api/auth/logout', 'POST', undefined, { quiet: true });
    } catch {
        // Redirect even if the logout request fails.
    }

    location.href = LOGIN;
}

/**
 * Build the shared staff page frame and verify the current role.
 *
 * The server still performs the real authorization. This frontend check
 * only prevents one role from remaining on another role's page.
 */
export async function staffPage(role, title) {
    const me = await api('/api/auth/me');

    if (me.role !== role) {
        location.replace(ROLE_HOME[me.role] || LOGIN);
        return new Promise(() => {});
    }

    document.title = `${title} · Yummy`;

    const root = $('#staff-root');
    root.innerHTML = `
        <header class="sbar">
            <a href="${ROLE_HOME[role]}">
                <img class="logo" src="/assets/img/logo.png" alt="Yummy">
            </a>

            <h1>${esc(title)}</h1>

            <div class="sright">
                <span class="sactions"></span>

                <span class="swho">
                    <b>${esc(me.prenom)} ${esc(me.nom)}</b>
                    <small>${esc(ROLES[me.role] || me.role)}</small>
                </span>

                <button class="ghost sm" id="slogout">Déconnexion</button>
            </div>
        </header>

        <main class="smain" id="screen"></main>
    `;

    $('#slogout', root).onclick = logout;

    if (!$('#dlg')) {
        document.body.append(
            Object.assign(document.createElement('dialog'), { id: 'dlg' }),
        );
    }

    return {
        me,
        main: $('#screen', root),
        actions: $('.sactions', root),
    };
}
