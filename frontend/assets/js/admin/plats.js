import { api } from '../shared/api.js';
import { attrUrl, da, esc, modal, toast } from '../shared/utils.js';

const filters = {
    category: '',
    query: '',
    archives: false,
};

export async function render(root) {
    const [categories, dishes] = await Promise.all([
        api('/api/admin/categories'),
        api(`/api/admin/plats?archives=${filters.archives}`),
    ]);

    const visibleDishes = dishes.filter((dish) => (
        (!filters.category || String(dish.categorie_id) === filters.category)
        && (!filters.query
            || dish.nom.toLowerCase().includes(filters.query.toLowerCase()))
    ));

    root.innerHTML = `
        <h2>Plats</h2>

        <div class="toolbar">
            <input
                id="q"
                placeholder="Rechercher un plat…"
                value="${esc(filters.query)}"
            >

            <select id="fc">
                <option value="">Toutes les catégories</option>
                ${categories.map((category) => `
                    <option
                        value="${category.id}"
                        ${String(category.id) === filters.category ? 'selected' : ''}
                    >${esc(category.nom)}</option>
                `).join('')}
            </select>

            <label>
                <input type="checkbox" id="fa" ${filters.archives ? 'checked' : ''}>
                Afficher les archivés
            </label>

            <button class="sp" id="new">+ Nouveau plat</button>
        </div>

        <div class="pgrid">
            ${visibleDishes.map((dish) => `
                <div
                    class="pcard ${dish.disponible ? '' : 'off'} ${dish.archive ? 'arch' : ''}"
                    data-id="${dish.id}"
                >
                    <div
                        class="pimg ${attrUrl(dish.photo_url) ? 'has' : ''}"
                        ${attrUrl(dish.photo_url)
                            ? `style="background-image:url('${attrUrl(dish.photo_url)}')"`
                            : ''}
                    >
                        ${dish.archive ? '<span class="tag">Archivé</span>' : ''}
                        ${!dish.disponible && !dish.archive
                            ? '<span class="tag">Épuisé</span>'
                            : ''}
                    </div>

                    <div class="pmain">
                        <div class="ptop">
                            <h3>${esc(dish.nom)}</h3>
                            <b>${da(dish.prix)}</b>
                        </div>

                        <small class="muted">
                            ${esc(dish.categorie)} · ${dish.temps_preparation} min
                        </small>
                        <p>${esc(dish.description)}</p>
                    </div>

                    <div class="pact">
                        <label>
                            <input
                                type="checkbox"
                                data-av
                                ${dish.disponible ? 'checked' : ''}
                                ${dish.archive ? 'disabled' : ''}
                            >
                            Disponible
                        </label>

                        <button class="ghost sm" data-edit>Modifier</button>
                        <button class="ghost sm" data-arch>
                            ${dish.archive ? 'Restaurer' : 'Archiver'}
                        </button>
                        <button class="danger sm" data-del>Supprimer</button>
                    </div>
                </div>
            `).join('') || '<p class="muted">Aucun plat.</p>'}
        </div>
    `;

    root.querySelector('#q').oninput = (event) => {
        filters.query = event.target.value;

        clearTimeout(render.searchTimer);
        render.searchTimer = setTimeout(() => render(root), 250);
    };

    root.querySelector('#fc').onchange = (event) => {
        filters.category = event.target.value;
        render(root);
    };

    root.querySelector('#fa').onchange = (event) => {
        filters.archives = event.target.checked;
        render(root);
    };

    root.querySelector('#new').onclick = () => openDishForm(root, categories);

    root.querySelectorAll('.pcard').forEach((card) => {
        const dish = dishes.find((item) => item.id === Number(card.dataset.id));

        card.querySelector('[data-av]').onchange = async (event) => {
            card.classList.toggle('off', !event.target.checked);

            try {
                await api(
                    `/api/staff/plats/${dish.id}/disponibilite`,
                    'PATCH',
                    { disponible: event.target.checked },
                );
            } catch {
                event.target.checked = !event.target.checked;
                card.classList.toggle('off', !event.target.checked);
            }
        };

        card.querySelector('[data-edit]').onclick = () => {
            openDishForm(root, categories, dish);
        };

        card.querySelector('[data-arch]').onclick = async () => {
            await api(
                `/api/admin/plats/${dish.id}/${dish.archive ? 'restaurer' : 'archiver'}`,
                'POST',
            );

            toast(dish.archive ? 'Plat restauré' : 'Plat archivé');
            render(root);
        };

        card.querySelector('[data-del]').onclick = async () => {
            if (!confirm(`Supprimer définitivement « ${dish.nom} » ?`)) {
                return;
            }

            try {
                await api(`/api/admin/plats/${dish.id}`, 'DELETE');
                toast('Plat supprimé');
                render(root);
            } catch {
                // api() displays the error.
            }
        };
    });
}

