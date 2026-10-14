"""One-time or deployment pre-warm script to subset all active database fonts into local cache."""

import asyncio
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import httpx
from sqlalchemy import select

from app.config import load_settings
from app.database import Database
from app.models import FontOption
from app.services.font_subset import (
    get_cached_subset,
    get_or_fetch_raw_font,
    subset_font_to_woff2,
)


async def prewarm() -> None:
    settings = load_settings()
    database = Database(settings.database_url)

    with database.sessions() as session:
        items = session.execute(
            select(FontOption.name, FontOption.font_url).where(FontOption.font_url.is_not(None))
        ).all()

    targets = [(name.strip(), url.strip()) for name, url in items if name and url]
    print(f"找到 {len(targets)} 个配置了字体的选项，开始预热缓存...")

    async with httpx.AsyncClient(timeout=30) as client:
        success = 0
        fallback = 0
        failed = 0
        for idx, (name, url) in enumerate(targets, 1):
            if get_cached_subset(url, name):
                print(f"[{idx}/{len(targets)}] {name}: 已在缓存中，跳过")
                success += 1
                continue
            try:
                print(f"[{idx}/{len(targets)}] {name}: 正在下载并切片...", end=" ", flush=True)
                raw_bytes, _ = await get_or_fetch_raw_font(url, client)
                res = subset_font_to_woff2(raw_bytes, name, url)
                if res.startswith(b"wOF2") and get_cached_subset(url, name) is not None:
                    print(f"完成 ({len(res)} 字节)")
                    success += 1
                else:
                    print("没有可复用的 WOFF2 缓存，运行时将处理原字体")
                    fallback += 1
            except Exception as e:
                print(f"失败: {e}")
                failed += 1

    print(
        f"\n预热结束：缓存切片 {success} 个，原字体回退或未缓存 {fallback} 个，"
        f"失败 {failed} 个（共 {len(targets)} 个字体）。"
    )


if __name__ == "__main__":
    asyncio.run(prewarm())
