import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
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


def sanitize_filename_part(value: str) -> str:
    """Convert free text into a filesystem-safe filename fragment."""
    cleaned = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "keyword"


def search_tiktok(keyword: str, max_videos: int) -> list[dict]:
    """Search TikTok videos via the signature server, numbered 1..N."""
    videos = _search_tiktok(
        keyword,
        max_videos,
        progress_callback=lambda message: print(f"  {message}"),
    )
    for index, video in enumerate(videos, start=1):
        video["video_no"] = index
    return videos


def scrape_tiktok_comments(aweme_id: str, total_comments: int) -> list[dict]:
    """Fetch main comments for a single TikTok video."""
    base_url = "https://www.tiktok.com/api/comment/list/"
    all_comments = []
    cursor = 0

    print(f"  Mengambil komentar untuk video ID {aweme_id} (target: {total_comments})")

    while len(all_comments) < total_comments:
        remaining = total_comments - len(all_comments)
        params = {
            "aid": "1988",
            "aweme_id": aweme_id,
            "count": min(remaining, 50),
            "cursor": cursor,
        }

        try:
            response = requests.get(base_url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.RequestException as error:
            print(f"  Gagal request komentar: {error}")
            break
        except ValueError as error:
            print(f"  Gagal membaca respons komentar: {error}")
            break

        comments = payload.get("comments") or []
        if not comments:
            print("  Tidak ada komentar tambahan.")
            break

        for comment in comments:
            if len(all_comments) >= total_comments:
                break

            user_data = comment.get("user") or {}
            username = user_data.get("unique_id") or user_data.get("nickname") or "unknown_user"
            text = (comment.get("text") or "").strip()

            all_comments.append(
                {
                    "comment_username": username,
                    "comment_text": text,
                    "comment_type": "main",
                }
            )

        cursor = payload.get("cursor", 0)
        if not payload.get("has_more", 0):
            print("  Sudah mencapai akhir komentar video ini.")
            break

        time.sleep(0.5)

    print(f"  Berhasil mengumpulkan {len(all_comments)} komentar")
    return all_comments


def build_output_rows(keyword: str, videos: list[dict], comments_per_video: int) -> list[dict]:
    """Combine video metadata and comments into one flat dataset."""
    rows = []

    for video in videos:
        print(f"\nVideo {video['video_no']}: @{video['username']}")
        print(f"URL: {video['url']}")

        comments = scrape_tiktok_comments(video["video_id"], comments_per_video)
        for comment in comments:
            rows.append(
                {
                    "keyword": keyword,
                    "video_no": video["video_no"],
                    "video_id": video["video_id"],
                    "video_url": video["url"],
                    "video_username": video["username"],
                    "video_caption": video.get("caption"),
                    "comment_username": comment["comment_username"],
                    "comment_text": comment["comment_text"],
                    "comment_type": comment["comment_type"],
                }
            )

    return rows


def save_to_excel(rows: list[dict], output_path: Path) -> None:
    """Persist combined rows to a single Excel workbook."""
    dataframe = pd.DataFrame(rows)
    ordered_columns = [
        "keyword",
        "video_no",
        "video_id",
        "video_url",
        "video_username",
        "video_caption",
        "comment_username",
        "comment_text",
        "comment_type",
    ]
    dataframe = dataframe[ordered_columns]

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        dataframe.to_excel(writer, sheet_name="TikTok Crawl", index=False)
        worksheet = writer.sheets["TikTok Crawl"]
        worksheet.column_dimensions["A"].width = 20
        worksheet.column_dimensions["B"].width = 10
        worksheet.column_dimensions["C"].width = 24
        worksheet.column_dimensions["D"].width = 50
        worksheet.column_dimensions["E"].width = 20
        worksheet.column_dimensions["F"].width = 50
        worksheet.column_dimensions["G"].width = 22
        worksheet.column_dimensions["H"].width = 60
        worksheet.column_dimensions["I"].width = 12


def read_positive_integer(prompt: str) -> int:
    """Read a positive integer from stdin."""
    while True:
        raw_value = input(prompt).strip()
        try:
            value = int(raw_value)
        except ValueError:
            print("Masukkan angka yang valid.")
            continue

        if value <= 0:
            print("Nilai harus lebih dari 0.")
            continue

        return value


def main() -> None:
    print("=" * 60)
    print("TIKTOK VIDEO + COMMENT CRAWLER")
    print("=" * 60)

    if not check_server_health():
        print("Signature server tidak berjalan.")
        print("Jalankan dulu: cd tiktok-signature-python && python main.py")
        return

    keyword = input("Masukkan keyword pencarian: ").strip()
    if not keyword:
        print("Keyword tidak boleh kosong.")
        return

    max_videos = read_positive_integer("Mau ambil berapa video? ")
    comments_per_video = read_positive_integer("Mau ambil berapa komentar per video? ")

    print("\nMemulai pencarian video...")
    videos = search_tiktok(keyword, max_videos)

    if not videos:
        print("Tidak ada video ditemukan untuk keyword tersebut.")
        return

    print(f"\nDitemukan {len(videos)} video untuk diproses.")
    rows = build_output_rows(keyword, videos, comments_per_video)

    if not rows:
        print("Video ditemukan, tetapi tidak ada komentar yang berhasil diambil.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    keyword_part = sanitize_filename_part(keyword)
    output_path = Path(f"tiktok_crawl_{keyword_part}_{timestamp}.xlsx")
    save_to_excel(rows, output_path)

    processed_video_count = len({row["video_id"] for row in rows})
    print("\n" + "=" * 60)
    print("RINGKASAN")
    print("=" * 60)
    print(f"Keyword                : {keyword}")
    print(f"Video diminta          : {max_videos}")
    print(f"Video diproses         : {len(videos)}")
    print(f"Video dengan komentar  : {processed_video_count}")
    print(f"Komentar per video     : {comments_per_video}")
    print(f"Total komentar tersimpan: {len(rows)}")
    print(f"File output            : {output_path}")


if __name__ == "__main__":
    try:
        import openpyxl  # noqa: F401
        import pandas  # noqa: F401
        import requests  # noqa: F401
    except ImportError:
        print("Library belum lengkap.")
        print("Install dependensi dengan:")
        print("pip install pandas openpyxl requests")
        raise SystemExit(1)

    main()
