from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName, PdfObject, PdfString
import os, shutil, subprocess

def _flatten_pdf_ghostscript(src: str, dst: str) -> None:
    """
    Сплющить PDF через Ghostscript (pdfwrite).
    Убирает формы и аннотации, сохраняет вектор/текст где возможно.
    """
    if not shutil.which("gs"):
        raise RuntimeError("Ghostscript (gs) не найден в PATH")
    cmd = [
        "gs",
        "-dBATCH", "-dNOPAUSE", "-dSAFER",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        f"-sOutputFile={dst}",
        src,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def fill_pdf(template_path: str, output_path: str, data: dict, *, flatten: bool = True) -> None:
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

                try:
                    if '/AP' not in annot or not getattr(annot.AP, 'N', None) or on_val not in annot.AP.N:
                        annot.AP = PdfDict(N=PdfDict())
                        annot.AP.N[PdfName('Off')] = PdfDict(Type=PdfName('XObject'),
                                                             Subtype=PdfName('Form'),
                                                             BBox='0 0 15 15',
                                                             Resources=PdfDict())
                        annot.AP.N[on_val] = PdfDict(Type=PdfName('XObject'),
                                                     Subtype=PdfName('Form'),
                                                     BBox='0 0 15 15',
                                                     Resources=PdfDict())
                except Exception:
                    pass

                state = on_val if checked else PdfName('Off')
                annot.update({PdfName('V'): state, PdfName('AS'): state})

    if pdf.Root.AcroForm:
        pdf.Root.AcroForm.update(PdfDict(NeedAppearances=PdfObject('true')))

    PdfWriter(output_path, trailer=pdf).write()

    if flatten:
        tmp = output_path + ".gs.tmp.pdf"
        try:
            _flatten_pdf_ghostscript(output_path, tmp)
            os.replace(tmp, output_path)
        except Exception as e:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            raise