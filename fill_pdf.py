from __future__ import annotations
from typing import Dict, List, Tuple

from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName, PdfString, PageMerge
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import io
import math


DEFAULT_FONT = "Helvetica"  
TEXT_SIZE = 12
CHECK_SIZE = 10 

def _rect_to_xy(rect) -> Tuple[float, float, float, float]:
    # rect: [llx, lly, urx, ury]
    llx, lly, urx, ury = [float(x) for x in rect]
    return llx, lly, urx, ury

def _fit_text(canvas_obj, text: str, x: float, y: float, w: float, h: float):
    """Пишем текст внутри прямоугольника поля, пытаемся подстроить размер."""
    if not text:
        return
    pad_x = 2
    pad_y = 1
    max_w = max(1.0, w - 2 * pad_x)
    max_h = max(1.0, h - 2 * pad_y)

    fs = TEXT_SIZE
    while fs > 6:
        canvas_obj.setFont(DEFAULT_FONT, fs)
        tw = canvas_obj.stringWidth(text, DEFAULT_FONT, fs)
        if tw <= max_w and fs <= max_h: 
            break
        fs -= 1

    canvas_obj.drawString(x + pad_x, y + (h - fs) / 2.0, text)

def _draw_check(canvas_obj, x: float, y: float, w: float, h: float, checked: bool):
    if not checked:
        return
    canvas_obj.setLineWidth(1)
    x1 = x + w * 0.2
    y1 = y + h * 0.5
    x2 = x + w * 0.45
    y2 = y + h * 0.25
    x3 = x + w * 0.8
    y3 = y + h * 0.75
    canvas_obj.line(x1, y1, x2, y2)
    canvas_obj.line(x2, y2, x3, y3)

def fill_pdf(template_path: str, output_path: str, data: Dict) -> None:
    """
    1) Читает шаблон с AcroForm.
    2) Для каждого поля берёт значение из data (по имени/ключу).
       - Текстовые: печатаем текст.
       - Чекбоксы: рисуем галочку, если truthy ('on', True, 'yes', '1').
    3) Полностью удаляем все поля и AcroForm.
    4) Сохраняем плоский PDF.
    """
    pdf = PdfReader(template_path)
    pages = pdf.pages

    draw_plan: Dict[int, List[Tuple[str, float, float, float, float, object]]] = {}

    for p_idx, page in enumerate(pages):
        annots = page.Annots
        if not annots:
            continue
        to_keep = []
        for annot in annots:
            try:
                if annot.Subtype != PdfName('Widget') or not annot.T:
                    to_keep.append(annot)
                    continue

                key = annot.T.to_unicode().strip('()')
                rect = annot.Rect
                if not rect:
                    to_keep.append(annot)
                    continue
                llx, lly, urx, ury = _rect_to_xy(rect)
                w = max(1.0, urx - llx)
                h = max(1.0, ury - lly)

                ft = annot.FT
                val = data.get(key)

                if ft == PdfName('Tx'):
                    text_val = "" if val is None else str(val)
                    draw_plan.setdefault(p_idx, []).append(("text", llx, lly, w, h, text_val))
                elif ft == PdfName('Btn'):
                    sval = str(val).strip().lower() if val is not None else ""
                    checked = sval in {"true", "on", "1", "yes", "да", "y", "ok"}
                    draw_plan.setdefault(p_idx, []).append(("check", llx, lly, w, h, checked))
                else:
                    pass
            except Exception:
                to_keep.append(annot)
        page.Annots = [a for a in (page.Annots or []) if getattr(a, "Subtype", None) != PdfName("Widget")]

    overlays: List[io.BytesIO] = []
    for p_idx, page in enumerate(pages):

        mediabox = page.MediaBox
        pw = float(mediabox[2]) - float(mediabox[0])
        ph = float(mediabox[3]) - float(mediabox[1])

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(pw, ph))
        c.setFont(DEFAULT_FONT, TEXT_SIZE)

        for item in draw_plan.get(p_idx, []):
            kind, x, y, w, h, val = item
            if kind == "text":
                _fit_text(c, val, x, y, w, h)
            elif kind == "check":
                _draw_check(c, x, y, w, h, bool(val))

        c.showPage()
        c.save()
        buf.seek(0)
        overlays.append(buf)

    if getattr(pdf.Root, "AcroForm", None):
        try:
            del pdf.Root.AcroForm
        except Exception:
            pdf.Root.AcroForm = PdfDict() 

    for p_idx, page in enumerate(pages):
        if p_idx < len(overlays):
            overlay_reader = PdfReader(overlays[p_idx])
            overlay_page = overlay_reader.pages[0]
            PageMerge(page).add(overlay_page, prepend=False).render()

    PdfWriter(output_path, trailer=pdf).write()
