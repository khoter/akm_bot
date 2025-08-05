from pdfrw import PdfReader, PdfWriter, PdfDict

def fill_pdf(template_path, output_path, data):
    template_pdf = PdfReader(template_path)
    annotations = template_pdf.pages[0]['/Annots']

    for annotation in annotations:
        if annotation['/Subtype'] == '/Widget' and annotation['/T']:
            key = annotation['/T'][1:-1]  # remove parentheses
            if key in data:
                value = data[key]
                if isinstance(value, bool):
                    annotation.update(PdfDict(AS='/Yes' if value else '/Off'))
                else:
                    annotation.update(PdfDict(V=str(value), AP=''))

    PdfWriter(output_path, trailer=template_pdf).write()
