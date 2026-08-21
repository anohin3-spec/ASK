"""
Сжатие PDF перед сохранением в облако или локально.

Раньше использовался только pikepdf (пересжатие потоков) — на сканах с JPEG внутри
выигрыш почти нулевой. Сейчас основной путь — PyMuPDF: rewrite_images() перекодирует
картинки в PDF (как типичные «сжималки»), плюс deflate/garbage.

При ошибке или отсутствии pymupdf пробуем pikepdf. Если ни один вариант не меньше
исходника — сохраняем файл как есть.
"""
from __future__ import annotations

import os
from io import BytesIO
from typing import Optional

# Баланс размер/качество (можно ослабить quality или dpi_target для ещё меньшего веса)
_PDF_JPEG_QUALITY = 72
_PDF_DPI_THRESHOLD = 120
_PDF_DPI_TARGET = 96


def _is_pdf_magic(data: bytes) -> bool:
    if not data:
        return False
    head = data.lstrip(b"\r\n\x00")[:32]
    return head.startswith(b"%PDF")


def _compress_pdf_pikepdf(raw: bytes) -> Optional[bytes]:
    try:
        import pikepdf
    except ImportError:
        return None
    try:
        pdf = pikepdf.open(BytesIO(raw))
        out = BytesIO()
        pdf.save(out, compress_streams=True)
        pdf.close()
        data = out.getvalue()
        return data if _is_pdf_magic(data) else None
    except Exception:
        return None


def _compress_pdf_pymupdf(raw: bytes) -> Optional[bytes]:
    try:
        import fitz
    except ImportError:
        return None
    doc = None
    try:
        doc = fitz.open(stream=raw, filetype="pdf")
        # Главный выигрыш на сканах: пережим встроенных изображений
        try:
            doc.rewrite_images(
                dpi_threshold=_PDF_DPI_THRESHOLD,
                dpi_target=_PDF_DPI_TARGET,
                quality=_PDF_JPEG_QUALITY,
                lossy=True,
                lossless=True,
                bitonal=True,
                color=True,
                gray=True,
            )
        except Exception:
            pass
        data = doc.write(
            garbage=4,
            clean=True,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            compression_effort=6,
        )
        doc.close()
        doc = None
        if not data or not _is_pdf_magic(data):
            return None
        # Проверка, что документ открывается
        test = fitz.open(stream=data, filetype="pdf")
        n = test.page_count
        test.close()
        if n < 1:
            return None
        return data
    except Exception:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
        return None


def read_file_bytes_for_upload(source_path: str) -> bytes:
    ext = os.path.splitext(source_path)[1].lower()
    with open(source_path, "rb") as f:
        original = f.read()
    if ext != ".pdf" or not original or not _is_pdf_magic(original):
        return original

    candidates: list[tuple[int, bytes]] = [(len(original), original)]

    z = _compress_pdf_pymupdf(original)
    if z is not None:
        candidates.append((len(z), z))

    z2 = _compress_pdf_pikepdf(original)
    if z2 is not None:
        candidates.append((len(z2), z2))

    candidates.sort(key=lambda t: t[0])
    best_size, best_data = candidates[0]
    if best_size < len(original):
        return best_data
    return original
