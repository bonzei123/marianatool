let config = [];
let currentSimType = 'einzel';

// NEU: Merkt sich rein optisch, welche Sektionen im EDITOR (links) zugeklappt sind
const editorCollapsedState = {};

// Helper für wirklich einzigartige IDs
function generateUniqueId(prefix) {
    return prefix + '_' + Date.now() + '_' + Math.floor(Math.random() * 1000);
}

// Elemente
const resizer = document.getElementById('dragMe');
const editorPane = document.getElementById('editorPane');
const previewPane = document.getElementById('previewPane');
const wrapper = document.getElementById('adminWrapper');

const configEl = document.getElementById('builder-config');
const LOAD_URL = configEl ? configEl.dataset.loadUrl : '/projects/config'; // Fallback
const SAVE_URL = configEl ? configEl.dataset.saveUrl : '/formbuilder/save';
const PREVIEW_KEY = configEl ? configEl.dataset.previewStorageKey : 'immo_admin_preview';

async function init() {
    const showPreview = localStorage.getItem(PREVIEW_KEY) !== 'false';
    setPreviewState(showPreview);

    try {
        const res = await fetch(LOAD_URL);
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        config = await res.json();
        renderEditor();
        renderPreview();
    } catch (e) {
        console.error("Fehler beim Laden der Config:", e);
        alert("Fehler beim Laden der Konfiguration. Siehe Konsole.");
    }
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
        localStorage.setItem(PREVIEW_KEY, 'true');
    } else {
        previewPane.style.display = 'none';
        resizer.style.display = 'none';
        editorPane.style.flex = '1';
        localStorage.setItem(PREVIEW_KEY, 'false');
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

// --- EDITOR SECTION TOGGLE ---
function toggleEditorSection(secId) {
    editorCollapsedState[secId] = !editorCollapsedState[secId];
    renderEditor();
}

// --- RENDER EDITOR ---
function renderEditor() {
    const con = document.getElementById('editorContainer');
    const scrollTop = editorPane.scrollTop;
    con.innerHTML = '';

    config.forEach(sec => {
        const secDiv = document.createElement('div'); secDiv.className = 'section-card';
        if(!sec.id) sec.id = generateUniqueId('s');

        const isMinimized = editorCollapsedState[sec.id] === true;
        if(isMinimized) secDiv.classList.add('minimized');

        const toggleIcon = isMinimized ? '▶' : '▼';

        secDiv.innerHTML = `
                <div class="section-header">
                    <span class="drag-handle">☰</span>
                    <button class="btn-collapse me-2" onclick="toggleEditorSection('${sec.id}')" title="Im Editor einklappen">${toggleIcon}</button>
                    <div style="flex:1"><input class="form-control fw-bold sec-title" value="${sec.title}" oninput="sync()"></div>
                    <div class="form-check form-switch ms-4" title="Standardmäßig ausgeklappt beim User?">
                        <input class="form-check-input sec-expand" type="checkbox" ${sec.is_expanded!==false?'checked':''} onchange="sync()">
                        <label class="small text-muted">Auto-Open</label>
                    </div>
                    <button class="btn btn-sm text-danger ms-3" onclick="removeEl(this)">🗑️</button>
                    <input type="hidden" class="sec-id" value="${sec.id}">
                </div>
                
                <div class="q-list"></div>
                <div class="p-2 card-footer-actions"><button class="btn btn-sm btn-light w-100 border" onclick="addQ(this)">+ Frage hinzufügen</button></div>
            `;
        con.appendChild(secDiv);

        const list = secDiv.querySelector('.q-list');
        sec.content.forEach(q => renderQ(list, q));

        new Sortable(list, { group:'q', handle:'.drag-handle', animation:150, onEnd:sync });
    });

    new Sortable(con, { handle:'.section-header', animation:150, onEnd:sync });
    editorPane.scrollTop = scrollTop;
}

function renderQ(list, q) {
    const div = document.createElement('div');
    div.className = 'question-card';

    if (['info', 'alert', 'header'].includes(q.type)) {
        div.classList.add('type-' + q.type);
    }

    const types = q.types || ['einzel','cluster','ausgabe'];
    if(!q.id) q.id = generateUniqueId('q');

    const isRequired = q.is_required ? 'checked' : '';
    const isMetadata = q.is_metadata ? 'checked' : '';
    const isPrint = (q.is_print !== false) ? 'checked' : '';

    // Values sicherstellen
    const wDesk = q.width || 'half';
    const wTab = q.width_tablet || 'default';
    const wMob = q.width_mobile || 'default';

    div.innerHTML = `
            <div class="grid-row" style="grid-template-columns: 20px 2fr 1.5fr 1.2fr 1.2fr 1.2fr 1fr 30px; gap: 5px;">
                <div class="drag-handle">::</div>
                
                <div>
                    <label class="input-label">Label</label>
                    <input class="form-control-sm q-label" value="${q.label}" oninput="sync()">
                </div>
                
                <div>
                    <label class="input-label">Typ</label>
                    <select class="form-select form-select-sm q-type" onchange="toggleOpt(this); sync()">
                        <option value="text" ${q.type=='text'?'selected':''}>Text</option>
                        <option value="textarea" ${q.type=='textarea'?'selected':''}>Textfeld</option>
                        <option value="number" ${q.type=='number'?'selected':''}>Zahl</option>
                        <option value="select" ${q.type=='select'?'selected':''}>Dropdown</option>
                        <option value="checkbox" ${q.type=='checkbox'?'selected':''}>Checkbox</option>
                        <option value="file" ${q.type=='file'?'selected':''}>Datei</option>
                        <option value="date" ${q.type=='date'?'selected':''}>Datum</option>
                        <option value="header" ${q.type=='header'?'selected':''}>ÜBERSCHRIFT</option>
                        <option value="info" ${q.type=='info'?'selected':''}>Info</option>
                        <option value="alert" ${q.type=='alert'?'selected':''}>Warnung</option>
                    </select>
                </div>

                <div>
                    <label class="input-label"><i class="bi bi-display"></i> Desk</label>
                    <select class="form-select form-select-sm q-width" onchange="sync()">
                        <option value="full" ${wDesk=='full'?'selected':''}>Voll</option>
                        <option value="half" ${wDesk=='half'?'selected':''}>Halb</option>
                        <option value="third" ${wDesk=='third'?'selected':''}>Drittel</option>
                    </select>
                </div>

                <div>
                    <label class="input-label"><i class="bi bi-tablet"></i> Tab</label>
                    <select class="form-select form-select-sm q-width-tab" onchange="sync()" style="background:#f8f9fa">
                        <option value="default" ${wTab=='default'?'selected':''}>Default</option>
                        <option value="full" ${wTab=='full'?'selected':''}>Voll</option>
                        <option value="half" ${wTab=='half'?'selected':''}>Halb</option>
                        <option value="third" ${wTab=='third'?'selected':''}>Drittel</option>
                    </select>
                </div>

                <div>
                    <label class="input-label"><i class="bi bi-phone"></i> Mob</label>
                    <select class="form-select form-select-sm q-width-mob" onchange="sync()" style="background:#f8f9fa">
                        <option value="default" ${wMob=='default'?'selected':''}>Default</option>
                        <option value="full" ${wMob=='full'?'selected':''}>Voll</option>
                        <option value="half" ${wMob=='half'?'selected':''}>Halb</option>
                        <option value="third" ${wMob=='third'?'selected':''}>Drittel</option>
                    </select>
                </div>

                <div>
                    <label class="input-label">Sichtbar</label>
                    <div style="line-height:1.1">
                        <span class="badge-check ${types.includes('einzel')?'active':''}" onclick="tog(this)">E</span> 
                        <span class="badge-check ${types.includes('cluster')?'active':''}" onclick="tog(this)">C</span> 
                        <span class="badge-check ${types.includes('ausgabe')?'active':''}" onclick="tog(this)">A</span>
                    </div>
                </div>
                
                <div><button class="btn-del" onclick="removeEl(this)">X</button></div>
            </div>
            
            <div class="d-flex gap-3 align-items-center mb-2 px-1">
                 <div class="form-check form-switch">
                    <input class="form-check-input q-required" type="checkbox" id="req_${q.id}" ${isRequired} onchange="sync()">
                    <label class="form-check-label small" for="req_${q.id}">Pflichtfeld (*)</label>
                </div>
                <div class="form-check form-switch">
                    <input class="form-check-input q-metadata" type="checkbox" id="meta_${q.id}" ${isMetadata} onchange="sync()">
                    <label class="form-check-label small" for="meta_${q.id}">Info-Tab</label>
                </div>
                <div class="form-check form-switch">
                    <input class="form-check-input q-print" type="checkbox" id="prn_${q.id}" ${isPrint} onchange="sync()">
                    <label class="form-check-label small" for="prn_${q.id}">Drucken</label>
                </div>
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

function addQ(btn) { renderQ(btn.parentElement.previousElementSibling, {id: generateUniqueId('q'), label:'', type:'text', is_print: true}); sync(); }

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
            // Falls ID ein Client-Side String ist, übergeben wir sie so,
            // Backend entscheidet (beim Onboarding ignorieren wir sie meist beim Re-Create)
            if(!qId) qId = generateUniqueId('q_scrape');

            qs.push({
                id: qId,
                label: q.querySelector('.q-label').value,
                type: q.querySelector('.q-type').value,
                // NEU: Alle 3 Breiten auslesen
                width: q.querySelector('.q-width').value,
                width_tablet: q.querySelector('.q-width-tab').value,
                width_mobile: q.querySelector('.q-width-mob').value,

                tooltip: q.querySelector('.q-tooltip').value,
                is_required: q.querySelector('.q-required').checked,
                is_metadata: q.querySelector('.q-metadata').checked,
                is_print: q.querySelector('.q-print').checked,
                options: q.querySelector('.q-opts').value.split(',').filter(x=>x),
                types: types
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
        const res = await fetch(SAVE_URL, {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify(scrape())
        });
        const result = await res.json();
        if(result.success) {
            alert("✅ Gespeichert!");
            // Optional: Seite neu laden, um echte DB-IDs zu bekommen
            // window.location.reload();
        }
        else { alert("❌ Fehler: " + (result.error || "Unbekannter Fehler")); }
    } catch(e) { alert("Netzwerk Fehler: " + e); }
}

async function loadBackups() {
    try {
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

// --- HELPER FÜR RESPONSIVE KLASSEN ---
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

function renderPreview() {
    const p = document.getElementById('previewContent');
    const openStates = {};
    const existingDetails = p.querySelectorAll('details');
    existingDetails.forEach((el, index) => {
        openStates[index] = el.open;
    });

    p.innerHTML = '';
    const data = scrape();

    data.forEach((s, index) => {
        let isOpen = s.is_expanded;
        if (openStates[index] !== undefined) {
            isOpen = openStates[index];
        }

        const openAttr = isOpen ? 'open' : '';
        let html = `<details ${openAttr}><summary>${s.title}</summary><div class="p-content row g-3">`;
        let hasVisible = false;

        s.content.forEach(q => {
            if(q.types && !q.types.includes(currentSimType)) return;
            hasVisible = true;

            const colClass = getColClass(q);
            const reqMark = q.is_required ? ' <span style="color:red; font-weight:bold">*</span>' : '';

            let fieldHtml = '';

            if(q.type === 'header') fieldHtml = `<div class="col-12" style="margin-top:15px; border-bottom:2px solid #ddd; padding-bottom:5px;"><h4 style="color:#19835A; margin:0;">${q.label}</h4></div>`;
            else if (q.type === 'info') fieldHtml = `<div class="col-12 alert alert-info">${q.label}</div>`;
            else if (q.type === 'alert') fieldHtml = `<div class="col-12 alert alert-danger">${q.label}</div>`;
            else {
                let input = `<input type="text" class="form-control" disabled>`;
                if(q.type === 'select') input = `<select class="form-select" disabled><option>Wählen...</option></select>`;
                if(q.type === 'textarea') input = `<textarea class="form-control" disabled rows="3"></textarea>`;
                if(q.type === 'checkbox') input = `<div style="padding:10px; border:1px solid #ddd; background:#f9f9f9; border-radius:5px;"><input type="checkbox" disabled style="width:auto; margin-right:10px;"> ${q.label}${reqMark}</div>`;
                if(q.type === 'file') input = `<input type="file" class="form-control" disabled>`;
                if(q.type === 'date') input = `<input type="date" class="form-control" disabled>`;

                if(q.type !== 'checkbox') fieldHtml = `<div class="${colClass}"><label class="form-label fw-bold">${q.label} ${q.tooltip?`<span style="color:#999; font-size:0.8em">(${q.tooltip})</span>`:''}${reqMark}</label>${input}</div>`;
                else fieldHtml = `<div class="${colClass}">${input}</div>`;
            }
            html += fieldHtml;
        });
        html += `</div></details>`;
        if(hasVisible) p.innerHTML += html;
    });
}

function sync() { renderPreview(); }

init();