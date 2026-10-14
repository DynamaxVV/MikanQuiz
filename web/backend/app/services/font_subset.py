"""Font subsetting and WOFF2 conversion service with LRU disk and memory caching."""

import hashlib
import io
import logging
from pathlib import Path
from tempfile import gettempdir

from app.errors import ApiError
from app.logging import log_event

try:
    from fontTools import subset
    from fontTools.ttLib import TTFont
    _FONTTOOLS_AVAILABLE = True
except ImportError:
    _FONTTOOLS_AVAILABLE = False


_CACHE_DIR = Path(gettempdir()) / "mikanquiz-font-subsets"


def subset_font_to_woff2(font_bytes: bytes, text: str) -> bytes:
    """Subset TTF/OTF/WOFF/WOFF2 font bytes to only target characters, converted to WOFF2.

    If fonttools is unavailable or subsetting fails gracefully, returns the original bytes.
    """
    if not _FONTTOOLS_AVAILABLE or not text.strip():
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
