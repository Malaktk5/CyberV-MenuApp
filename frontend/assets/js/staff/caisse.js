import { staffPage } from '../shared/staff.js';

const { main } = await staffPage('caissier', 'Caisse');

main.innerHTML = `
    <div class="panel placeholder">
        <h2>Écran caisse</h2>
        <p class="muted">En construction (F4, puis F5 pour l'affectation des livraisons).</p>
    </div>
`;
