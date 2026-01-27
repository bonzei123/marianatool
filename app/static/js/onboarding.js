document.addEventListener('DOMContentLoaded', async function() {

    // Konfiguration
    const CONFIG_URL = '/formbuilder/onboarding/config';
    const COMPLETE_URL = '/onboarding/complete';

    // Elemente
    const modalEl = document.getElementById('onboardingModal');
    if (!modalEl) return; // Sollte nicht passieren, da Backend das Script sonst nicht lädt

    const bsModal = new bootstrap.Modal(modalEl);
    const titleEl = document.getElementById('onbTitle');
    const bodyEl = document.getElementById('onbBody');
    const stepsEl = document.getElementById('onbSteps');
    const btnNext = document.getElementById('btnNext');
    const btnPrev = document.getElementById('btnPrev');

    let steps = [];
    let currentStepIndex = 0;

    // 1. Starten: Modal zeigen und Daten laden
    bsModal.show();
    await loadConfig();

    async function loadConfig() {
        try {
            const res = await fetch(CONFIG_URL);
            if(!res.ok) throw new Error("Netzwerk Fehler");

            const data = await res.json();

            // Wir filtern leere Sektionen raus (Sicher ist sicher)
            steps = data.filter(s => s.content && s.content.length > 0);

            if (steps.length === 0) {
                // Fallback, falls noch kein Onboarding konfiguriert ist
                steps = [{
                    title: "Willkommen",
                    content: [{type: 'info', label: "Willkommen in der App. Viel Erfolg!"}]
                }];
            }

            renderStep();
        } catch (e) {
            console.error(e);
            bodyEl.innerHTML = `<div class="alert alert-danger">Fehler beim Laden der Anleitung.</div>`;
            // Notfall-Button, damit User nicht gefangen ist
            btnNext.innerText = "Schließen";
            btnNext.onclick = () => bsModal.hide();
        }
    }

    // 2. Einen Schritt rendern
    function renderStep() {
        const step = steps[currentStepIndex];

        // Titel setzen
        titleEl.innerText = step.title;

        // Content bauen (Wir nutzen deine Formbuilder Typen als Layout-Elemente)
        let html = '';
        step.content.forEach(item => {
            // Hier entscheidet sich, wie deine Formbuilder-Elemente dargestellt werden
            // Da es eine Anleitung ist, rendern wir meist nur Labels/Texte

            if (item.type === 'header') {
                html += `<h4 class="mt-3 mb-2" style="color:#19835A">${item.label}</h4>`;
            }
            else if (item.type === 'info') {
                html += `<div class="alert alert-info border-0 bg-light-info"><i class="bi bi-info-circle me-2"></i>${item.label}</div>`;
            }
            else if (item.type === 'alert') {
                html += `<div class="alert alert-warning border-0"><i class="bi bi-exclamation-triangle me-2"></i>${item.label}</div>`;
            }
            else {
                // Standard Text (Text, Textarea etc. werden als Paragraphen dargestellt)
                html += `<p class="mb-2">${item.label}</p>`;

                // Falls du Bilder via HTML im Label hast, werden die gerendert.
                // Falls du echte Inputs anzeigen willst, müsstest du hier <input> bauen.
            }
        });

        bodyEl.innerHTML = html;

        // Footer Infos update
        stepsEl.innerText = `Seite ${currentStepIndex + 1} von ${steps.length}`;

        // Buttons steuern
        btnPrev.style.display = currentStepIndex === 0 ? 'none' : 'inline-block';

        if (currentStepIndex === steps.length - 1) {
            btnNext.innerText = "Verstanden & Starten 🚀";
            btnNext.classList.remove('btn-primary');
            btnNext.classList.add('btn-success');
        } else {
            btnNext.innerText = "Weiter";
            btnNext.classList.add('btn-primary');
            btnNext.classList.remove('btn-success');
        }
    }

    // 3. Navigation Events
    btnNext.onclick = async () => {
        if (currentStepIndex < steps.length - 1) {
            currentStepIndex++;
            renderStep();
        } else {
            // Letzter Schritt: Speichern und Schließen
            await finishOnboarding();
        }
    };

    btnPrev.onclick = () => {
        if (currentStepIndex > 0) {
            currentStepIndex--;
            renderStep();
        }
    };

    async function finishOnboarding() {
        // Lade-Status auf Button
        const originalText = btnNext.innerText;
        btnNext.disabled = true;
        btnNext.innerText = "Speichere...";

        try {
            const res = await fetch(COMPLETE_URL, { method: 'POST' });
            const result = await res.json();

            if (result.success) {
                bsModal.hide();
                // Optional: Seite neu laden, um Dashboard ohne Modal-Code zu haben
                // location.reload();
            } else {
                alert("Fehler beim Speichern: " + result.error);
                btnNext.disabled = false;
                btnNext.innerText = originalText;
            }
        } catch (e) {
            alert("Netzwerk Fehler beim Speichern.");
            btnNext.disabled = false;
            btnNext.innerText = originalText;
        }
    }
});