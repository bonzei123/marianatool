document.addEventListener('DOMContentLoaded', () => {
    initForm();
});

// --- GLOBALE VARIABLEN ---
let formConfig = [];
let autosaveTimer = null;
const AUTOSAVE_DELAY = 2000;
const RETRY_DELAY = 10000;
const STORAGE_KEY = `immo_draft_${inspectionId}`;

// --- HELPER FUNCTIONS ---

function cleanFileName(path) {
    if (!path) return "";
    return path.split(/[/\\]/).pop();
}

function getFileType(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return 'img';
    if (['mp4', 'mov', 'avi', 'mkv'].includes(ext)) return 'vid';
    if (ext === 'pdf') return 'pdf';
    return 'other';
}

function getColClass(q) {
    const map = { 'full': 12, 'half': 6, 'third': 4 };
    let desk = map[q.width] || 6;
    let tab = (q.width_tablet === 'default' || !q.width_tablet) ? desk : (map[q.width_tablet] || desk);
    let mob = (q.width_mobile === 'default' || !q.width_mobile) ? desk : (map[q.width_mobile] || desk);
    let classes = `col-${mob}`;
    if (tab !== mob) classes += ` col-md-${tab}`;
    if (desk !== tab) classes += ` col-lg-${desk}`;
    return classes;
}

// --- INITIALISIERUNG ---

async function initForm() {
    const container = document.getElementById('formContainer');
    try {
        const res = await fetch(formConfigUrl);
        if (!res.ok) throw new Error("Netzwerkfehler");
        formConfig = await res.json();

        renderForm(container);
        checkLocalStorage();

    } catch (e) {
        container.innerHTML = `<div class="alert alert-danger">Fehler: ${e.message}</div>`;
    }
}

// --- LOCALSTORAGE & AUTOSAVE ---

function checkLocalStorage() {
    const raw = localStorage.getItem(STORAGE_KEY);
    if(!raw) return;

    try {
        const localData = JSON.parse(raw);
        console.log("📥 Lokale Daten wiederhergestellt.");

        for (const [key, value] of Object.entries(localData)) {
            const input = document.querySelector(`.immo-input[data-id="${key}"]`);
            if(input) {
                if(input.type === 'checkbox') input.checked = value;
                else input.value = value;
            }
        }

        const btn = document.querySelector('button[onclick="saveFormData()"]');
        if(btn) {
            btn.classList.add('btn-warning');
            btn.innerHTML = `<i class="bi bi-cloud-upload"></i> Ungespeicherte Daten senden...`;
        }
        triggerAutosave();

    } catch(e) { console.error(e); }
}

function saveToLocalStorage(data) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

function clearLocalStorage() {
    localStorage.removeItem(STORAGE_KEY);
}

function collectFormData() {
    const formData = {};
    document.querySelectorAll('.immo-input').forEach(input => {
        if (input.type === 'file') return;
        const id = input.dataset.id;
        if (!id) return;
        formData[id] = input.type === 'checkbox' ? input.checked : input.value;
    });
    return formData;
}

window.handleInput = function(el) {
    if(el.classList.contains('is-invalid')) {
        el.classList.remove('is-invalid');
    }
    saveToLocalStorage(collectFormData());
    triggerAutosave();
}

function triggerAutosave() {
    if(autosaveTimer) clearTimeout(autosaveTimer);

    const btn = document.querySelector('button[onclick="saveFormData()"]');
    if(btn) {
        btn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Speichere...`;
        btn.classList.remove('btn-success', 'btn-primary', 'btn-warning');
        btn.classList.add('btn-light');
    }

    autosaveTimer = setTimeout(() => {
        saveFormData(true);
    }, AUTOSAVE_DELAY);
}

// --- CORE: SAVE ---
async function saveFormData(silent = false) {
    const btn = document.querySelector('button[onclick="saveFormData()"]');
    const originalText = `<i class="bi bi-save"></i> Speichern`;

    if(btn && !silent) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Sync...`;
    }

    const formData = collectFormData();

    try {
        const res = await fetch(`/projects/${inspectionId}/update_data`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ form_data: formData })
        });
        const result = await res.json();

        if (result.success) {
            clearLocalStorage();
            if(btn) {
                btn.classList.remove('btn-primary', 'btn-light', 'btn-warning');
                btn.classList.add('btn-success');
                btn.innerHTML = `✅ Gespeichert`;
                if(!silent) btn.disabled = false;
                setTimeout(() => {
                    if(btn.innerHTML.includes('Gespeichert')) {
                        btn.classList.remove('btn-success');
                        btn.classList.add('btn-primary');
                        btn.innerHTML = originalText;
                    }
                }, 2000);
            }
        } else {
            throw new Error(result.error);
        }
    } catch (e) {
        if(btn) {
            btn.classList.remove('btn-primary', 'btn-light', 'btn-success');
            btn.classList.add('btn-warning');
            btn.innerHTML = `<i class="bi bi-wifi-off"></i> Offline (Lokal)`;
            if(!silent) btn.disabled = false;
        }
        if(autosaveTimer) clearTimeout(autosaveTimer);
        autosaveTimer = setTimeout(() => triggerAutosave(), RETRY_DELAY);
    }
}

