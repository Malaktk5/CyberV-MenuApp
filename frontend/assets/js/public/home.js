import { $, da, esc, safeUrl } from '../shared/utils.js';
import { addToCart, initCart, syncWithMenu } from './cart.js';

let menu = [];
let selectedCategory = 'all';
let searchQuery = '';

function normalize(text) {
    return String(text ?? '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase();
}

function dishCard(dish) {
    const unavailable = !dish.disponible;
    const photoUrl = safeUrl(dish.photo_url);

    return `
        <article class="card ${unavailable ? 'off' : ''}">
            ${unavailable ? '<span class="badge">Épuisé</span>' : ''}

            <div class="card-image ${photoUrl ? '' : 'empty'}">
                ${photoUrl
                    ? `<img src="${esc(photoUrl)}" alt="${esc(dish.nom)}" loading="lazy">`
                    : ''}
            </div>

            <div class="card-content">
                <h2 class="card-title">${esc(dish.nom)}</h2>
                <p class="card-description">${esc(dish.description)}</p>
                <small class="muted">${dish.temps_preparation} min</small>

                <div class="card-footer">
                    <span class="price">${da(dish.prix)}</span>
                    ${dish.disponible
                        ? `<button class="add-to-cart" data-add="${dish.id}">Ajouter au panier</button>`
                        : ''}
                </div>
            </div>
        </article>
    `;
}

function drawMenu() {
    const categoryFilter = $('#category-filter');

    if (categoryFilter.options.length === 1) {
        menu.forEach((category) => {
            categoryFilter.add(new Option(category.nom, category.id));
        });
    }

    const visibleCategories = menu
        .filter((category) => (
            selectedCategory === 'all'
            || String(category.id) === selectedCategory
        ))
        .map((category) => ({
            ...category,
            plats: category.plats.filter((dish) => (
                !searchQuery
                || normalize(`${dish.nom} ${dish.description}`).includes(searchQuery)
            )),
        }))
        .filter((category) => category.plats.length);

    $('#menuList').innerHTML = visibleCategories
        .map((category) => `
            <div class="category">
                <h2 class="category-title">${esc(category.nom)}</h2>
                <div class="title-line"></div>

                <div class="card-container">
                    ${category.plats.map(dishCard).join('')}
                </div>
            </div>
        `)
        .join('');

    $('#no-results').style.display = visibleCategories.length ? 'none' : 'block';

    const dishesById = new Map(
        menu
            .flatMap((category) => category.plats)
            .map((dish) => [dish.id, dish]),
    );

    document.querySelectorAll('[data-add]').forEach((button) => {
        button.onclick = () => addToCart(dishesById.get(Number(button.dataset.add)));
    });
}

$('#category-filter').onchange = (event) => {
    selectedCategory = event.target.value;
    drawMenu();
};

$('#search').oninput = (event) => {
    searchQuery = normalize(event.target.value.trim());
    drawMenu();
};

initCart();

fetch('/api/menu')
    .then((response) => response.json())
    .then((loadedMenu) => {
        menu = loadedMenu;
        drawMenu();
        syncWithMenu(loadedMenu);
    })
    .catch(() => {
        $('#menuList').innerHTML = `
            <p class="err menu-loading-error">Impossible de charger le menu.</p>
        `;
    });
