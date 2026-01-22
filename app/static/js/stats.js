/**
 * stats.js
 */

let chartInstance = null;

// Helper: Wandelt "24.01.2026" in eine Zahl 20260124 um (zum Vergleichen)
function dateToNum(dStr) {
    if(!dStr) return 0;
    const parts = dStr.split('.');
    if(parts.length !== 3) return 0;
    return parseInt(parts[2] + parts[1] + parts[0]);
}

function calculateTotal() {
    // Initialisiere mit dem Datum des ersten Eintrags als Fallback
    let t = { applied:0, approved:0, rejected:0, withdrawn:0, open:0, date: (rawData[0] ? rawData[0].date : "") };

    if (typeof rawData === 'undefined') return t;

    let maxDateNum = 0;

    rawData.forEach(d => {
        t.applied += d.applied;
        t.approved += d.approved;
        t.rejected += d.rejected;
        t.withdrawn += d.withdrawn;
        t.open += d.open;

        // Prüfen ob dieses Datum neuer ist
        const currentNum = dateToNum(d.date);
        if (currentNum > maxDateNum) {
            maxDateNum = currentNum;
            t.date = d.date; // Das String-Datum übernehmen
        }
    });
    return t;
}

// Helper: Prozent berechnen
function calcPct(val, total) {
    if(!total || total === 0) return '0%';
    return ((val / total) * 100).toFixed(1) + '%';
}

function updateChart() {
    if (typeof rawData === 'undefined') return;

    const sel = document.getElementById('stateSelector').value;
    let d = null;
    let titleText = "";

    if (sel === 'DE') {
        d = calculateTotal();
        titleText = "Marktübersicht: Deutschland (Gesamt)";
    } else {
        d = rawData.find(x => x.id === sel);
        titleText = "Marktübersicht: " + d.name;
    }

    if (!d) return;

    // 1. Titel Update
    document.getElementById('chartTitle').innerText = titleText;

    // 2. Datum Update (Oben Info & Footer für Bild)
    const dateText = d.date; // Ist jetzt entweder das Datum des Landes oder das neuste bei DE

    // Oben neben Dropdown
    const dateEl = document.getElementById('disp_date');
    if (dateEl) dateEl.innerText = (sel === 'DE') ? '' : 'Stand: ' + dateText;

    // Unten im Footer (für Screenshot)
    const footerDateEl = document.getElementById('footer_date');
    if (footerDateEl) footerDateEl.innerText = dateText;

    // 3. Absolute Zahlen setzen
    document.getElementById('disp_applied').innerText = d.applied;
    document.getElementById('disp_approved').innerText = d.approved;
    document.getElementById('disp_rejected').innerText = d.rejected;
    document.getElementById('disp_withdrawn').innerText = d.withdrawn;
    document.getElementById('disp_open').innerText = d.open;

    // 4. Prozente berechnen & setzen
    const total = d.applied;
    document.getElementById('pct_approved').innerText = calcPct(d.approved, total);
    document.getElementById('pct_rejected').innerText = calcPct(d.rejected, total);
    document.getElementById('pct_withdrawn').innerText = calcPct(d.withdrawn, total);
    document.getElementById('pct_open').innerText = calcPct(d.open, total);


    // 5. Chart Update
    const ctx = document.getElementById('marketChart');
    if (!ctx) return;

    if (chartInstance) chartInstance.destroy();

    chartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Genehmigt', 'Offen / In Prüfung', 'Abgelehnt', 'Zurückgezogen'],
            datasets: [{
                data: [d.approved, d.open, d.rejected, d.withdrawn],
                backgroundColor: ['#198754', '#ffc107', '#dc3545', '#6c757d'],
                borderWidth: 0,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { padding: 20 } },
                title: { display: false }
            }
        }
    });
}

// --- Screenshot Funktion ---
function saveAsImage() {
    const element = document.getElementById("captureArea");
    document.body.classList.add('taking-screenshot');

    html2canvas(element, {
        scale: 2,
        backgroundColor: "#ffffff",
        logging: false
    }).then(canvas => {
        const link = document.createElement('a');
        link.download = 'Markt_Daten_' + new Date().toISOString().slice(0,10) + '.png';
        link.href = canvas.toDataURL("image/png");
        link.click();
        document.body.classList.remove('taking-screenshot');
    }).catch(err => {
        console.error("Screenshot Fehler:", err);
        alert("Fehler beim Speichern des Bildes.");
        document.body.classList.remove('taking-screenshot');
    });
}