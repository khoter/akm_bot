from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName

def fill_pdf(template_path, output_path, data):
    template_pdf = PdfReader(template_path)
    annotations = template_pdf.pages[0].get('/Annots') or []

    for annotation in annotations:
        if annotation.get('/Subtype') != '/Widget' or not annotation.get('/T'):
            continue

        key_raw = annotation['/T']
        key = key_raw.decode('utf-8') if hasattr(key_raw, 'decode') else str(key_raw)
        key = key.strip('()')

        # Текстовые поля
        if annotation.get('/FT') == '/Tx':
            if key in data:
                annotation.update(PdfDict(V=str(data[key]), AP=''))

        # Чекбоксы
        elif annotation.get('/FT') == '/Btn':
            value = data.get(key, False)
            checked = str(value).lower() in ['true', 'on', '1', 'yes']
            annotation.update({
                PdfName('V'): PdfName('Yes') if checked else PdfName('Off'),
                PdfName('AS'): PdfName('Yes') if checked else PdfName('Off'),
            })

    PdfWriter(output_path, trailer=template_pdf).write()