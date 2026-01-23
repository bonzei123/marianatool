// --- HELPER FUNCTIONS ---

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

function getFileType(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return 'img';
    if (['mp4', 'mov', 'avi', 'mkv'].includes(ext)) return 'vid';
    if (ext === 'pdf') return 'pdf';
    return 'other';
}

// Injiziert das Modal in den Body, falls es nicht existiert (für Preview)
function ensureModalExists() {
    if (document.getElementById('filePreviewModal')) return;

    const modalHtml = `
    <div class="modal fade" id="filePreviewModal" tabindex="-1" aria-hidden="true" style="z-index: 10000;">
        <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content" style="height: 90vh;">
                <div class="modal-header">
                    <h5 class="modal-title text-truncate" id="previewTitle" style="max-width: 80%;">Vorschau</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body p-0 bg-dark d-flex align-items-center justify-content-center position-relative">
                    <div id="previewContent" class="w-100 h-100 d-flex align-items-center justify-content-center"></div>
                </div>
                <div class="modal-footer bg-light">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Schließen</button>
                </div>
            </div>
        </div>
    </div>`;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

function openLocalPreview(url, name, type) {
    ensureModalExists();
    const modalEl = document.getElementById('filePreviewModal');
    const titleEl = document.getElementById('previewTitle');
    const contentEl = document.getElementById('previewContent');

    titleEl.textContent = name;
    contentEl.innerHTML = '';

    if(type === 'img') {
        contentEl.innerHTML = `<img src="${url}" class="img-fluid" style="max-height: 85vh; object-fit: contain;">`;
    } else if (type === 'pdf') {
        contentEl.innerHTML = `<object data="${url}" type="application/pdf" width="100%" height="100%" style="min-height: 80vh;">
                                 <p class="text-white">Vorschau nicht möglich.</p>
                               </object>`;
    } else if (type === 'vid') {
        contentEl.innerHTML = `<video controls style="max-width: 100%; max-height: 85vh;"><source src="${url}">Browser unterstützt Video nicht.</video>`;
    } else {
        contentEl.innerHTML = `<div class="text-center text-white"><i class="bi bi-file-earmark fs-1 mb-3"></i><br>Keine Vorschau verfügbar.</div>`;
    }

    const modal = new bootstrap.Modal(modalEl);
    modal.show();
}


// --- UPLOADER LOGIK ---

const uploader = {
    queue: [],
    isUploading: false,
    isPaused: false,
    folderName: "",

    initModal: function(pdfBlob, pdfName) {
        this.queue = [];
        this.isPaused = false;
        this.isUploading = false;
        this.folderName = "";

        // 1. PDF hinzufügen (falls generiert)
        if (pdfBlob && pdfName) {
            this.addItemToQueue(new File([pdfBlob], pdfName, {type:"application/pdf"}));
        }

        // 2. NEU: Dateien aus dem app.pendingFiles Speicher holen (statt aus inputs)
        Object.values(app.pendingFiles).forEach(fileList => {
            fileList.forEach(file => {
                this.addItemToQueue(file);
            });
        });

        document.getElementById('uploadModal').style.display='block';
        this.renderList();
        this.updateControls();
    },

    addItemToQueue: function(file) {
        this.queue.push({
            file: file,
            status: 'pending',
            progress: 0,
            uploadedChunks: 0,
            totalChunks: Math.ceil(file.size / (1024 * 1024))
        });
    },

    renderList: function() {
        const list = document.getElementById('uploadList');

        if (this.queue.length === 0) {
            list.innerHTML = `
                <div class="alert alert-info text-center">
                    <i class="bi bi-info-circle"></i> Keine Dateien zum Hochladen.<br>
                    Klicke auf <strong>"Speichern & Beenden"</strong>, um die Daten zu übertragen.
                </div>
            `;
            return;
        }

        const totalSize = this.queue.reduce((acc, item) => acc + item.file.size, 0);
        const totalLoaded = this.queue.reduce((acc, item) => acc + (item.progress / 100 * item.file.size), 0);
        const totalPercent = totalSize > 0 ? Math.round((totalLoaded / totalSize) * 100) : 0;

        let html = `
            <div class="mb-3">
                <div class="d-flex justify-content-between small fw-bold mb-1">
                    <span>Gesamtfortschritt</span>
                    <span>${totalPercent}%</span>
                </div>
                <div class="progress" style="height: 15px;">
                    <div class="progress-bar bg-success" style="width: ${totalPercent}%"></div>
                </div>
            </div>
            <hr>
        `;

        html += this.queue.map(item => {
            let icon = '⏳';
            let statusClass = 'status-pending';
            let statusText = 'Warteschlange...';

            if(item.status === 'uploading') { icon = '🚀'; statusClass = 'status-uploading'; statusText = 'Lädt hoch...'; }
            if(item.status === 'done') { icon = '✅'; statusClass = 'status-done'; statusText = 'Fertig'; }
            if(item.status === 'error') { icon = '❌'; statusClass = 'status-error'; statusText = 'Fehler'; }
            if(item.status === 'paused') { icon = '⏸️'; statusClass = 'status-paused'; statusText = 'Pausiert'; }

            return `
            <div class="upload-item">
                <div class="upload-info ${statusClass}">
                    <span>${icon} ${item.file.name}</span>
                    <span>${item.progress}%</span>
                </div>
                <div class="progress">
                    <div class="progress-bar ${item.status === 'error' ? 'bg-danger' : ''}" style="width: ${item.progress}%"></div>
                </div>
                <div class="d-flex justify-content-between mt-1">
                    <small class="text-muted">${statusText}</small>
                    <small class="text-muted">${(item.file.size / (1024*1024)).toFixed(2)} MB</small>
                </div>
            </div>`;
        }).join('');

        list.innerHTML = html;
    },

    updateControls: function() {
        const btnStart = document.getElementById('startUploadBtn');
        const btnPause = document.getElementById('pauseUploadBtn');

        if (!btnStart || !btnPause) return;

        if (this.queue.length === 0) {
            btnStart.innerText = "Speichern & Beenden";
            btnStart.className = "btn btn-success fw-bold";
        } else {
            btnStart.innerText = this.queue.some(i => i.uploadedChunks > 0) ? "Fortsetzen" : "Starten";
            btnStart.className = "btn btn-primary fw-bold";
        }

        if (this.isUploading) {
            btnStart.style.display = 'none';
            btnPause.style.display = 'inline-block';
            btnPause.innerText = this.isPaused ? "▶️ Fortsetzen" : "⏸️ Pause";
            btnPause.className = this.isPaused ? "btn btn-warning" : "btn btn-secondary";
        } else {
            const isDone = this.queue.length > 0 && this.queue.every(i => i.status === 'done');
            btnStart.style.display = isDone ? 'none' : 'inline-block';
            btnPause.style.display = 'none';
        }
    },

    togglePause: function() {
        this.isPaused = !this.isPaused;
        if (!this.isPaused) this.start();
        this.renderList();
        this.updateControls();
    },

    start: async function() {
        if (this.isUploading && !this.isPaused) return;
        this.isUploading = true;
        this.isPaused = false;
        this.updateControls();

        try {
            const cscName = document.getElementById('global_csc_name').value || "Unbekannt";

            if (!this.folderName) {
                let baseName = "";
                if (this.queue.length > 0) {
                    baseName = this.queue[0].file.name.replace(/\.[^/.]+$/, "");
                } else {
                    baseName = cscName.replace(/[^a-zA-Z0-9]/g, "_");
                }
                const folderPayload = { folder_name: baseName + "_" + Date.now() };

                const initRes = await fetch('/projects/upload/init', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(folderPayload)
                });
                const initJson = await initRes.json();
                if (!initJson.success) throw new Error("Ordner Init fehlgeschlagen");
                this.folderName = initJson.path;
            }

            for (const item of this.queue) {
                if (item.status === 'done') continue;
                item.status = 'uploading';
                this.renderList();
                const chunkSize = 1024 * 1024;

                for (let i = item.uploadedChunks; i < item.totalChunks; i++) {
                    if (this.isPaused) {
                        item.status = 'paused';
                        this.renderList();
                        this.updateControls();
                        return;
                    }
                    const start = i * chunkSize;
                    const end = Math.min(start + chunkSize, item.file.size);
                    const chunk = item.file.slice(start, end);

                    const fd = new FormData();
                    fd.append('file', chunk);
                    fd.append('filename', item.file.name);
                    fd.append('folder', this.folderName);
                    fd.append('chunkIndex', i);
                    fd.append('totalChunks', item.totalChunks);

                    try {
                        const res = await fetch('/projects/upload/chunk', { method: 'POST', body: fd });
                        if (!res.ok) throw new Error("Netzwerkfehler");
                        item.uploadedChunks = i + 1;
                        item.progress = Math.round((item.uploadedChunks / item.totalChunks) * 100);
                        this.renderList();
                    } catch (err) {
                        console.error(err);
                        item.status = 'error';
                        this.isPaused = true;
                        this.renderList();
                        this.updateControls();
                        alert(`Fehler bei ${item.file.name}.`);
                        return;
                    }
                }
                item.status = 'done';
                this.renderList();
            }

            if (this.queue.length === 0 || this.queue.every(i => i.status === 'done')) {
                const immoType = document.getElementById('immoSelector').value;
                const finalRes = await fetch('/projects/submit', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        filename: "",
                        folder: this.folderName,
                        csc_name: cscName,
                        immo_type: immoType,
                        form_data: app.data
                    })
                });
                const finalJson = await finalRes.json();
                if (finalJson.success) {
                    const btn = document.getElementById('startUploadBtn');
                    btn.className = "btn btn-success";
                    btn.innerText = "✅ Erfolgreich! Weiterleitung...";
                    setTimeout(() => {
                        localStorage.removeItem('project_data');
                        window.location.href = `/projects/${finalJson.id}/details`;
                    }, 1000);
                } else {
                    throw new Error(finalJson.error);
                }
            }
        } catch (e) {
            alert("Fehler: " + e.message);
            this.isUploading = false;
            this.updateControls();
        } finally {
            if (!this.isPaused) {
                this.isUploading = false;
                this.updateControls();
            }
        }
    }
};


