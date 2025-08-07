from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName, PdfObject, PdfString

OFF = PdfName('Off')


def fill_pdf(template_path: str, output_path: str, data: dict) -> None:
    """Заполняет PDF‑форму. Для чекбоксов берём «включённое» значение
    прямо из /AP, поэтому работает с любым именем (Yes, On, 1 …)."""

    pdf = PdfReader(template_path)

    for page in pdf.pages:
        for annot in page.Annots or []:
            if annot.Subtype != PdfName('Widget') or not annot.T:
                continue

            key = annot.T.to_unicode().strip('()')
            ft  = annot.FT

            # ─── текстовое поле ───────────────────────────────────────
            if ft == PdfName('Tx') and key in data:
                annot.update(PdfDict(
                    V=PdfString.encode(str(data[key])),
                    AP=''   # сброс старого вида
                ))

            # ─── чекбокс ─────────────────────────────────────────────
            elif ft == PdfName('Btn'):
                checked = str(data.get(key, '')).lower() in {'true', 'on', '1', 'yes'}

                # «Включённое» состояние берём из первого ключа /AP.N
                if '/AP' in annot and '/N' in annot.AP:
                    on_val = next(iter(annot.AP.N.keys()))
                else:
                    on_val = PdfName('Yes')   # дефолт, если /AP отсутствует

                state = on_val if checked else OFF
                annot.update({PdfName('V'): state, PdfName('AS'): state})

    # Просим ридер перерисовать внешние виды
    if pdf.Root.AcroForm:
        pdf.Root.AcroForm.update(PdfDict(NeedAppearances=PdfObject('true')))

    PdfWriter(output_path, trailer=pdf).write()