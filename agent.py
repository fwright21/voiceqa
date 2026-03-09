import logging
from pathlib import Path

from tools.transcribe_audio import transcribe_audio
from tools.diff_transcript import diff_transcript
from tools.detect_pauses import detect_pauses
from tools.detect_audio_artifacts import detect_audio_artifacts
from tools.generate_qa_report import generate_qa_report
from tools.save_report import save_report

logger = logging.getLogger(__name__)

def run_analysis(audio_path: str, expected_script: str) -> dict:
    audio_name = Path(audio_path).name

    logger.info("Step 1/6 — Transcribing audio")
    transcription = transcribe_audio.func(audio_path=audio_path)
    transcript_text = transcription["transcript"]

    logger.info("Step 2/6 — Diffing transcript")
    diff = diff_transcript.func(
        expected_script=expected_script,
        actual_transcript=transcript_text,
    )
    print(f"DEBUG diff: {diff}")

    logger.info("Step 3/6 — Detecting pauses")
    pause_result = detect_pauses.func(audio_path=audio_path)

    logger.info("Step 4/6 — Detecting artifacts")
    artifact_result = detect_audio_artifacts.func(audio_path=audio_path)

    logger.info("Step 5/6 — Generating report")
    report = generate_qa_report.func(analysis_data={
        "audio_name":    audio_name,
        "transcription": transcription,
        "diff":          diff,
        "pauses":        pause_result,
        "artifacts":     artifact_result,
    })

    logger.info("Step 6/6 — Saving to database")
    saved = save_report.func(
        audio_name=audio_name,
        expected=expected_script,
        transcript=transcript_text,
        wer=diff["wer"],
        score=report["score"],
        suggestions=report["suggestions"],
        full_report=report["report_text"],
    )

    return {
        "report_id":   saved["report_id"],
        "audio_name":  audio_name,
        "score":       report["score"],
        "transcript":  transcript_text,
        "accuracy": {
            "wer":          diff["wer"],
            "mer":          diff["mer"],
            "wil":          diff["wil"],
            "accuracy_pct": diff["accuracy_pct"],
            "error_counts": diff["error_counts"],
        },
        "diff_ops":    diff["diff_ops"],
        "pauses":      pause_result,
        "artifacts":   artifact_result,
        "suggestions": report["suggestions"],
        "report_text": report["report_text"],
    }