from pathlib import Path

import pandas as pd

from services.comments_service import scrape_tiktok_comments
from services.common import build_timestamped_filename
from services.video_service import fetch_video_results


def build_output_rows(keyword: str, videos: list[dict], comments_per_video: int) -> tuple[list[dict], list[dict]]:
    """Combine video metadata and comments into one flat dataset."""
    rows = []
    video_summaries = []

    for video in videos:
        comments = scrape_tiktok_comments(
            aweme_id=video["video_id"],
            total_comments=comments_per_video,
            include_replies=False,
        )

        video_summaries.append(
            {
                "video_no": video["video_no"],
                "video_id": video["video_id"],
                "video_username": video["username"],
                "comment_count": len(comments),
            }
        )

        for comment in comments:
            rows.append(
                {
                    "keyword": keyword,
                    "video_no": video["video_no"],
                    "video_id": video["video_id"],
                    "video_url": video["url"],
                    "video_username": video["username"],
                    "video_caption": video.get("caption"),
                    "comment_username": comment["username"],
                    "comment_text": comment["text"],
                    "comment_type": comment["type"],
                }
            )

    return rows, video_summaries


def save_crawl_results_to_excel(rows: list[dict], output_path: Path) -> None:
    """Persist combined crawl results to Excel."""
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


def run_crawl(keyword: str, max_videos: int, comments_per_video: int, output_dir: Path) -> dict:
    """Run keyword -> videos -> comments workflow for the Flask UI."""
    videos = fetch_video_results(keyword, max_videos)
    if not videos:
        raise RuntimeError("Tidak ada video ditemukan untuk keyword tersebut.")

    rows, video_summaries = build_output_rows(keyword, videos, comments_per_video)
    if not rows:
        raise RuntimeError("Video ditemukan, tetapi tidak ada komentar yang berhasil diambil.")

    filename = build_timestamped_filename("crawl", keyword, "xlsx")
    output_path = output_dir / filename
    save_crawl_results_to_excel(rows, output_path)

    return {
        "keyword": keyword,
        "rows": rows,
        "preview_rows": rows[:10],
        "video_summaries": video_summaries,
        "summary": {
            "requested_videos": max_videos,
            "processed_videos": len(videos),
            "requested_comments_per_video": comments_per_video,
            "videos_with_comments": sum(1 for item in video_summaries if item["comment_count"] > 0),
            "total_comments": len(rows),
        },
        "download_name": filename,
    }
