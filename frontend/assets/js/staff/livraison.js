import { staffPage } from '../shared/staff.js';

const { main } = await staffPage('livreur', 'Livraisons');

main.innerHTML = `
    <div class="panel placeholder">
        <h2>Écran livraisons</h2>
        <p class="muted">En construction (F6).</p>
    </div>
`;
