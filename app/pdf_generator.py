import os
from fpdf import FPDF
from datetime import datetime


class PDFReport(FPDF):
    def header(self):
        # Header Grün
        self.set_fill_color(39, 174, 96)
        self.rect(0, 0, 210, 20, 'F')
        self.set_text_color(255)
        self.set_font("Helvetica", "B", 16)
        # Titel wird von außen gesetzt oder generisch
        self.cell(0, 10, "", 0, 1, 'C')
        self.ln(5)


class PdfGenerator:
    def __init__(self, config_models, inspection, upload_folder):
        """
        :param config_models: Liste der ImmoSection Objekte (aus DB)
        :param inspection: Das Inspection Objekt (aus DB)
        :param upload_folder: Pfad zum Upload Ordner (app.config['UPLOAD_FOLDER'])
        """
        self.config = config_models
        self.inspection = inspection
        self.data = {}
        self.upload_folder = upload_folder

        # JSON Daten parsen
        import json
        if self.inspection.data_json:
            loaded = json.loads(self.inspection.data_json)
            self.data = loaded.get('form_responses', {})
            self.meta = loaded.get('meta', {})

        self.current_type = self.inspection.inspection_type or 'einzel'

    def create(self):
        pdf = PDFReport()
        pdf.add_page()

        # --- HEADER TEXT ---
        pdf.set_y(6)
        pdf.set_text_color(255)
        pdf.set_font("Helvetica", "B", 16)
        title = f"PROTOKOLL: {self.current_type.upper()}"
        pdf.cell(0, 10, title, 0, 0, 'C')

        # --- SUBHEADER (Weißer Bereich) ---
        pdf.set_y(25)
        pdf.set_text_color(0)
        pdf.set_font("Helvetica", "", 10)
        date_str = self.inspection.created_at.strftime('%d.%m.%Y')
        pdf.cell(0, 10, f"CSC: {self.inspection.csc_name} | Datum: {date_str} | ID: {self.inspection.id}", 0, 1)

        pdf.ln(5)

        # --- CONTENT LOOP ---
        for section in self.config:
            # 1. Section Titel (Grau hinterlegt)
            pdf.set_fill_color(230, 230, 230)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, section.title, 0, 1, 'L', True)
            pdf.ln(2)

            pdf.set_font("Helvetica", "", 10)

            # Fragen durchgehen
            for q in section.questions:
                # Typ-Filter prüfen (JSON parsen)
                import json
                try:
                    types = json.loads(q.types_json) if q.types_json else []
                    if types and self.current_type not in types:
                        continue
                except:
                    pass

                # Ignorierte Typen
                if q.type in ['info', 'alert', 'file']:
                    continue

                # Header innerhalb der Sektion
                if q.type == 'header':
                    pdf.ln(3)
                    pdf.set_font("Helvetica", "B", 10)
                    pdf.cell(0, 6, q.label.upper(), 0, 1)
                    pdf.set_font("Helvetica", "", 10)
                    continue

                # Wert holen
                raw_val = self.data.get(q.id)
                val_text = "-"

                if q.type == 'checkbox':
                    if str(raw_val).lower() in ['true', 'on', '1']:
                        val_text = "[x] Ja"
                    else:
                        val_text = "[ ] Nein"
                elif q.type == 'select':
                    val_text = str(raw_val) if raw_val else "-"
                else:
                    val_text = str(raw_val) if raw_val else "-"

                # Layout: Label links (Bold), Wert rechts (Normal)
                # Wir nutzen MultiCell für Umbrüche

                x_start = pdf.get_x()
                y_start = pdf.get_y()

                # Label Spalte
                pdf.set_font("Helvetica", "B", 9)
                pdf.multi_cell(70, 5, q.label)

                # Maximale Y-Position nach Label merken
                y_after_label = pdf.get_y()

                # Zurück nach oben rechts für den Wert
                pdf.set_xy(x_start + 75, y_start)
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 5, val_text)

                y_after_value = pdf.get_y()

                # Cursor auf die tiefste Position setzen + Abstand
                pdf.set_y(max(y_after_label, y_after_value) + 3)

                # Seitenumbruch Check (einfach gehalten)
                if pdf.get_y() > 270:
                    pdf.add_page()

            pdf.ln(5)

        # --- SPEICHERN ---
        # Dateiname generieren
        filename = f"Protokoll_{self.inspection.csc_name}_{self.inspection.id}.pdf".replace(" ", "_")
        # Zeichen bereinigen
        from werkzeug.utils import secure_filename
        filename = secure_filename(filename)

        # Ordner Logik (Wir nutzen den Ordner, in dem die Attachments liegen, oder erstellen einen)
        # inspection.pdf_path ist z.B. "OrdnerName/File.pdf" oder leer.

        folder_name = ""
        if self.inspection.pdf_path:
            folder_name = os.path.dirname(self.inspection.pdf_path)

        if not folder_name:
            # Fallback: Neuen Ordner anlegen
            folder_name = secure_filename(f"{self.inspection.csc_name}_{datetime.now().strftime('%Y%m%d')}")

        full_dir = os.path.join(self.upload_folder, folder_name)
        os.makedirs(full_dir, exist_ok=True)

        full_path = os.path.join(full_dir, filename)
        pdf.output(full_path)

        # Relativen Pfad für DB zurückgeben
        return os.path.join(folder_name, filename)