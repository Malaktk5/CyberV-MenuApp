import { staffPage } from '../shared/staff.js';

const { main } = await staffPage('cuisinier', 'Cuisine');
main.innerHTML = `<div class="panel placeholder"><h2>Écran cuisine</h2><p class="muted">En construction (F2).</p></div>`;
