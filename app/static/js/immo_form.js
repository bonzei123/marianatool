const uploader = {
    queue: [],
    isUploading: false,
    isPaused: false,
    folderName: "",

    // Initialisiert das Modal und die Queue
    initModal: function(blob, name) {
        this.queue = [];
        this.isPaused = false;
        this.isUploading = false;

        // 1. PDF hinzufügen
        this.addItemToQueue(new File([blob], name, {type:"application/pdf"}));

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

        if (this.isUploading) {
            btnStart.style.display = 'none';
            btnPause.style.display = 'inline-block';
            btnPause.innerText = this.isPaused ? "▶️ Fortsetzen" : "⏸️ Pause";
            btnPause.className = this.isPaused ? "btn btn-warning" : "btn btn-secondary";
        } else {
            const hasPending = this.queue.some(i => i.status !== 'done');
            btnStart.style.display = hasPending ? 'inline-block' : 'none';
            btnStart.innerText = this.queue.some(i => i.uploadedChunks > 0) ? "Fortsetzen" : "Starten";
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
            // 1. Ordner Init
            if (!this.folderName) {
                const baseName = this.queue[0].file.name.replace('.pdf', '');
                // ROUTE CHECK: OK
                const initRes = await fetch('/projects/upload/init', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ folder_name: baseName + "_" + Date.now() })
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
                        // ROUTE CHECK: OK
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
            if (this.queue.every(i => i.status === 'done')) {
                const cscName = document.getElementById('global_csc_name').value;
                const immoType = document.getElementById('immoSelector').value;

                // WICHTIG: UPDATE URL auf /submit
                const finalRes = await fetch('/projects/submit', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        filename: this.queue[0].file.name,
                        folder: this.folderName,
                        csc_name: cscName,
                        immo_type: immoType,
                        form_data: app.data
                    })
                });

                const finalJson = await finalRes.json();
                if (finalJson.success) {
                    alert("✅ Upload erfolgreich!");
                    document.getElementById('uploadModal').style.display = 'none';
                    app.reset();
                } else {
                    throw new Error(finalJson.error);
                }
            }

        } catch (e) {
            alert("Fehler: " + e.message);
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
        // ROUTE CHECK: OK
        const res = await fetch('/projects/config');
        this.config = await res.json();

        // Key umbenannt auf project_data
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

    generatePDF: async function(isEmptyTemplate) {
        const cscName = document.getElementById('global_csc_name').value;
        const currentType = document.getElementById('immoSelector').value;

        if (!isEmptyTemplate) {
            if (!cscName) return alert("Bitte CSC Name eingeben!");
            if (!currentType) return alert("Bitte Typ wählen!");
        }

        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();

        // Header Grün
        doc.setFillColor(39, 174, 96); doc.rect(0, 0, 210, 20, 'F');
        doc.setTextColor(255); doc.setFontSize(16); doc.setFont("helvetica", "bold");
        doc.text(isEmptyTemplate ? "DRUCKVORLAGE" : "PROTOKOLL: " + currentType.toUpperCase(), 105, 13, null, null, "center");

        doc.setTextColor(0); doc.setFontSize(10); doc.setFont("helvetica", "normal");
        if(!isEmptyTemplate) doc.text(`CSC: ${cscName} | ${new Date().toLocaleDateString()}`, 15, 30);

        let y = 40;
        const checkPage = () => { if(y > 280) { doc.addPage(); y=20; } };

        for (const section of this.config) {
            checkPage(); y += 5;
            // Sektions-Balken Grau
            doc.setFillColor(230); doc.rect(15, y-5, 180, 7, 'F');
            doc.setFont("helvetica", "bold"); doc.text(section.title, 17, y); y += 10;
            doc.setFont("helvetica", "normal");

            for (const field of section.content) {
                if (field.types && !field.types.includes(currentType)) continue;

                if (field.type === 'header') {
                    checkPage(); y+=3; doc.setFont("helvetica", "bold");
                    doc.text(field.label.toUpperCase(), 15, y);
                    doc.setTextColor(0); doc.setFont("helvetica", "normal"); y+=6; continue;
                }
                if (['alert','info','file'].includes(field.type)) continue;

                checkPage();
                const col1Width = 65; const col2Width = 110; const startX1 = 15; const startX2 = 85;

                doc.setFont("helvetica", "bold");
                const labelLines = doc.splitTextToSize(field.label, col1Width);
                doc.text(labelLines, startX1, y);

                doc.setFont("helvetica", "normal");
                let valText = "";
                if (isEmptyTemplate) {
                    if (field.type === 'select') valText = "[  ] " + field.options.join("  [  ] ");
                    else if (field.type === 'checkbox') valText = "[  ] Ja    [  ] Nein";
                    else valText = "__________________________________";
                } else {
                    let raw = this.data[field.id];
                    if (raw === true) valText = "[x] Ja"; else if (raw === false) valText = "[ ] Nein"; else valText = raw || "-";
                }

                const valLines = doc.splitTextToSize(String(valText), col2Width);
                const linesCount = Math.max(labelLines.length, valLines.length);
                const rowHeight = linesCount * 5;

                if (y + rowHeight > 280) { doc.addPage(); y=20; doc.text(labelLines, startX1, y); }
                doc.text(valLines, startX2, y);
                y += rowHeight + 6;
            }
        }

        if(isEmptyTemplate) doc.save(`Druckvorlage.pdf`);
        else {
            const blob = doc.output('blob');
            // Name für das Backend
            uploader.initModal(blob, `Protokoll_${cscName}.pdf`);
        }
    }
};
app.init();