function openDishForm(root, categories, dish = null) {
    if (!categories.length) {
        toast("Créez d'abord une catégorie", 'err');
        return;
    }

    const form = modal(
        dish ? 'Modifier le plat' : 'Nouveau plat',
        `
            <label>
                Nom
                <input name="nom" required maxlength="150" value="${esc(dish?.nom)}">
            </label>

            <div class="two">
                <label>
                    Catégorie
                    <select name="categorie_id">
                        ${categories.map((category) => `
                            <option
                                value="${category.id}"
                                ${dish?.categorie_id === category.id ? 'selected' : ''}
                            >${esc(category.nom)}</option>
                        `).join('')}
                    </select>
                </label>

                <label>
                    Prix (DA)
                    <input
                        name="prix"
                        type="number"
                        min="0"
                        step="any"
                        required
                        value="${dish?.prix ?? ''}"
                    >
                </label>
            </div>

            <div class="two">
                <label>
                    Temps de préparation (min)
                    <input
                        name="temps_preparation"
                        type="number"
                        min="0"
                        value="${dish?.temps_preparation ?? 10}"
                    >
                </label>

                <label class="row dish-available-label">
                    <input
                        type="checkbox"
                        name="disponible"
                        ${dish?.disponible === false ? '' : 'checked'}
                    >
                    Disponible
                </label>
            </div>

            <label>
                Description
                <textarea name="description">${esc(dish?.description)}</textarea>
            </label>

            <label>
                Photo
                <input type="file" name="file" accept="image/png,image/jpeg,image/webp">
            </label>

            <div
                class="prev"
                id="prev"
                style="background-image:url('${attrUrl(dish?.photo_url)}')"
            ></div>

            <input type="hidden" name="photo_url" value="${esc(dish?.photo_url)}">
        `,
        async (dialogForm) => {
            const formData = new FormData(dialogForm);

            const body = {
                nom: formData.get('nom'),
                categorie_id: Number(formData.get('categorie_id')),
                prix: Number(formData.get('prix')),
                temps_preparation: Number(formData.get('temps_preparation')) || 0,
                disponible: dialogForm.disponible.checked,
                description: formData.get('description') || null,
                photo_url: formData.get('photo_url') || null,
            };

            try {
                await api(
                    dish ? `/api/admin/plats/${dish.id}` : '/api/admin/plats',
                    dish ? 'PUT' : 'POST',
                    body,
                );

                toast(dish ? 'Plat modifié' : 'Plat créé');
                render(root);
            } catch {
                return false;
            }
        },
    );

    form.file.onchange = async () => {
        const file = form.file.files[0];
        if (!file) return;

        try {
            const uploaded = await api('/api/admin/upload', 'POST', file);
            form.photo_url.value = uploaded.url;

            form.querySelector('#prev').style.backgroundImage =
                `url('${attrUrl(uploaded.url)}')`;
        } catch {
            form.file.value = '';
        }
    };
}
