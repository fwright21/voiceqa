import os
import json
import re
from langchain_core.tools import tool
from langchain_ollama import OllamaLLM

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")

_REPORT_PROMPT = """\
You are VoiceQA, an expert QA engineer evaluating Text-to-Speech (TTS) voice agent outputs.

You have been given structured analysis results for one audio file. Write a concise QA report.

## Analysis Data
```json
{analysis_json}
```

You MUST follow this EXACT format. Do not add extra text or change the section headers:

### Overall Score
[JUST a single integer between 0 and 100. Nothing else on this line. Example: 87]

### Summary
2-3 sentences summarising the quality.

### Transcript Accuracy
Comment on the WER score and specific word errors from diff_ops.

### Pause Analysis
Flag any unnatural pauses with their timestamps and durations.

### Audio Artifact Analysis
List any detected artifacts and their likely causes.

### Suggestions
1. First suggestion
2. Second suggestion
3. Third suggestion
"""

@tool("generate_qa_report")
def generate_qa_report(analysis_data: dict) -> dict:
    """
    Use a local Ollama LLM to synthesise all QA analysis results into a
    human-readable report with an overall score and suggestions.

    Args:
        analysis_data: Dict containing results from all previous tools.

    Returns:
        A dict with report_text, score, and suggestions.
    """
    llm = OllamaLLM(
        model=OLLAMA_MODEL,
        base_url="http://localhost:11434",
        temperature=0.2,
    )

    prompt = _REPORT_PROMPT.format(
        analysis_json=json.dumps(analysis_data, indent=2)
    )

    report_text = llm.invoke(prompt)

    # More flexible score extraction — finds any number after Overall Score
    score = 50
    score_match = re.search(r"###\s*Overall Score\s*\n+\s*(\d+)", report_text)
    if not score_match:
        # fallback: find any standalone number 0-100 near "score"
        score_match = re.search(r"(?:score|Score)[^\d]*(\d{1,3})", report_text)
    if score_match:
        score = min(100, max(0, int(score_match.group(1))))

    # Extract suggestions
    suggestions = []
    in_suggestions = False
    for line in report_text.splitlines():
        if "### Suggestions" in line:
            in_suggestions = True
            continue
        if in_suggestions:
            if line.startswith("###"):
                break
            cleaned = re.sub(r"^\s*\d+[\.\)]\s*", "", line).strip()
            if cleaned and not cleaned.startswith("*"):
                suggestions.append(cleaned)

    return {
        "report_text": report_text,
        "score":       score,
        "suggestions": suggestions,
    }