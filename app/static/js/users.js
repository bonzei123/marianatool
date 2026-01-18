// Globale Variablen
let currentUserId = null;
let resetBaseUrl = "";
let deleteBaseUrl = ""; // Global verfügbar machen

document.addEventListener('DOMContentLoaded', function() {
    // 1. Basis URLs aus dem HTML Config-Div lesen
    const configDiv = document.getElementById('js-config');
    const updateBaseUrl = configDiv.dataset.updateUrl.slice(0, -1);

    // Slice entfernt die "0" am Ende des Platzhalters
    deleteBaseUrl = configDiv.dataset.deleteUrl.slice(0, -1);
    resetBaseUrl = configDiv.dataset.resetUrl.slice(0, -1);

    // 2. Modal initialisieren
    const editModalEl = document.getElementById('editModal');
    let editModalInstance = null;
    if (editModalEl) {
        editModalInstance = new bootstrap.Modal(editModalEl);
    }

    // 3. Funktion: Modal öffnen und Daten befüllen
    window.openEditModal = function(row) {
        // A. Daten aus Data-Attributen der Tabelle lesen
        currentUserId = row.getAttribute('data-id');
        const name = row.getAttribute('data-username');
        const email = row.getAttribute('data-email');
        const isAdmin = row.getAttribute('data-admin') === 'true';
        const permissionsRaw = row.getAttribute('data-permissions');
        const permissions = permissionsRaw ? permissionsRaw.split(',').map(Number) : [];

        // B. Formular Action URL für Update setzen (POST an /user/manage/ID/update)
        document.getElementById('editForm').action = updateBaseUrl + currentUserId;

        // C. Delete Button konfigurieren (Kein href mehr, sondern OnClick Event)
        const delBtn = document.getElementById('delBtn');
        delBtn.onclick = function() {
            deleteUser(name); // Ruft die neue async Funktion auf
        };

        // D. Felder im Modal befüllen
        document.getElementById('editTitle').innerText = "Bearbeiten: " + name;
        document.getElementById('editUser').value = name;
        document.getElementById('editEmail').value = email || "";
        document.getElementById('editAdmin').checked = isAdmin;

        // E. Checkboxen für Permissions setzen
        document.querySelectorAll('.edit-srv').forEach(cb => {
            cb.checked = permissions.includes(parseInt(cb.value));
        });

        // F. Modal anzeigen
        if (editModalInstance) editModalInstance.show();
    };

    // 4. Suchfunktion für die Tabelle
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

// NEU: User löschen via POST Request
async function deleteUser(username) {
    if (!currentUserId) return;
    if (!confirm(`Möchtest du den User "${username}" wirklich unwiderruflich löschen?`)) return;

    try {
        // UI Feedback
        const delBtn = document.getElementById('delBtn');
        const originalText = delBtn.innerHTML;
        delBtn.disabled = true;
        delBtn.innerHTML = "Lösche...";

        // POST Request senden
        const res = await fetch(deleteBaseUrl + currentUserId, { method: 'POST' });

        // Da der Server bei Erfolg einen Redirect macht (oder Flash Messages),
        // reicht es oft, die Seite neu zu laden, um das Ergebnis zu sehen.
        if (res.ok) {
            window.location.reload(); // Seite neu laden um Tabelle zu aktualisieren
        } else {
            alert("Fehler beim Löschen. Server antwortete mit Status " + res.status);
            delBtn.disabled = false;
            delBtn.innerHTML = originalText;
        }
    } catch (e) {
        alert("Netzwerkfehler: " + e);
        document.getElementById('delBtn').disabled = false;
    }
}

// Reset Mail senden
async function sendResetMail() {
    if (!currentUserId || !confirm("Einen Reset-Link an die E-Mail Adresse dieses Users senden?")) return;

    try {
        const btn = document.querySelector('button[onclick="sendResetMail()"]');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = "⏳ Sende...";

        const res = await fetch(resetBaseUrl + currentUserId, { method: 'POST' });
        const data = await res.json();

        if (data.success) {
            alert("✅ " + data.message);
        } else {
            alert("❌ Fehler: " + data.message);
        }
        
        btn.disabled = false;
        btn.innerHTML = originalText;
    } catch (e) {
        alert("Netzwerkfehler: " + e);
    }
}