let config = [];
let currentSimType = 'einzel';

// Helper für wirklich einzigartige IDs
function generateUniqueId(prefix) {
    return prefix + '_' + Date.now() + '_' + Math.floor(Math.random() * 1000);
}

// Elemente
const resizer = document.getElementById('dragMe');
const editorPane = document.getElementById('editorPane');
const previewPane = document.getElementById('previewPane');
const wrapper = document.getElementById('adminWrapper');

async function init() {
    // 1. Status aus LocalStorage laden
    const showPreview = localStorage.getItem('immo_admin_preview') !== 'false'; // Default true
    setPreviewState(showPreview);

    // 2. Config laden
    // ROUTE CHECK: OK (/projects/config existiert im neuen 'projects' Blueprint)
    const res = await fetch('/projects/config');
    config = await res.json();
    renderEditor();
    renderPreview();
    loadBackups();
}

// --- VIEW TOGGLE & STORAGE ---
function togglePreview() {
    const isHidden = previewPane.style.display === 'none';
    setPreviewState(isHidden);
}

function setPreviewState(show) {
    if (show) {
        previewPane.style.display = 'block';
        resizer.style.display = 'flex';
        editorPane.style.flex = '1';
        localStorage.setItem('immo_admin_preview', 'true');
    } else {
        previewPane.style.display = 'none';
        resizer.style.display = 'none';
        editorPane.style.flex = '1';
        localStorage.setItem('immo_admin_preview', 'false');
    }
}

// --- RESIZER LOGIC ---
let isResizing = false;
resizer.addEventListener('mousedown', e => { isResizing = true; resizer.classList.add('resizing'); document.body.style.cursor = 'col-resize'; });
document.addEventListener('mousemove', e => {
    if (!isResizing) return;
    const containerRect = wrapper.getBoundingClientRect();
    let newW = e.clientX - containerRect.left;
    if (newW < 300) newW = 300;
    if (newW > containerRect.width - 320) newW = containerRect.width - 320;
    editorPane.style.flex = `0 0 ${newW}px`;
    previewPane.style.width = 'auto'; previewPane.style.flex = '1';
});
document.addEventListener('mouseup', e => { if(isResizing) { isResizing = false; resizer.classList.remove('resizing'); document.body.style.cursor = 'default'; } });

// --- RENDER EDITOR ---
function renderEditor() {
    const con = document.getElementById('editorContainer'); con.innerHTML = '';
    config.forEach(sec => {
        const secDiv = document.createElement('div'); secDiv.className = 'section-card';
        if(!sec.id) sec.id = generateUniqueId('s');

        secDiv.innerHTML = `
                <div class="section-header">
                    <span class="drag-handle">☰</span>
                    <div style="flex:1"><input class="form-control fw-bold sec-title" value="${sec.title}" oninput="sync()"></div>
                    <div class="form-check form-switch ms-4"><input class="form-check-input sec-expand" type="checkbox" ${sec.is_expanded!==false?'checked':''} onchange="sync()"><label class="small text-muted">Ausgeklappt</label></div>
                    <button class="btn btn-sm text-danger ms-3" onclick="removeEl(this)">🗑️</button>
                    <input type="hidden" class="sec-id" value="${sec.id}">
                </div>
                <div class="q-list"></div>
                <div class="p-2"><button class="btn btn-sm btn-light w-100 border" onclick="addQ(this)">+ Frage hinzufügen</button></div>
            `;
        con.appendChild(secDiv);
        const list = secDiv.querySelector('.q-list');
        sec.content.forEach(q => renderQ(list, q));
        new Sortable(list, { group:'q', handle:'.drag-handle', animation:150, onEnd:sync });
    });
    new Sortable(con, { handle:'.section-header', animation:150, onEnd:sync });
}

