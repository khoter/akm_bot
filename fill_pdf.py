# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from typing import Any

from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName, PdfString, PdfObject
import fitz  


OFF = PdfName("Off")


def _boolish(v: Any) -> bool:
    """Интерпретировать значение как булево для чекбоксов."""
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "on", "да", "y", "д", "угу"}


def _fill_with_pdfrw(template_path: str, tmp_path: str, data: dict) -> None:
    """
    1) Читает шаблон
    2) Записывает значения в поля формы (/V), у чекбоксов также /AS
    3) Включает NeedAppearances, чтобы вьюверы могли сгенерировать /AP при необходимости
    4) Сохраняет во временный PDF (без flatten)
    """
    pdf = PdfReader(template_path)

    for page in pdf.pages:
        annots = getattr(page, "Annots", None)
        if not annots:
            continue

        for annot in annots:
            try:
                if annot.Subtype != PdfName("Widget") or not getattr(annot, "T", None):
                    continue

                key = annot.T.to_unicode().strip("()")
                ft = getattr(annot, "FT", None)

                if ft == PdfName("Tx"):
                    if key in data and data[key] is not None:
                        annot.update(
                            PdfDict(
                                V=PdfString.encode(str(data[key]))
                            )
                        )

                elif ft == PdfName("Btn"):
                    checked = _boolish(data.get(key, ""))
                    on_name = None

                    ap = getattr(annot, "AP", None)
                    if ap and getattr(ap, "N", None):
                        for k in ap.N.keys():
                            if k != OFF:
                                on_name = k
                                break

                    if on_name is None:
                        on_name = PdfName("Yes")

                    state = on_name if checked else OFF
                    annot.update(PdfDict(V=state, AS=state))

            except Exception:
                continue

    if getattr(pdf.Root, "AcroForm", None) is not None:
        pdf.Root.AcroForm.update(PdfDict(NeedAppearances=PdfObject("true")))

    PdfWriter(tmp_path, trailer=pdf).write()


def _materialize_and_flatten(in_path: str, out_path: str) -> None:
    """
    Через PyMuPDF:
      - форсируем генерацию /AP (update) для всех виджетов;
      - сплющиваем виджеты (flatten), превращая их в «краску» на странице.
    """
    doc = fitz.open(in_path)

    for page in doc:
        widgets = page.widgets() or []
        for w in widgets:
            try:
                w.update()  
            except Exception:
                pass
        try:
            page.update_widgets()
        except Exception:
            pass

    for page in doc:
        widgets = page.widgets() or []
        for w in widgets:
            try:
                w.flatten()
            except Exception:
                pass

    doc.save(out_path, incremental=False)
    doc.close()


def fill_pdf(template_path: str, output_path: str, data: dict) -> None:
    """
    Главная функция:
      - заполнение полей формы;
      - генерация внешних видов;
      - сплющивание в «обычный» PDF без форм.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    tmp_path = output_path + ".tmp_pdfrw.pdf"

    _fill_with_pdfrw(template_path, tmp_path, data)
    _materialize_and_flatten(tmp_path, output_path)

    try:
        os.remove(tmp_path)
    except OSError:
        pass
