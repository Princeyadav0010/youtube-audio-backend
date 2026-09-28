import os
import shutil
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel


app = FastAPI(title="YouTube Audio Backend")


class DownloadRequest(BaseModel):
    url: str


def is_youtube_url(url: str) -> bool:
    try:
        parsed = urlparse(url)

        host = parsed.netloc.lower().split(":")[0]

        allowed_hosts = {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "music.youtube.com",
            "youtu.be",
        }

        return (
            parsed.scheme in {"http", "https"}
            and host in allowed_hosts
        )

    except Exception:
        return False


def download_audio(url: str) -> str:
    temp_dir = tempfile.mkdtemp(
        prefix="yt_"
    )

    output_template = os.path.join(
        temp_dir,
        "%(id)s.%(ext)s"
    )

    options = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,

        # Current yt-dlp recommendation:
        # use mweb with a PO-token provider
        "extractor_args": {
            "youtube": {
                "player_client": ["mweb"]
            }
        },

        # Try modern JS challenge support
        "remote_components": ["ejs:npm"],
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(
                url,
                download=True
            )

            downloaded = ydl.prepare_filename(
                info
            )

            if os.path.exists(downloaded):
                return downloaded

            base = os.path.splitext(
                downloaded
            )[0]

            candidates = [
                base + ".webm",
                base + ".m4a",
                base + ".mp4",
                base + ".opus",
                base + ".wav",
            ]

            for path in candidates:
                if os.path.exists(path):
                    return path

        raise FileNotFoundError(
            "Downloaded audio file not found."
        )

    except Exception:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )
        raise


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "youtube-audio-backend"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/download-audio")
def download_audio_endpoint(
    request: DownloadRequest
):
    url = request.url.strip()

    if not is_youtube_url(url):
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid YouTube URL."
        )

    try:
        file_path = download_audio(url)

        return FileResponse(
            path=file_path,
            media_type="application/octet-stream",
            filename=f"{uuid.uuid4().hex}{Path(file_path).suffix}",
            background=None,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"YouTube download failed: {e}"
        ) from e