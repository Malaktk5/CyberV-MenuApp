import { $, da, esc, toast } from '../shared/utils.js';
import { openCheckout } from './checkout.js';

const CART_KEY = 'yummy_cart';
let items = [];

try {
    items = JSON.parse(localStorage.getItem(CART_KEY) || '[]')
        .filter((item) => (
            item
            && Number.isInteger(item.id)
            && item.qty > 0
            && item.qty <= 20
        ));
} catch {
    items = [];
}

function saveCart() {
    try {
        localStorage.setItem(CART_KEY, JSON.stringify(items));
    } catch {
        // Storage can be unavailable in private or restricted browser contexts.
    }
}

export function total() {
    return items.reduce((sum, item) => sum + item.prix * item.qty, 0);
}

export function getItems() {
    return items;
}

export function clearCart() {
    items = [];
    saveCart();
    renderCart();
}

export function addToCart(dish) {
    const existingItem = items.find((item) => item.id === dish.id);

    if (existingItem) {
        existingItem.qty = Math.min(20, existingItem.qty + 1);
    } else {
        items.push({
            id: dish.id,
            nom: dish.nom,
            prix: dish.prix,
            qty: 1,
            note: '',
        });
    }

    saveCart();
    renderCart();
    toast(`${dish.nom} ajouté au panier`);
}

export function syncWithMenu(menu) {
    const availableDishes = new Map(
        menu
            .flatMap((category) => category.plats)
            .map((dish) => [dish.id, dish]),
    );

    const previousLength = items.length;

    items = items.filter((item) => availableDishes.get(item.id)?.disponible);

    items.forEach((item) => {
        const dish = availableDishes.get(item.id);
        item.nom = dish.nom;
        item.prix = dish.prix;
    });

    if (items.length !== previousLength) {
        toast('Certains plats de votre panier ne sont plus disponibles', 'err');
    }

    saveCart();
    renderCart();
}

function renderCart() {
    $('#cart-count').textContent = items.reduce((count, item) => count + item.qty, 0);
    $('#cart-total').textContent = da(total());
    $('#checkoutBtn').disabled = !items.length;

    $('#cart-items').innerHTML = items
        .map((item) => `
            <li data-id="${item.id}">
                <div class="ci-top">
                    <b>${esc(item.nom)}</b>
                    <span>${da(item.prix * item.qty)}</span>
                </div>

                <div class="ci-ctl">
                    <button class="sm ghost" data-m aria-label="Moins">−</button>
                    <b>${item.qty}</b>
                    <button class="sm ghost" data-p aria-label="Plus">+</button>
                    <button class="sm danger" data-x>Retirer</button>
                </div>

                <input
                    class="ci-note"
                    maxlength="200"
                    placeholder="Remarque (ex : sans oignons)"
                    value="${esc(item.note)}"
                >
            </li>
        `)
        .join('') || '<li class="muted">Votre panier est vide.</li>';

    document.querySelectorAll('#cart-items li[data-id]').forEach((listItem) => {
        const item = items.find((cartItem) => cartItem.id === Number(listItem.dataset.id));

        listItem.querySelector('[data-m]').onclick = () => {
            item.qty--;
            if (item.qty < 1) {
                items = items.filter((cartItem) => cartItem !== item);
            }
            saveCart();
            renderCart();
        };

        listItem.querySelector('[data-p]').onclick = () => {
            item.qty = Math.min(20, item.qty + 1);
            saveCart();
            renderCart();
        };

        listItem.querySelector('[data-x]').onclick = () => {
            items = items.filter((cartItem) => cartItem !== item);
            saveCart();
            renderCart();
        };

        listItem.querySelector('.ci-note').oninput = (event) => {
            item.note = event.target.value;
            saveCart();
        };
    });
}

export function initCart() {
    const panel = $('#cart');

    $('#cartBtn').onclick = () => panel.classList.toggle('open');

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            panel.classList.remove('open');
        }
    });

    $('#checkoutBtn').onclick = () => {
        if (items.length) {
            panel.classList.remove('open');
            openCheckout({ items, onSuccess: clearCart });
        }
    };

    renderCart();
}