function renderQ(list, q) {
    const div = document.createElement('div');
    div.className = 'question-card';

    // Farbe setzen
    if (['info', 'alert', 'header'].includes(q.type)) {
        div.classList.add('type-' + q.type);
    }

    const types = q.types || ['einzel','cluster','ausgabe'];
    if(!q.id) q.id = generateUniqueId('q');

    div.innerHTML = `
            <div class="grid-row">
                <div class="drag-handle">::</div>
                <div><label class="input-label">Label</label><input class="form-control-sm q-label" value="${q.label}" oninput="sync()"></div>
                <div><label class="input-label">Typ</label><select class="form-select form-select-sm q-type" onchange="toggleOpt(this); sync()"><option value="text" ${q.type=='text'?'selected':''}>Text</option><option value="textarea" ${q.type=='textarea'?'selected':''}>Textfeld</option><option value="number" ${q.type=='number'?'selected':''}>Zahl</option><option value="select" ${q.type=='select'?'selected':''}>Dropdown</option><option value="checkbox" ${q.type=='checkbox'?'selected':''}>Checkbox</option><option value="file" ${q.type=='file'?'selected':''}>Datei</option><option value="header" ${q.type=='header'?'selected':''}>ÜBERSCHRIFT</option><option value="info" ${q.type=='info'?'selected':''}>Info</option><option value="alert" ${q.type=='alert'?'selected':''}>Warnung</option></select></div>
                <div><label class="input-label">Breite</label><select class="form-select form-select-sm q-width" onchange="sync()"><option value="half" ${q.width!='full'?'selected':''}>Halb</option><option value="full" ${q.width=='full'?'selected':''}>Voll</option></select></div>
                <div><label class="input-label">Sichtbar</label><div><span class="badge-check ${types.includes('einzel')?'active':''}" onclick="tog(this)">Einzel</span> <span class="badge-check ${types.includes('cluster')?'active':''}" onclick="tog(this)">Cluster</span> <span class="badge-check ${types.includes('ausgabe')?'active':''}" onclick="tog(this)">Ausgabe</span></div></div>
                <div><button class="btn-del" onclick="removeEl(this)">X</button></div>
            </div>
            <div class="d-flex gap-2 align-items-center">
                <input class="form-control-sm sys-id q-id" style="width:100px" value="${q.id}" placeholder="ID">
                <input class="form-control-sm q-tooltip" style="flex:1" value="${q.tooltip||''}" placeholder="Tooltip..." oninput="sync()">
                <input class="form-control-sm q-opts" style="flex:1; display:${q.type=='select'?'block':'none'}" value="${(q.options||[]).join(',')}" placeholder="Optionen (Komma)" oninput="sync()">
            </div>
        `;
    list.appendChild(div);
}

function tog(el) { el.classList.toggle('active'); sync(); }

function toggleOpt(sel) {
    const card = sel.closest('.question-card');
    card.querySelector('.q-opts').style.display = sel.value==='select'?'block':'none';
    card.classList.remove('type-info', 'type-alert', 'type-header');
    if (['info', 'alert', 'header'].includes(sel.value)) {
        card.classList.add('type-' + sel.value);
    }
}

function removeEl(btn) { btn.closest(btn.classList.contains('btn-del')?'.question-card':'.section-card').remove(); sync(); }
function addSection() { config.push({id: generateUniqueId('s'), title:'Neu', content:[]}); renderEditor(); sync(); }
function addQ(btn) { renderQ(btn.parentElement.previousElementSibling, {id: generateUniqueId('q'), label:'', type:'text'}); sync(); }

