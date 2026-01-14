const uploader = {
    // ... (Dein Uploader Code von vorhin hier einfügen) ...
    queue: [], isUploading: false, folderName: "", pdfBlob: null,
    initModal: function(blob, name) {
        this.pdfBlob = blob; this.queue = [{file: new File([blob], name, {type:"application/pdf"}), status:'pending', progress:0}];
        document.querySelectorAll('input[type="file"]').forEach(i => { if(i.files.length) Array.from(i.files).forEach(f=>this.queue.push({file:f, status:'pending', progress:0})) });
        document.getElementById('uploadModal').style.display='block';
        this.renderList();
    },
    renderList: function() {
        document.getElementById('uploadList').innerHTML = this.queue.map(i=>`<div>${i.status=='done'?'✅':'⏳'} ${i.file.name}</div>`).join('');
    },
    start: async function() {
        // ... (Hier der Fetch Upload Code aus dem letzten Chat) ...
        // Dummy für Demo:
        alert("Upload Startet (Hier Code einfügen)");
    }
};

const app = {
    data: {}, config: [],
    init: async function() {
        const res = await fetch('/api/config'); this.config = await res.json();
        const raw = localStorage.getItem('immo_data');
        if(raw) { this.data = JSON.parse(raw); document.getElementById('global_csc_name').value = this.data.csc_name||''; if(this.data.immo_typ) { document.getElementById('immoSelector').value = this.data.immo_typ; this.render(); }}
        document.addEventListener('input', e => { if(e.target.id!='global_csc_name') this.data[e.target.name] = e.target.type=='checkbox'?e.target.checked:e.target.value; this.save(); });
    },
    save: function() {
        this.data.csc_name = document.getElementById('global_csc_name').value;
        this.data.immo_typ = document.getElementById('immoSelector').value;
        localStorage.setItem('immo_data', JSON.stringify(this.data));
    },
    reset: function() { localStorage.removeItem('immo_data'); location.reload(); },

    render: function() {
        const type = document.getElementById('immoSelector').value;
        const container = document.getElementById('form-generator-output'); container.innerHTML = '';

        this.config.forEach(sec => {
            const details = document.createElement('details');
            // HIER: Das neue Feature "Standardmäßig ausgeklappt"
            if(sec.is_expanded !== false) details.open = true; // Default true

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

    // --- DEIN ORIGINAL PDF CODE (WIEDERHERGESTELLT) ---
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

                // Header in Section
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

        // Bilder Seiten (Code hier gekürzt, aber du hast ihn in deiner index.html)

        if(isEmptyTemplate) doc.save(`Druckvorlage.pdf`);
        else {
            const blob = doc.output('blob');
            uploader.initModal(blob, `Protokoll_${cscName}.pdf`);
        }
    }
};
app.init();