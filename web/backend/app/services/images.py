"""Server-side image and font upload through the configured storage backend."""

import hashlib
import json
import logging
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired, run
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

import httpx

from app.config import AppSettings
from app.errors import ApiError
from app.logging import log_event


MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGES = {"image/jpeg": (".jpg", b"\xff\xd8\xff"), "image/png": (".png", b"\x89PNG\r\n\x1a\n"), "image/gif": (".gif", b"GIF8"), "image/webp": (".webp", b"RIFF")}
MAX_FONT_BYTES = 40 * 1024 * 1024
ALLOWED_FONTS = {
    "font/ttf": (".ttf", b"\x00\x01\x00\x00"),
    "application/x-font-ttf": (".ttf", b"\x00\x01\x00\x00"),
    "font/otf": (".otf", b"OTTO"),
    "application/x-font-opentype": (".otf", b"OTTO"),
    "font/woff": (".woff", b"wOFF"),
    "application/font-woff": (".woff", b"wOFF"),
    "font/woff2": (".woff2", b"wOF2"),
}
UPLOADER = Path(__file__).resolve().parents[3] / "r2-uploader" / "upload.mjs"
DELETER = Path(__file__).resolve().parents[3] / "r2-uploader" / "delete.mjs"


def upload_image(settings: AppSettings, content: bytes, content_type: str, prefix: str | None = None) -> str:
    """Validate and store one image in the configured upload backend."""
    suffix = validate_image(content, content_type)
    if settings.storage_backend == "local":
        return write_local(settings, content, prefix, suffix)
    ensure_configured(settings)
    with NamedTemporaryFile(suffix=suffix) as image:
        image.write(content)
        image.flush()
        if prefix:
            key = f"{prefix.strip('/')}/{_random_key()}{suffix}"
            return run_uploader(settings, image.name, content_type, key=key)
        return run_uploader(settings, image.name, content_type)


def _random_key() -> str:
    """Generate a short random hex string for unique object keys."""
    import secrets
    return secrets.token_hex(16)


def validate_image(content: bytes, content_type: str) -> str:
    """Reject oversized, unsupported, or malformed binary image uploads."""
    allowed = ALLOWED_IMAGES.get(content_type.lower())
    if allowed is None or len(content) > MAX_IMAGE_BYTES or not content.startswith(allowed[1]):
        raise ApiError(422, "INVALID_IMAGE", "仅支持 8MB 以内的 JPG、PNG、GIF 或 WebP 图片")
    if content_type.lower() == "image/webp" and content[8:12] != b"WEBP":
        raise ApiError(422, "INVALID_IMAGE", "上传的 WebP 图片无效")
    return allowed[0]


def ensure_configured(settings: AppSettings) -> None:
    """Require complete R2 configuration and a public HTTPS delivery domain."""
    values = (settings.r2_endpoint, settings.r2_access_key_id, settings.r2_secret_access_key, settings.r2_bucket, settings.r2_public_base_url)
    if not all(values) or not UPLOADER.is_file():
        raise ApiError(503, "IMAGE_UPLOAD_UNCONFIGURED", "R2 图片上传尚未配置")
    if any(urlparse(url).scheme != "https" or not urlparse(url).netloc for url in (settings.r2_endpoint, settings.r2_public_base_url)):
        raise ApiError(503, "IMAGE_UPLOAD_UNCONFIGURED", "R2 地址配置无效")


def write_local(
    settings: AppSettings,
    content: bytes,
    prefix: str | None,
    suffix: str,
    filename: str | None = None,
) -> str:
    """Write a development upload below the configured directory and return its URL."""
    base = Path(settings.local_storage_path).resolve()
    directory = base / prefix.strip("/") if prefix else base
    directory.mkdir(parents=True, exist_ok=True)
    filename = filename or f"{_random_key()}{suffix}"
    (directory / filename).write_bytes(content)
    relative = f"{prefix.strip('/')}/{filename}" if prefix else filename
    return f"{settings.local_public_base_url.rstrip('/')}/{relative}"


def upload_json(settings: AppSettings, key: str, data: dict | list) -> str:
    """Upload a JSON document to the configured backend with no-cache policy."""
    if settings.storage_backend == "local":
        parent, _, filename = key.rpartition("/")
        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        return write_local(settings, content, parent or None, ".json", filename)
    ensure_configured(settings)
    content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    with NamedTemporaryFile(suffix=".json", mode="wb") as f:
        f.write(content)
        f.flush()
        return run_uploader(settings, f.name, "application/json", key=key, cache_control="no-cache")


