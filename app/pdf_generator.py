import os
import json
from fpdf import FPDF
from datetime import datetime
from flask import current_app


class PdfGenerator(FPDF):
    def __init__(self, sections, inspection=None, upload_folder="app/static/uploads", target_type=None):
        super().__init__()
        self.sections = sections
        self.inspection = inspection
        self.upload_folder = upload_folder

        # PFADE
        self.logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo_green.png')
        self.watermark_path = os.path.join(current_app.root_path, 'static', 'img', 'logo_transparent.png')

        if self.inspection:
            self.target_type = self.inspection.inspection_type
        else:
            self.target_type = target_type

        # Daten laden
        self.form_data = {}
        self.project_folder_path = None

        if self.inspection and self.inspection.data_json:
            try:
                data = json.loads(self.inspection.data_json)
                self.form_data = data.get('form_responses', {})
                if self.inspection.pdf_path:
                    folder_name = os.path.dirname(self.inspection.pdf_path)
                    if not folder_name: folder_name = self.inspection.pdf_path
                    self.project_folder_path = os.path.join(self.upload_folder, folder_name)
            except:
                self.form_data = {}

        # Ränder (Oben 35mm Platz für Header/Logo)
        self.set_margins(20, 35, 20)
        self.set_auto_page_break(auto=True, margin=20)

        self.add_page()

    def header(self):
        # 1. WASSERZEICHEN (Zentriert)
        if os.path.exists(self.watermark_path):
            # A4 Seite = 210mm Breite
            wm_width = 160  # Breite des Wasserzeichens (mm)

            # Automatische Berechnung der X-Mitte: (Seite - Bild) / 2
            x_pos = (210 - wm_width) / 2

            # Y-Position: Optische Mitte (ca. 85-90mm von oben)
            y_pos = 85

            self.image(self.watermark_path, x=x_pos, y=y_pos, w=wm_width)

        # 2. LOGO OBEN RECHTS (Klein & Original)
        if os.path.exists(self.logo_path):
            # x=165 (rechtsbündig zum Rand 20mm), y=10 (oben)
            self.image(self.logo_path, x=165, y=10, w=30)

        # 3. HEADER TEXT
        self.set_y(10)  # Auf Höhe des Logos beginnen
        self.set_font('Arial', 'B', 14)

        if self.inspection:
            title = f"Protokoll: {self._clean(self.inspection.csc_name)}"
            sub = f"ID: {self.inspection.id} | {self.inspection.created_at.strftime('%d.%m.%Y')}"
        else:
            t_label = self._clean(self.target_type.upper()) if self.target_type else "ALLE"
            title = f"Erfassungsbogen ({t_label})"
            sub = "Leerformular"

        # Titel rendern (Links)
        self.cell(0, 8, self._clean(title), ln=True, align='L')
        self.set_font('Arial', '', 10)
        self.cell(0, 6, self._clean(sub), ln=True, align='L')

        # Trennlinie
        self.ln(5)
        self.line(self.l_margin, self.get_y(), 210 - self.r_margin, self.get_y())
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        page = f"Seite {self.page_no()}"
        self.cell(0, 10, page, 0, 0, 'C')
        self.set_text_color(0)

    # --- HELPER & LOGIK ---

    def _clean(self, text):
        if not text: return ""
        text = str(text)
        replacements = {"–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "€": "EUR"}
        for k, v in replacements.items():
            text = text.replace(k, v)
        try:
            return text.encode('latin-1', 'replace').decode('latin-1')
        except:
            return text

    def _calculate_height(self, q, label):
        lines = self.multi_cell(0, 6, label, split_only=True)
        label_height = len(lines) * 6
        input_height = 0
        if self.inspection is None:
            if q.type == 'textarea':
                input_height = 30 + 2
            elif q.type == 'checkbox':
                input_height = 6 + 2
            elif q.type == 'select':
                opts = json.loads(q.options_json) if q.options_json else []
                input_height = (len(opts) * 5) + 2
            elif q.type == 'file':
                input_height = 40 + 2
            elif q.type in ['info', 'alert']:
                return len(self.multi_cell(0, 6, self._clean(f"Hinweis: {q.label}"), split_only=True)) * 6 + 4
            elif q.type == 'header':
                return len(self.multi_cell(0, 8, label, split_only=True)) * 8 + 4
            else:
                input_height = 8 + 2
            return label_height + input_height + 2

        val = self.form_data.get(q.id, "")
        val_lines = self.multi_cell(0, 6, str(val), split_only=True)
        text_height = len(val_lines) * 6 + 4
        return label_height + text_height + 5

    def create(self):
        self.set_font('Arial', '', 11)
        for sec in self.sections:
            visible_questions = []
            for q in sec.questions:
                q_types = json.loads(q.types_json) if q.types_json else []
                type_match = not self.target_type or self.target_type in q_types
                print_allowed = getattr(q, 'is_print', True)
                if type_match and print_allowed: visible_questions.append(q)

            if not visible_questions: continue

            if self.get_y() + 30 > self.page_break_trigger: self.add_page()

            self.set_fill_color(240, 240, 240)
            self.set_font('Arial', 'B', 12)
            self.set_x(self.l_margin)
            self.cell(0, 10, self._clean(sec.title), 1, 1, 'L', fill=True)
            self.ln(2)
            self.set_font('Arial', '', 11)

            for q in visible_questions:
                self.set_x(self.l_margin)
                label = self._clean(q.label)
                if getattr(q, 'is_required', False): label += " *"
                needed = self._calculate_height(q, label)

                if self.get_y() + needed > self.page_break_trigger:
                    self.add_page()
                    self._print_continuation(sec.title)

                if q.type == 'header':
                    self.ln(3)
                    self.set_font('Arial', 'B', 11)
                    self.multi_cell(0, 8, label)
                    self.set_font('Arial', '', 11)
                    continue

                if q.type in ['info', 'alert']:
                    self.set_text_color(100, 100, 100)
                    self.set_font('Arial', 'I', 10)
                    self.multi_cell(0, 6, self._clean(f"Hinweis: {q.label}"))
                    self.set_font('Arial', '', 11)
                    self.set_text_color(0, 0, 0)
                    self.ln(4)
                    continue

                val = self.form_data.get(q.id)
                if self.inspection is None:
                    self._render_blank_field(q, label)
                else:
                    self._render_filled_field(q, label, val)
                self.ln(2)

        if self.inspection:
            filename = f"Inspection_{self.inspection.id}.pdf"
            folder = os.path.dirname(self.inspection.pdf_path) if self.inspection.pdf_path else "temp"
        else:
            t_suffix = self.target_type if self.target_type else "all"
            filename = f"Formular_{t_suffix}_{datetime.now().strftime('%Y%m%d')}.pdf"
            folder = "templates"

        full_path = os.path.join(self.upload_folder, folder)
        os.makedirs(full_path, exist_ok=True)
        output_path = os.path.join(full_path, filename)
        self.output(output_path)
        return os.path.join(folder, filename)

    def _print_continuation(self, title):
        self.set_font('Arial', 'I', 10)
        self.set_text_color(128)
        self.cell(0, 8, f"(Fortsetzung: {self._clean(title)})", 0, 1, 'L')
        self.set_text_color(0)
        self.set_font('Arial', '', 11)
        self.set_x(self.l_margin)

    def _render_blank_field(self, q, label):
        self.set_x(self.l_margin)
        self.set_font('Arial', 'B', 10)
        self.multi_cell(0, 6, label)
        self.set_font('Arial', '', 10)
        if q.type == 'textarea':
            self.ln(1);
            self.set_x(self.l_margin);
            self.cell(0, 30, "", 1, 1)
        elif q.type == 'checkbox':
            self.ln(1);
            self.set_x(self.l_margin);
            self.cell(5, 5, "", 1, 0);
            self.cell(0, 5, self._clean(" Ja / Bestätigt"), ln=True)
        elif q.type == 'select':
            options = json.loads(q.options_json) if q.options_json else []
            self.ln(1)
            for opt in options:
                self.set_x(self.l_margin);
                self.cell(5, 5, "", 1, 0);
                self.cell(0, 5, self._clean(f" {opt}"), ln=True)
        elif q.type == 'file':
            self.ln(1);
            self.set_x(self.l_margin);
            self.set_font('Arial', 'I', 9)
            self.cell(0, 40, self._clean("[ Platz für Fotos / Skizzen ]"), 1, 1, 'C');
            self.set_font('Arial', '', 10)
        else:
            self.ln(6);
            self.set_x(self.l_margin)
            self.line(self.get_x(), self.get_y(), self.w - self.r_margin, self.get_y());
            self.ln(2)

    def _render_filled_field(self, q, label, val):
        self.set_x(self.l_margin)
        self.set_font('Arial', 'B', 10)
        self.multi_cell(0, 6, label + ":")
        self.set_font('Arial', '', 10)

        if q.type == 'file':
            if not val:
                self.set_x(self.l_margin + 5);
                self.cell(0, 6, "-", ln=True);
                return
            filenames = [f.strip() for f in str(val).split(',') if f.strip()]
            for fname in filenames:
                if self.project_folder_path:
                    clean_fname = fname.split('\\')[-1].split('/')[-1]
                    fpath = os.path.join(self.project_folder_path, clean_fname)
                    is_img = clean_fname.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))
                    if is_img and os.path.exists(fpath):
                        img_height = 80
                        if self.get_y() + img_height > self.page_break_trigger: self.add_page()
                        self.ln(2);
                        self.set_x(self.l_margin + 5)
                        try:
                            self.image(fpath, h=img_height)
                        except:
                            self.set_text_color(255, 0, 0)
                            self.cell(0, 6, self._clean(f"[Fehler: {clean_fname}]"), ln=True)
                            self.set_text_color(0)
                        self.ln(2);
                        self.set_font('Arial', 'I', 8);
                        self.set_x(self.l_margin + 5)
                        self.cell(0, 5, self._clean(clean_fname), ln=True);
                        self.set_font('Arial', '', 10);
                        self.ln(4)
                    else:
                        self.set_x(self.l_margin + 5);
                        icon = "[DATEI]" if os.path.exists(fpath) else "[FEHLT]"
                        self.cell(0, 6, self._clean(f"{icon} {clean_fname}"), ln=True)
            return

        if val is True: val = "Ja"
        if val is False: val = "Nein"
        if val == "": val = "-"
        if val is None: val = "-"
        display_val = self._clean(val)
        self.set_x(self.l_margin + 5)
        self.multi_cell(0, 6, display_val)