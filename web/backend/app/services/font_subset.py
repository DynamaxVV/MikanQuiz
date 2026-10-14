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
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
    _FONTTOOLS_AVAILABLE = True
except Exception as exc:
    _FONTTOOLS_AVAILABLE = False
    _IMPORT_ERROR = str(exc)


_CACHE_DIR = Path(gettempdir()) / "mikanquiz-font-subsets"
_RAW_CACHE_DIR = Path(gettempdir()) / "mikanquiz-raw-fonts"

# Fast in-memory subset cache: (url_hash_text_hash) -> validated WOFF2 bytes
_MEMORY_SUBSET_CACHE: dict[str, bytes] = {}
_VALIDATED_SUBSET_KEYS: set[str] = set()
_MAX_MEMORY_CACHE_ITEMS = 2000


def get_subset_status() -> dict:
    return {
        "fonttools_available": _FONTTOOLS_AVAILABLE,
        "import_error": _IMPORT_ERROR,
    }


def _cache_key_for(url: str, text: str) -> str:
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    text_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]
    return f"{url_hash}_{text_hash}"


def _unicode_cmap_with_legacy_gbk(font) -> dict[int, str]:
    """Expose Windows-GB format 2 mappings as Unicode for browser font subsetting."""
    character_map = dict(font.getBestCmap() or {})
    cmap_table = font.get("cmap")
    if cmap_table is None:
        return character_map

    legacy_tables = [
        table
        for table in cmap_table.tables
        if table.platformID == 3 and table.platEncID == 3 and table.format == 2
    ]
    if not legacy_tables:
        return character_map

    glyph_order = set(font.getGlyphOrder())
    for table in legacy_tables:
        for encoded_character, glyph_name in table.cmap.items():
            if glyph_name == ".notdef" or glyph_name not in glyph_order:
                continue
            try:
                encoded = (
                    bytes([encoded_character])
                    if encoded_character <= 0xFF
                    else encoded_character.to_bytes(2, "big")
                )
                unicode_character = encoded.decode("gbk")
            except (UnicodeDecodeError, OverflowError, ValueError):
                continue
            if len(unicode_character) == 1:
                character_map.setdefault(ord(unicode_character), glyph_name)

    if len(character_map) == len(font.getBestCmap() or {}):
        return character_map

    unicode_table = next(
        (
            table
            for table in cmap_table.tables
            if table.platformID == 3 and table.platEncID == 1 and table.format in (4, 12)
        ),
        None,
    )
    if unicode_table is None:
        unicode_table = CmapSubtable.newSubtable(4)
        unicode_table.platformID = 3
        unicode_table.platEncID = 1
        unicode_table.language = 0
        cmap_table.tables.append(unicode_table)
    unicode_table.cmap = character_map

    # The subset now has a real Unicode cmap. The legacy table uses GBK code values,
    # which would otherwise remain unrelated to the subset's Unicode glyph mappings.
    cmap_table.tables = [table for table in cmap_table.tables if table not in legacy_tables]
    return character_map


def _woff2_validation_error(data: bytes, text: str) -> str | None:
    """Return why a cached/generated WOFF2 cannot safely be used for this text."""
    if not data.startswith(b"wOF2"):
        return "missing WOFF2 signature"
    if not _FONTTOOLS_AVAILABLE:
        return "fontTools is unavailable for validation"

    font = None
    try:
        font = TTFont(io.BytesIO(data), lazy=False)
        font.ensureDecompiled()

        if "maxp" not in font:
            return "missing maxp table"
        glyph_count = font["maxp"].numGlyphs
        if glyph_count < 1 or glyph_count != len(font.getGlyphOrder()):
            return "invalid glyph count"

        character_map = font.getBestCmap() or {}
        mapped_text = [
            character_map.get(ord(character))
            for character in text
            if not character.isspace()
        ]
        if not any(glyph_name and glyph_name != ".notdef" for glyph_name in mapped_text):
            return "requested text has no Unicode glyphs"

        if "hhea" not in font or "hmtx" not in font:
            return "missing horizontal metrics"
        horizontal_metrics = font["hmtx"].metrics
        horizontal_limit = min(glyph_count, len(horizontal_metrics))
        horizontal_count = font["hhea"].numberOfHMetrics
        if horizontal_limit < 1 or not 1 <= horizontal_count <= horizontal_limit:
            return "invalid horizontal metric count"

        has_vhea = "vhea" in font
        has_vmtx = "vmtx" in font
        if has_vhea != has_vmtx:
            return "unpaired vertical metrics tables"
        if has_vhea:
            vertical_metrics = font["vmtx"].metrics
            vertical_limit = min(glyph_count, len(vertical_metrics))
            vertical_count = font["vhea"].numberOfVMetrics
            if vertical_limit < 1 or not 1 <= vertical_count <= vertical_limit:
                return "invalid vertical metric count"

        if "glyf" in font and len(font.getTableData("glyf")) <= 1:
            return "empty glyf table"

        return None
    except Exception as exc:
        return f"fontTools could not parse WOFF2: {exc}"
    finally:
        if font is not None:
            font.close()