def run_uploader(settings: AppSettings, file_path: str, content_type: str, key: str | None = None, cache_control: str | None = None) -> str:
    """Invoke the local adapter and expose only its JSON public URL result."""
    payload: dict[str, object] = {"filePath": file_path, "contentType": content_type, "endpoint": settings.r2_endpoint, "accessKeyId": settings.r2_access_key_id, "secretAccessKey": settings.r2_secret_access_key, "bucket": settings.r2_bucket, "publicBaseUrl": settings.r2_public_base_url}
    if key is not None:
        payload["key"] = key
    if cache_control is not None:
        payload["cacheControl"] = cache_control
    try:
        result = run(["node", str(UPLOADER)], input=json.dumps(payload), check=True, capture_output=True, text=True, timeout=30)
        return json.loads(result.stdout)["imageUrl"]
    except (CalledProcessError, FileNotFoundError, TimeoutExpired, KeyError, json.JSONDecodeError) as error:
        log_event(
            "r2_uploader_error",
            logging.ERROR,
            error_type=type(error).__name__,
        )
        raise ApiError(502, "IMAGE_UPLOAD_FAILED", "图片上传失败，请稍后重试") from error


def upload_font(settings: AppSettings, content: bytes, content_type: str, filename: str = "font") -> str:
    """Validate one font file, deduplicate it in R2, or write it locally for development."""
    suffix = validate_font(content, content_type)
    if settings.storage_backend == "local":
        return write_local(settings, content, "quiz-fonts", suffix)
    ensure_configured(settings)
    content_hash = hashlib.sha256(content).hexdigest()
    safe_filename = _safe_filename(filename)
    key = f"quiz-fonts/{content_hash[:12]}-{safe_filename}{suffix}"
    public_url = f"{settings.r2_public_base_url.rstrip('/')}/{key}"
    if _font_already_uploaded(public_url):
        return public_url
    with NamedTemporaryFile(suffix=suffix) as font:
        font.write(content)
        font.flush()
        return run_uploader(settings, font.name, content_type, key)


def validate_font(content: bytes, content_type: str) -> str:
    """Reject oversized or malformed font files. Format detected by magic bytes, not Content-Type."""
    if len(content) > MAX_FONT_BYTES:
        raise ApiError(422, "INVALID_FONT", "仅支持 40MB 以内的 TTF、OTF、WOFF 或 WOFF2 字体文件")
    for suffix, magic in ALLOWED_FONTS.values():
        if content.startswith(magic):
            return suffix
    raise ApiError(422, "INVALID_FONT", "仅支持 TTF、OTF、WOFF 或 WOFF2 字体文件")


def _safe_filename(filename: str) -> str:
    """Keep only alphanumeric, hyphen, underscore and dot characters."""
    clean = "".join(c if c.isalnum() or c in "-_. " else "" for c in filename)
    return clean.strip()[:64] or "font"


def _font_already_uploaded(url: str) -> bool:
    """Check whether a font file already exists at its public R2 URL."""
    try:
        response = httpx.head(url, timeout=5)
        return response.status_code == 200
    except httpx.RequestError:
        return False


def delete_r2_object(settings: AppSettings, font_url: str) -> None:
    """Extract the R2 key from a public URL and delete the object."""
    if settings.storage_backend == "local":
        delete_local(settings, font_url)
        return
    key = _url_to_key(settings, font_url)
    try:
        ensure_configured(settings)
    except ApiError:
        return
    payload = {"endpoint": settings.r2_endpoint, "accessKeyId": settings.r2_access_key_id, "secretAccessKey": settings.r2_secret_access_key, "bucket": settings.r2_bucket, "key": key}
    try:
        run(["node", str(DELETER)], input=json.dumps(payload), check=True, capture_output=True, text=True, timeout=15)
    except (CalledProcessError, FileNotFoundError, TimeoutExpired) as error:
        log_event(
            "r2_delete_error",
            logging.WARNING,
            error_type=type(error).__name__,
            key=key,
        )


def delete_r2_object_strict(settings: AppSettings, font_url: str) -> None:
    """Delete one object and propagate errors so the durable worker can retry."""
    if settings.storage_backend == "local":
        delete_local(settings, font_url)
        return
    key = _url_to_key(settings, font_url)
    ensure_configured(settings)
    payload = {
        "endpoint": settings.r2_endpoint,
        "accessKeyId": settings.r2_access_key_id,
        "secretAccessKey": settings.r2_secret_access_key,
        "bucket": settings.r2_bucket,
        "key": key,
    }
    run(
        ["node", str(DELETER)],
        input=json.dumps(payload),
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )


def delete_local(settings: AppSettings, url: str) -> None:
    """Delete a local upload only when its resolved path stays in storage."""
    base_url = settings.local_public_base_url.rstrip("/") + "/"
    if not url.startswith(base_url):
        return
    candidate = (Path(settings.local_storage_path).resolve() / url.removeprefix(base_url)).resolve()
    if candidate.is_relative_to(Path(settings.local_storage_path).resolve()):
        candidate.unlink(missing_ok=True)


def _url_to_key(settings: AppSettings, url: str) -> str:
    """Strip the public base URL prefix to recover the R2 object key."""
    base = settings.r2_public_base_url.rstrip("/") + "/"
    if url.startswith(base):
        return url[len(base):]
    return url
