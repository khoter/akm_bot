from __future__ import annotations
from typing import Dict, Any
import os

from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName, PdfObject, PdfString
import fitz  

OFF = PdfName("Off")

def _boolish(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "true", "on", "yes", "y", "да"}

def _fill_acroform(template_path: str, out_path: str, data: Dict[str, Any]) -> None:
    pdf = PdfReader(template_path)

    for page in pdf.pages:
        annots = getattr(page, "Annots", None)
        if not annots:
            continue

        for a in annots:
            if a.Subtype != PdfName("Widget") or not getattr(a, "T", None):
                continue
            key = a.T.to_unicode().strip("()")
            ft  = getattr(a, "FT", None)

            if ft == PdfName("Tx") and key in data:
                a.update(PdfDict(
                    V=PdfString.encode(str(data[key])),
                    AP=""  
                ))

            elif ft == PdfName("Btn"):
                checked = _boolish(data.get(key, ""))
                on_val = PdfName("Yes")
                try:
                    if "/AP" in a and "/N" in a.AP:
                        on_val = next(iter(a.AP.N.keys()))
                except Exception:
                    pass
                state = on_val if checked else OFF
                a.update(PdfDict(V=state, AS=state))

    if getattr(pdf.Root, "AcroForm", None):
        pdf.Root.AcroForm.update(PdfDict(NeedAppearances=PdfObject("false")))

    PdfWriter(out_path, trailer=pdf).write()

def _flatten_reimport(in_path: str, out_path: str) -> None:
    """Полный флеттенинг: переносим каждую страницу как изображённую в новый PDF.
    Форм, аннотаций и AcroForm в результате не остаётся вообще.
    """
    src = fitz.open(in_path)
    dst = fitz.open()
    for i in range(len(src)):
        sp = src[i]
        dp = dst.new_page(width=sp.rect.width, height=sp.rect.height)
        dp.show_pdf_page(dp.rect, src, i)
    dst.save(out_path, deflate=True, clean=True, garbage=4)  
    dst.close()
    src.close()

def fill_pdf(template_path: str, output_path: str, data: Dict[str, Any]) -> None:
    """Заполнить и «запечь» PDF-форму в обычный нередактируемый PDF."""
    tmp = output_path + ".tmpfill.pdf"
    _fill_acroform(template_path, tmp, data)
    try:
        _flatten_reimport(tmp, output_path)
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass