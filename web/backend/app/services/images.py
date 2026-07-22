"""Server-side image upload through the local AWS SDK v3 R2 adapter."""

import json
import logging
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired, run
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

from app.config import AppSettings
from app.errors import ApiError
from app.logging import log_event


MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGES = {"image/jpeg": (".jpg", b"\xff\xd8\xff"), "image/png": (".png", b"\x89PNG\r\n\x1a\n"), "image/gif": (".gif", b"GIF8"), "image/webp": (".webp", b"RIFF")}
UPLOADER = Path(__file__).resolve().parents[3] / "r2-uploader" / "upload.mjs"


def upload_image(settings: AppSettings, content: bytes, content_type: str) -> str:
    """Validate one image, then delegate the authenticated R2 PUT to Node."""
    suffix = validate_image(content, content_type)
    ensure_configured(settings)
    with NamedTemporaryFile(suffix=suffix) as image:
        image.write(content)
        image.flush()
        return run_uploader(settings, image.name, content_type)


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


def run_uploader(settings: AppSettings, image_path: str, content_type: str) -> str:
    """Invoke the local adapter and expose only its JSON public URL result."""
    payload = {"filePath": image_path, "contentType": content_type, "endpoint": settings.r2_endpoint, "accessKeyId": settings.r2_access_key_id, "secretAccessKey": settings.r2_secret_access_key, "bucket": settings.r2_bucket, "publicBaseUrl": settings.r2_public_base_url}
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
