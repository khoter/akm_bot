from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName, PdfObject, PdfString

OFF = PdfName('Off')


try:
    import fitz  
    _HAS_PYMUPDF = True
except Exception:
    _HAS_PYMUPDF = False


def _flatten_pdf_pymupdf(path_in: str, path_out: str | None = None) -> None:
    """Сплющить формы с помощью PyMuPDF. Если path_out не указан — перезаписываем файл."""
    if not _HAS_PYMUPDF:
        return
    out = path_out or path_in
    doc = fitz.open(path_in)
    try:
        for page in doc:
            for w in page.widgets():
                try:
                    w.update()
                except Exception:
                    pass
                try:
                    w.flatten()
                except Exception:
                    pass

        doc.save(out)  
    finally:
        doc.close()


def fill_pdf(template_path: str, output_path: str, data: dict, *, flatten: bool = True) -> None:
    """Заполняет PDF-форму и (опционально) сплющивает её в статический PDF."""
    pdf = PdfReader(template_path)

    for page in pdf.pages:
        for annot in page.Annots or []:
            if annot.Subtype != PdfName('Widget') or not annot.T:
                continue

            key = annot.T.to_unicode().strip('()')
            ft  = annot.FT

            if ft == PdfName('Tx') and key in data:
                annot.update(PdfDict(
                    V=PdfString.encode(str(data[key])),
                    AP=''   
                ))

            elif ft == PdfName('Btn'):
                checked = str(data.get(key, '')).lower() in {'true', 'on', '1', 'yes'}
                if '/AP' in annot and '/N' in annot.AP and annot.AP.N:
                    on_val = next(iter(annot.AP.N.keys()))
                else:
                    on_val = PdfName('Yes')

                if '/AP' not in annot or on_val not in annot.AP.N:
                    off_form = PdfDict(Type=PdfName('XObject'), Subtype=PdfName('Form'),
                                       BBox='0 0 15 15', Resources=PdfDict())
                    yes_form = PdfDict(Type=PdfName('XObject'), Subtype=PdfName('Form'),
                                       BBox='0 0 15 15',
                                       Resources=PdfDict(ProcSet=[PdfName('PDF')]),
                                       stream=b'q BT /ZaDb 14 Tf 1 1 Td (\x04) Tj ET Q')
                    annot.AP = PdfDict(N=PdfDict())
                    annot.AP.N[PdfName('Off')] = off_form
                    annot.AP.N[on_val] = yes_form

                state = on_val if checked else PdfName('Off')
                annot.update({PdfName('V'): state, PdfName('AS'): state})

    if pdf.Root.AcroForm:
        pdf.Root.AcroForm.update(PdfDict(NeedAppearances=PdfObject('true')))

    PdfWriter(output_path, trailer=pdf).write()

    if flatten and _HAS_PYMUPDF:
        _flatten_pdf_pymupdf(output_path)