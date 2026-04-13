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
      opt.value = s.suite_id;
      opt.textContent = s.suite_id;
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
    el.textContent = chip;
    row.appendChild(el);
  }
  return row;
}

function caseMetricChips(highlights) {
  if (!highlights) return [];
  const h = highlights;
  const chips = [];
  if (h.vitals_mismatch_count) chips.push(`Vitals mismatches: ${h.vitals_mismatch_count}`);
  if (h.term_mismatch_count) chips.push(`Term mismatches: ${h.term_mismatch_count}`);
  if (h.entity_mismatch_count) chips.push(`Entity mismatches: ${h.entity_mismatch_count}`);
  if (h.name_mismatch_count) chips.push(`Name mismatches: ${h.name_mismatch_count}`);
  if (h.faithfulness_violation_count) chips.push(`Meaning drift signals: ${h.faithfulness_violation_count}`);
  if (h.mos_score !== undefined && h.mos_score !== null) chips.push(`Voice naturalness: ${h.mos_score}`);
  if (h.longest_pause_sec) chips.push(`Longest pause: ${h.longest_pause_sec}s`);
  if (h.max_within_phrase_gap_sec) chips.push(`Within-phrase gap: ${h.max_within_phrase_gap_sec}s`);
  if (h.speaking_rate_wps) chips.push(`Speaking rate: ${h.speaking_rate_wps} wps`);
  if (h.pause_flag_count) chips.push(`Pause flags: ${h.pause_flag_count}`);
  if (h.artifact_count) chips.push(`Audio artifacts: ${h.artifact_count}`);
  if (h.wer !== undefined && h.wer !== null) chips.push(`Transcript drift: WER ${Number(h.wer).toFixed(3)}`);
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
  setJson($("eval-json"), "Running suite (this can take a while if audio exists)...");
  $("eval-top-failures").innerHTML = "";
  $("eval-cases").innerHTML = "";
  renderSummaryStrip(null);
  renderBaselineDelta(null);
  setHidden($("eval-secondary-actions"), true);
  setHidden($("eval-review-guidance"), true);

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
    setJson($("eval-json"), { error: String(e) });
    setSummary($("eval-summary"), "Error");
    renderSummaryStrip(null);
  } finally {
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

    // Flagged moments: pauses + pause_naturalness + pops/clicks
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
    renderList($("single-moments"), moments);

    const diffOps = data?.metrics?.accuracy?.diff_ops || [];
    renderTranscriptComparison($("single-diff"), script, data.transcript || "", diffOps);

    const m = [];
    const acc = data?.metrics?.accuracy || {};
    if (acc?.wer !== undefined) m.push(`Transcript error: WER ${acc.wer}`);
    if (acc?.accuracy_pct !== undefined) m.push(`Transcript match: ${acc.accuracy_pct}%`);
    const mos = data?.metrics?.mos?.mos_score;
    if (mos !== undefined && mos !== null) m.push(`Voice naturalness: ${mos}`);
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
  $("single-failures").textContent = "Run an analysis to see results.";
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
