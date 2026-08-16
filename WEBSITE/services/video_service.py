import json
import os
import re
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode

import requests

from services.common import build_timestamped_filename

SIGNATURE_SERVER = os.environ.get("TIKTOK_SIGNATURE_URL", "http://localhost:8080")

# ponytail: core pencarian di-copy dari script CLI 2 & 3 (tanpa file client shared;
# naikkan ke modul bersama bila logikanya berubah >1 kali).


def check_server_health() -> bool:
    """True bila signature server siap dipakai."""
    try:
        return requests.get(f"{SIGNATURE_SERVER}/health", timeout=5).status_code == 200
    except requests.RequestException:
        return False


def _search_tiktok(keyword: str, max_videos: int = 30, progress_callback=None) -> list[dict]:
    """Cari video via POST /fetch di signature server (main.py) — tanpa browser lokal.

    TikTok sesekali memberi hasil pengganti (feed fallback) ke sesi tamu;
    halaman yang tak memuat token keyword di caption-nya diulang sampai asli.
    """
    videos = []
    cursor = 0
    search_id = f"{int(time.time() * 1000)}{uuid.uuid4().hex[:12].upper()}"
    stopwords = {"yang", "dan", "dengan", "untuk", "dari", "ada"}
    tokens = [
        w.lower() for w in re.split(r"\W+", keyword)
        if len(w) >= 3 and w.lower() not in stopwords
    ]

    while len(videos) < max_videos:
        params = {
            "aid": "1988",
            "keyword": keyword,
            "count": str(min(12, max_videos - len(videos))),
            "cursor": str(cursor),
            "search_source": "query",  # search_history memberi hasil tak relevan
            "search_id": search_id,
            "type": "1",  # wajib: filter video; tanpa ini TikTok beri hasil pengganti
            "channel": "tiktok_web",
        }
        url = f"https://www.tiktok.com/api/search/general/full/?{urlencode(params)}"

        items, data = [], {}
        for retries in range(4):
            if progress_callback:
                progress_callback(
                    f"Halaman {cursor // 12 + 1}..." + (f" (retry {retries})" if retries else "")
                )
            try:
                response = requests.post(f"{SIGNATURE_SERVER}/fetch", json={"url": url}, timeout=60)
                response.raise_for_status()
                result = response.json()
            except (requests.RequestException, ValueError) as error:
                raise RuntimeError(
                    f"Gagal memanggil signature server ({SIGNATURE_SERVER}): {error}. "
                    "Jalankan dulu di repo tiktok-signature-python: python main.py"
                ) from error
            if result.get("status") != "ok":
                raise RuntimeError(f"Signature server gagal: {result.get('message', result)}")

            data = result.get("data") or {}
            items = [
                entry.get("item") for entry in (data.get("data") or [])
                if isinstance(entry, dict) and isinstance(entry.get("item"), dict)
            ]
            if items and tokens and not any(
                token in " ".join((item.get("desc") or "") for item in items[:8]).lower()
                for token in tokens
            ):
                continue  # hasil pengganti — retry
            break

        if not items:
            break

        seen = {video["video_id"] for video in videos}
        for item in items:
            video_id = item.get("id")
            author = item.get("author") or {}
            username = author.get("uniqueId") if isinstance(author, dict) else None
            if not video_id or not username:
                continue
            video_id = str(video_id)
            if video_id in seen:
                continue
            seen.add(video_id)
            videos.append({
                "video_id": video_id,
                "url": f"https://www.tiktok.com/@{username}/video/{video_id}",
                "username": username,
                "caption": (item.get("desc") or "").strip()[:200] or None,
            })

        cursor = data.get("cursor", cursor + len(items))
        if not data.get("has_more", False):
            break
        time.sleep(1)

    return videos[:max_videos]


def search_tiktok(keyword: str, max_videos: int) -> list[dict]:
    """Search TikTok videos via the signature server."""
    if not check_server_health():
        raise RuntimeError(
            "Signature server tidak berjalan. "
            "Jalankan: cd tiktok-signature-python && python main.py"
        )

    videos = _search_tiktok(keyword, max_videos)
    for index, video in enumerate(videos, start=1):
        video["video_no"] = index

    return videos


def save_video_results_json(videos: list[dict], output_path: Path) -> None:
    """Persist video search results to JSON."""
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(videos, file, indent=2, ensure_ascii=False)


def fetch_video_results(keyword: str, max_videos: int) -> list[dict]:
    """Sync entrypoint for the crawl workflow (dulu asyncio.run)."""
    return search_tiktok(keyword, max_videos)


def run_video_search(keyword: str, max_videos: int, output_dir: Path) -> dict:
    """Run video search for the Flask UI and persist output."""
    videos = fetch_video_results(keyword, max_videos)
    if not videos:
        raise RuntimeError("Tidak ada video ditemukan untuk keyword tersebut.")

    filename = build_timestamped_filename("videos", keyword, "json")
    output_path = output_dir / filename
    save_video_results_json(videos, output_path)

    return {
        "keyword": keyword,
        "videos": videos,
        "preview_rows": videos[:10],
        "summary": {
            "total_found": len(videos),
            "requested": max_videos,
        },
        "download_name": filename,
    }
