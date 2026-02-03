// Globale Variable für die aktuell ausgewählte ID
let currentUserId = null;

document.addEventListener('DOMContentLoaded', function() {
    // Modal Instanz vorbereiten
    const editModalEl = document.getElementById('editModal');
    let editModalInstance = null;
    if (editModalEl) {
        editModalInstance = new bootstrap.Modal(editModalEl);
    }

    // URLs aus dem Config-Div lesen
    const configDiv = document.getElementById('js-config');
    const updateUrlTemplate = configDiv.dataset.updateUrl;
    const deleteUrlTemplate = configDiv.dataset.deleteUrl;
    const resetUrlTemplate = configDiv.dataset.resetUrl;

    // --- UX - Ganze Permission-Box klickbar machen ---
    document.querySelectorAll('.permission-item').forEach(item => {
        item.style.cursor = 'pointer'; // Hand-Cursor anzeigen

        item.addEventListener('click', function(e) {
            const chk = this.querySelector('input[type="checkbox"]');
            if (!chk) return;

            // 1. Wenn der User direkt das kleine Kästchen trifft:
            if (e.target === chk) return;

            // 2. Wenn der User auf Text, Icon, Label oder Hintergrund klickt:
            e.preventDefault();

            // Und schalten den Haken manuell um
            chk.checked = !chk.checked;
        });
    });

    // --- FUNKTION: Modal öffnen ---
    window.openEditModal = function(row) {
        // A. Daten aus Tabelle lesen
        currentUserId = row.getAttribute('data-id');
        const name = row.getAttribute('data-username');

        // <--- NEU: Vor- und Nachname lesen
        const firstName = row.getAttribute('data-firstname');
        const lastName = row.getAttribute('data-lastname');

        const email = row.getAttribute('data-email');
        const vereinId = row.getAttribute('data-verein-id');
        const isAdmin = row.getAttribute('data-admin') === 'true';
        const onboardingDate = row.getAttribute('data-onboarding');
        const permissionsRaw = row.getAttribute('data-permissions');
        const permissions = permissionsRaw ? permissionsRaw.split(',').map(Number) : [];

        // B. URLs generieren (Die "0" durch echte ID ersetzen)
        const realUpdateUrl = updateUrlTemplate.replace('/0/', `/${currentUserId}/`);
        const realDeleteUrl = deleteUrlTemplate.replace('/0/', `/${currentUserId}/`);
        const realResetUrl = resetUrlTemplate.replace('/0/', `/${currentUserId}/`);
        const realResetOnboardingUrl = configDiv.dataset.resetOnboardingUrl.replace('/0/', `/${currentUserId}/`);

        // C. Form Action setzen
        document.getElementById('editForm').action = realUpdateUrl;

        // D. Buttons konfigurieren
        const delBtn = document.getElementById('delBtn');
        delBtn.dataset.url = realDeleteUrl;
        delBtn.onclick = function() { deleteUser(name); };

        const resetBtn = document.querySelector('button[onclick="sendResetMail()"]');
        if(resetBtn) resetBtn.dataset.url = realResetUrl;

        // E. Felder befüllen
        document.getElementById('editTitle').innerText = "Bearbeiten: " + name;
        document.getElementById('editUser').value = name;

        // <--- NEU: Input Felder befüllen
        document.getElementById('editFirstName').value = firstName || "";
        document.getElementById('editLastName').value = lastName || "";

        document.getElementById('editEmail').value = email || "";

        const vereinSelect = document.getElementById('editVerein');
        if (vereinSelect) {
            vereinSelect.value = vereinId || "";
        }

        document.getElementById('editAdmin').checked = isAdmin;
        const obText = document.getElementById('onboardingStatusText');
        const obBtn = document.getElementById('btnResetOnboarding');

        // F. Checkboxen setzen (zuerst alle resetten, dann setzen)
        document.querySelectorAll('#editModal .edit-srv').forEach(cb => cb.checked = false);
        permissions.forEach(permId => {
            // Suche Checkbox im Edit-Modal via Value (da IDs dynamisch sein können)
            const chk = document.querySelector(`#editModal input[value="${permId}"]`);
            if (chk) chk.checked = true;
        });

        obBtn.dataset.url = realResetOnboardingUrl;

        if (onboardingDate) {
            obText.innerHTML = `<span class="text-success"><i class="bi bi-check-circle-fill"></i> ${onboardingDate}</span>`;
            obBtn.disabled = false;
        } else {
            obText.innerHTML = `<span class="text-muted"><i class="bi bi-circle"></i> Ausstehend</span>`;
            obBtn.disabled = true;
        }

        // G. Anzeigen
        if (editModalInstance) editModalInstance.show();
    };

    // --- SUCHFUNKTION ---
    window.filterUsers = function() {
        const filter = document.getElementById('userSearch').value.toLowerCase();
        const rows = document.querySelectorAll('#userTable tbody tr');
        rows.forEach(r => {
            // Wir suchen jetzt im gesamten Text der Zeile (enthält Username, Fullname und Email)
            const text = r.innerText.toLowerCase();
            r.style.display = text.includes(filter) ? '' : 'none';
        });
    };
});

// --- API ACTIONS ---

async function deleteUser(username) {
    const btn = document.getElementById('delBtn');
    const url = btn.dataset.url;

    if (!url || !confirm(`User "${username}" wirklich löschen?`)) return;

    try {
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = "Lösche...";

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
    const url = btn.dataset.url;

    if (!url || !confirm("Passwort-Reset senden?")) return;

    try {
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = "⏳ Sende...";

        const res = await fetch(url, { method: 'POST' });
        const data = await res.json();

        if (data.success) {
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

async function resetOnboarding() {
    const btn = document.getElementById('btnResetOnboarding');
    const url = btn.dataset.url;

    if(!url || !confirm("Soll das Onboarding für diesen User zurückgesetzt werden? Er muss es beim nächsten Login erneut durchlaufen.")) return;

    try {
        const res = await fetch(url, { method: 'POST' });
        const data = await res.json();

        if(data.success) {
            alert("Erfolgreich zurückgesetzt.");
            window.location.reload();
        } else {
            alert("Fehler: " + data.message);
        }
    } catch(e) {
        alert("Netzwerkfehler");
    }
}