def _discard_cached_subset(key: str) -> None:
    """Remove an invalid cache entry so it can be regenerated from the source font."""
    _MEMORY_SUBSET_CACHE.pop(key, None)
    _VALIDATED_SUBSET_KEYS.discard(key)
    try:
        (_CACHE_DIR / f"{key}.woff2").unlink(missing_ok=True)
    except OSError:
        pass


def _get_valid_cached_subset(key: str, text: str) -> bytes | None:
    """Read and validate a cached subset before returning it to the API or prewarmer."""
    data = _MEMORY_SUBSET_CACHE.get(key)
    if data is not None:
        if key in _VALIDATED_SUBSET_KEYS:
            return data
        error = _woff2_validation_error(data, text)
        if error is None:
            _VALIDATED_SUBSET_KEYS.add(key)
            return data
        _discard_cached_subset(key)
        log_event("font_subset_cache_invalid", logging.WARNING, reason=error)

    cached_file = _CACHE_DIR / f"{key}.woff2"
    if not cached_file.is_file():
        return None
    try:
        data = cached_file.read_bytes()
    except OSError:
        return None

    error = _woff2_validation_error(data, text)
    if error is not None:
        _discard_cached_subset(key)
        log_event("font_subset_cache_invalid", logging.WARNING, reason=error)
        return None

    if len(_MEMORY_SUBSET_CACHE) < _MAX_MEMORY_CACHE_ITEMS:
        _MEMORY_SUBSET_CACHE[key] = data
        _VALIDATED_SUBSET_KEYS.add(key)
    return data


def _normalize_metric_tables(font) -> None:
    """Repair metric counts after subsetting; discard incomplete vertical metrics."""
    glyph_count = font["maxp"].numGlyphs

    if "hhea" in font and "hmtx" in font:
        metrics = font["hmtx"].metrics
        limit = min(glyph_count, len(metrics))
        if limit > 0 and not 1 <= font["hhea"].numberOfHMetrics <= limit:
            font["hhea"].numberOfHMetrics = limit

    has_vhea = "vhea" in font
    has_vmtx = "vmtx" in font
    if has_vhea != has_vmtx:
        if has_vhea:
            del font["vhea"]
        if has_vmtx:
            del font["vmtx"]
        return

    if has_vhea:
        metrics = font["vmtx"].metrics
        limit = min(glyph_count, len(metrics))
        if limit < 1:
            del font["vhea"]
            del font["vmtx"]
        elif not 1 <= font["vhea"].numberOfVMetrics <= limit:
            font["vhea"].numberOfVMetrics = limit


def get_cached_subset(url: str, text: str) -> bytes | None:
    """Return a structurally valid cached WOFF2 subset without reading the raw font."""
    clean_text = text.strip()
    if not clean_text:
        return None
    return _get_valid_cached_subset(_cache_key_for(url, clean_text), clean_text)


def subset_font_to_woff2(font_bytes: bytes, text: str, url: str | None = None) -> bytes:
    """Subset TTF/OTF/WOFF/WOFF2 font bytes to only target characters, converted to WOFF2.

    If fonttools is unavailable or subsetting fails gracefully, returns the original bytes.
    """
    if not _FONTTOOLS_AVAILABLE:
        log_event("font_subset_unavailable", logging.WARNING, error=_IMPORT_ERROR)
        return font_bytes

    clean_text = text.strip()
    if not clean_text:
        return font_bytes

    if url:
        key = _cache_key_for(url, clean_text)
    else:
        cache_key = hashlib.sha256(font_bytes).hexdigest()[:16]
        text_key = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()[:16]
        key = f"{cache_key}_{text_key}"

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = _get_valid_cached_subset(key, clean_text)
    if cached is not None:
        return cached

    font = None
    try:
        font = TTFont(io.BytesIO(font_bytes))
        source_cmap = _unicode_cmap_with_legacy_gbk(font)
        if not any(
            source_cmap.get(ord(character)) not in (None, ".notdef")
            for character in clean_text
            if not character.isspace()
        ):
            # Subsetting a font with no Unicode glyph for the requested label leaves
            # only .notdef; some such WOFF2 files have an empty glyf table that OTS
            # rejects. Keep the original font for the browser's normal fallback.
            return font_bytes

        options = subset.Options()
        options.flavor = "woff2"
        options.desubroutinize = True
        options.name_IDs = ["*"]
        options.name_legacy = True
        options.name_languages = ["*"]

        subsetter = subset.Subsetter(options=options)
        subsetter.populate(text=clean_text)
        subsetter.subset(font)
        _normalize_metric_tables(font)
        font.flavor = "woff2"

        out = io.BytesIO()
        font.save(out)
        result = out.getvalue()
    except Exception as exc:
        log_event("font_subset_fallback", logging.WARNING, error=str(exc))
        return font_bytes
    finally:
        if font is not None:
            font.close()

    validation_error = _woff2_validation_error(result, clean_text)
    if validation_error is not None:
        log_event(
            "font_subset_invalid_output",
            logging.WARNING,
            reason=validation_error,
        )
        return font_bytes

    try:
        cached_file.write_bytes(result)
        if len(_MEMORY_SUBSET_CACHE) < _MAX_MEMORY_CACHE_ITEMS:
            _MEMORY_SUBSET_CACHE[key] = result
            _VALIDATED_SUBSET_KEYS.add(key)
    except OSError:
        pass
    return result


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
