from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName

YES  = PdfName('Yes')
OFF  = PdfName('Off')

def fill_pdf(template_path: str, output_path: str, data: dict) -> None:
    pdf = PdfReader(template_path)
    annotations = pdf.pages[0].get('/Annots') or []

    for annot in annotations:
        # интересуют только поля-виджеты с именем (/T)
        if annot.get('/Subtype') != PdfName('Widget') or not annot.get('/T'):
            continue

        # /T может быть PdfString или уже строкой
        key_raw = annot['/T']
        key = key_raw.to_unicode() if hasattr(key_raw, 'to_unicode') else str(key_raw)
        key = key.strip('()')           # убираем скобки, если остались

        ft = annot.get('/FT')           # тип поля

        # ───────── текстовые поля ─────────
        if ft == PdfName('Tx') and key in data:
            annot.update(PdfDict(V=str(data[key]), AP=''))

        # ───────── чекбоксы ───────────────
        elif ft == PdfName('Btn'):
            checked = str(data.get(key, '')).lower() in {'true', 'on', '1', 'yes'}
            state = YES if checked else OFF
            annot.update({PdfName('V'): state, PdfName('AS'): state})

    PdfWriter(output_path, trailer=pdf).write()