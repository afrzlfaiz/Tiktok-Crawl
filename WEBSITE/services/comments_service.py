from pathlib import Path
import re
import time

import pandas as pd
import requests

from services.common import build_timestamped_filename


def get_tiktok_video_id(link: str) -> str | None:
    """Resolve TikTok short or full links into a numeric video ID."""
    try:
        response = requests.get(link, allow_redirects=True, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        raise RuntimeError(f"Gagal membuka link TikTok: {error}") from error

    final_url = response.url
    match = re.search(r"video/(\d+)", final_url)
    if match:
        return match.group(1)

    match = re.search(r'"id":"(\d+)"', response.text)
    if match:
        return match.group(1)

    return None


def normalize_video_input(video_link_or_id: str) -> str:
    """Accept a TikTok URL or numeric ID and always return aweme_id."""
    value = video_link_or_id.strip()
    if not value:
        raise ValueError("Link TikTok atau video ID tidak boleh kosong.")

    if "tiktok.com" in value or "vt.tiktok.com" in value:
        aweme_id = get_tiktok_video_id(value)
        if not aweme_id:
            raise ValueError("Link TikTok tidak bisa dikonversi menjadi video ID.")
        return aweme_id

    if value.isdigit():
        return value

    raise ValueError("Input harus berupa link TikTok atau video ID numeric.")


def scrape_tiktok_replies(aweme_id: str, comment_id: str, total_replies: int) -> list[dict]:
    """Fetch reply comments for one main comment."""
    replies_url = "https://www.tiktok.com/api/comment/list/reply/"
    all_replies = []
    cursor = 0

    while len(all_replies) < total_replies:
        remaining = total_replies - len(all_replies)
        params = {
            "aid": "1988",
            "comment_id": comment_id,
            "item_id": aweme_id,
            "count": min(remaining, 50),
            "cursor": cursor,
        }

        try:
            response = requests.get(replies_url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.RequestException:
            break
        except ValueError:
            break

        replies_batch = payload.get("comments") or payload.get("replies") or []
        if not replies_batch:
            break

        for reply in replies_batch:
            if len(all_replies) >= total_replies:
                break

            user_data = reply.get("user") or {}
            all_replies.append(
                {
                    "username": user_data.get("unique_id") or user_data.get("nickname") or "unknown_user",
                    "text": (reply.get("text") or "").strip(),
                    "type": "reply",
                }
            )

        cursor = payload.get("cursor", 0)
        if not payload.get("has_more", 0):
            break

        time.sleep(0.3)

    return all_replies


def scrape_tiktok_comments(aweme_id: str, total_comments: int, include_replies: bool = True) -> list[dict]:
    """Fetch TikTok comments by aweme_id."""
    comments_url = "https://www.tiktok.com/api/comment/list/"
    all_comments = []
    cursor = 0

    while len(all_comments) < total_comments:
        remaining = total_comments - len(all_comments)
        params = {
            "aid": "1988",
            "aweme_id": aweme_id,
            "count": min(remaining, 50),
            "cursor": cursor,
        }

        try:
            response = requests.get(comments_url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.RequestException as error:
            raise RuntimeError(f"Gagal mengambil komentar TikTok: {error}") from error
        except ValueError as error:
            raise RuntimeError(f"Respons komentar TikTok tidak valid: {error}") from error

        comments = payload.get("comments") or []
        if not comments:
            break

        for comment in comments:
            if len(all_comments) >= total_comments:
                break

            user_data = comment.get("user") or {}
            comment_row = {
                "username": user_data.get("unique_id") or user_data.get("nickname") or "unknown_user",
                "text": (comment.get("text") or "").strip(),
                "type": "main",
            }
            all_comments.append(comment_row)

            reply_count = comment.get("reply_comment_total", 0)
            comment_id = comment.get("cid")
            if include_replies and reply_count > 0 and comment_id and len(all_comments) < total_comments:
                replies = scrape_tiktok_replies(aweme_id, comment_id, reply_count)
                for reply in replies:
                    if len(all_comments) >= total_comments:
                        break
                    all_comments.append(reply)

        cursor = payload.get("cursor", 0)
        if not payload.get("has_more", 0):
            break

        time.sleep(0.5)

    return all_comments


def save_comments_to_excel(rows: list[dict], output_path: Path) -> None:
    """Write comment scrape output to Excel."""
    dataframe = pd.DataFrame(rows)
    dataframe = dataframe[["text", "username", "type"]]

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        dataframe.to_excel(writer, sheet_name="TikTok Comments", index=False)
        worksheet = writer.sheets["TikTok Comments"]
        worksheet.column_dimensions["A"].width = 60
        worksheet.column_dimensions["B"].width = 24
        worksheet.column_dimensions["C"].width = 12


def run_comment_scrape(
    video_link_or_id: str,
    total_comments: int,
    include_replies: bool,
    output_dir: Path,
) -> dict:
    """Run comment scraping for the Flask UI and persist output."""
    aweme_id = normalize_video_input(video_link_or_id)
    rows = scrape_tiktok_comments(aweme_id, total_comments, include_replies)

    if not rows:
        raise RuntimeError("Tidak ada komentar yang berhasil diambil dari video ini.")

    filename = build_timestamped_filename("comments", aweme_id, "xlsx")
    output_path = output_dir / filename
    save_comments_to_excel(rows, output_path)

    summary = {
        "total_items": len(rows),
        "main_comments": sum(1 for row in rows if row["type"] == "main"),
        "reply_comments": sum(1 for row in rows if row["type"] == "reply"),
    }

    return {
        "aweme_id": aweme_id,
        "rows": rows,
        "preview_rows": rows[:10],
        "summary": summary,
        "download_name": filename,
    }
