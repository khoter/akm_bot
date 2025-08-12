from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName, PdfObject, PdfString

try:
    import fitz 
    _HAS_PYMUPDF = True
except Exception:
    _HAS_PYMUPDF = False

def _flatten_pdf_pymupdf(src: str, dst: str) -> None:
    """Сплющить формы в dst с помощью PyMuPDF (не поверх src!)."""
    if not _HAS_PYMUPDF:
        return
    doc = fitz.open(src)
    try:
        for page in doc:
            for w in page.widgets() or []:
                try:
                    w.update()
                except Exception:
                    pass
                try:
                    w.flatten()
                except Exception:
                    pass
        doc.save(dst)
    finally:
        doc.close()

def fill_pdf(template_path: str, output_path: str, data: dict, *, flatten: bool = True) -> None:
    """
    Заполняет PDF-форму и (опционально) сплющивает её в обычный PDF.
    """
    pdf = PdfReader(template_path)

    for page in pdf.pages:
        for annot in (page.Annots or []):
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

                on_val = PdfName('Yes')
                try:
                    if '/AP' in annot and '/N' in annot.AP and annot.AP.N:
                        on_val = next(iter(annot.AP.N.keys()))
                except Exception:
                    pass

                if '/AP' not in annot or not getattr(annot.AP, 'N', None) or on_val not in annot.AP.N:
                    annot.AP = PdfDict(N=PdfDict())
                    annot.AP.N[PdfName('Off')] = PdfDict(
                        Type=PdfName('XObject'),
                        Subtype=PdfName('Form'),
                        BBox='0 0 15 15',
                        Resources=PdfDict()
                    )
                    annot.AP.N[on_val] = PdfDict(
                        Type=PdfName('XObject'),
                        Subtype=PdfName('Form'),
                        BBox='0 0 15 15',
                        Resources=PdfDict()
                    )

                state = on_val if checked else PdfName('Off')
                annot.update({PdfName('V'): state, PdfName('AS'): state})

    if pdf.Root.AcroForm:
        pdf.Root.AcroForm.update(PdfDict(NeedAppearances=PdfObject('true')))

    PdfWriter(output_path, trailer=pdf).write()

    if flatten and _HAS_PYMUPDF:
        tmp_out = output_path + ".flat.tmp.pdf"
        try:
            _flatten_pdf_pymupdf(output_path, tmp_out)
            import os
            os.replace(tmp_out, output_path)
        except Exception as e:
            print("PyMuPDF flatten failed:", e)
            try:
                import os
                if os.path.exists(tmp_out):
                    os.remove(tmp_out)
            except Exception:
                pass