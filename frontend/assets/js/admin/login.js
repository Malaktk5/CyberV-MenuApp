import { api } from '../shared/api.js';
import { ROLE_HOME } from '../shared/staff.js';

const loginForm = document.getElementById('f');
const errorMessage = document.getElementById('err');

loginForm.onsubmit = async (event) => {
    event.preventDefault();
    errorMessage.textContent = '';

    try {
        const user = await api(
            '/api/auth/login',
            'POST',
            Object.fromEntries(new FormData(loginForm)),
            { quiet: true },
        );

        const home = ROLE_HOME[user.role];

        if (home) {
            location.href = home;
        } else {
            errorMessage.textContent = `Aucun écran n'est prévu pour le rôle « ${user.role} ».`;
        }
    } catch (error) {
        errorMessage.textContent = error.message;
    }
};
