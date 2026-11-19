import { api } from '../shared/api.js';
import { da, esc } from '../shared/utils.js';

const filters = {
    period: 'day',
    date: new Date().toISOString().slice(0, 10),
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

function kpi(title, value) {
    return `
        <div class="card kpi">
            <small>${title}</small>
            <b>${value}</b>
        </div>
    `;
}

export async function render(root) {
    const stats = await api(
        `/api/admin/stats?period=${filters.period}&date=${filters.date}`,
    );

    const chartMaximum = Math.max(1, ...stats.serie.map((item) => item.ca));
    const chartLabelStep = Math.ceil(stats.serie.length / 12);
    const topDishMaximum = stats.top_plats[0]?.quantite || 1;

    root.innerHTML = `
        <h2>
            Tableau de bord
            <small class="muted dashboard-range">
                ${stats.debut} → ${stats.fin}
            </small>
        </h2>

        <div class="tabs">
            ${[
                ['day', 'Jour'],
                ['week', 'Semaine'],
                ['month', 'Mois'],
                ['year', 'Année'],
            ].map(([period, label]) => `
                <button
                    data-p="${period}"
                    class="${period === filters.period ? 'on' : ''}"
                >${label}</button>
            `).join('')}

            <input type="date" id="d" value="${filters.date}">
        </div>

        <div class="grid">
            ${kpi('Recette', da(stats.ca))}
            ${kpi('Clients (commandes)', stats.commandes)}
            ${kpi('Panier moyen', da(stats.panier_moyen))}
            ${kpi('Plats vendus', stats.plats_vendus)}
            ${kpi(
                'Temps moyen de préparation',
                stats.temps_prep_moyen != null
                    ? `${stats.temps_prep_moyen} min`
                    : '—',
            )}
            ${kpi('Annulations', `${stats.annulees} (${stats.taux_annulation} %)`)}
            ${kpi('Commandes en cours', stats.en_cours)}
        </div>

        <h3>Recette</h3>
        <div class="bars">
            ${stats.serie.map((item, index) => `
                <div
                    class="col"
                    title="${esc(item.label)} : ${da(item.ca)} · ${item.commandes} cmd"
                >
                    <i style="height:${Math.round(100 * item.ca / chartMaximum)}%"></i>
                    <span>${index % chartLabelStep ? '' : esc(item.label)}</span>
                </div>
            `).join('') || '<p class="muted">Aucune donnée sur cette période</p>'}
        </div>

        <div class="grid two">
            <div class="card">
                <h3>Plats les plus vendus</h3>

                ${stats.top_plats.map((dish) => `
                    <div>
                        <b>${esc(dish.nom)}</b>
                        <span class="muted">— ${dish.quantite}</span>
                        <div
                            class="hbar"
                            style="width:${Math.round(100 * dish.quantite / topDishMaximum)}%"
                        ></div>
                    </div>
                `).join('') || '<p class="muted">—</p>'}
            </div>

            <div class="card">
                <h3>Heures de pointe</h3>

                ${stats.heures_de_pointe.map((hour) => `
                    <p class="dashboard-line">
                        <b>${hour.h}h</b> — ${hour.n} commandes
                    </p>
                `).join('') || '<p class="muted">—</p>'}

                <h3 class="dashboard-subtitle">Mode de service</h3>

                ${Object.entries(stats.modes).map(([mode, count]) => `
                    <p class="dashboard-line">
                        ${MODES[mode] || mode} : <b>${count}</b>
                    </p>
                `).join('') || '<p class="muted">—</p>'}
            </div>
        </div>

        <h3>Dernières commandes</h3>

        <div class="tbl">
            <table>
                <tr>
                    <th>N°</th>
                    <th>Mode</th>
                    <th>Statut</th>
                    <th>Total</th>
                    <th>Date</th>
                </tr>

                ${stats.recentes.map((order) => `
                    <tr>
                        <td>${esc(order.numero)}</td>
                        <td>${MODES[order.mode]}</td>
                        <td><span class="tag">${STATUSES[order.statut]}</span></td>
                        <td>${da(order.total)}</td>
                        <td>${new Date(order.created_at).toLocaleString('fr-FR')}</td>
                    </tr>
                `).join('') || `
                    <tr>
                        <td colspan="5" class="muted">Aucune commande</td>
                    </tr>
                `}
            </table>
        </div>
    `;

    root.querySelectorAll('[data-p]').forEach((button) => {
        button.onclick = () => {
            filters.period = button.dataset.p;
            render(root);
        };
    });

    root.querySelector('#d').onchange = (event) => {
        filters.date = event.target.value || filters.date;
        render(root);
    };
}
