document.addEventListener('DOMContentLoaded', function() {
    // Basis URLs aus dem HTML Config-Div laden
    const configDiv = document.getElementById('js-config');
    // Wir entfernen die "0" am Ende, die wir als Platzhalter im HTML gesetzt haben
    const updateBaseUrl = configDiv.dataset.updateUrl.slice(0, -1);
    const deleteBaseUrl = configDiv.dataset.deleteUrl.slice(0, -1);

    // Edit Modal Referenz
    // (getOrCreateInstance ist sicherer als new Modal, falls es schon initialisiert wurde)
    const editModalEl = document.getElementById('editModal');
    let editModalInstance = null;
    if (editModalEl) {
        editModalInstance = new bootstrap.Modal(editModalEl);
    }

    // Funktion global verfügbar machen, damit onclick im HTML funktioniert
    window.openEditModal = function(row) {
        const id = row.getAttribute('data-id');
        const name = row.getAttribute('data-username');
        const isAdmin = row.getAttribute('data-admin') === 'true';
        const servicesRaw = row.getAttribute('data-services');
        const services = servicesRaw ? servicesRaw.split(',').map(Number) : [];

        // URLs zusammensetzen
        document.getElementById('editForm').action = updateBaseUrl + id;

        const delBtn = document.getElementById('delBtn');
        delBtn.href = deleteBaseUrl + id;
        delBtn.onclick = () => confirm(`User "${name}" wirklich löschen?`);

        // Felder befüllen
        document.getElementById('editTitle').innerText = "Bearbeiten: " + name;
        document.getElementById('editUser').value = name;
        document.getElementById('editAdmin').checked = isAdmin;

        // Checkboxen setzen
        document.querySelectorAll('.edit-srv').forEach(cb => {
            cb.checked = services.includes(parseInt(cb.value));
        });

        if (editModalInstance) editModalInstance.show();
    };

    // Suchfunktion
    window.filterUsers = function() {
        const filter = document.getElementById('userSearch').value.toLowerCase();
        const rows = document.querySelectorAll('#userTable tbody tr');
        rows.forEach(r => {
            const text = r.innerText.toLowerCase();
            r.style.display = text.includes(filter) ? '' : 'none';
        });
    };
});