// --- VALIDIERUNG ---
function validateForm() {
    const currentType = (savedResponses && savedResponses.meta && savedResponses.meta.type) ? savedResponses.meta.type : 'einzel';
    let isValid = true;
    let firstError = null;

    formConfig.forEach(sec => {
        sec.content.forEach(field => {
            if(field.types && !field.types.includes(currentType)) return;
            if(!field.is_required) return;

            let el = document.querySelector(`.immo-input[data-id="${field.id}"]`);
            if(!el) return;

            let isFieldValid = true;
            if (field.type === 'checkbox') {
                 if (!el.checked) isFieldValid = false;
            } else {
                 if (!el.value || el.value.trim() === "") isFieldValid = false;
            }

            if (!isFieldValid) {
                isValid = false;
                if(field.type === 'file') {
                     const btn = el.parentElement.querySelector('.btn-outline-secondary');
                     if(btn) btn.classList.add('border-danger', 'text-danger');
                } else {
                    el.classList.add('is-invalid');
                }
                if(!firstError) firstError = el;
            } else {
                if(field.type === 'file') {
                     const btn = el.parentElement.querySelector('.btn-outline-secondary');
                     if(btn) btn.classList.remove('border-danger', 'text-danger');
                } else {
                    el.classList.remove('is-invalid');
                }
            }
        });
    });

    if (!isValid && firstError) {
        const details = firstError.closest('details');
        if(details) details.open = true;
        firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
        alert("⚠️ Bitte füllen Sie alle Pflichtfelder aus, bevor Sie einreichen!");
    }

    return isValid;
}

// --- STATUS UPDATE ---
async function setStatus(newStatus) {
    if (newStatus === 'submitted') {
        if (!validateForm()) return;
        await saveFormData(true);
    }

    try {
        const res = await fetch('/projects/status', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id: inspectionId, status: newStatus })
        });

        const data = await res.json();
        if (data.success) {
            location.reload();
        } else {
            alert("Fehler: " + (data.error || "Unbekannt"));
        }
    } catch (e) {
        alert("Netzwerkfehler: " + e.message);
    }
}

