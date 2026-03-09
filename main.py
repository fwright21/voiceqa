import logging
import uuid
from pathlib import Path

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voiceqa")

app = FastAPI(title="VoiceQA", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/analyse")
async def analyse(
    audio: UploadFile = File(...),
    expected_script: str = Form(...),
):
    if not expected_script.strip():
        raise HTTPException(status_code=422, detail="expected_script must not be empty.")

    # Save uploaded file to disk temporarily
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    tmp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"

    try:
        async with aiofiles.open(tmp_path, "wb") as f:
            content = await audio.read()
            await f.write(content)

        from agent import run_analysis
        result = run_analysis(
            audio_path=str(tmp_path),
            expected_script=expected_script,
        )
        return JSONResponse(content=result)

    except Exception as exc:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        if tmp_path.exists():
            tmp_path.unlink()