function scrape() {
    const data = [];
    document.querySelectorAll('.section-card').forEach(s => {
        const qs = [];
        s.querySelectorAll('.question-card').forEach(q => {
            const types = [];
            const badges = q.querySelectorAll('.badge-check');
            if(badges[0].classList.contains('active')) types.push('einzel');
            if(badges[1].classList.contains('active')) types.push('cluster');
            if(badges[2].classList.contains('active')) types.push('ausgabe');

            let qId = q.querySelector('.q-id').value;
            if(!qId) qId = generateUniqueId('q_scrape');

            qs.push({
                id: qId, label: q.querySelector('.q-label').value,
                type: q.querySelector('.q-type').value, width: q.querySelector('.q-width').value,
                tooltip: q.querySelector('.q-tooltip').value,
                options: q.querySelector('.q-opts').value.split(',').filter(x=>x), types: types
            });
        });
        let sId = s.querySelector('.sec-id').value;
        if(!sId) sId = generateUniqueId('s_scrape');

        data.push({ id: sId, title: s.querySelector('.sec-title').value, is_expanded: s.querySelector('.sec-expand').checked, content: qs });
    });
    return data;
}

async function saveConfig() {
    try {
        // UPDATE: Route auf /formbuilder/save
        const res = await fetch('/formbuilder/save', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(scrape()) });
        const result = await res.json();
        if(result.success) { alert("✅ Gespeichert!"); loadBackups(); }
        else { alert("❌ Fehler: " + result.error); }
    } catch(e) { alert("Netzwerk Fehler: " + e); }
}

async function loadBackups() {
    try {
        // UPDATE: Route auf /formbuilder/backups
        const res = await fetch('/formbuilder/backups');
        if (!res.ok) throw new Error("Fehler beim Laden");

        const list = await res.json();
        const sel = document.getElementById('backupLoader');
        sel.innerHTML = '<option value="">Wähle Sicherung...</option>';
        list.forEach(b => {
            const opt = document.createElement('option');
            opt.value = JSON.stringify(b.data);
            opt.innerText = b.name;
            sel.appendChild(opt);
        });
    } catch(e) { console.error("Backup Load Error", e); }
}

function loadBackup(json) { if(json && confirm("Backup laden?")) { config = JSON.parse(json); renderEditor(); sync(); } }

function renderPreview() {
    const p = document.getElementById('previewContent'); p.innerHTML = '';
    const data = scrape();
    data.forEach(s => {
        const openAttr = s.is_expanded ? 'open' : '';
        let html = `<details ${openAttr}><summary>${s.title}</summary><div class="p-content">`;
        let hasVisible = false;
        s.content.forEach(q => {
            if(q.types && !q.types.includes(currentSimType)) return;
            hasVisible = true;
            const wClass = q.width === 'full' ? 'w-full' : 'w-half';
            let fieldHtml = '';
            if(q.type === 'header') fieldHtml = `<div class="w-full" style="margin-top:15px; border-bottom:2px solid #ddd; padding-bottom:5px;"><h4 style="color:#19835A; margin:0;">${q.label}</h4></div>`;
            else if (q.type === 'info') fieldHtml = `<div class="w-full alert alert-info">${q.label}</div>`;
            else if (q.type === 'alert') fieldHtml = `<div class="w-full alert alert-danger">${q.label}</div>`;
            else {
                let input = `<input type="text" disabled>`;
                if(q.type === 'select') input = `<select disabled><option>Wählen...</option></select>`;
                if(q.type === 'textarea') input = `<textarea disabled rows="3"></textarea>`;
                if(q.type === 'checkbox') input = `<div style="padding:10px; border:1px solid #ddd; background:#f9f9f9; border-radius:5px;"><input type="checkbox" disabled style="width:auto; margin-right:10px;"> ${q.label}</div>`;
                if(q.type === 'file') input = `<input type="file" disabled>`;
                if(q.type !== 'checkbox') fieldHtml = `<div class="field-wrapper ${wClass}"><label>${q.label} ${q.tooltip?`<span style="color:#999; font-size:0.8em">(${q.tooltip})</span>`:''}</label>${input}</div>`;
                else fieldHtml = `<div class="field-wrapper ${wClass}">${input}</div>`;
            }
            html += fieldHtml;
        });
        html += `</div></details>`;
        if(hasVisible) p.innerHTML += html;
    });
}
function sync() { renderPreview(); }

init();