export const $ = (selector, root = document) => root.querySelector(selector);

export const esc = (value) => String(value ?? '').replace(
    /[&<>"']/g,
    (character) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
    })[character],
);

export const da = (value) => (
    `${new Intl.NumberFormat('fr-FR', {
        maximumFractionDigits: 0,
    }).format(value ?? 0)} DA`
);

export const safeUrl = (url) => (
    /^(\/uploads\/|\/assets\/|https?:\/\/)/.test(url || '')
        ? url
        : ''
);

export const attrUrl = (url) => safeUrl(url).replace(
    /['"()\\\s]/g,
    encodeURIComponent,
);

export function toast(message, kind = '') {
    let box = $('#toast');

    if (!box) {
        box = document.createElement('div');
        box.id = 'toast';
        document.body.append(box);
    }

    const toastItem = document.createElement('div');
    toastItem.textContent = message;

    if (kind) {
        toastItem.className = kind;
    }

    box.append(toastItem);

    setTimeout(() => toastItem.remove(), 3500);
}

/** Open the shared staff dialog with a form and submit handler. */
export function modal(title, body, onSubmit) {
    const dialog = $('#dlg');

    dialog.innerHTML = `
        <form class="mform">
            <h3>${title}</h3>
            ${body}

            <div class="mbtns">
                <button type="button" class="ghost" data-close>Annuler</button>
                <button>Enregistrer</button>
            </div>
        </form>
    `;

    dialog.querySelector('[data-close]').onclick = () => dialog.close();

    const form = dialog.querySelector('form');
    form.onsubmit = async (event) => {
        event.preventDefault();

        if ((await onSubmit(form)) !== false) {
            dialog.close();
        }
    };

    dialog.showModal();
    return form;
}

let audioContext = null;

const unlockAudio = () => {
    try {
        audioContext = audioContext
            || new (window.AudioContext || window.webkitAudioContext)();
        audioContext.resume();
    } catch {
        // Audio is optional and may be blocked by the browser.
    }
};

document.addEventListener('click', unlockAudio);

export const soundOn = () => {
    try {
        return localStorage.getItem('sound') !== '0';
    } catch {
        return true;
    }
};

export const setSound = (enabled) => {
    try {
        localStorage.setItem('sound', enabled ? '1' : '0');
    } catch {
        // Storage can be unavailable.
    }

    unlockAudio();
};

export function beep() {
    if (!soundOn() || !audioContext) {
        return;
    }

    [880, 1175, 1568].forEach((frequency, index) => {
        const oscillator = audioContext.createOscillator();
        const gain = audioContext.createGain();
        const time = audioContext.currentTime + index * 0.18;

        oscillator.frequency.value = frequency;
        gain.gain.setValueAtTime(0.0001, time);
        gain.gain.exponentialRampToValueAtTime(0.3, time + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.0001, time + 0.35);

        oscillator.connect(gain);
        gain.connect(audioContext.destination);

        oscillator.start(time);
        oscillator.stop(time + 0.4);
    });
}
