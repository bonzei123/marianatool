document.addEventListener('DOMContentLoaded', () => {
    initForm();
});

let formConfig = [];

async function initForm() {
    const container = document.getElementById('formContainer');
    try {
        const res = await fetch(formConfigUrl);
        if (!res.ok) throw new Error("Netzwerkfehler");
        formConfig = await res.json();
        renderForm(container);
    } catch (e) {
        container.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
    }
}

/**
 * Rendert das Formular EXAKT wie im Generator (immo_form.js).
 * Unterschied: Werte werden aus savedResponses geladen.
 */
function renderForm(container) {
    container.innerHTML = '';

    // Gespeicherte Antworten aus DB laden
    const responses = (savedResponses && savedResponses.form_responses) ? savedResponses.form_responses : {};

    // Typ aus dem inspection object lesen (wird im Template in JS-Variable geschrieben)
    // Da wir das im Template noch nicht explizit gemacht haben, lesen wir es aus dem DOM oder nehmen den Default.
    // Aber warte: savedResponses hat "meta.type" oder inspection object hat es.
    // Wir nehmen an, dass 'einzel' der Fallback ist, falls im JS nicht definiert.
    // Besser: Wir definieren currentType im Template oben.
    const currentType = (savedResponses && savedResponses.meta && savedResponses.meta.type) ? savedResponses.meta.type : 'einzel';

    formConfig.forEach(sec => {
        // Nutzt native <details> für Collapse, genau wie im Original
        const details = document.createElement('details');
        details.className = 'mb-3 border rounded shadow-sm bg-white';
        // Wenn in Config nicht explizit eingeklappt, dann offen
        if(sec.is_expanded !== false) details.open = true;

        const summary = document.createElement('summary');
        summary.className = 'bg-light p-3 fw-bold text-primary rounded-top';
        summary.style.cursor = 'pointer';
        summary.innerText = sec.title;
        details.appendChild(summary);

        const content = document.createElement('div');
        content.style.padding = "20px";

        let hasVisibleFields = false;

        sec.content.forEach(field => {
            // Sichtbarkeits-Check wie im Original
            if(field.types && !field.types.includes(currentType)) return;
            hasVisibleFields = true;

            const wrap = document.createElement('div');
            // WICHTIG: CSS Klassen exakt wie im Original für Grid
            wrap.className = `field-wrapper w-${field.width||'half'}`;

            // Wert holen
            let val = responses[field.id];
            if (val === undefined || val === null) val = '';

            // Input Element bauen (mit 'immo-input' Klasse für unseren Saver)
            const commonInputClass = "immo-input"; // Im Original gibt es diese Klasse nicht, aber wir brauchen sie zum Selektieren

            if(field.type === 'header') {
                wrap.className = 'w-full';
                wrap.innerHTML = `<h4 style="margin-top:15px; border-bottom:2px solid #ddd; padding-bottom:5px;">${field.label}</h4>`;
            }
            else if(field.type === 'info' || field.type === 'alert') {
                wrap.className = 'w-full alert ' + (field.type=='alert'?'alert-danger':'alert-info');
                wrap.innerText = field.label;
            }
            else if(field.type === 'text' || field.type === 'number' || field.type === 'date') {
                wrap.innerHTML = `
                    <label>${field.label} ${field.tooltip?`<span class="text-muted small">(${field.tooltip})</span>`:''}</label>
                    <input type="${field.type}" class="${commonInputClass}" data-id="${field.id}" value="${val}">
                `;
            }
            else if(field.type === 'select') {
                const optionsHtml = field.options.map(o => `<option ${val===o?'selected':''}>${o}</option>`).join('');
                wrap.innerHTML = `
                    <label>${field.label}</label>
                    <select class="${commonInputClass}" data-id="${field.id}">
                        <option value="">Wählen...</option>
                        ${optionsHtml}
                    </select>
                `;
            }
            else if(field.type === 'checkbox') {
                // Checkbox Style exakt kopiert
                wrap.innerHTML = `
                    <label style="cursor:pointer; display:flex; align-items:center; gap:10px; background:#f9f9f9; padding:10px; border:1px solid #eee; border-radius:4px;">
                        <input type="checkbox" class="${commonInputClass}" data-id="${field.id}" ${val === true || val === 'true' || val === 'on' ? 'checked' : ''} style="width:20px; height:20px;"> 
                        ${field.label}
                    </label>
                `;
            }
            else if(field.type === 'textarea') {
                wrap.innerHTML = `
                    <label>${field.label}</label>
                    <textarea class="${commonInputClass}" data-id="${field.id}" rows="4">${val}</textarea>
                `;
            }
            // File Uploads blenden wir im Editor aus, da Anhänge im anderen Tab sind

            content.appendChild(wrap);
        });

        if(hasVisibleFields) {
            details.appendChild(content);
            container.appendChild(details);
        }
    });
}

async function saveFormData() {
    const btn = document.querySelector('button[onclick="saveFormData()"]');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Speichere...`;

    const formData = {};
    document.querySelectorAll('.immo-input').forEach(input => {
        const id = input.dataset.id;
        if (!id) return;
        formData[id] = input.type === 'checkbox' ? input.checked : input.value;
    });

    try {
        const res = await fetch(`/projects/${inspectionId}/update_data`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ form_data: formData })
        });
        const result = await res.json();

        if (result.success) {
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-success');
            btn.innerHTML = `✅ Gespeichert!`;
            setTimeout(() => {
                location.reload();
            }, 800);
        } else {
            alert("Fehler: " + result.error);
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    } catch (e) {
        alert("Netzwerkfehler");
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function setStatus(newStatus) {
    if(!confirm("Status ändern?")) return;
    try {
        const res = await fetch('/projects/status', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id: inspectionId, status: newStatus })
        });
        if ((await res.json()).success) location.reload();
    } catch (e) { alert(e); }
}