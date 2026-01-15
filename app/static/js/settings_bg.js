// app/static/js/settings_bg.js

document.addEventListener('DOMContentLoaded', function() {

    // Alle Select-Boxen finden, die unsere Klasse haben
    const selectors = document.querySelectorAll('.bg-selector');

    selectors.forEach(select => {
        select.addEventListener('change', function() {
            // ID des Vorschaubildes aus dem data-Attribut holen
            const previewId = this.dataset.previewId;
            const imgElement = document.getElementById(previewId);

            if (this.value) {
                // Bildpfad bauen (statisch)
                imgElement.src = "/static/img/backgrounds/" + this.value;
                imgElement.style.display = 'block';
            } else {
                // Wenn "Standard" gewählt ist -> kein Vorschaubild oder Default
                // Wir verstecken es hier einfachheitshalber oder laden ein Platzhalter
                imgElement.style.display = 'none';
            }
        });
    });
});