import threading
import uuid
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import yt_dlp

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="YouTube Downloader")

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
JOB_TTL_SECONDS = 60 * 60  # ניקוי קבצים אחרי שעה


class InfoRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    quality: str = "best"   # "best" | "2160" | "1440" | "1080" | "720" | "480" | "360"
    mode: str = "video"     # "video" | "audio"


def _validate_url(url: str) -> str:
    url = (url or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(400, "כתובת לא תקינה — הדבק לינק מלא שמתחיל ב-http/https")
    return url


def build_format(quality: str, mode: str) -> str:
    if mode == "audio":
        return "ba/b"
    if quality == "best":
        return "bv*+ba/b"
    return f"bv*[height<={quality}]+ba/b[height<={quality}]/b"


@app.post("/api/info")
def get_info(req: InfoRequest):
    url = _validate_url(req.url)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"לא הצלחתי לקרוא את הסרטון: {e}")

    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]

    heights = sorted(
        {
            f.get("height")
            for f in info.get("formats", [])
            if f.get("vcodec") not in (None, "none") and f.get("height")
        },
        reverse=True,
    )
    return {
        "title": info.get("title"),
        "uploader": info.get("uploader") or info.get("channel"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "heights": heights,
    }


def run_download(job_id: str, url: str, quality: str, mode: str):
    job_dir = DOWNLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    def progress_hook(d):
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job is None:
                return
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                job["status"] = "downloading"
                job["percent"] = round(downloaded / total * 100, 1) if total else None
                job["speed"] = d.get("speed")
                job["eta"] = d.get("eta")
                job["downloaded_bytes"] = downloaded
                job["total_bytes"] = total
            elif d["status"] == "finished":
                # הורדת זרם בודד הסתיימה — ייתכן שעדיין נשאר מיזוג
                job["status"] = "processing"

    def postprocessor_hook(d):
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job is not None:
                job["status"] = "processing"

    opts = {
        "format": build_format(quality, mode),
        "outtmpl": str(job_dir / "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "merge_output_format": "mp4",
    }
    if mode == "audio":
        opts.pop("merge_output_format", None)
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",  # האיכות הגבוהה ביותר
            }
        ]

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        files = [
            p
            for p in job_dir.iterdir()
            if p.is_file() and not p.name.endswith((".part", ".ytdl"))
        ]
        if not files:
            raise RuntimeError("ההורדה הסתיימה אך לא נמצא קובץ פלט")
        out = max(files, key=lambda p: p.stat().st_size)

        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job is not None:
                job.update(
                    status="done",
                    percent=100,
                    filepath=str(out),
                    filename=out.name,
                    finished_at=time.time(),
                )
    except Exception as e:  # noqa: BLE001
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job is not None:
                job.update(status="error", error=str(e))


def _cleanup_old_jobs():
    now = time.time()
    with JOBS_LOCK:
        stale = [
            jid
            for jid, j in JOBS.items()
            if j.get("finished_at") and now - j["finished_at"] > JOB_TTL_SECONDS
        ]
        for jid in stale:
            JOBS.pop(jid, None)
    import shutil

    for jid in stale:
        shutil.rmtree(DOWNLOAD_DIR / jid, ignore_errors=True)


@app.post("/api/download")
def start_download(req: DownloadRequest):
    url = _validate_url(req.url)
    _cleanup_old_jobs()
    job_id = uuid.uuid4().hex
    with JOBS_LOCK:
        JOBS[job_id] = {"status": "queued", "percent": 0}
    t = threading.Thread(
        target=run_download, args=(job_id, url, req.quality, req.mode), daemon=True
    )
    t.start()
    return {"job_id": job_id}


@app.get("/api/progress/{job_id}")
def progress(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(404, "המשימה לא נמצאה")
        return {k: v for k, v in job.items() if k != "filepath"}


@app.get("/api/file/{job_id}")
def get_file(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if job is None or job.get("status") != "done" or not job.get("filepath"):
        raise HTTPException(404, "הקובץ עדיין לא מוכן")
    path = Path(job["filepath"])
    if not path.exists():
        raise HTTPException(404, "הקובץ נמחק מהשרת")
    return FileResponse(
        path, filename=job["filename"], media_type="application/octet-stream"
    )


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
