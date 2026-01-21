/**
 * immo_overview.js
 * - Status Updates
 * - Echtzeit Suche (Filter)
 * - Tabellen Sortierung
 */

async function changeStatus(id, newStatus) {
    try {
        const res = await fetch('/projects/status', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id: id, status: newStatus })
        });

        const data = await res.json();

        if (data.success) {
            const btn = document.querySelector(`#row-${id} .status-btn`);
            if(btn) {
                btn.className = btn.className.replace(/btn-(primary|secondary|success|danger|warning|light)/g, '');
                btn.classList.add('btn-' + data.new_color);
                btn.innerText = data.new_label;
            } else {
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

// --- SUCHE ---
function filterProjects() {
    const input = document.getElementById('projectSearch');
    const filter = input.value.toLowerCase();
    const table = document.getElementById('projectTableBody');
    const tr = table.getElementsByTagName('tr');

    for (let i = 0; i < tr.length; i++) {
        // Ignoriere die "Keine Ergebnisse" Zeile
        if(tr[i].id === 'noResultsRow') continue;

        const tdArr = tr[i].getElementsByTagName('td');
        let found = false;

        // Durchsuche alle Spalten der Zeile
        for (let j = 0; j < tdArr.length - 1; j++) { // -1 um Aktion Spalte zu ignorieren
            if (tdArr[j]) {
                let txtValue = "";

                // SPEZIALFALL SPALTE 0 (Status): Nur den sichtbaren Text (Button/Badge) nehmen
                if (j === 0) {
                    // Versuche Button zu finden (Admin Ansicht)
                    const btn = tdArr[j].querySelector('.status-btn');
                    if (btn) {
                        // Nur den direkten Text des Buttons nehmen (ohne Dropdown-Items)
                        // .childNodes[0] ist meist der Textknoten vor eventuellen Icons/Sub-Elementen,
                        // aber innerText des Buttons reicht meist, da das <ul> nicht IM Button liegt, sondern daneben.
                        txtValue = btn.textContent || btn.innerText;
                    } else {
                        // Versuche Badge zu finden (User Ansicht)
                        const badge = tdArr[j].querySelector('.badge');
                        if (badge) txtValue = badge.textContent || badge.innerText;
                    }
                } else {
                    // Standard für alle anderen Spalten
                    txtValue = tdArr[j].textContent || tdArr[j].innerText;
                }

                if (txtValue.trim().toLowerCase().indexOf(filter) > -1) {
                    found = true;
                    break;
                }
            }
        }
        tr[i].style.display = found ? "" : "none";
    }
}

// --- SORTIEREN ---
let sortDir = {}; // Speichert Sortierrichtung pro Spalte (asc/desc)

function sortTable(n) {
    const table = document.getElementById("projectTable");
    const tbody = document.getElementById("projectTableBody");
    let rows = Array.from(tbody.getElementsByTagName("tr"));

    // Ignoriere leere Zeile
    if(rows.length > 0 && rows[0].id === 'noResultsRow') return;

    // Toggle Richtung
    sortDir[n] = sortDir[n] === 'asc' ? 'desc' : 'asc';
    const isAsc = sortDir[n] === 'asc';

    // Icons aktualisieren
    updateSortIcons(n, isAsc);

    rows.sort((rowA, rowB) => {
        let x = rowA.getElementsByTagName("td")[n].innerText.toLowerCase();
        let y = rowB.getElementsByTagName("td")[n].innerText.toLowerCase();

        // Datum Logik (Spalte 3, Index 3: "dd.mm.yyyy")
        if (n === 3) {
            x = parseDate(x);
            y = parseDate(y);
        }

        if (x < y) return isAsc ? -1 : 1;
        if (x > y) return isAsc ? 1 : -1;
        return 0;
    });

    // Zeilen neu einhängen
    rows.forEach(row => tbody.appendChild(row));
}

function parseDate(dateStr) {
    // Wandelt "21.01.2026" in 20260121 um (Zahl) für korrekten Vergleich
    const parts = dateStr.trim().split('.');
    if (parts.length === 3) {
        return parseInt(parts[2] + parts[1] + parts[0]);
    }
    return 0;
}

function updateSortIcons(colIndex, isAsc) {
    // Alle Icons zurücksetzen
    document.querySelectorAll('.sort-icon').forEach(icon => {
        icon.className = 'bi bi-arrow-down-up small text-muted ms-1 sort-icon';
    });

    // Aktives Icon setzen
    const activeHeader = document.querySelectorAll('#projectTable thead th')[colIndex];
    const icon = activeHeader.querySelector('i');
    if(icon) {
        icon.className = isAsc ? 'bi bi-sort-down ms-1 sort-icon text-dark' : 'bi bi-sort-up ms-1 sort-icon text-dark';
    }
}