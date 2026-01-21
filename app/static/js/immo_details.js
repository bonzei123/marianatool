document.addEventListener('DOMContentLoaded', () => {
    initForm();
});

let formConfig = [];

// --- HELPER FÜR RESPONSIVE KLASSEN (Identisch zu immo_admin.js & immo_form.js) ---
function getColClass(q) {
    const map = { 'full': 12, 'half': 6, 'third': 4 };

    // 1. Desktop Wert ermitteln (Fallback: 6/Halb)
    let desk = map[q.width] || 6;

    // 2. Tablet Wert (Wenn 'default', nimm Desktop)
    let tab = (q.width_tablet === 'default' || !q.width_tablet) ? desk : (map[q.width_tablet] || desk);

    // 3. Mobile Wert (Wenn 'default', nimm Desktop)
    let mob = (q.width_mobile === 'default' || !q.width_mobile) ? desk : (map[q.width_mobile] || desk);

    // 4. Bootstrap Klassen bauen
    let classes = `col-${mob}`;
    if (tab !== mob) classes += ` col-md-${tab}`;
    if (desk !== tab) classes += ` col-lg-${desk}`;

    return classes;
}

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
 * Rendert das Formular responsive mit Bootstrap Grid.
 */
function renderForm(container) {
    container.innerHTML = '';

    // Gespeicherte Antworten aus DB laden
    const responses = (savedResponses && savedResponses.form_responses) ? savedResponses.form_responses : {};

    // Typ aus dem inspection object lesen
    const currentType = (savedResponses && savedResponses.meta && savedResponses.meta.type) ? savedResponses.meta.type : 'einzel';

    formConfig.forEach(sec => {
        const details = document.createElement('details');
        details.className = 'mb-3 border rounded shadow-sm bg-white';
        // Wenn in Config nicht explizit eingeklappt, dann offen
        if(sec.is_expanded !== false) details.open = true;

        const summary = document.createElement('summary');
        summary.className = 'bg-light p-3 fw-bold text-primary rounded-top';
        summary.style.cursor = 'pointer';
        summary.innerText = sec.title;
        details.appendChild(summary);

        // UPDATE: Bootstrap Row Container mit Gutter (g-3)
        const content = document.createElement('div');
        content.className = "p-3 row g-3";

        let hasVisibleFields = false;

        sec.content.forEach(field => {
            // Sichtbarkeits-Check
            if(field.types && !field.types.includes(currentType)) return;
            hasVisibleFields = true;

            const wrap = document.createElement('div');

            // UPDATE: Responsive Klassen berechnen
            const colClasses = getColClass(field);

            // Sonderfall: Header, Info, Alert sind immer volle Breite
            if(['header', 'info', 'alert'].includes(field.type)) {
                wrap.className = 'col-12';
            } else {
                wrap.className = colClasses;
            }

            // Wert holen
            let val = responses[field.id];
            if (val === undefined || val === null) val = '';

            // Input Element bauen. 'immo-input' für Selektor, 'form-control' für Bootstrap Design
            const commonInputClass = "immo-input form-control";

            if(field.type === 'header') {
                wrap.innerHTML = `<h4 style="margin-top:15px; border-bottom:2px solid #ddd; padding-bottom:5px;">${field.label}</h4>`;
            }
            else if(field.type === 'info' || field.type === 'alert') {
                wrap.className += ' alert ' + (field.type=='alert'?'alert-danger':'alert-info');
                wrap.innerText = field.label;
            }
            else if(field.type === 'text' || field.type === 'number' || field.type === 'date') {
                wrap.innerHTML = `
                    <label class="form-label fw-bold">${field.label} ${field.tooltip?`<span class="text-muted small">(${field.tooltip})</span>`:''}</label>
                    <input type="${field.type}" class="${commonInputClass}" data-id="${field.id}" value="${val}">
                `;
            }
            else if(field.type === 'select') {
                const optionsHtml = field.options.map(o => `<option ${val===o?'selected':''}>${o}</option>`).join('');
                // Bei Select 'form-select' statt 'form-control' nutzen
                wrap.innerHTML = `
                    <label class="form-label fw-bold">${field.label}</label>
                    <select class="immo-input form-select" data-id="${field.id}">
                        <option value="">Wählen...</option>
                        ${optionsHtml}
                    </select>
                `;
            }
            else if(field.type === 'checkbox') {
                // Checkbox Style angepasst, damit die Höhe passt
                wrap.innerHTML = `
                    <label style="cursor:pointer; display:flex; align-items:center; gap:10px; background:#f9f9f9; padding:10px; border:1px solid #eee; border-radius:4px; height:100%;">
                        <input type="checkbox" class="immo-input" data-id="${field.id}" ${val === true || val === 'true' || val === 'on' ? 'checked' : ''} style="width:20px; height:20px;"> 
                        ${field.label}
                    </label>
                `;
            }
            else if(field.type === 'textarea') {
                wrap.innerHTML = `
                    <label class="form-label fw-bold">${field.label}</label>
                    <textarea class="${commonInputClass}" data-id="${field.id}" rows="4">${val}</textarea>
                `;
            }
            // File Uploads blenden wir im Editor aus

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