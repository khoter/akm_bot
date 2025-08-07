from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName, PdfObject, PdfString

YES = PdfName("Yes")
OFF = PdfName("Off")

def fill_pdf(template_path: str, output_path: str, data: dict) -> None:
    pdf = PdfReader(template_path)

    for page in pdf.pages:
        for annot in page.Annots or []:
            if annot.Subtype != PdfName("Widget") or not annot.T:
                continue

            key = annot.T.to_unicode().strip("()")
            ft  = annot.FT

            # ───── текстовое поле
            if ft == PdfName("Tx") and key in data:
                annot.update(PdfDict(
                    V=PdfString.encode(str(data[key])),
                    AP=""                      # сброс старого вида
                ))

            # ───── чекбокс
            elif ft == PdfName("Btn"):
                checked = str(data.get(key, "")).lower() in {"true", "on", "1", "yes"}
                state = YES if checked else OFF
                annot.update({PdfName("V"): state, PdfName("AS"): state})
                if '/AP' in annot:                          # 👈 сбросим старый вид
                    del annot['/AP']

    # заставляем ридер отрисовать новые значения
    acro = pdf.Root.AcroForm
    if acro:
        acro.update(PdfDict(NeedAppearances=PdfObject("true")))

    PdfWriter(output_path, trailer=pdf).write()