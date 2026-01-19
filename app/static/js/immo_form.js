const uploader = {
    queue: [],
    isUploading: false,
    isPaused: false,
    folderName: "",

    // Initialisiert das Modal und die Queue
    initModal: function(pdfBlob, pdfName) {
        this.queue = [];
        this.isPaused = false;
        this.isUploading = false;
        this.folderName = "";

        // 1. PDF hinzufügen (falls vorhanden)
        if (pdfBlob && pdfName) {
            this.addItemToQueue(new File([pdfBlob], pdfName, {type:"application/pdf"}));
        }

        // 2. Anhänge hinzufügen
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
            totalChunks: Math.ceil(file.size / (1024 * 1024)) // 1MB Chunks
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

            // 1. Ordner Init
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

            // 2. Queue abarbeiten
            for (const item of this.queue) {
                if (item.status === 'done') continue;

                item.status = 'uploading';
                this.renderList();

                const chunkSize = 1024 * 1024; // 1MB

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

            // 3. Abschluss
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

                // UPDATE: Weiterleitung zur Detailseite
                if (finalJson.success) {
                    const btn = document.getElementById('startUploadBtn');
                    btn.className = "btn btn-success";
                    btn.innerText = "✅ Erfolgreich! Weiterleitung...";

                    setTimeout(() => {
                        // LocalStorage aufräumen
                        localStorage.removeItem('project_data');
                        // Weiterleiten zur ID aus der Response
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

const app = {
    data: {}, config: [],
    init: async function() {
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
        document.addEventListener('input', e => {
            if(e.target.id!='global_csc_name')
                this.data[e.target.name] = e.target.type=='checkbox'?e.target.checked:e.target.value;
            this.save();
        });
    },
    save: function() {
        this.data.csc_name = document.getElementById('global_csc_name').value;
        this.data.immo_typ = document.getElementById('immoSelector').value;
        localStorage.setItem('project_data', JSON.stringify(this.data));
    },
    reset: function() {
        localStorage.removeItem('project_data');
        location.reload();
    },

    render: function() {
        const type = document.getElementById('immoSelector').value;
        const container = document.getElementById('form-generator-output');
        container.innerHTML = '';

        this.config.forEach(sec => {
            const details = document.createElement('details');
            if(sec.is_expanded !== false) details.open = true;

            const content = document.createElement('div'); content.style.padding = "20px";
            let hasFields = false;

            sec.content.forEach(field => {
                if(field.types && !field.types.includes(type)) return;
                hasFields = true;

                const wrap = document.createElement('div'); wrap.className = `field-wrapper w-${field.width||'half'}`;
                const val = this.data[field.id] || '';

                if(field.type === 'header') {
                    wrap.className = 'w-full'; wrap.innerHTML = `<h4 style="margin-top:15px; border-bottom:2px solid #ddd; padding-bottom:5px;">${field.label}</h4>`;
                } else if(field.type === 'info' || field.type === 'alert') {
                    wrap.className = 'w-full alert ' + (field.type=='alert'?'alert-danger':'alert-info'); wrap.innerText = field.label;
                } else if(field.type === 'text' || field.type === 'number' || field.type === 'date') {
                    wrap.innerHTML = `<label>${field.label} ${field.tooltip?`(${field.tooltip})`:''}</label><input type="${field.type}" name="${field.id}" value="${val}">`;
                } else if(field.type === 'select') {
                    wrap.innerHTML = `<label>${field.label}</label><select name="${field.id}"><option value="">Wählen...</option>${field.options.map(o=>`<option ${val===o?'selected':''}>${o}</option>`).join('')}</select>`;
                } else if(field.type === 'checkbox') {
                    wrap.innerHTML = `<label style="cursor:pointer; display:flex; align-items:center; gap:10px; background:#f9f9f9; padding:10px; border:1px solid #eee; border-radius:4px;"><input type="checkbox" name="${field.id}" ${val?'checked':''} style="width:20px; height:20px;"> ${field.label}</label>`;
                } else if(field.type === 'textarea') {
                    wrap.innerHTML = `<label>${field.label}</label><textarea name="${field.id}" rows="4">${val}</textarea>`;
                } else if(field.type === 'file') {
                    wrap.innerHTML = `<label>${field.label}</label><input type="file" name="${field.id}" multiple>`;
                }
                content.appendChild(wrap);
            });

            if(hasFields) {
                details.innerHTML = `<summary>${sec.title}</summary>`;
                details.appendChild(content); container.appendChild(details);
            }
        });
    },

    submitData: async function() {
        const cscName = document.getElementById('global_csc_name').value;
        const currentType = document.getElementById('immoSelector').value;
        if (!cscName || !currentType) return alert("Bitte CSC Name und Typ angeben!");

        uploader.initModal(null, null);
    }
};
app.init();