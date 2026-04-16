import asyncio
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests
from playwright.async_api import async_playwright


def sanitize_filename_part(value: str) -> str:
    """Convert free text into a filesystem-safe filename fragment."""
    cleaned = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "keyword"


async def search_tiktok(keyword: str, max_videos: int) -> list[dict]:
    """Search TikTok videos for a keyword and return unique video metadata."""
    search_url = f"https://www.tiktok.com/search?q={quote(keyword)}"
    print(f"\nMembuka halaman pencarian: {search_url}")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="Asia/Jakarta",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
                "Referer": "https://www.google.com/",
                "DNT": "1",
            },
        )

        page = await context.new_page()
        await page.goto(search_url, wait_until="networkidle")
        await page.wait_for_timeout(5000)

        print(f"Memuat daftar video (target: {max_videos})...")

        scroll_script = """
            () => {
                const lastGrid = document.querySelector('[id^="grid-item-container-"]:last-child');
                if (lastGrid) {
                    lastGrid.scrollIntoView({ behavior: 'smooth', block: 'end' });
                } else {
                    window.scrollTo(0, document.body.scrollHeight);
                }
            }
        """

        max_attempts = 50
        last_video_count = 0

        for attempt in range(1, max_attempts + 1):
            await page.evaluate(scroll_script)
            await page.wait_for_timeout(2000)

            current_video_count = await page.evaluate(
                """
                () => document.querySelectorAll('a[href*="/video/"]').length
                """
            )
            print(f"  Attempt {attempt}: {current_video_count} link video terdeteksi")

            if current_video_count >= max_videos:
                print("Target jumlah video tercapai.")
                break

            if current_video_count == last_video_count and attempt > 5:
                print("Jumlah video tidak bertambah lagi, proses pencarian dihentikan.")
                break

            last_video_count = current_video_count

        videos = await page.evaluate(
            """
            () => {
                const videoLinks = document.querySelectorAll('a[href*="/video/"]');
                const seen = new Set();
                const results = [];

                videoLinks.forEach((link) => {
                    const videoUrl = link.href;
                    const videoId = videoUrl ? videoUrl.split('/video/')[1]?.split('?')[0] : null;
                    const hrefParts = videoUrl?.split('/');
                    const username = hrefParts && hrefParts.length > 3
                        ? hrefParts[3]?.replace('@', '')
                        : null;

                    const container = link.closest('[class*="DivWrapper"]') || link.parentElement;
                    const image = container?.querySelector('img');
                    const caption = image?.alt || null;

                    if (!videoId || !username || seen.has(videoId)) {
                        return;
                    }

                    seen.add(videoId);
                    results.push({
                        video_id: videoId,
                        url: videoUrl,
                        username: username,
                        caption: caption ? caption.substring(0, 200) : null
                    });
                });

                return results;
            }
            """
        )

        await browser.close()

    for index, video in enumerate(videos, start=1):
        video["video_no"] = index

    return videos[:max_videos]


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


async def main() -> None:
    print("=" * 60)
    print("TIKTOK VIDEO + COMMENT CRAWLER")
    print("=" * 60)

    keyword = input("Masukkan keyword pencarian: ").strip()
    if not keyword:
        print("Keyword tidak boleh kosong.")
        return

    max_videos = read_positive_integer("Mau ambil berapa video? ")
    comments_per_video = read_positive_integer("Mau ambil berapa komentar per video? ")

    print("\nMemulai pencarian video...")
    videos = await search_tiktok(keyword, max_videos)

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
        import playwright  # noqa: F401
        import requests  # noqa: F401
    except ImportError:
        print("Library belum lengkap.")
        print("Install dependensi dengan:")
        print("pip install pandas openpyxl requests playwright")
        print("python -m playwright install chromium")
        raise SystemExit(1)

    asyncio.run(main())
