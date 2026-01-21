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

        if (pdfBlob && pdfName) {
            this.addItemToQueue(new File([pdfBlob], pdfName, {type:"application/pdf"}));
        }

        document.querySelectorAll('input[type="file"]').forEach(i => {
            if(i.files.length) {
                Array.from(i.files).forEach(f => this.addItemToQueue(f));
            }
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

function getColClass(q) {
    // ... (Code exakt wie oben) ...
    const map = { 'full': 12, 'half': 6, 'third': 4 };
    let desk = map[q.width] || 6;
    let tab = (q.width_tablet === 'default' || !q.width_tablet) ? desk : (map[q.width_tablet] || desk);
    let mob = (q.width_mobile === 'default' || !q.width_mobile) ? desk : (map[q.width_mobile] || desk);
    let classes = `col-${mob}`;
    if (tab !== mob) classes += ` col-md-${tab}`;
    if (desk !== tab) classes += ` col-lg-${desk}`;
    return classes;
}

const app = {
    data: {}, config: [],

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
                this.render();
            }
        }

        // Live-Saving bei Eingabe
        document.addEventListener('input', e => {
            if(e.target.id != 'global_csc_name') {
                this.data[e.target.name] = e.target.type === 'checkbox' ? e.target.checked : e.target.value;

                // NEU: Wenn ein Feld ausgefüllt wird, Fehler-Klasse entfernen
                if(e.target.classList.contains('is-invalid') && e.target.value.trim() !== '') {
                    e.target.classList.remove('is-invalid');
                }
            }
            this.save();
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

    render: function() {
        const type = document.getElementById('immoSelector').value;
        const container = document.getElementById('form-generator-output');
        container.innerHTML = '';

        this.config.forEach(sec => {
            const details = document.createElement('details');
            if(sec.is_expanded !== false) details.open = true;

            // UPDATE: Nutze Bootstrap Grid Container (row g-3)
            const content = document.createElement('div');
            content.className = "p-3 row g-3"; // <--- WICHTIG: row g-3

            let hasFields = false;

            sec.content.forEach(field => {
                if(field.types && !field.types.includes(type)) return;
                hasFields = true;

                const wrap = document.createElement('div');

                // UPDATE: Hole die berechneten Klassen
                const colClasses = getColClass(field);

                // Sonderfall: Header/Info/Alert sind immer volle Breite
                if(['header', 'info', 'alert'].includes(field.type)) {
                    wrap.className = 'col-12';
                } else {
                    wrap.className = colClasses;
                }

                const val = this.data[field.id] || '';
                const reqMark = field.is_required ? ' <span class="text-danger fw-bold">*</span>' : '';

                // HINWEIS: Ich habe hier auch gleich 'form-control' Klassen für Bootstrap Styling ergänzt
                if(field.type === 'header') {
                    wrap.innerHTML = `<h4 style="margin-top:15px; border-bottom:2px solid #ddd; padding-bottom:5px;">${field.label}</h4>`;

                } else if(field.type === 'info' || field.type === 'alert') {
                    wrap.className += ' alert ' + (field.type=='alert'?'alert-danger':'alert-info');
                    wrap.innerText = field.label;

                } else if(field.type === 'text' || field.type === 'number' || field.type === 'date') {
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

                } else if(field.type === 'file') {
                    wrap.innerHTML = `<label class="form-label fw-bold">${field.label}</label><input type="file" name="${field.id}" multiple class="form-control">`;
                }
                content.appendChild(wrap);
            });

            if(hasFields) {
                details.innerHTML = `<summary>${sec.title}</summary>`;
                details.appendChild(content);
                container.appendChild(details);
            }
        });
    },

    // NEU: Validierungsfunktion
    validate: function() {
        const cscName = document.getElementById('global_csc_name');
        const currentType = document.getElementById('immoSelector').value;
        let isValid = true;
        let firstErrorElement = null;

        // 1. Basis-Check
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

        // 2. Felder Check
        this.config.forEach(sec => {
            sec.content.forEach(field => {
                // Nur Felder prüfen, die sichtbar sind (Typ-Filter) UND Required sind
                if(field.types && !field.types.includes(currentType)) return;
                if(!field.is_required) return;

                const el = document.querySelector(`[name="${field.id}"]`);
                if(!el) return;

                // Wert prüfen
                let isFieldValid = true;

                if (field.type === 'checkbox') {
                    // Bei Checkbox (z.B. "Ich stimme zu") muss sie checked sein
                    if (!el.checked) isFieldValid = false;
                } else {
                    // Text, Select, Number etc.
                    if (!el.value || el.value.trim() === "") isFieldValid = false;
                }

                if (!isFieldValid) {
                    el.classList.add('is-invalid'); // Nutzt Bootstrap Klasse (roter Rahmen)

                    // Bei Checkboxen den Container färben (optional)
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
            // Zum ersten Fehler scrollen
            firstErrorElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            alert("⚠️ Bitte füllen Sie alle Pflichtfelder aus (rot markiert)!");
            // Details öffnen, falls Fehler in zugeklapptem Bereich
            const parentDetails = firstErrorElement.closest('details');
            if(parentDetails) parentDetails.open = true;
        }

        return isValid;
    },

    submitData: async function() {
        // Erst Validieren
        if (!this.validate()) return;

        // Dann Upload
        uploader.initModal(null, null);
    }
};
app.init();