function $(id) {
  return document.getElementById(id);
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

function setVerdict(el, verdict) {
  el.textContent = verdict || "—";
}

function setScore(el, score) {
  if (score === null || score === undefined) el.textContent = "—";
  else el.textContent = String(score);
}

function setSummary(el, summary) {
  el.textContent = summary || "—";
}

function setJson(el, obj) {
  el.textContent = typeof obj === "string" ? obj : pretty(obj);
}

function setHidden(el, hidden) {
  if (!el) return;
  if (hidden) el.classList.add("hidden");
  else el.classList.remove("hidden");
}

function downloadText(filename, text, mime = "application/json") {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function nowStamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`;
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function switchTab(tabId) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));

  document.querySelector(`.tab[data-tab="${tabId}"]`)?.classList.add("active");
  $(`tab-${tabId}`)?.classList.add("active");
}

function verdictHelpText(verdict) {
  if (verdict === "FAIL") return "FAIL — critical fidelity or audio issues detected (should block release).";
  if (verdict === "REVIEW") return "REVIEW — non-critical issues or uncertain findings (listen and decide).";
  if (verdict === "LOW_CONFIDENCE") return "LOW_CONFIDENCE — analysis ran, but key signals were missing/low confidence.";
  if (verdict === "PASS") return "PASS — no major issues crossed thresholds.";
  return "";
}

function fmtTime(sec) {
  if (sec === null || sec === undefined || Number.isNaN(Number(sec))) return "—";
  const s = Math.max(0, Number(sec));
  const m = Math.floor(s / 60);
  const r = s - m * 60;
  return `${String(m).padStart(2, "0")}:${r.toFixed(1).padStart(4, "0")}`;
}

function renderList(container, items) {
  if (!container) return;
  if (!items || items.length === 0) {
    container.textContent = "—";
    return;
  }
  const ul = document.createElement("ul");
  for (const it of items) {
    const li = document.createElement("li");
    li.textContent = String(it);
    ul.appendChild(li);
  }
  container.innerHTML = "";
  container.appendChild(ul);
}

function renderListEl(items) {
  const div = document.createElement("div");
  if (!items || items.length === 0) {
    div.textContent = "—";
    return div;
  }
  const ul = document.createElement("ul");
  for (const it of items) {
    const li = document.createElement("li");
    li.textContent = String(it);
    ul.appendChild(li);
  }
  div.appendChild(ul);
  return div;
}

function parseSuggestionTask(text) {
  const s = String(text || "").trim();

  // New plain-language format: "What happened: ... || How to fix: ... || How to check: ..."
  if (s.includes("||")) {
    const parts = s.split("||").map((p) => p.trim()).filter(Boolean);
    const sections = { what: null, fix: null, check: null };
    let title = null;
    for (const p of parts) {
      const lower = p.toLowerCase();
      if (lower.startsWith("what happened:")) {
        sections.what = p.replace(/^what happened:\s*/i, "").trim();
        if (!title) title = sections.what;
      } else if (lower.startsWith("how to fix:")) {
        sections.fix = p.replace(/^how to fix:\s*/i, "").trim();
      } else if (lower.startsWith("how to check:")) {
        sections.check = p.replace(/^how to check:\s*/i, "").trim();
      } else if (!title) {
        title = p;
      }
    }
    return {
      title: title || s,
      doneWhen: null,
      what: sections.what,
      fix: sections.fix,
      check: sections.check,
    };
  }

  // Legacy format: "task (Done when: criterion)"
  const m = s.match(/^(.*)\s+\(Done when:\s*(.*)\)\s*$/);
  if (!m) return { title: s, doneWhen: null };
  return { title: (m[1] || "").trim(), doneWhen: (m[2] || "").trim() };
}

function renderTaskList(container, items) {
  if (!container) return;
  if (!items || items.length === 0) {
    container.textContent = "—";
    return;
  }
  const el = renderTaskListEl(items);
  container.innerHTML = "";
  container.appendChild(el);
}

function renderTaskListEl(items) {
  const div = document.createElement("div");
  if (!items || items.length === 0) {
    div.textContent = "—";
    return div;
  }
  const ul = document.createElement("ul");
  ul.className = "task-list";

  for (const it of items) {
    const t = parseSuggestionTask(it);
    const li = document.createElement("li");
    li.className = "task-item";

    const label = document.createElement("label");
    label.className = "task";

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "task-check";
    label.appendChild(cb);

    const text = document.createElement("div");
    text.className = "task-text";

    const title = document.createElement("div");
    title.className = "task-title";
    title.textContent = t.title || "Next action";
    text.appendChild(title);

    // New 3-part plain-language suggestion
    if (t.fix || t.check) {
      if (t.fix) {
        const fixRow = document.createElement("div");
        fixRow.className = "task-fix";
        const fixLabel = document.createElement("span");
        fixLabel.className = "task-label";
        fixLabel.textContent = "How to fix: ";
        fixRow.appendChild(fixLabel);
        fixRow.appendChild(document.createTextNode(t.fix));
        text.appendChild(fixRow);
      }
      if (t.check) {
        const checkRow = document.createElement("div");
        checkRow.className = "task-check-line";
        const checkLabel = document.createElement("span");
        checkLabel.className = "task-label";
        checkLabel.textContent = "How to check: ";
        checkRow.appendChild(checkLabel);
        checkRow.appendChild(document.createTextNode(t.check));
        text.appendChild(checkRow);
      }
    } else if (t.doneWhen) {
      // Legacy format
      const done = document.createElement("div");
      done.className = "task-done";
      done.textContent = `Done when: ${t.doneWhen}`;
      text.appendChild(done);
    }

    label.appendChild(text);
    li.appendChild(label);
    ul.appendChild(li);
  }

  div.appendChild(ul);
  return div;
}

function severityBadge(severity) {
  if (severity === "fail") return "✗";
  if (severity === "warn") return "⚠";
  if (severity === "info") return "ℹ";
  return "•";
}

function severityClass(severity) {
  if (severity === "fail") return "badge-fail";
  if (severity === "warn") return "badge-warn";
  if (severity === "info") return "badge-info";
  return "";
}

function jumpToRegion(startSec, targetAudio = null) {
  const audioEl = targetAudio || $("single-audio-player") || document.querySelector("audio");
  if (!audioEl) {
    console.warn("No audio element found for jump");
    return;
  }
  if (startSec === null || startSec === undefined) return;
  const desired = Number(startSec);
  if (!Number.isFinite(desired)) return;

  const seekAndPlay = () => {
    let t = Math.max(0, desired - 0.2);
    const d = Number(audioEl.duration);
    if (Number.isFinite(d) && d > 0) {
      t = Math.min(t, Math.max(0, d - 0.05));
    }
    try {
      audioEl.pause();
      audioEl.currentTime = Number(t);
    } catch {
      // Best-effort: some browsers throw if metadata isn't ready.
    }
    audioEl.play().catch(() => {});
  };

  // If the audio hasn't loaded metadata yet (preload="none"), wait until it can seek.
  if (audioEl.readyState < 1 || !audioEl.seekable || audioEl.seekable.length === 0) {
    audioEl.addEventListener("loadedmetadata", seekAndPlay, { once: true });
    try {
      audioEl.load();
    } catch {
      // ignore
    }
    return;
  }

  seekAndPlay();
}

function renderFlaggedRegions(container, regions, targetAudio = null) {
  if (!container) return;
  if (!regions || regions.length === 0) {
    container.textContent = "—";
    return;
  }
  container.innerHTML = "";
  const list = document.createElement("ul");
  list.className = "flagged-regions";

  for (const r of regions) {
    const li = document.createElement("li");
    li.className = "flagged-region-item";

    const badge = document.createElement("span");
    badge.className = `badge ${severityClass(r.severity)}`;
    badge.textContent = severityBadge(r.severity);
    li.appendChild(badge);

    const label = document.createElement("span");
    label.className = "fr-label";
    label.textContent = r.label || r.check || "Issue";
    li.appendChild(label);

    if (r.start_sec !== null && r.start_sec !== undefined) {
      const times = document.createElement("span");
      times.className = "fr-times";
      times.textContent = `${fmtTime(r.start_sec)} → ${fmtTime(r.end_sec)}`;
      li.appendChild(times);

      const jumpBtn = document.createElement("button");
      jumpBtn.className = "btn small";
      jumpBtn.type = "button";
      jumpBtn.textContent = "▶ Jump";
      jumpBtn.addEventListener("click", (e) => {
        e.preventDefault();
        jumpToRegion(r.start_sec, targetAudio);
      });
      li.appendChild(jumpBtn);
    } else {
      const noTs = document.createElement("span");
      noTs.className = "fr-no-ts muted";
      noTs.textContent = "(no timestamp)";
      li.appendChild(noTs);
    }

    list.appendChild(li);
  }
  container.appendChild(list);
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

// Hero shortcuts
$("hero-go-single")?.addEventListener("click", () => switchTab("single"));
$("hero-go-eval")?.addEventListener("click", () => switchTab("eval"));

async function loadSuites() {
  const select = $("eval-suite");
  select.innerHTML = "";
  setJson($("eval-json"), "Loading suites...");
  try {
    const resp = await fetch("/eval/suites");
    const data = await resp.json();
    const suites = data.suites || [];
    for (const s of suites) {
      const opt = document.createElement("option");
      const SUITE_LABELS = {
        "demo-test-suite": "Demo Test Suite",
        "hallucination-demo": "Large Demo — Hallucination",
        "prosody-demo": "Large Demo — Prosody",
        "symptom-triage": "Large Demo — Symptom Triage",
      };
      opt.value = s.suite_id;
      opt.textContent = SUITE_LABELS[s.suite_id] || s.suite_id;
      select.appendChild(opt);
    }
    setJson($("eval-json"), data);
  } catch (e) {
    setJson($("eval-json"), { error: String(e) });
  }
}

let lastEvalResult = null;
let lastSingleResult = null;

function toBaselinePayload(result) {
  if (!result) return null;
  const summary = result.summary || null;
  const reports = Array.isArray(result.reports) ? result.reports : [];
  const cases = reports.map((r) => ({
    case_id: r.case_id,
    verdict: r.verdict,
    score: r.score,
    failures: (r.failures || []).slice(0, 6),
    audio_rel_path: r.audio_rel_path || null,
  }));
  return { summary, cases };
}

function renderBaselineDelta(diff) {
  const el = $("eval-baseline-delta");
  if (!el) return;
  if (!diff) {
    el.style.display = "none";
    el.textContent = "";
    return;
  }
  const d = diff.delta || {};
  const parts = [
    `ΔPASS ${d.pass ?? 0}`,
    `ΔREVIEW ${d.review ?? 0}`,
    `ΔFAIL ${d.fail ?? 0}`,
    `ΔLOW_CONF ${d.low_confidence ?? 0}`,
  ];
  if (d.avg_score !== null && d.avg_score !== undefined) parts.push(`Δavg_score ${d.avg_score}`);
  el.textContent = `Baseline compare: ${parts.join(" · ")} (changed cases: ${(diff.changed_cases || []).length})`;
  el.style.display = "block";
}

function renderTopFailures(items) {
  const container = $("eval-top-failures");
  container.innerHTML = "";
  if (!items || items.length === 0) return;
  for (const it of items) {
    const pill = document.createElement("div");
    pill.className = "pill";
    const reason = document.createElement("div");
    reason.className = "reason";
    reason.textContent = it.reason;
    const count = document.createElement("div");
    count.className = "count";
    count.textContent = `x${it.count}`;
    pill.appendChild(reason);
    pill.appendChild(count);
    container.appendChild(pill);
  }
}

function renderSummaryStrip(summary) {
  const container = $("eval-summary-strip");
  if (!container) return;
  container.innerHTML = "";
  if (!summary) return;
  const items = [
    ["PASS", summary.pass || 0, "pass"],
    ["REVIEW", summary.review || 0, "review"],
    ["FAIL", summary.fail || 0, "fail"],
    ["LOW CONF", summary.low_confidence || 0, "low"],
  ];
  for (const [label, value, cls] of items) {
    const card = document.createElement("div");
    card.className = `summary-tile ${cls}`;
    const num = document.createElement("div");
    num.className = "summary-tile-value";
    num.textContent = value;
    const text = document.createElement("div");
    text.className = "summary-tile-label";
    text.textContent = label;
    card.appendChild(num);
    card.appendChild(text);
    container.appendChild(card);
  }
}

function verdictBadgeClass(verdict) {
  if (verdict === "PASS") return "pass";
  if (verdict === "REVIEW") return "review";
  if (verdict === "FAIL") return "fail";
  if (verdict === "LOW_CONFIDENCE") return "low";
  return "";
}

function humanIssue(issue) {
  const text = String(issue || "");
  const lower = text.toLowerCase();
  if (lower.includes("vitals mismatch")) return "Vital mismatch detected";
  if (lower.includes("critical term")) return "Critical symptom/medication term changed or missed";
  if (lower.includes("term mismatch")) return "Must-preserve term changed or missed";
  if (lower.includes("entity mismatch")) return "Number, code, or date mismatch";
  if (lower.includes("name mismatch")) return "Name or proper noun mismatch";
  if (lower.includes("mos score")) return "Voice naturalness score is low";
  if (lower.includes("faithfulness")) return "Possible meaning drift";
  if (lower.includes("pause")) return "Suspicious pause pattern";
  if (lower.includes("artifact") || lower.includes("clipping")) return "Audio artifact detected";
  return text;
}

function appendCaseSection(body, title, nodeOrText, extraClass = "") {
  const section = document.createElement("div");
  section.className = `case-section ${extraClass}`.trim();
  const heading = document.createElement("div");
  heading.className = "case-section-h";
  heading.textContent = title;
  section.appendChild(heading);
  if (typeof nodeOrText === "string") {
    const text = document.createElement("div");
    text.className = "case-section-text";
    text.textContent = nodeOrText;
    section.appendChild(text);
  } else {
    section.appendChild(nodeOrText);
  }
  body.appendChild(section);
  return section;
}

function appendScriptDetails(body, title, text) {
  if (!text) return;
  const details = document.createElement("details");
  details.open = false;
  const sum = document.createElement("summary");
  sum.textContent = title;
  sum.style.cursor = "pointer";
  const txt = document.createElement("div");
  txt.className = "case-script";
  txt.textContent = text;
  details.appendChild(sum);
  details.appendChild(txt);
  body.appendChild(details);
}

function renderChipRow(chips) {
  const row = document.createElement("div");
  row.className = "chip-row";
  for (const chip of chips) {
    const el = document.createElement("span");
    el.className = "chip";
    // Backward-compatible: chips can be strings or objects.
    if (typeof chip === "string") {
      el.textContent = chip;
    } else {
      el.textContent = chip.text || "";
      if (chip.tone) el.classList.add(`chip-${chip.tone}`);
      if (chip.title) {
        el.title = chip.title;
        el.setAttribute("aria-label", `${chip.text || ""}. ${chip.title}`);
        el.tabIndex = 0; // allow keyboard focus for tooltip
      }
    }
    row.appendChild(el);
  }
  return row;
}

function _fmtPct(x) {
  if (x === null || x === undefined || Number.isNaN(Number(x))) return "—";
  return `${Math.round(Number(x) * 1000) / 10}%`;
}

function _chip(text, title, tone = "neutral") {
  return { text, title, tone };
}

function _toneFromWer(wer) {
  const w = Number(wer);
  if (!Number.isFinite(w)) return "neutral";
  if (w > 0.30) return "bad";
  if (w > 0.10) return "warn";
  return "ok";
}

function _toneFromWps(wps) {
  const r = Number(wps);
  if (!Number.isFinite(r)) return "neutral";
  const wpm = r * 60.0;
  if (wpm > 260 || wpm < 90) return "bad";
  if (wpm > 220 || wpm < 120) return "warn";
  return "ok";
}

function _toneFromWpm(wpm) {
  const r = Number(wpm);
  if (!Number.isFinite(r)) return "neutral";
  if (r > 260 || r < 90) return "bad";
  if (r > 220 || r < 120) return "warn";
  return "ok";
}

function _toneFromSps(sps) {
  const r = Number(sps);
  if (!Number.isFinite(r)) return "neutral";
  if (r > 7.5 || r < 3.5) return "bad";
  if (r > 6.5 || r < 4.5) return "warn";
  return "ok";
}

function _toneFromMos(mos) {
  const m = Number(mos);
  if (!Number.isFinite(m)) return "neutral";
  if (m < 2.5) return "bad";
  if (m < 3.5) return "warn";
  return "ok";
}

function caseMetricChips(highlights) {
  if (!highlights) return [];
  const h = highlights;
  const chips = [];

  if (h.vitals_mismatch_count) {
    chips.push(
      _chip(
        `Vitals mismatches: ${h.vitals_mismatch_count}`,
        "Extracted vitals differed from expected (BP, SpO2, temperature). See case JSON: metrics.vitals_fidelity.",
        "bad"
      )
    );
  }
  if (h.term_mismatch_count) {
    chips.push(
      _chip(
        `Term mismatches: ${h.term_mismatch_count}`,
        "Must-preserve terms (symptoms/meds) differed from expected. See case JSON: metrics.term_fidelity.mismatches.",
        "bad"
      )
    );
  }
  if (h.entity_mismatch_count) {
    chips.push(
      _chip(
        `Entity mismatches: ${h.entity_mismatch_count}`,
        "Numbers/codes/dates differed from expected. See case JSON: metrics.entity_fidelity.mismatches.",
        "bad"
      )
    );
  }
  if (h.name_mismatch_count) {
    chips.push(
      _chip(
        `Name mismatches: ${h.name_mismatch_count}`,
        "Proper noun/name mismatch detected. See case JSON: metrics.name_fidelity.mismatches.",
        "warn"
      )
    );
  }
  if (h.faithfulness_violation_count) {
    chips.push(
      _chip(
        `Meaning drift signals: ${h.faithfulness_violation_count}`,
        "LLM-as-judge flagged possible addition/omission/contradiction. Advisory only. See case JSON: metrics.faithfulness.violations.",
        "warn"
      )
    );
  }
  if (h.mos_score !== undefined && h.mos_score !== null) {
    const tone = _toneFromMos(h.mos_score);
    chips.push(
      _chip(
        `Voice naturalness: ${h.mos_score}`,
        "Predicted MOS (1-5). Higher is better. <3.5 is often noticeable; <2.5 is poor. See case JSON: metrics.mos.",
        tone
      )
    );
  } else if (h.mos_skipped) {
    const detail = h.mos_error ? ` (${String(h.mos_error)})` : "";
    chips.push(
      _chip(
        "Voice naturalness: skipped",
        `MOS model not available${detail}. Install the optional 'speechmos' dependency to enable DNSMOS scoring.`,
        "warn"
      )
    );
  }
  if (h.longest_pause_sec) {
    const lp = Number(h.longest_pause_sec);
    const tone = Number.isFinite(lp) && lp > 3.0 ? "warn" : "neutral";
    chips.push(
      _chip(
        `Longest pause: ${h.longest_pause_sec}s`,
        "Longest detected silence gap. Long pauses can sound broken. See case JSON: metrics.pauses.pauses.",
        tone
      )
    );
  }
  if (h.max_within_phrase_gap_sec) {
    const g = Number(h.max_within_phrase_gap_sec);
    const tone = Number.isFinite(g) && g >= 1.6 ? "bad" : Number.isFinite(g) && g >= 0.9 ? "warn" : "neutral";
    chips.push(
      _chip(
        `Within-phrase gap: ${h.max_within_phrase_gap_sec}s`,
        "Max pause classified as within-phrase (more suspicious than between-phrase). See case JSON: metrics.pause_naturalness.flags.",
        tone
      )
    );
  }
  if (h.speaking_rate_overall !== undefined && h.speaking_rate_overall !== null) {
    const unit = h.speaking_rate_unit || "wpm";
    const tone =
      unit === "sps" ? _toneFromSps(h.speaking_rate_overall) : _toneFromWpm(h.speaking_rate_overall);
    const labelUnit = unit === "sps" ? "SPS" : "WPM";
    chips.push(
      _chip(
        `Speaking rate: ${h.speaking_rate_overall} ${labelUnit}`,
        `Estimated pace from aligned phrase spans. Typical English is ~120–220 WPM. See case JSON: metrics.speaking_rate.segments.`,
        tone
      )
    );
  } else if (h.speaking_rate_wps) {
    // Backward-compatible: older compact payloads expose words/sec from pause_naturalness.
    const tone = _toneFromWps(h.speaking_rate_wps);
    const wpm = Number(h.speaking_rate_wps) * 60.0;
    chips.push(
      _chip(
        `Speaking rate: ${h.speaking_rate_wps} wps`,
        `Estimated pace (words/sec). ~${Math.round(wpm)} WPM. Typical English is ~2.0–3.7 wps (~120–220 WPM). See case JSON: metrics.pause_naturalness.speaking_rate_wps.`,
        tone
      )
    );
  }
  if (h.pause_flag_count) {
    chips.push(
      _chip(
        `Pause flags: ${h.pause_flag_count}`,
        "Number of pause-nature flags raised (within/between phrase). See case JSON: metrics.pause_naturalness.flags.",
        "warn"
      )
    );
  }
  if (h.artifact_count) {
    chips.push(
      _chip(
        `Audio artifacts: ${h.artifact_count}`,
        "Potential signal issues (clipping, pops/clicks, DC offset, noise). Count is detected artifact types. See case JSON: metrics.artifacts.artifacts.",
        "warn"
      )
    );
  }
  if (h.wer !== undefined && h.wer !== null) {
    const tone = _toneFromWer(h.wer);
    chips.push(
      _chip(
        `Transcript drift: WER ${Number(h.wer).toFixed(3)}`,
        `Word Error Rate vs expected script. Lower is better. This is ${_fmtPct(h.wer)} word error. >10% is often noticeable; >30% is usually unusable.`,
        tone
      )
    );
  }
  return chips;
}

function appendDiffWords(container, diffOps, side, fallback) {
  if (!Array.isArray(diffOps) || diffOps.length === 0) {
    container.textContent = fallback || "—";
    return;
  }
  let wrote = false;
  for (const op of diffOps) {
    const raw = side === "expected" ? op.expected : op.actual;
    const words = String(raw || "").split(/\s+/).filter(Boolean);
    if (!words.length) continue;
    const span = document.createElement("span");
    let cls = "diff-token";
    if (op.op === "equal") cls += " diff-equal";
    else if (side === "expected" && (op.op === "delete" || op.op === "replace")) cls += " diff-missing";
    else if (side === "actual" && (op.op === "insert" || op.op === "replace")) cls += " diff-added";
    else cls += " diff-change";
    span.className = cls;
    span.textContent = words.join(" ");
    container.appendChild(span);
    container.appendChild(document.createTextNode(" "));
    wrote = true;
  }
  if (!wrote) container.textContent = fallback || "—";
}

function renderTranscriptComparison(container, expected, transcript, diffOps) {
  if (!container) return;
  container.innerHTML = "";
  if (!expected && !transcript) {
    container.textContent = "—";
    return;
  }

  const grid = document.createElement("div");
  grid.className = "transcript-grid";

  const expectedBox = document.createElement("div");
  expectedBox.className = "transcript-box";
  const expectedLabel = document.createElement("div");
  expectedLabel.className = "transcript-label";
  expectedLabel.textContent = "Expected";
  const expectedLine = document.createElement("div");
  expectedLine.className = "transcript-line";
  appendDiffWords(expectedLine, diffOps, "expected", expected || "—");
  expectedBox.appendChild(expectedLabel);
  expectedBox.appendChild(expectedLine);

  const actualBox = document.createElement("div");
  actualBox.className = "transcript-box";
  const actualLabel = document.createElement("div");
  actualLabel.className = "transcript-label";
  actualLabel.textContent = "Heard";
  const actualLine = document.createElement("div");
  actualLine.className = "transcript-line";
  appendDiffWords(actualLine, diffOps, "actual", transcript || "—");
  actualBox.appendChild(actualLabel);
  actualBox.appendChild(actualLine);

  grid.appendChild(expectedBox);
  grid.appendChild(actualBox);
  container.appendChild(grid);
}

function renderCases(reports) {
  const container = $("eval-cases");
  container.innerHTML = "";
  if (!reports || reports.length === 0) return;

  const includePass = $("eval-show-pass")?.checked;
  const search = ($("eval-search")?.value || "").trim().toLowerCase();
  const sort = ($("eval-sort")?.value || "severity").trim();
  const verdictFilter = includePass ? "all" : ($("eval-filter-verdict")?.value || "non_pass").trim();

  let filtered = reports;
  if (verdictFilter === "non_pass") filtered = filtered.filter((r) => r.verdict !== "PASS");
  else if (verdictFilter === "fail") filtered = filtered.filter((r) => r.verdict === "FAIL");
  else if (verdictFilter === "review") filtered = filtered.filter((r) => r.verdict === "REVIEW");
  else if (verdictFilter === "pass") filtered = filtered.filter((r) => r.verdict === "PASS");

  if (search) {
    filtered = filtered.filter((r) => {
      const blob = [
        r.case_id,
        r.audio_name,
        ...(r.tags || []),
        ...(r.failures || []),
        r.expected_script,
        r.transcript,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return blob.includes(search);
    });
  }

  const severitySorted = [...filtered].sort((a, b) => {
    const order = (v) => (v === "FAIL" ? 0 : v === "REVIEW" ? 1 : v === "LOW_CONFIDENCE" ? 2 : 3);
    return order(a.verdict) - order(b.verdict);
  });

  const sorted = (() => {
    if (sort === "score_asc") return [...severitySorted].sort((a, b) => (a.score ?? 0) - (b.score ?? 0));
    if (sort === "score_desc") return [...severitySorted].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    if (sort === "case_id")
      return [...severitySorted].sort((a, b) => String(a.case_id || "").localeCompare(String(b.case_id || "")));
    return severitySorted;
  })();

  for (const r of sorted) {
    const wrap = document.createElement("div");
    wrap.className = "case";

    const top = document.createElement("div");
    top.className = "case-top";

    const left = document.createElement("div");
    const id = document.createElement("div");
    id.className = "case-id";
    id.textContent = r.case_id || r.audio_name || "case";
    const badge = document.createElement("span");
    badge.className = `badge ${verdictBadgeClass(r.verdict)}`;
    badge.textContent = r.verdict || "—";
    const score = document.createElement("div");
    score.className = "case-score";
    score.textContent = `score=${r.score ?? "—"}`;
    left.appendChild(id);
    left.appendChild(badge);

    const right = document.createElement("div");
    right.appendChild(score);

    top.appendChild(left);
    top.appendChild(right);
    wrap.appendChild(top);

    const body = document.createElement("div");
    body.className = "case-body";

    const failures = (r.failures || []).slice(0, 6);
    if (failures.length) {
      const ul = document.createElement("ul");
      ul.className = "issue-list";
      for (const failure of failures) {
        const li = document.createElement("li");
        li.textContent = humanIssue(failure);
        ul.appendChild(li);
      }
      appendCaseSection(body, "Top issues", ul, "case-issues");
    }

    const suggestions = (r.suggestions || []).slice(0, 3);
    if (suggestions.length) {
      appendCaseSection(body, "Next actions", renderTaskListEl(suggestions), "case-suggestions");
    }

    const metricChips = caseMetricChips(r.highlights);
    if (metricChips.length) {
      appendCaseSection(body, "Checks that fired", renderChipRow(metricChips), "case-metrics");
    }

    if (r.audio_rel_path) {
      const audioWrap = document.createElement("div");
      audioWrap.className = "case-audio";
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.preload = "none";
      audio.src = `/eval/audio/${encodeURIComponent(r.suite_id || $("eval-suite").value)}/${r.audio_rel_path}`;
      audioWrap.appendChild(audio);
      appendCaseSection(body, "Audio review", audioWrap, "case-review");

      const flaggedRegions = r.flagged_regions || [];
      if (Array.isArray(flaggedRegions) && flaggedRegions.length) {
        const jumpList = document.createElement("div");
        renderFlaggedRegions(jumpList, flaggedRegions, audio);
        appendCaseSection(body, "Flagged moments", jumpList, "case-moments");
      } else {
        const pauseFlags = r.highlights?.pause_flags || [];
        if (Array.isArray(pauseFlags) && pauseFlags.length) {
          const jumpList = document.createElement("div");
          jumpList.className = "jump-list";

          for (const f of pauseFlags) {
            const start = f.start_sec ?? f.gap_start_sec ?? f.gap_start ?? null;
            const dur = f.duration_sec ?? f.gap_sec ?? null;
            const label = `${f.type || "pause"} · ${dur ? dur + "s" : "—"} · ${start !== null ? fmtTime(start) : ""}`.trim();
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "btn secondary";
            btn.textContent = `Jump: ${label}`;
            btn.addEventListener("click", () => {
              const t = Number(start ?? 0);
              audio.currentTime = Math.max(0, t - 0.2);
              audio.scrollIntoView({ block: "nearest", behavior: "smooth" });
            });
            jumpList.appendChild(btn);
          }
          appendCaseSection(body, "Flagged moments", jumpList, "case-moments");
        }
      }
    }

    appendScriptDetails(body, "Expected script", r.expected_script);
    appendScriptDetails(body, "Transcript", r.transcript);

    const actions = document.createElement("div");
    actions.className = "case-actions";
    const dl = document.createElement("button");
    dl.type = "button";
    dl.className = "btn secondary";
    dl.textContent = "Download case JSON";
    dl.addEventListener("click", () => {
      const fname = `voiceqa_${r.suite_id || "suite"}_${r.case_id || "case"}_${nowStamp()}.json`;
      downloadText(fname, pretty(r));
    });
    actions.appendChild(dl);
    body.appendChild(actions);

    const json = document.createElement("details");
    const sum = document.createElement("summary");
    sum.textContent = "View JSON";
    sum.style.cursor = "pointer";
    const pre = document.createElement("div");
    pre.className = "case-json";
    pre.textContent = pretty(r);
    json.appendChild(sum);
    json.appendChild(pre);
    body.appendChild(json);

    wrap.appendChild(body);
    container.appendChild(wrap);
  }
}

async function runSuite() {
  const suiteId = $("eval-suite").value;
  if (!suiteId) return;

  $("eval-run").disabled = true;
  setSummary($("eval-summary"), "Running...");
  setScore($("eval-avg-score"), null);
  $("eval-top-failures").innerHTML = "";
  $("eval-cases").innerHTML = "";
  renderSummaryStrip(null);
  renderBaselineDelta(null);
  setHidden($("eval-secondary-actions"), true);
  setHidden($("eval-review-guidance"), true);

  const statusBar = $("eval-status-bar");
  const startTime = Date.now();
  const messages = [
    "Transcribing audio with Whisper…",
    "Running deterministic checks…",
    "Checking entity and term fidelity…",
    "Analysing prosody and pauses…",
    "Generating verdicts…",
  ];
  let msgIdx = 0;
  if (statusBar) { statusBar.style.display = "block"; statusBar.textContent = messages[0]; }
  const loadingTimer = setInterval(() => {
    const elapsed = Math.round((Date.now() - startTime) / 1000);
    msgIdx = Math.min(msgIdx + 1, messages.length - 1);
    if (statusBar) statusBar.textContent = `${messages[msgIdx]} (${elapsed}s)`;
  }, 4000);

  try {
    const includeReports = $("eval-include-reports").checked;
    const fullJson = $("eval-full-json")?.checked;
    const reportMode = includeReports ? (fullJson ? "full" : "compact") : "none";
    const resp = await fetch("/eval/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ suite_id: suiteId, include_reports: includeReports, report_mode: reportMode }),
    });
    const data = await resp.json();
    lastEvalResult = data;
    if (data.reports && Array.isArray(data.reports)) {
      for (const r of data.reports) r.suite_id = suiteId;
      renderCases(data.reports);
    }
    const summary = data.summary || {};
    setSummary(
      $("eval-summary"),
      `${summary.pass || 0} PASS · ${summary.review || 0} REVIEW · ${summary.fail || 0} FAIL · ${summary.low_confidence || 0} LOW_CONF`
    );
    setScore($("eval-avg-score"), summary.avg_score);
    renderSummaryStrip(summary);
    renderTopFailures(summary.top_failures || []);
    setJson($("eval-json"), data);

    // Reveal secondary actions once a run exists.
    setHidden($("eval-secondary-actions"), false);
    const help = verdictHelpText("REVIEW");
    const helpEl = $("eval-review-guidance");
    if (helpEl) {
      helpEl.textContent = help + " Review guidance: start with FAIL and REVIEW cases, then compare against baseline if needed.";
      setHidden(helpEl, false);
    }
  } catch (e) {
    clearInterval(loadingTimer);
    if (statusBar) statusBar.style.display = "none";
    setJson($("eval-json"), { error: String(e) });
    setSummary($("eval-summary"), "Error");
    renderSummaryStrip(null);
  } finally {
    clearInterval(loadingTimer);
    if (statusBar) statusBar.style.display = "none";
    $("eval-run").disabled = false;
  }
}

async function saveBaseline() {
  const suiteId = $("eval-suite").value;
  const payload = toBaselinePayload(lastEvalResult);
  if (!suiteId || !payload) {
    setJson($("eval-json"), { error: "Run a suite with per-case reports before saving a baseline." });
    return;
  }
  try {
    const resp = await fetch("/eval/baseline/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ suite_id: suiteId, baseline: payload }),
    });
    const data = await resp.json();
    setJson($("eval-json"), data);
  } catch (e) {
    setJson($("eval-json"), { error: String(e) });
  }
}

async function compareBaseline() {
  const suiteId = $("eval-suite").value;
  const payload = toBaselinePayload(lastEvalResult);
  if (!suiteId || !payload) {
    setJson($("eval-json"), { error: "Run a suite with per-case reports before comparing." });
    return;
  }
  try {
    const resp = await fetch("/eval/baseline/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ suite_id: suiteId, current: payload }),
    });
    const data = await resp.json();
    renderBaselineDelta(data);
    setJson($("eval-json"), data);
  } catch (e) {
    renderBaselineDelta(null);
    setJson($("eval-json"), { error: String(e) });
  }
}

async function runSingle(formEvent) {
  formEvent.preventDefault();
  const file = $("single-audio").files[0];
  const script = $("single-script").value;
  if (!file || !script) return;

  const btn = document.querySelector("#single-form button[type='submit']");
  btn.disabled = true;
  setVerdict($("single-verdict"), "Running...");
  setScore($("single-score"), null);
  setJson($("single-json"), "Uploading and analysing...");
  setHidden($("single-verdict-help"), true);
  setHidden($("single-download-json"), true);
  setHidden($("single-copy-json"), true);

  try {
    const fd = new FormData();
    fd.append("audio", file);
    fd.append("expected_script", script);
    const resp = await fetch("/analyse", { method: "POST", body: fd });
    const data = await resp.json();
    lastSingleResult = data;
    setVerdict($("single-verdict"), data.verdict);
    setScore($("single-score"), data.score);
    setJson($("single-json"), data);
    setHidden($("single-download-json"), false);
    setHidden($("single-copy-json"), false);

    const helpEl = $("single-verdict-help");
    if (helpEl) {
      helpEl.textContent = verdictHelpText(data.verdict);
      setHidden(helpEl, false);
    }

    // Why flagged
    renderList($("single-failures"), (data.failures || []).map(humanIssue).slice(0, 10));

    // Suggestions (actionable next steps)
    renderTaskList($("single-suggestions"), (data.suggestions || []).slice(0, 3));

    // Flagged regions with timestamps (for jump-to-region)
    const flaggedRegions = data?.flagged_regions || [];
    renderFlaggedRegions($("single-moments"), flaggedRegions);

    // Legacy backward compat: also show pause_naturalness flags if no flagged_regions
    if (flaggedRegions.length === 0) {
      const moments = [];
      const pn = data?.metrics?.pause_naturalness || {};
      if (Array.isArray(pn?.flags)) {
        for (const f of pn.flags.slice(0, 6)) {
          const start = f.start_sec ?? null;
          const end = f.end_sec ?? null;
          const dur = f.duration_sec ?? null;
          moments.push(`${fmtTime(start)}–${fmtTime(end)} · ${f.type || "pause"} · ${dur ? dur.toFixed(2) + "s" : "—"}`);
        }
      }
      const pauses = data?.metrics?.pauses?.pauses || [];
      if (Array.isArray(pauses)) {
        for (const p of pauses.slice(0, 4)) {
          if (p?.duration_sec >= 1.0) {
            moments.push(`${fmtTime(p.start_sec)}–${fmtTime(p.end_sec)} · silence · ${Number(p.duration_sec).toFixed(2)}s`);
          }
        }
      }
      const artifacts = data?.metrics?.artifacts?.artifacts || [];
      if (Array.isArray(artifacts)) {
        for (const a of artifacts.slice(0, 3)) {
          moments.push(`artifact · ${a.type} · ${a.detail}`);
        }
      }
      if (moments.length > 0) {
        renderList($("single-moments"), moments);
      }
    }

    const diffOps = data?.metrics?.accuracy?.diff_ops || [];
    renderTranscriptComparison($("single-diff"), script, data.transcript || "", diffOps);

    const m = [];
    const acc = data?.metrics?.accuracy || {};
    if (acc?.wer !== undefined) m.push(`Transcript error: WER ${acc.wer}`);
    if (acc?.accuracy_pct !== undefined) m.push(`Transcript match: ${acc.accuracy_pct}%`);
    const mosObj = data?.metrics?.mos || {};
    const mos = mosObj?.mos_score;
    if (mos !== undefined && mos !== null) m.push(`Voice naturalness: ${mos}`);
    else if (mosObj?.skipped) m.push(`Voice naturalness: skipped`);
    const tc = data?.metrics?.transcript_confidence || data?.transcript_confidence;
    if (tc) m.push(`Transcript confidence: ${tc}`);
    const ent = data?.metrics?.entity_fidelity || {};
    if (ent?.mismatch_count) m.push(`Number/code/date mismatches: ${ent.mismatch_count}`);
    renderList($("single-metrics"), m);
  } catch (e) {
    setVerdict($("single-verdict"), "Error");
    setJson($("single-json"), { error: String(e) });
  } finally {
    btn.disabled = false;
  }
}

$("eval-refresh").addEventListener("click", loadSuites);
$("eval-run").addEventListener("click", runSuite);
$("eval-save-baseline")?.addEventListener("click", saveBaseline);
$("eval-compare-baseline")?.addEventListener("click", compareBaseline);
$("eval-show-pass")?.addEventListener("change", () => {
  if (lastEvalResult?.reports) renderCases(lastEvalResult.reports);
});
$("eval-search")?.addEventListener("input", () => {
  if (lastEvalResult?.reports) renderCases(lastEvalResult.reports);
});
$("eval-sort")?.addEventListener("change", () => {
  if (lastEvalResult?.reports) renderCases(lastEvalResult.reports);
});
$("eval-filter-verdict")?.addEventListener("change", () => {
  if (lastEvalResult?.reports) renderCases(lastEvalResult.reports);
});

$("eval-download-json")?.addEventListener("click", () => {
  if (!lastEvalResult) return setJson($("eval-json"), { error: "Run a suite first." });
  const suiteId = $("eval-suite").value || "suite";
  downloadText(`voiceqa_${suiteId}_${nowStamp()}.json`, pretty(lastEvalResult));
});

function csvEscape(v) {
  const s = String(v ?? "");
  if (s.includes('"') || s.includes(",") || s.includes("\n")) return `"${s.replaceAll('"', '""')}"`;
  return s;
}

$("eval-download-csv")?.addEventListener("click", () => {
  if (!lastEvalResult) return setJson($("eval-json"), { error: "Run a suite first (with per-case reports enabled)." });
  const suiteId = $("eval-suite").value || "suite";
  const reports = Array.isArray(lastEvalResult?.reports) ? lastEvalResult.reports : [];
  const header = ["case_id", "verdict", "score", "failures", "tags", "audio_rel_path"];
  const rows = [header];
  for (const r of reports) {
    rows.push([
      r.case_id || "",
      r.verdict || "",
      r.score ?? "",
      (r.failures || []).join(" | "),
      (r.tags || []).join(","),
      r.audio_rel_path || "",
    ]);
  }
  const csv = rows.map((r) => r.map(csvEscape).join(",")).join("\n");
  downloadText(`voiceqa_${suiteId}_${nowStamp()}.csv`, csv, "text/csv");
});

$("single-form").addEventListener("submit", runSingle);
$("single-audio").addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  const playerRow = $("single-audio-player-row");
  const player = $("single-audio-player");
  if (file && player && playerRow) {
    const url = URL.createObjectURL(file);
    player.src = url;
    setHidden(playerRow, false);
  } else if (playerRow) {
    setHidden(playerRow, true);
  }
});
$("single-clear").addEventListener("click", () => {
  $("single-audio").value = "";
  $("single-script").value = "";
  setVerdict($("single-verdict"), "—");
  setScore($("single-score"), null);
  setJson($("single-json"), "Run an analysis to see output.");
  lastSingleResult = null;
  setHidden($("single-verdict-help"), true);
  setHidden($("single-download-json"), true);
  setHidden($("single-copy-json"), true);
  setHidden($("single-audio-player-row"), true);
  $("single-failures").textContent = "Run an analysis to see results.";
  $("single-suggestions").textContent = "—";
  $("single-moments").textContent = "—";
  $("single-diff").textContent = "—";
  $("single-metrics").textContent = "—";
});

$("single-download-json")?.addEventListener("click", () => {
  if (!lastSingleResult) return setJson($("single-json"), "Run an analysis first.");
  downloadText(`voiceqa_single_${nowStamp()}.json`, pretty(lastSingleResult));
});
$("single-copy-json")?.addEventListener("click", async () => {
  const ok = await copyToClipboard(pretty(lastSingleResult || {}));
  if (!ok) setJson($("single-json"), { error: "Copy failed (browser blocked clipboard)." });
});

loadSuites();
