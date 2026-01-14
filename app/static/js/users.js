// Globale Variablen für den Reset
let currentUserId = null;
let resetBaseUrl = "";

document.addEventListener('DOMContentLoaded', function() {
    // Basis URLs laden
    const configDiv = document.getElementById('js-config');
    const updateBaseUrl = configDiv.dataset.updateUrl.slice(0, -1);
    const deleteBaseUrl = configDiv.dataset.deleteUrl.slice(0, -1);
    resetBaseUrl = configDiv.dataset.resetUrl.slice(0, -1); // "0" abschneiden

    // Modal Init
    const editModalEl = document.getElementById('editModal');
    let editModalInstance = null;
    if (editModalEl) {
        editModalInstance = new bootstrap.Modal(editModalEl);
    }

    // Modal Öffnen Funktion
    window.openEditModal = function(row) {
        // Daten auslesen
        currentUserId = row.getAttribute('data-id'); // ID merken für Reset Button
        const name = row.getAttribute('data-username');
        const email = row.getAttribute('data-email'); // NEU
        const isAdmin = row.getAttribute('data-admin') === 'true';
        const servicesRaw = row.getAttribute('data-services');
        const services = servicesRaw ? servicesRaw.split(',').map(Number) : [];

        // URLs setzen
        document.getElementById('editForm').action = updateBaseUrl + currentUserId;
        
        const delBtn = document.getElementById('delBtn');
        delBtn.href = deleteBaseUrl + currentUserId;
        delBtn.onclick = () => confirm(`User "${name}" wirklich löschen?`);

        // Felder befüllen
        document.getElementById('editTitle').innerText = "Bearbeiten: " + name;
        document.getElementById('editUser').value = name;
        document.getElementById('editEmail').value = email || ""; // NEU
        document.getElementById('editAdmin').checked = isAdmin;

        // Services Checkboxen
        document.querySelectorAll('.edit-srv').forEach(cb => {
            cb.checked = services.includes(parseInt(cb.value));
        });

        if (editModalInstance) editModalInstance.show();
    };

    // Filter Funktion
    window.filterUsers = function() {
        const filter = document.getElementById('userSearch').value.toLowerCase();
        const rows = document.querySelectorAll('#userTable tbody tr');
        rows.forEach(r => {
            const text = r.innerText.toLowerCase();
            r.style.display = text.includes(filter) ? '' : 'none';
        });
    };
});

// NEUE Funktion für den Reset Button
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