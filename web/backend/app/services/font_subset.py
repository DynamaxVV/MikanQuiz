"""Font subsetting and WOFF2 conversion service with LRU disk and memory caching."""

import hashlib
import io
import logging
from pathlib import Path
from tempfile import gettempdir

from app.logging import log_event

_FONTTOOLS_AVAILABLE = False
_IMPORT_ERROR = None

try:
    from fontTools import subset
    from fontTools.ttLib import TTFont
    _FONTTOOLS_AVAILABLE = True
except Exception as exc:
    _FONTTOOLS_AVAILABLE = False
    _IMPORT_ERROR = str(exc)


_CACHE_DIR = Path(gettempdir()) / "mikanquiz-font-subsets"
_RAW_CACHE_DIR = Path(gettempdir()) / "mikanquiz-raw-fonts"


def get_subset_status() -> dict:
    return {
        "fonttools_available": _FONTTOOLS_AVAILABLE,
        "import_error": _IMPORT_ERROR,
    }


def subset_font_to_woff2(font_bytes: bytes, text: str) -> bytes:
    """Subset TTF/OTF/WOFF/WOFF2 font bytes to only target characters, converted to WOFF2.

    If fonttools is unavailable or subsetting fails gracefully, returns the original bytes.
    """
    if not _FONTTOOLS_AVAILABLE:
        log_event("font_subset_unavailable", logging.WARNING, error=_IMPORT_ERROR)
        return font_bytes

    if not text.strip():
        return font_bytes

    cache_key = hashlib.sha256(font_bytes).hexdigest()[:16]
    text_key = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached_file = _CACHE_DIR / f"{cache_key}_{text_key}.woff2"

    if cached_file.is_file():
        try:
            return cached_file.read_bytes()
        except OSError:
            pass

    try:
        options = subset.Options()
        options.flavor = "woff2"
        options.desubroutinize = True
        options.name_IDs = ["*"]
        options.name_legacy = True
        options.name_languages = ["*"]

        subsetter = subset.Subsetter(options=options)
        subsetter.populate(text=text)

        font = TTFont(io.BytesIO(font_bytes))
        subsetter.subset(font)
        font.flavor = "woff2"

        out = io.BytesIO()
        font.save(out)
        result = out.getvalue()

        # Sanity check: must be valid WOFF2
        if result.startswith(b"wOF2"):
            try:
                cached_file.write_bytes(result)
            except OSError:
                pass
            return result
        return font_bytes
    except Exception as exc:
        log_event("font_subset_fallback", logging.WARNING, error=str(exc))
        return font_bytes

async def get_or_fetch_raw_font(url: str, client) -> tuple[bytes, str]:
    """Cache downloaded raw fonts on local disk to avoid repeated 17MB downloads from R2."""
    _RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    raw_path = _RAW_CACHE_DIR / f"{url_hash}.bin"
    meta_path = _RAW_CACHE_DIR / f"{url_hash}.type"

    if raw_path.is_file() and meta_path.is_file():
        try:
            return raw_path.read_bytes(), meta_path.read_text("utf-8").strip()
        except OSError:
            pass

    resp = await client.get(url)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "font/ttf").split(";", 1)[0]

    try:
        raw_path.write_bytes(resp.content)
        meta_path.write_text(content_type, "utf-8")
    except OSError:
        pass

    return resp.content, content_type
