import { api } from '../shared/api.js';
import { esc, modal, toast } from '../shared/utils.js';

export async function render(root) {
    const categories = await api('/api/admin/categories');

    root.innerHTML = `
        <h2>Catégories</h2>

        <div class="toolbar">
            <button class="sp" id="new">+ Nouvelle catégorie</button>
        </div>

        <div class="tbl">
            <table>
                <tr>
                    <th>Ordre</th>
                    <th>Nom</th>
                    <th>Plats</th>
                    <th></th>
                </tr>

                ${categories.map((category) => `
                    <tr data-id="${category.id}">
                        <td>${category.ordre}</td>
                        <td><b>${esc(category.nom)}</b></td>
                        <td>${category.nb_plats}</td>
                        <td class="table-actions">
                            <button class="ghost sm" data-edit>Modifier</button>
                            <button class="danger sm" data-del>Supprimer</button>
                        </td>
                    </tr>
                `).join('') || `
                    <tr>
                        <td colspan="4" class="muted">Aucune catégorie</td>
                    </tr>
                `}
            </table>
        </div>
    `;

    root.querySelector('#new').onclick = () => openCategoryForm(root);

    root.querySelectorAll('tr[data-id]').forEach((row) => {
        const category = categories.find(
            (item) => item.id === Number(row.dataset.id),
        );

        row.querySelector('[data-edit]').onclick = () => {
            openCategoryForm(root, category);
        };

        row.querySelector('[data-del]').onclick = async () => {
            if (!confirm(`Supprimer la catégorie « ${category.nom} » ?`)) {
                return;
            }

            try {
                await api(`/api/admin/categories/${category.id}`, 'DELETE');
                toast('Catégorie supprimée');
                render(root);
            } catch {
                // api() shows the error message.
            }
        };
    });
}

function openCategoryForm(root, category = null) {
    modal(
        category ? 'Modifier la catégorie' : 'Nouvelle catégorie',
        `
            <label>
                Nom
                <input
                    name="nom"
                    required
                    maxlength="100"
                    value="${esc(category?.nom)}"
                >
            </label>

            <label>
                Ordre d'affichage
                <input name="ordre" type="number" value="${category?.ordre ?? 0}">
            </label>
        `,
        async (form) => {
            try {
                await api(
                    category
                        ? `/api/admin/categories/${category.id}`
                        : '/api/admin/categories',
                    category ? 'PUT' : 'POST',
                    {
                        nom: form.nom.value,
                        ordre: Number(form.ordre.value) || 0,
                    },
                );

                toast('Catégorie enregistrée');
                render(root);
            } catch {
                return false;
            }
        },
    );
}
