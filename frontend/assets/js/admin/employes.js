import { api } from '../shared/api.js';
import { esc, modal, toast } from '../shared/utils.js';

const ROLES = {
    gerant: 'Gérant',
    cuisinier: 'Cuisinier',
    serveur: 'Serveur',
    caissier: 'Caissier',
    livreur: 'Livreur',
};

export async function render(root) {
    const data = await api('/api/admin/employes');

    root.innerHTML = `
        <h2>
            Employés
            <small class="muted employee-total">${data.total} actifs</small>
        </h2>

        <div class="tabs">
            ${Object.entries(data.par_role).map(([role, count]) => `
                <span class="tag">${ROLES[role]} : ${count}</span>
            `).join('')}

            <button class="sp new-account-button" id="new">+ Nouveau compte</button>
        </div>

        <div class="tbl">
            <table>
                <tr>
                    <th>Nom</th>
                    <th>Email</th>
                    <th>Rôle</th>
                    <th>Actif</th>
                    <th></th>
                </tr>

                ${data.employes.map((employee) => `
                    <tr data-id="${employee.id}">
                        <td><b>${esc(employee.prenom)} ${esc(employee.nom)}</b></td>
                        <td>${esc(employee.email)}</td>
                        <td>${ROLES[employee.role]}</td>
                        <td>
                            <input
                                type="checkbox"
                                data-act
                                ${employee.actif ? 'checked' : ''}
                            >
                        </td>
                        <td class="table-actions">
                            <button class="ghost sm" data-pw>
                                Nouveau mot de passe
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </table>
        </div>
    `;

    root.querySelector('#new').onclick = () => openCreateForm(root);

    root.querySelectorAll('tr[data-id]').forEach((row) => {
        const employeeId = row.dataset.id;

        row.querySelector('[data-act]').onchange = async (event) => {
            try {
                await api(`/api/admin/employes/${employeeId}`, 'PATCH', {
                    actif: event.target.checked,
                });
                render(root);
            } catch {
                event.target.checked = !event.target.checked;
            }
        };

        row.querySelector('[data-pw]').onclick = () => {
            modal(
                'Nouveau mot de passe',
                `
                    <label>
                        Mot de passe (8 caractères min.)
                        <input name="pw" type="password" minlength="8" required>
                    </label>
                `,
                async (form) => {
                    try {
                        await api(`/api/admin/employes/${employeeId}`, 'PATCH', {
                            mot_de_passe: form.pw.value,
                        });
                        toast('Mot de passe modifié');
                    } catch {
                        return false;
                    }
                },
            );
        };
    });
}

function openCreateForm(root) {
    modal(
        'Nouveau compte employé',
        `
            <div class="two">
                <label>
                    Prénom
                    <input name="prenom" required>
                </label>

                <label>
                    Nom
                    <input name="nom" required>
                </label>
            </div>

            <label>
                Email
                <input name="email" type="email" required>
            </label>

            <label>
                Téléphone
                <input name="telephone">
            </label>

            <div class="two">
                <label>
                    Rôle
                    <select name="role">
                        ${Object.entries(ROLES).map(([value, label]) => `
                            <option value="${value}">${label}</option>
                        `).join('')}
                    </select>
                </label>

                <label>
                    Mot de passe
                    <input name="mot_de_passe" type="password" minlength="8" required>
                </label>
            </div>
        `,
        async (form) => {
            const body = Object.fromEntries(new FormData(form));
            body.telephone = body.telephone || null;

            try {
                await api('/api/admin/employes', 'POST', body);
                toast('Compte créé');
                render(root);
            } catch {
                return false;
            }
        },
    );
}
