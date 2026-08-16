import json
import os
import re
import time
import uuid
from urllib.parse import urlencode

import requests

SIGNATURE_SERVER = os.environ.get("TIKTOK_SIGNATURE_URL", "http://localhost:8080")

# ponytail: core pencarian di-copy di script 2, 3, dan WEBSITE/services/video_service.py
# (sengaja, tanpa file client shared; naikkan ke modul bersama bila berubah >1 kali).


def check_server_health() -> bool:
    """True bila signature server siap dipakai."""
    try:
        return requests.get(f"{SIGNATURE_SERVER}/health", timeout=5).status_code == 200
    except requests.RequestException:
        return False


def _search_tiktok(keyword: str, max_videos: int = 30, progress_callback=None):
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


def search_tiktok(keyword: str, max_videos: int = 30):
    """Cari video via signature server — tanpa browser lokal."""

    def progress(message):
        print(f"  📊 {message}")

    videos = _search_tiktok(keyword, max_videos, progress_callback=progress)
    for index, video in enumerate(videos, start=1):
        video["no"] = index
    return videos


def main():
    keyword = input("Masukkan keyword pencarian: ").strip()

    if not keyword:
        print("❌ Keyword tidak boleh kosong!")
        return

    try:
        max_videos = int(input("Masukkan jumlah video yang diinginkan: ").strip())
        if max_videos <= 0:
            print("❌ Jumlah video harus lebih dari 0!")
            return
    except ValueError:
        print("❌ Jumlah video harus berupa angka!")
        return

    if not check_server_health():
        print("❌ Signature server tidak berjalan!")
        print("💡 Jalankan dulu: cd tiktok-signature-python && python main.py")
        return

    print(f"\n🎯 Mencari: {keyword} (target: {max_videos} video)\n")
    results = search_tiktok(keyword, max_videos)

    display_count = min(len(results), max_videos)
    if results:
        print(f"\n✅ Ditemukan {len(results)} video, menampilkan {display_count}:\n")
        for video in results[:display_count]:
            print(f"{video['no']}. @{video['username']}")
            if video['caption']:
                caption_preview = video['caption'][:100] + "..." if len(video['caption']) > 100 else video['caption']
                print(f"   📝 {caption_preview}")
            print(f"   🔗 {video['url']}")
            print()
    else:
        print("❌ Tidak ada video ditemukan")
        return

    filename = f"tiktok_{keyword.replace(' ', '_')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"💾 Data disimpan ke {filename}")


if __name__ == "__main__":
    main()
