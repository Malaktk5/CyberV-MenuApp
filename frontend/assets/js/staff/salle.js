import { staffPage } from '../shared/staff.js';

const { main } = await staffPage('serveur', 'Salle');

main.innerHTML = `
    <div class="panel placeholder">
        <h2>Écran salle</h2>
        <p class="muted">En construction (F3).</p>
    </div>
`;