// --- RENDER FORM ---
function renderForm(container) {
    container.innerHTML = '';
    const responses = (savedResponses && savedResponses.form_responses) ? savedResponses.form_responses : {};
    const currentType = (savedResponses && savedResponses.meta && savedResponses.meta.type) ? savedResponses.meta.type : 'einzel';

    formConfig.forEach(sec => {
        const details = document.createElement('details');
        details.className = 'mb-3 border rounded shadow-sm bg-white';

        const summary = document.createElement('summary');
        summary.className = 'bg-light p-3 fw-bold text-primary rounded-top';
        summary.style.cursor = 'pointer';
        summary.innerText = sec.title;
        details.appendChild(summary);

        const content = document.createElement('div');
        content.className = "p-3 row g-3";

        let hasVisibleFields = false;

        // LOGIK UPDATE: Auto-Collapse
        let hasInputFields = false; // Gibt es überhaupt Felder zum Ausfüllen?
        let isComplete = true; // Sind ALLE diese Felder ausgefüllt?

        sec.content.forEach(field => {
            if(field.types && !field.types.includes(currentType)) return;
            hasVisibleFields = true;

            const wrap = document.createElement('div');
            wrap.className = ['header', 'info', 'alert'].includes(field.type) ? 'col-12' : getColClass(field);

            let val = responses[field.id];
            if (val === undefined || val === null) val = '';

            // --- PRÜFUNG OB SEKTION FERTIG IST ---
            // Wir ignorieren reine Infotexte für die "Fertig"-Prüfung
            if (!['header', 'info', 'alert'].includes(field.type)) {
                hasInputFields = true;

                // Bei Checkboxen: Auch wenn sie nicht checked sind, sind sie "da".
                // Aber für "Auto-Collapse" wollen wir, dass der User sie explizit bestätigt hat.
                // In einem neuen Projekt sind sie false. -> isComplete = false -> Offen lassen.
                if (field.type === 'checkbox') {
                    if (!val) isComplete = false;
                } else {
                    if (val === '') isComplete = false;
                }
            }

            const reqMark = field.is_required ? ' <span class="text-danger fw-bold">*</span>' : '';
            const inputEvents = `oninput="handleInput(this)" onchange="handleInput(this)"`;
            const commonInputClass = "immo-input form-control";
            let fieldHtml = '';

            if(field.type === 'header') {
                fieldHtml = `<h4 style="margin-top:15px; border-bottom:2px solid #ddd; padding-bottom:5px;">${field.label}</h4>`;
            }
            else if(field.type === 'info' || field.type === 'alert') {
                wrap.className += ' alert ' + (field.type=='alert'?'alert-danger':'alert-info');
                fieldHtml = field.label;
            }
            else if(['text', 'number', 'date'].includes(field.type)) {
                fieldHtml = `
                    <label class="form-label fw-bold">${field.label} ${field.tooltip?`<span class="text-muted small">(${field.tooltip})</span>`:''}${reqMark}</label>
                    <input type="${field.type}" class="${commonInputClass}" data-id="${field.id}" value="${val}" ${inputEvents}>
                `;
            }
            else if(field.type === 'select') {
                const optionsHtml = field.options.map(o => `<option ${val===o?'selected':''}>${o}</option>`).join('');
                fieldHtml = `
                    <label class="form-label fw-bold">${field.label}${reqMark}</label>
                    <select class="immo-input form-select" data-id="${field.id}" ${inputEvents}><option value="">Wählen...</option>${optionsHtml}</select>
                `;
            }
            else if(field.type === 'checkbox') {
                fieldHtml = `
                    <label style="cursor:pointer; display:flex; align-items:center; gap:10px; background:#f9f9f9; padding:10px; border:1px solid #eee; border-radius:4px; height:100%;">
                        <input type="checkbox" class="immo-input" data-id="${field.id}" ${val===true||val==='true'||val==='on'?'checked':''} style="width:20px; height:20px;" ${inputEvents}> 
                        ${field.label}${reqMark}
                    </label>
                `;
            }
            else if(field.type === 'textarea') {
                fieldHtml = `
                    <label class="form-label fw-bold">${field.label}${reqMark}</label>
                    <textarea class="${commonInputClass}" data-id="${field.id}" rows="4" ${inputEvents}>${val}</textarea>
                `;
            }
            else if(field.type === 'file') {
                 const filesArray = val ? val.split(',').map(s => s.trim()).filter(s => s) : [];
                 let filesListHtml = '';
                 if(filesArray.length > 0) {
                     filesListHtml = '<div class="mt-2 d-flex flex-wrap gap-2">';
                     filesArray.forEach(f => {
                         const cleanName = cleanFileName(f);
                         const linkUrl = `/projects/download/${encodeURIComponent(uploadFolder)}/${encodeURIComponent(cleanName)}`;
                         const fType = getFileType(cleanName);
                         filesListHtml += `
                             <div class="badge bg-white text-primary border border-primary p-2 d-flex align-items-center cursor-pointer hover-shadow"
                                  onclick="openFilePreview('${linkUrl}', '${cleanName}', '${fType}')" title="Vorschau">
                                 <i class="bi bi-file-earmark-text me-2"></i> ${cleanName}
                                 <i class="bi bi-eye ms-2 small text-muted"></i>
                             </div>
                         `;
                     });
                     filesListHtml += '</div>';
                 }

                 fieldHtml = `
                    <label class="form-label fw-bold mb-1">${field.label}${reqMark}</label>
                    <div class="d-flex align-items-center gap-2">
                         <button class="btn btn-sm btn-outline-secondary" type="button" onclick="document.getElementById('file-${field.id}').click()">
                            <i class="bi bi-cloud-plus"></i> Hinzufügen
                        </button>
                        ${filesArray.length === 0 ? '<span class="text-muted small fst-italic ms-2">Keine Datei</span>' : ''}
                    </div>
                    ${filesListHtml}
                    <input type="hidden" class="immo-input" data-id="${field.id}" value="${val}">
                    <input type="file" id="file-${field.id}" style="display:none;" 
                           onchange="handleFormFieldUpload(this, '${field.id}', '${field.label.replace(/'/g, "\\'")}')">
                    <div id="progress-${field.id}" class="progress mt-2" style="height: 3px; display:none;">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                 `;
            }

            wrap.innerHTML = fieldHtml;
            content.appendChild(wrap);
        });

        if(hasVisibleFields) {
            details.appendChild(content);
            container.appendChild(details);

            // LOGIK ENTSCHEIDUNG:
            // 1. Haben wir Input Felder UND sind alle ausgefüllt? -> Zuklappen (Auto-Collapse)
            if (hasInputFields && isComplete) {
                details.open = false;
            }
            // 2. Ansonsten (Leer, Neu, oder nur Info-Texte) -> Config respektieren
            else if (sec.is_expanded !== false) {
                details.open = true;
            }
        }
    });
}

