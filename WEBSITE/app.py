from pathlib import Path

from flask import Flask, render_template, request, send_from_directory

from services.comments_service import run_comment_scrape
from services.crawl_service import run_crawl
from services.video_service import run_video_search


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["OUTPUT_DIR"] = OUTPUT_DIR
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


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
    result = None
    error = None
    form_data = {
        "video_link_or_id": "",
        "total_comments": "",
        "include_replies": "yes",
    }

    if request.method == "POST":
        form_data["video_link_or_id"] = (request.form.get("video_link_or_id") or "").strip()
        form_data["total_comments"] = (request.form.get("total_comments") or "").strip()
        form_data["include_replies"] = request.form.get("include_replies", "yes")

        try:
            if not form_data["video_link_or_id"]:
                raise ValueError("Link TikTok atau video ID tidak boleh kosong.")

            total_comments = parse_positive_integer(form_data["total_comments"], "Jumlah komentar")
            include_replies = form_data["include_replies"] == "yes"
            result = run_comment_scrape(
                video_link_or_id=form_data["video_link_or_id"],
                total_comments=total_comments,
                include_replies=include_replies,
                output_dir=app.config["OUTPUT_DIR"],
            )
        except Exception as exc:
            error = str(exc)

    return render_template("comments.html", result=result, error=error, form_data=form_data)


@app.route("/videos", methods=["GET", "POST"])
def videos_page():
    result = None
    error = None
    form_data = {
        "keyword": "",
        "max_videos": "",
    }

    if request.method == "POST":
        form_data["keyword"] = (request.form.get("keyword") or "").strip()
        form_data["max_videos"] = (request.form.get("max_videos") or "").strip()

        try:
            if not form_data["keyword"]:
                raise ValueError("Keyword tidak boleh kosong.")

            max_videos = parse_positive_integer(form_data["max_videos"], "Jumlah video")
            result = run_video_search(
                keyword=form_data["keyword"],
                max_videos=max_videos,
                output_dir=app.config["OUTPUT_DIR"],
            )
        except Exception as exc:
            error = str(exc)

    return render_template("videos.html", result=result, error=error, form_data=form_data)


@app.route("/crawl", methods=["GET", "POST"])
def crawl_page():
    result = None
    error = None
    form_data = {
        "keyword": "",
        "max_videos": "",
        "comments_per_video": "",
    }

    if request.method == "POST":
        form_data["keyword"] = (request.form.get("keyword") or "").strip()
        form_data["max_videos"] = (request.form.get("max_videos") or "").strip()
        form_data["comments_per_video"] = (request.form.get("comments_per_video") or "").strip()

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
        except Exception as exc:
            error = str(exc)

    return render_template("crawl.html", result=result, error=error, form_data=form_data)


@app.get("/download/<path:filename>")
def download_file(filename: str):
    return send_from_directory(app.config["OUTPUT_DIR"], filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
