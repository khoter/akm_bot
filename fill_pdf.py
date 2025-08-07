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
                if '/AP' not in annot:
                    # квадратик для Off
                    off_appearance = PdfDict(
                        N=PdfDict(Off=PdfDict(
                            Type=PdfName('XObject'), Subtype=PdfName('Form'),
                            BBox='0 0 20 20', Resources=PdfDict()))
                    )
                     # галочка (ZapfDingbats, символ 4)
                    yes_appearance = PdfDict(
                        Type=PdfName('XObject'), Subtype=PdfName('Form'),
                        BBox='0 0 20 20',
                        Resources=PdfDict(ProcSet=[PdfName('PDF')]),
                        stream='q BT /ZaDb 18 Tf 3 3 Td (\x4) Tj ET Q'
                    )
                    off_appearance.N.Yes = yes_appearance
                    annot.AP = off_appearance

                annot.update({PdfName('V'): state, PdfName('AS'): state})

    # заставляем ридер отрисовать новые значения
    acro = pdf.Root.AcroForm
    if acro:
        acro.update(PdfDict(NeedAppearances=PdfObject("true")))

    PdfWriter(output_path, trailer=pdf).write()