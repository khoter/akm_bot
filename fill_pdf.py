from __future__ import annotations
from typing import Dict, Any
import os, uuid

from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName, PdfObject, PdfString
import fitz  

OFF = PdfName("Off")

def _boolish(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "true", "on", "yes", "y", "да"}

def _fill_pdfrw(template_path: str, out_path: str, data: Dict[str, Any]) -> None:
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
                a.update(PdfDict(V=PdfString.encode(str(data[key]))))

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
        pdf.Root.AcroForm.update(PdfDict(NeedAppearances=PdfObject("true")))
    PdfWriter(out_path, trailer=pdf).write()

def _ensure_widget_appearances(path_in: str, path_out: str) -> None:
    """Открываем PDF и принудительно генерим AP для всех виджетов."""
    doc = fitz.open(path_in)
    for page in doc:
        widgets = page.widgets() or []
        for w in widgets:
            w.update()  

    doc.save(path_out, deflate=True, clean=True, garbage=4)
    doc.close()

def _flatten_reimport(path_in: str, path_out: str) -> None:
    """Финально «запекаем»: переносим отрисованные страницы в новый PDF."""
    src = fitz.open(path_in)
    dst = fitz.open()
    for i in range(len(src)):
        sp = src[i]
        dp = dst.new_page(width=sp.rect.width, height=sp.rect.height)
        dp.show_pdf_page(dp.rect, src, i)
    dst.save(path_out, deflate=True, clean=True, garbage=4)
    dst.close()
    src.close()

def fill_pdf(template_path: str, output_path: str, data: Dict[str, Any]) -> None:
    """Заполнить форму и получить обычный нередактируемый PDF (без форм/аннотаций)."""
    base = output_path + f".tmp-{uuid.uuid4().hex}"
    tmp1 = base + ".pdfrw.pdf"     
    tmp2 = base + ".ap.pdf"        
    try:
        _fill_pdfrw(template_path, tmp1, data)
        _ensure_widget_appearances(tmp1, tmp2)   
        _flatten_reimport(tmp2, output_path)     
    finally:
        for p in (tmp1, tmp2):
            try:
                os.remove(p)
            except Exception:
                pass