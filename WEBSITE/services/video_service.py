import asyncio
import json
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from services.common import build_timestamped_filename


def _friendly_playwright_error(error: Exception) -> RuntimeError:
    message = str(error)
    if "Executable doesn't exist" in message or "browserType.launch" in message:
        return RuntimeError(
            "Browser Playwright belum siap. Jalankan: python -m playwright install chromium"
        )
    return RuntimeError(f"Gagal menjalankan pencarian video TikTok: {message}")


async def search_tiktok(keyword: str, max_videos: int) -> list[dict]:
    """Search TikTok videos using browser automation."""
    search_url = f"https://www.tiktok.com/search?q={quote(keyword)}"

    try:
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

                if current_video_count >= max_videos:
                    break

                if current_video_count == last_video_count and attempt > 5:
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
    except PlaywrightError as error:
        raise _friendly_playwright_error(error) from error
    except Exception as error:
        raise _friendly_playwright_error(error) from error

    for index, video in enumerate(videos, start=1):
        video["video_no"] = index

    return videos[:max_videos]


def save_video_results_json(videos: list[dict], output_path: Path) -> None:
    """Persist video search results to JSON."""
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(videos, file, indent=2, ensure_ascii=False)


def fetch_video_results(keyword: str, max_videos: int) -> list[dict]:
    """Run the async browser search from sync Flask code."""
    return asyncio.run(search_tiktok(keyword, max_videos))


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
