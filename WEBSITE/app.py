import os
from pathlib import Path

from flask import Flask, redirect, render_template, request, send_from_directory, session, url_for

from services.comments_service import run_comment_scrape
from services.crawl_service import run_crawl
from services.video_service import run_video_search


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["OUTPUT_DIR"] = OUTPUT_DIR
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
app.secret_key = os.environ.get("SECRET_KEY", "tiktok-scraper-dev")


def parse_positive_integer(raw_value: str, field_label: str) -> int:
    """Validate and normalize positive integer form input."""
    try:
        value = int((raw_value or "").strip())
    except ValueError as error:
        raise ValueError(f"{field_label} harus berupa angka.") from error

    if value <= 0:
        raise ValueError(f"{field_label} harus lebih dari 0.")

    return value


@app.get("/")
def index():
    return render_template("index.html")


@app.route("/comments", methods=["GET", "POST"])
def comments_page():
    if request.method == "POST":
        form_data = {
            "video_link_or_id": (request.form.get("video_link_or_id") or "").strip(),
            "total_comments": (request.form.get("total_comments") or "").strip(),
            "include_replies": request.form.get("include_replies", "yes"),
        }
        try:
            if not form_data["video_link_or_id"]:
                raise ValueError("Link TikTok atau video ID tidak boleh kosong.")

            total_comments = parse_positive_integer(form_data["total_comments"], "Jumlah komentar")
            result = run_comment_scrape(
                video_link_or_id=form_data["video_link_or_id"],
                total_comments=total_comments,
                include_replies=form_data["include_replies"] == "yes",
                output_dir=app.config["OUTPUT_DIR"],
            )
            # PRG: hasil diringkas ke session, refresh jadi GET bersih (tak re-submit)
            session["result"] = {k: v for k, v in result.items() if k != "rows"}
            session.pop("error", None)
            session.pop("form_data", None)
        except Exception as exc:
            session["error"] = str(exc)
            session["form_data"] = form_data
        return redirect(url_for("comments_page"), code=303)

    return render_template(
        "comments.html",
        result=session.pop("result", None),
        error=session.pop("error", None),
        form_data=session.pop(
            "form_data",
            {"video_link_or_id": "", "total_comments": "", "include_replies": "yes"},
        ),
    )


@app.route("/videos", methods=["GET", "POST"])
def videos_page():
    if request.method == "POST":
        form_data = {
            "keyword": (request.form.get("keyword") or "").strip(),
            "max_videos": (request.form.get("max_videos") or "").strip(),
        }
        try:
            if not form_data["keyword"]:
                raise ValueError("Keyword tidak boleh kosong.")

            max_videos = parse_positive_integer(form_data["max_videos"], "Jumlah video")
            result = run_video_search(
                keyword=form_data["keyword"],
                max_videos=max_videos,
                output_dir=app.config["OUTPUT_DIR"],
            )
            # PRG: hasil diringkas ke session, refresh jadi GET bersih (tak re-submit)
            session["result"] = {k: v for k, v in result.items() if k not in ("rows", "videos")}
            session.pop("error", None)
            session.pop("form_data", None)
        except Exception as exc:
            session["error"] = str(exc)
            session["form_data"] = form_data
        return redirect(url_for("videos_page"), code=303)

    return render_template(
        "videos.html",
        result=session.pop("result", None),
        error=session.pop("error", None),
        form_data=session.pop("form_data", {"keyword": "", "max_videos": ""}),
    )


@app.route("/crawl", methods=["GET", "POST"])
def crawl_page():
    if request.method == "POST":
        form_data = {
            "keyword": (request.form.get("keyword") or "").strip(),
            "max_videos": (request.form.get("max_videos") or "").strip(),
            "comments_per_video": (request.form.get("comments_per_video") or "").strip(),
        }
        try:
            if not form_data["keyword"]:
                raise ValueError("Keyword tidak boleh kosong.")

            max_videos = parse_positive_integer(form_data["max_videos"], "Jumlah video")
            comments_per_video = parse_positive_integer(
                form_data["comments_per_video"],
                "Jumlah komentar per video",
            )
            result = run_crawl(
                keyword=form_data["keyword"],
                max_videos=max_videos,
                comments_per_video=comments_per_video,
                output_dir=app.config["OUTPUT_DIR"],
            )
            # PRG: hasil diringkas ke session, refresh jadi GET bersih (tak re-submit)
            session["result"] = {k: v for k, v in result.items() if k != "rows"}
            session.pop("error", None)
            session.pop("form_data", None)
        except Exception as exc:
            session["error"] = str(exc)
            session["form_data"] = form_data
        return redirect(url_for("crawl_page"), code=303)

    return render_template(
        "crawl.html",
        result=session.pop("result", None),
        error=session.pop("error", None),
        form_data=session.pop(
            "form_data",
            {"keyword": "", "max_videos": "", "comments_per_video": ""},
        ),
    )


@app.get("/download/<path:filename>")
def download_file(filename: str):
    return send_from_directory(app.config["OUTPUT_DIR"], filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