// --- APP LOGIK ---

const app = {
    data: {}, config: [],
    pendingFiles: {}, // NEU: Zwischenspeicher für Dateien

    init: async function() {
        // Daten holen
        const res = await fetch('/projects/config');
        this.config = await res.json();

        const raw = localStorage.getItem('project_data');
        if(raw) {
            this.data = JSON.parse(raw);
            document.getElementById('global_csc_name').value = this.data.csc_name||'';
            if(this.data.immo_typ) {
                document.getElementById('immoSelector').value = this.data.immo_typ;
                // Files säubern beim Neuladen, da wir die Binary-Daten nicht im LocalStorage haben
                this.cleanFileFieldData();
                this.render();
            }
        }

        // Live-Saving bei Eingabe
        document.addEventListener('input', e => {
            if(e.target.id != 'global_csc_name' && e.target.type !== 'file') {
                this.data[e.target.name] = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
                if(e.target.classList.contains('is-invalid') && e.target.value.trim() !== '') {
                    e.target.classList.remove('is-invalid');
                }
            }
            this.save();
        });
    },

    // Entfernt Dateinamen aus app.data bei Reload (da echte Dateien weg sind)
    cleanFileFieldData: function() {
        this.config.forEach(sec => {
            sec.content.forEach(field => {
                if(field.type === 'file') {
                    this.data[field.id] = "";
                }
            });
        });
    },

    save: function() {
        this.data.csc_name = document.getElementById('global_csc_name').value;
        this.data.immo_typ = document.getElementById('immoSelector').value;
        localStorage.setItem('project_data', JSON.stringify(this.data));
    },

    reset: function() {
        if(confirm("Möchten Sie wirklich alle Eingaben löschen?")) {
            localStorage.removeItem('project_data');
            location.reload();
        }
    },

    // Handelt Datei-Auswahl: Umbenennen & Speichern
    handleFileUpload: function(input, fieldId, fieldLabel) {
        if(!input.files || !input.files[0]) return;
        const file = input.files[0];

        // 1. Name generieren
        const cleanLabel = fieldLabel.replace(/[^a-zA-Z0-9äöüÄÖÜß]/g, '_');
        const ext = file.name.split('.').pop();

        if(!this.pendingFiles[fieldId]) this.pendingFiles[fieldId] = [];
        const count = this.pendingFiles[fieldId].length + 1;
        const newName = `${cleanLabel}_${count}.${ext}`;

        // 2. Neues File Objekt erstellen (mit neuem Namen)
        const renamedFile = new File([file], newName, {type: file.type});

        // 3. Speichern
        this.pendingFiles[fieldId].push(renamedFile);

        // 4. app.data aktualisieren (CSV String für DB)
        const names = this.pendingFiles[fieldId].map(f => f.name).join(',');
        this.data[fieldId] = names;

        // 5. UI Update & Reset
        this.render();
        this.save();
    },

    render: function() {
        const type = document.getElementById('immoSelector').value;
        const container = document.getElementById('form-generator-output');
        // Merken der Scroll-Position, da render() alles neu baut
        // const scrollPos = window.scrollY;

        container.innerHTML = '';

        this.config.forEach(sec => {
            const details = document.createElement('details');
            if(sec.is_expanded !== false) details.open = true;

            const content = document.createElement('div');
            content.className = "p-3 row g-3";

            let hasFields = false;

            sec.content.forEach(field => {
                if(field.types && !field.types.includes(type)) return;
                hasFields = true;

                const wrap = document.createElement('div');
                const colClasses = getColClass(field);

                if(['header', 'info', 'alert'].includes(field.type)) {
                    wrap.className = 'col-12';
                } else {
                    wrap.className = colClasses;
                }

                const val = this.data[field.id] || '';
                const reqMark = field.is_required ? ' <span class="text-danger fw-bold">*</span>' : '';

                if(field.type === 'header') {
                    wrap.innerHTML = `<h4 style="margin-top:15px; border-bottom:2px solid #ddd; padding-bottom:5px;">${field.label}</h4>`;

                } else if(field.type === 'info' || field.type === 'alert') {
                    wrap.className += ' alert ' + (field.type=='alert'?'alert-danger':'alert-info');
                    wrap.innerText = field.label;

                } else if(['text', 'number', 'date'].includes(field.type)) {
                    wrap.innerHTML = `<label class="form-label fw-bold">${field.label} ${field.tooltip?`(${field.tooltip})`:''}${reqMark}</label>
                                      <input type="${field.type}" name="${field.id}" value="${val}" class="form-control">`;

                } else if(field.type === 'select') {
                    wrap.innerHTML = `<label class="form-label fw-bold">${field.label}${reqMark}</label>
                                      <select name="${field.id}" class="form-select">
                                          <option value="">Wählen...</option>
                                          ${field.options.map(o=>`<option ${val===o?'selected':''}>${o}</option>`).join('')}
                                      </select>`;

                } else if(field.type === 'checkbox') {
                    wrap.innerHTML = `<label style="cursor:pointer; display:flex; align-items:center; gap:10px; background:#f9f9f9; padding:10px; border:1px solid #eee; border-radius:4px; height:100%;">
                                            <input type="checkbox" name="${field.id}" ${val?'checked':''} style="width:20px; height:20px;"> 
                                            ${field.label}${reqMark}
                                      </label>`;

                } else if(field.type === 'textarea') {
                    wrap.innerHTML = `<label class="form-label fw-bold">${field.label}${reqMark}</label>
                                      <textarea name="${field.id}" rows="4" class="form-control">${val}</textarea>`;

                }
                // --- NEUE DATEI LOGIK ---
                else if(field.type === 'file') {
                    const files = this.pendingFiles[field.id] || [];

                    let chips = '';
                    if(files.length > 0) {
                         chips = '<div class="mt-2 d-flex flex-wrap gap-2">';
                         files.forEach(f => {
                             // URL für Vorschau erstellen
                             const url = URL.createObjectURL(f);
                             const fType = getFileType(f.name);

                             chips += `
                                <div class="badge bg-white text-primary border border-primary p-2 d-flex align-items-center cursor-pointer hover-shadow"
                                     onclick="openLocalPreview('${url}', '${f.name}', '${fType}')">
                                    <i class="bi bi-file-earmark-text me-2"></i> ${f.name}
                                    <i class="bi bi-eye ms-2 small text-muted"></i>
                                </div>`;
                         });
                         chips += '</div>';
                    }

                    wrap.innerHTML = `
                        <label class="form-label fw-bold mb-1">${field.label}</label>
                        <div class="d-flex align-items-center gap-2">
                             <button class="btn btn-sm btn-outline-secondary" type="button" onclick="document.getElementById('file-${field.id}').click()">
                                <i class="bi bi-cloud-plus"></i> Hinzufügen
                            </button>
                            ${files.length === 0 ? '<span class="text-muted small fst-italic ms-2">Keine Datei</span>' : ''}
                        </div>
                        ${chips}
                        
                        <input type="hidden" name="${field.id}" value="${val}">
                        
                        <input type="file" id="file-${field.id}" style="display:none;" 
                               onchange="app.handleFileUpload(this, '${field.id}', '${field.label.replace(/'/g, "\\'")}')">
                    `;
                }

                content.appendChild(wrap);
            });

            if(hasFields) {
                details.innerHTML = `<summary>${sec.title}</summary>`;
                details.appendChild(content);
                container.appendChild(details);
            }
        });

        // window.scrollTo(0, scrollPos); // Optional: Scroll Position halten
    },

    validate: function() {
        const cscName = document.getElementById('global_csc_name');
        const currentType = document.getElementById('immoSelector').value;
        let isValid = true;
        let firstErrorElement = null;

        if (!cscName.value.trim()) {
            cscName.classList.add('is-invalid');
            if(!firstErrorElement) firstErrorElement = cscName;
            isValid = false;
        } else {
            cscName.classList.remove('is-invalid');
        }

        if (!currentType) {
            document.getElementById('immoSelector').classList.add('is-invalid');
            isValid = false;
        } else {
            document.getElementById('immoSelector').classList.remove('is-invalid');
        }

        this.config.forEach(sec => {
            sec.content.forEach(field => {
                if(field.types && !field.types.includes(currentType)) return;
                if(!field.is_required) return;

                const el = document.querySelector(`[name="${field.id}"]`);
                if(!el) return;

                let isFieldValid = true;
                if (field.type === 'checkbox') {
                    if (!el.checked) isFieldValid = false;
                } else {
                    if (!el.value || el.value.trim() === "") isFieldValid = false;
                }

                if (!isFieldValid) {
                    el.classList.add('is-invalid');
                    if(field.type === 'checkbox') el.parentElement.style.border = "1px solid red";
                    isValid = false;
                    if(!firstErrorElement) firstErrorElement = el;
                } else {
                    el.classList.remove('is-invalid');
                    if(field.type === 'checkbox') el.parentElement.style.border = "1px solid #eee";
                }
            });
        });

        if (!isValid && firstErrorElement) {
            firstErrorElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            alert("⚠️ Bitte füllen Sie alle Pflichtfelder aus (rot markiert)!");
            const parentDetails = firstErrorElement.closest('details');
            if(parentDetails) parentDetails.open = true;
        }

        return isValid;
    },

    submitData: async function() {
        if (!this.validate()) return;

        // Uploader starten (nimmt jetzt Files aus app.pendingFiles)
        uploader.initModal(null, null);
    }
};

app.init();