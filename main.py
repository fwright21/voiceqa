import logging
import uuid
from pathlib import Path
from typing import List

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voiceqa")

app = FastAPI(title="VoiceQA", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

UI_DIR = Path(__file__).parent / "ui"
STATIC_DIR = UI_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/ui")
async def ui() -> HTMLResponse:
    index_path = UI_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=500, detail="UI assets missing (ui/index.html not found).")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/analyse")
async def analyse(
    audio: UploadFile = File(...),
    expected_script: str = Form(...),
):
    """
    Analyse a single audio file against an expected script.

    Returns a full VoiceQA report including:
      - verdict: PASS | REVIEW | FAIL | LOW_CONFIDENCE
      - failures: list of specific reasons driving the verdict
      - score: 0–100
      - metrics: nested dict with all analysis results
      - report_text: human-readable summary
    """
    if not expected_script.strip():
        raise HTTPException(status_code=422, detail="expected_script must not be empty.")

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


class EvalRunRequest(BaseModel):
    suite_id: str
    include_reports: bool = False
    report_mode: str = "none"  # none | compact | full


@app.get("/eval/suites")
async def eval_suites():
    from tools.eval_runner import list_suites

    return {"suites": list_suites()}


@app.post("/eval/run")
async def eval_run(req: EvalRunRequest):
    from tools.eval_runner import compact_report, run_suite

    result = run_suite(req.suite_id)
    report_mode = (req.report_mode or "none").lower().strip()
    if req.include_reports and report_mode == "none":
        report_mode = "full"

    if report_mode == "none":
        result = {k: v for k, v in result.items() if k != "reports"}
    elif report_mode == "compact":
        result["reports"] = [compact_report(r) for r in (result.get("reports") or [])]
    elif report_mode == "full":
        pass
    else:
        raise HTTPException(status_code=422, detail="report_mode must be one of: none, compact, full")
    return JSONResponse(content=result)


class EvalBaselineSaveRequest(BaseModel):
    suite_id: str
    baseline: dict


class EvalBaselineCompareRequest(BaseModel):
    suite_id: str
    current: dict


@app.post("/eval/baseline/save")
async def eval_baseline_save(req: EvalBaselineSaveRequest):
    from tools.eval_runner import save_baseline

    return JSONResponse(content=save_baseline(req.suite_id, req.baseline))


@app.post("/eval/baseline/compare")
async def eval_baseline_compare(req: EvalBaselineCompareRequest):
    from tools.eval_runner import compare_to_baseline

    return JSONResponse(content=compare_to_baseline(req.suite_id, req.current))


@app.get("/eval/audio/{suite_id}/{audio_rel_path:path}")
async def eval_audio(suite_id: str, audio_rel_path: str):
    """
    Serve eval_set audio files to the UI.
    Paths are restricted to files under eval_set/suites/<suite_id>/.
    """
    from tools.eval_runner import EVAL_ROOT

    suite_dir = (EVAL_ROOT / suite_id).resolve()
    if not suite_dir.exists():
        raise HTTPException(status_code=404, detail="Unknown suite_id")

    candidate = (suite_dir / audio_rel_path).resolve()
    if suite_dir not in candidate.parents and candidate != suite_dir:
        raise HTTPException(status_code=400, detail="Invalid path")

    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")

    if candidate.suffix.lower() not in {".wav", ".mp3", ".m4a", ".flac", ".ogg"}:
        raise HTTPException(status_code=415, detail="Unsupported audio type")

    return FileResponse(path=str(candidate))


@app.post("/analyse/batch")
async def analyse_batch(
    audio_files: List[UploadFile] = File(...),
    expected_scripts: List[str] = Form(...),
):
    """
    Analyse a batch of audio files (5–20 recommended for MVP).

    audio_files and expected_scripts must be the same length — paired by index.

    Returns:
        {
          "total": int,
          "pass": int,
          "review": int,
          "fail": int,
          "low_confidence": int,
          "reports": [ ...per-audio report... ]
        }
    """
    if len(audio_files) != len(expected_scripts):
        raise HTTPException(
            status_code=422,
            detail=f"audio_files ({len(audio_files)}) and expected_scripts "
                   f"({len(expected_scripts)}) must have the same length.",
        )

    if len(audio_files) == 0:
        raise HTTPException(status_code=422, detail="No audio files provided.")

    from agent import run_analysis

    tmp_paths = []
    reports = []
    counts = {"PASS": 0, "REVIEW": 0, "FAIL": 0, "LOW_CONFIDENCE": 0}

    try:
        # Save all files first
        for audio in audio_files:
            suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
            tmp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
            async with aiofiles.open(tmp_path, "wb") as f:
                content = await audio.read()
                await f.write(content)
            tmp_paths.append(tmp_path)

        # Process sequentially
        for i, (tmp_path, expected) in enumerate(zip(tmp_paths, expected_scripts)):
            logger.info(f"Batch: processing file {i + 1}/{len(tmp_paths)}")
            try:
                result = run_analysis(
                    audio_path=str(tmp_path),
                    expected_script=expected,
                )
                reports.append(result)
                verdict = result.get("verdict", "FAIL")
                counts[verdict] = counts.get(verdict, 0) + 1
            except Exception as exc:
                logger.error(f"Failed on file {i + 1}: {exc}")
                reports.append({
                    "audio_name": tmp_path.name,
                    "verdict":    "FAIL",
                    "failures":   [f"Processing error: {str(exc)}"],
                    "score":      0,
                    "error":      str(exc),
                })
                counts["FAIL"] += 1

        return JSONResponse(content={
            "total":          len(reports),
            "pass":           counts.get("PASS", 0),
            "review":         counts.get("REVIEW", 0),
            "fail":           counts.get("FAIL", 0),
            "low_confidence": counts.get("LOW_CONFIDENCE", 0),
            "reports":        reports,
        })

    finally:
        for p in tmp_paths:
            if p.exists():
                p.unlink()