// --- UPLOAD ---
async function uploadFileChunked(file, folderName, customName, onProgress) {
    const initRes = await fetch('/projects/upload/init', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ folder_name: folderName })
    });
    if(!initRes.ok) throw new Error("Upload Init fehlgeschlagen");

    const targetFilename = customName || file.name;
    const chunkSize = 1024 * 1024; // 1MB
    const totalChunks = Math.ceil(file.size / chunkSize);

    for(let i=0; i<totalChunks; i++) {
        const start = i * chunkSize;
        const end = Math.min(file.size, start + chunkSize);
        const chunk = file.slice(start, end);

        const fd = new FormData();
        fd.append('folder', folderName);
        fd.append('filename', targetFilename);
        fd.append('chunkIndex', i);
        fd.append('file', chunk);

        const res = await fetch('/projects/upload/chunk', { method: 'POST', body: fd });
        if(!res.ok) throw new Error("Chunk Upload fehlgeschlagen");

        if(onProgress) onProgress(Math.round(((i+1)/totalChunks)*100));
    }
    return targetFilename;
}

window.handleFormFieldUpload = async function(input, fieldId, fieldLabel) {
    if(!input.files || !input.files[0]) return;
    const file = input.files[0];
    const progressEl = document.getElementById(`progress-${fieldId}`);
    const barEl = progressEl.querySelector('.progress-bar');

    progressEl.style.display = 'flex';
    barEl.style.width = '0%';

    const cleanLabel = fieldLabel.replace(/[^a-zA-Z0-9äöüÄÖÜß]/g, '_');
    const ext = file.name.split('.').pop();

    const hiddenInput = document.querySelector(`.immo-input[data-id="${fieldId}"]`);
    let currentVal = hiddenInput ? hiddenInput.value : '';
    let filesArray = currentVal ? currentVal.split(',').map(s => s.trim()).filter(s => s) : [];
    filesArray = filesArray.map(f => cleanFileName(f));

    const count = filesArray.length + 1;
    const newFilename = `${cleanLabel}_${count}.${ext}`;

    try {
        await uploadFileChunked(file, uploadFolder, newFilename, (pct) => {
            barEl.style.width = pct + '%';
        });

        filesArray.push(newFilename);
        if(hiddenInput) hiddenInput.value = filesArray.join(',');
        input.value = '';

        const btn = document.querySelector(`.immo-input[data-id="${fieldId}"]`).parentElement.querySelector('.btn-outline-secondary');
        if(btn) btn.classList.remove('border-danger', 'text-danger');

        await saveFormData(true);
        location.reload();
    } catch(e) {
        alert("Fehler beim Upload: " + e.message);
        progressEl.style.display = 'none';
        input.value = '';
    }
}

window.uploadFileGeneric = async function(file) {
    if(!confirm(`Datei "${file.name}" wirklich hochladen?`)) return;
    document.body.style.cursor = 'wait';
    try {
        await uploadFileChunked(file, uploadFolder, null, (pct) => console.log(pct));
        alert("Datei erfolgreich hochgeladen!");
        location.reload();
    } catch(e) {
        alert("Fehler: " + e.message);
    } finally {
        document.body.style.cursor = 'default';
    }
}

window.openFilePreview = function(url, name, type) {
    const modalEl = document.getElementById('filePreviewModal');
    const titleEl = document.getElementById('previewTitle');
    const contentEl = document.getElementById('previewContent');
    const dlBtn = document.getElementById('previewDownloadBtn');

    titleEl.textContent = name;
    dlBtn.href = url;
    contentEl.innerHTML = '';

    if(type === 'img') {
        contentEl.innerHTML = `<img src="${url}" class="img-fluid" style="max-height: 85vh; object-fit: contain;">`;
    } else if (type === 'pdf') {
        contentEl.innerHTML = `<object data="${url}" type="application/pdf" width="100%" height="100%" style="min-height: 80vh;">
                                 <p class="text-white">Vorschau nicht möglich. <a href="${url}" class="text-info">Download</a>.</p>
                               </object>`;
    } else if (type === 'vid') {
        contentEl.innerHTML = `<video controls style="max-width: 100%; max-height: 85vh;"><source src="${url}">Video nicht unterstützt.</video>`;
    } else {
        contentEl.innerHTML = `<div class="text-center text-white"><i class="bi bi-file-earmark fs-1 mb-3"></i><br>Keine Vorschau verfügbar.</div>`;
    }

    const modal = new bootstrap.Modal(modalEl);
    modal.show();
}