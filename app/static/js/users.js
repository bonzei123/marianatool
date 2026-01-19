// Globale Variable für die aktuell ausgewählte ID
let currentUserId = null;

document.addEventListener('DOMContentLoaded', function() {
    // Modal Instanz vorbereiten
    const editModalEl = document.getElementById('editModal');
    let editModalInstance = null;
    if (editModalEl) {
        editModalInstance = new bootstrap.Modal(editModalEl);
    }

    // URLs aus dem Config-Div lesen (NICHT schneiden, wir ersetzen später die 0)
    const configDiv = document.getElementById('js-config');
    // Wir speichern die Templates mit der "0" drin
    const updateUrlTemplate = configDiv.dataset.updateUrl;
    const deleteUrlTemplate = configDiv.dataset.deleteUrl;
    const resetUrlTemplate = configDiv.dataset.resetUrl;

    // --- FUNKTION: Modal öffnen ---
    window.openEditModal = function(row) {
        // A. Daten aus Tabelle lesen
        currentUserId = row.getAttribute('data-id');
        const name = row.getAttribute('data-username');
        const email = row.getAttribute('data-email');
        const isAdmin = row.getAttribute('data-admin') === 'true';
        const permissionsRaw = row.getAttribute('data-permissions');
        const permissions = permissionsRaw ? permissionsRaw.split(',').map(Number) : [];

        // B. URLs generieren (Die "0" durch echte ID ersetzen)
        // WICHTIG: Das behebt den "...updat1" Fehler
        const realUpdateUrl = updateUrlTemplate.replace('/0/', `/${currentUserId}/`);
        const realDeleteUrl = deleteUrlTemplate.replace('/0/', `/${currentUserId}/`);
        const realResetUrl = resetUrlTemplate.replace('/0/', `/${currentUserId}/`);

        // C. Form Action setzen
        document.getElementById('editForm').action = realUpdateUrl;

        // D. Delete Button und Reset Button mit korrekten URLs versorgen
        // Wir speichern die URL direkt am Button, damit die Funktionen sie nutzen können
        const delBtn = document.getElementById('delBtn');
        delBtn.dataset.url = realDeleteUrl;
        delBtn.onclick = function() { deleteUser(name); };

        const resetBtn = document.querySelector('button[onclick="sendResetMail()"]');
        if(resetBtn) resetBtn.dataset.url = realResetUrl;


        // E. Felder befüllen
        document.getElementById('editTitle').innerText = "Bearbeiten: " + name;
        document.getElementById('editUser').value = name;
        document.getElementById('editEmail').value = email || "";
        document.getElementById('editAdmin').checked = isAdmin;

        // F. Checkboxen setzen
        document.querySelectorAll('.edit-srv').forEach(cb => {
            cb.checked = permissions.includes(parseInt(cb.value));
        });

        // G. Anzeigen
        if (editModalInstance) editModalInstance.show();
    };

    // --- SUCHFUNKTION ---
    window.filterUsers = function() {
        const filter = document.getElementById('userSearch').value.toLowerCase();
        const rows = document.querySelectorAll('#userTable tbody tr');
        rows.forEach(r => {
            const text = r.innerText.toLowerCase();
            r.style.display = text.includes(filter) ? '' : 'none';
        });
    };
});

// --- API ACTIONS ---

async function deleteUser(username) {
    const btn = document.getElementById('delBtn');
    const url = btn.dataset.url; // URL vom Button holen

    if (!url || !confirm(`User "${username}" wirklich löschen?`)) return;

    try {
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = "Lösche...";

        // Da Delete im Backend ein Redirect macht, nutzen wir hier Submit oder Fetch mit Reload
        // Fetch ist sauberer, wenn wir Errors fangen wollen
        const res = await fetch(url, { method: 'POST' });

        if (res.ok || res.redirected) {
            window.location.reload();
        } else {
            alert("Fehler beim Löschen.");
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    } catch (e) {
        alert("Netzwerkfehler: " + e);
        btn.disabled = false;
    }
}

async function sendResetMail() {
    const btn = document.querySelector('button[onclick="sendResetMail()"]');
    const url = btn.dataset.url; // URL vom Button holen

    if (!url || !confirm("Passwort-Reset senden?")) return;

    try {
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = "⏳ Sende...";

        const res = await fetch(url, { method: 'POST' });
        const data = await res.json();

        if (data.success) {
            // Button kurz grün machen
            btn.className = "btn btn-success w-100 fw-bold";
            btn.innerHTML = "✅ Gesendet!";
            setTimeout(() => {
                btn.className = "btn btn-outline-warning w-100 fw-bold";
                btn.innerHTML = originalText;
                btn.disabled = false;
            }, 2000);
        } else {
            alert("❌ Fehler: " + data.message);
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    } catch (e) {
        alert("Netzwerkfehler: " + e);
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}