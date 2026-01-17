/**
 * immo_overview.js
 * Handhabt die Status-Updates in der Übersichtstabelle.
 */

async function changeStatus(id, newStatus) {
    try {
        const res = await fetch('/immo/status/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id: id, status: newStatus })
        });

        const data = await res.json();

        if (data.success) {
            // Button Live Updaten ohne Reload
            const btn = document.querySelector(`#row-${id} .status-btn`);
            if(btn) {
                // Alte Farbe entfernen (RegEx)
                btn.className = btn.className.replace(/btn-(primary|secondary|success|danger|warning|light)/g, '');
                // Neue Farbe und Text setzen
                btn.classList.add('btn-' + data.new_color);
                btn.innerText = data.new_label;
            } else {
                // Fallback, falls DOM-Element nicht gefunden
                location.reload();
            }
        } else {
            alert('Fehler: ' + data.error);
        }
    } catch (e) {
        console.error(e);
        alert('Verbindungsfehler beim Status-Update.');
    }
}