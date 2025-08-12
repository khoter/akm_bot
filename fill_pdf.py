from __future__ import annotations
import os
from typing import Dict, Any

from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName, PdfObject, PdfString
import fitz  

OFF = PdfName("Off")

def _boolish(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in {"1", "true", "on", "yes", "y", "да", "ok"}

def _fill_with_pdfrw(template_path: str, out_path: str, data: Dict[str, Any]) -> None:
    pdf = PdfReader(template_path)

    for page in pdf.pages:
        annots = getattr(page, "Annots", None)
        if not annots:
            continue

        for annot in annots:
            if annot.Subtype != PdfName("Widget") or not getattr(annot, "T", None):
                continue

            key = annot.T.to_unicode().strip("()")
            ft = getattr(annot, "FT", None)

            if ft == PdfName("Tx") and key in data:
                annot.update(
                    PdfDict(
                        V=PdfString.encode(str(data[key])),
                        AP=""  
                    )
                )

            elif ft == PdfName("Btn"):
                checked = _boolish(data.get(key, ""))
                on_val = PdfName("Yes")
                try:
                    if "/AP" in annot and "/N" in annot.AP:
                        on_val = next(iter(annot.AP.N.keys()))
                except Exception:
                    pass

                state = on_val if checked else OFF
                annot.update(PdfDict(V=state, AS=state))

    if getattr(pdf.Root, "AcroForm", None):
        pdf.Root.AcroForm.update(PdfDict(NeedAppearances=PdfObject("false")))
    PdfWriter(out_path, trailer=pdf).write()

def _flatten_with_pymupdf(in_path: str, out_path: str) -> None:
    doc = fitz.open(in_path)

    for page in doc:  
        widgets = page.widgets() or [] 
        for w in widgets:
            rect = w.rect
            name = (w.field_name or "").strip()
            ftype = w.field_type

            if ftype == fitz.PDF_WIDGET_TYPE_TEXT:
                val = (w.field_value or "").strip()
                if val:
                    page.insert_textbox(
                        rect,
                        val,
                        fontname="helv",
                        fontsize=10,
                        align=fitz.TEXT_ALIGN_LEFT,
                    )

            elif ftype == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                on = (w.field_value or "").strip().lower() not in {"", "off"}
                page.draw_rect(rect, width=0.8) 
                if on:
                    cx = (rect.x0 + rect.x1) / 2
                    cy = (rect.y0 + rect.y1) / 2
                    page.draw_line((rect.x0 + 1.5, cy), (cx - 0.5, rect.y1 - 1.5), width=1.3)
                    page.draw_line((cx - 0.5, rect.y1 - 1.5), (rect.x1 - 1.5, rect.y0 + 1.5), width=1.3)

            elif ftype == fitz.PDF_WIDGET_TYPE_RADIOBUTTON:
                sel = (w.field_value or "").strip() not in {"", "off"}
                page.draw_oval(rect, width=0.8)
                if sel:
                    inset = rect + fitz.Rect(3, 3, -3, -3)
                    page.draw_oval(inset, fill=1)

        for w in widgets:
            try:
                w.remove_from_page()
            except Exception:
                if getattr(w, "annot", None):
                    try:
                        page.delete_annot(w.annot)
                    except Exception:
                        pass

        annot = page.first_annot
        while annot:
            nxt = annot.next
            if annot.type[0] == fitz.PDF_ANNOT_WIDGET:
                try:
                    page.delete_annot(annot)
                except Exception:
                    pass
            annot = nxt

    try:
        root = doc.pdf_catalog()  
        if "/AcroForm" in root:
            xref = root["/AcroForm"]
            del root["/AcroForm"]
            try:
                doc.xref_delete(xref)
            except Exception:
                pass
    except Exception:
        pass

    doc.save(out_path, deflate=True, clean=True, garbage=4)
    doc.close()

def fill_pdf(template_path: str, output_path: str, data: Dict[str, Any]) -> None:
    """
    1) Заполняет поля PDF формата AcroForm (текст / чекбоксы).
    2) ФЛЕТТЕНИТ: печатает значения прямо в страницы и удаляет виджеты / AcroForm.
    В результате PDF больше нельзя редактировать ни в одном viewer’е.
    """
    tmp = output_path + ".__tmp_fill.pdf"
    _fill_with_pdfrw(template_path, tmp, data)
    try:
        _flatten_with_pymupdf(tmp, output_path)
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
