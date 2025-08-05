from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName

def fill_pdf(template_path, output_path, data):
    template_pdf = PdfReader(template_path)
    annotations = template_pdf.pages[0]['/Annots']

    for annotation in annotations:
        if annotation['/Subtype'] != '/Widget' or not annotation.get('/T'):
            continue

        key = annotation['/T'][1:-1]  # Убираем скобки с названия поля

        # Текстовые поля
        if annotation['/FT'] == '/Tx':
            if key in data:
                annotation.update(PdfDict(V=str(data[key]), AP=''))

        # Чекбоксы
        elif annotation['/FT'] == '/Btn':
            value = data.get(key, False)
            if str(value).lower() in ['true', 'on', '1', 'yes']:
                annotation.update({
                    PdfName('V'): PdfName('Yes'),
                    PdfName('AS'): PdfName('Yes')
                })
            else:
                annotation.update({
                    PdfName('V'): PdfName('Off'),
                    PdfName('AS'): PdfName('Off')
                })

    PdfWriter(output_path, trailer=template_pdf).write()