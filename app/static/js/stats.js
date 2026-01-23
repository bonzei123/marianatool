/**
 * stats.js - Mit doppelter Prozentanzeige im Tooltip
 */
let chartInstance = null;

function dateToNum(dStr) {
    if(!dStr) return 0;
    const parts = dStr.split('.');
    if(parts.length !== 3) return 0;
    return parseInt(parts[2] + parts[1] + parts[0]);
}

function calculateTotal() {
    let t = {
        applied:0, approved:0, rejected:0, withdrawn:0, open:0,
        m_applied:0, m_approved:0, m_rejected:0, m_withdrawn:0, m_open:0,
        date: (rawData[0] ? rawData[0].date : "")
    };

    if (typeof rawData === 'undefined') return t;
    let maxDateNum = 0;

    rawData.forEach(d => {
        t.applied += d.applied; t.approved += d.approved; t.rejected += d.rejected; t.withdrawn += d.withdrawn; t.open += d.open;
        t.m_applied += d.m_applied; t.m_approved += d.m_approved; t.m_rejected += d.m_rejected; t.m_withdrawn += d.m_withdrawn; t.m_open += d.m_open;

        const currentNum = dateToNum(d.date);
        if (currentNum > maxDateNum) {
            maxDateNum = currentNum;
            t.date = d.date;
        }
    });
    return t;
}

// Helper: Prozent berechnen
// val = Teilwert, total = Bezugsgröße
function calcPct(val, total) {
    if(!total || total === 0) return '0.0%';
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

    // --- DOM UPDATES ---
    document.getElementById('chartTitle').innerText = titleText;
    const dateEl = document.getElementById('disp_date');
    if (dateEl) dateEl.innerText = (sel === 'DE') ? '' : 'Stand: ' + d.date;
    const footerDateEl = document.getElementById('footer_date');
    if (footerDateEl) footerDateEl.innerText = d.date;

    // Boxen
    document.getElementById('disp_applied').innerText = d.applied;
    document.getElementById('disp_approved').innerText = d.approved;
    document.getElementById('disp_rejected').innerText = d.rejected;
    document.getElementById('disp_withdrawn').innerText = d.withdrawn;
    document.getElementById('disp_open').innerText = d.open;

    const total = d.applied; // Basis: Alle gestellten Anträge
    document.getElementById('pct_approved').innerText = calcPct(d.approved, total);
    document.getElementById('pct_rejected').innerText = calcPct(d.rejected, total);
    document.getElementById('pct_withdrawn').innerText = calcPct(d.withdrawn, total);
    document.getElementById('pct_open').innerText = calcPct(d.open, total);

    // --- CHART LOGIC ---
    const ctx = document.getElementById('marketChart');
    if (!ctx) return;
    if (chartInstance) chartInstance.destroy();

    const chartLabels = ['Genehmigt', 'Offen / In Prüfung', 'Abgelehnt', 'Zurückgezogen'];
    const chartData = [d.approved, d.open, d.rejected, d.withdrawn];
    const chartColors = ['#198754', '#ffc107', '#dc3545', '#6c757d'];

    const marianaData = [d.m_approved, d.m_open, d.m_rejected, d.m_withdrawn];

    chartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: chartLabels,
            datasets: [{
                data: chartData,
                backgroundColor: chartColors,
                borderWidth: 1,
                borderColor: '#ffffff',
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { padding: 20 } },
                title: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.85)',
                    padding: 12,
                    titleFont: { size: 14, weight: 'bold' },
                    bodyFont: { size: 13, family: "'Segoe UI', Roboto, sans-serif" },
                    callbacks: {
                        label: function(context) {
                            const label = context.label;
                            const value = context.raw;     // Wert des Segments (z.B. 50 Genehmigte)
                            const idx = context.dataIndex;

                            // 1. Prozentualer Anteil des Segments am GESAMTMARKT
                            const slicePct = calcPct(value, total);

                            // Mariana Aufschlüsselung
                            const mVal = marianaData[idx] || 0;
                            const otherVal = Math.max(0, value - mVal);

                            // 2. Berechnung für Mariana
                            const mPctTotal = calcPct(mVal, total); // % vom Gesamtmarkt
                            const mPctSlice = calcPct(mVal, value); // % innerhalb dieses Segments (z.B. % der Genehmigungen)

                            // 3. Berechnung für Andere
                            const oPctTotal = calcPct(otherVal, total); // % vom Gesamtmarkt
                            const oPctSlice = calcPct(otherVal, value); // % innerhalb dieses Segments

                            return [
                                `Gesamt: ${value} (${slicePct})`,
                                `------------------`,
                                `🟢 Mariana: ${mVal} (${mPctTotal} / ${mPctSlice})`,
                                `⚪ Andere: ${otherVal} (${oPctTotal} / ${oPctSlice})`
                            ];
                        }
                    }
                }
            }
        }
    });
}

function saveAsImage() {
    const element = document.getElementById("captureArea");
    document.body.classList.add('taking-screenshot');

    html2canvas(element, {
        scale: 2,
        backgroundColor: "#ffffff",
        logging: false
    }).then(canvas => {
        const link = document.createElement('a');
        link.download = 'Mariana_Markt_Daten_' + new Date().toISOString().slice(0,10) + '.png';
        link.href = canvas.toDataURL("image/png");
        link.click();
        document.body.classList.remove('taking-screenshot');
    }).catch(err => {
        console.error("Screenshot Fehler:", err);
        alert("Fehler beim Speichern des Bildes.");
        document.body.classList.remove('taking-screenshot');
    });
}