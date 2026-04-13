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

function verdictBadgeClass(verdict) {
  if (verdict === "PASS") return "pass";
  if (verdict === "REVIEW") return "review";
  if (verdict === "FAIL") return "fail";
  if (verdict === "LOW_CONFIDENCE") return "low";
  return "";
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

    if (r.expected_script) {
      const details = document.createElement("details");
      details.open = false;
      const sum = document.createElement("summary");
      sum.textContent = "Expected script";
      sum.style.cursor = "pointer";
      const txt = document.createElement("div");
      txt.className = "case-script";
      txt.textContent = r.expected_script;
      details.appendChild(sum);
      details.appendChild(txt);
      body.appendChild(details);
    }

    if (r.transcript) {
      const details = document.createElement("details");
      details.open = false;
      const sum = document.createElement("summary");
      sum.textContent = "Transcript";
      sum.style.cursor = "pointer";
      const txt = document.createElement("div");
      txt.className = "case-script";
      txt.textContent = r.transcript;
      details.appendChild(sum);
      details.appendChild(txt);
      body.appendChild(details);
    }

    const failures = (r.failures || []).slice(0, 6);
    if (failures.length) {
      const flags = document.createElement("div");
      flags.className = "case-flags";
      flags.textContent = `Flags: ${failures.join(" · ")}`;
      body.appendChild(flags);
    }

    if (r.highlights) {
      const h = r.highlights;
      const parts = [];
      if (h.wer !== undefined && h.wer !== null) parts.push(`WER=${Number(h.wer).toFixed(3)}`);
      if (h.vitals_mismatch_count) parts.push(`Vitals mismatches=${h.vitals_mismatch_count}`);
      if (h.term_mismatch_count) parts.push(`Term mismatches=${h.term_mismatch_count}`);
      if (h.entity_mismatch_count) parts.push(`Entity mismatches=${h.entity_mismatch_count}`);
      if (h.name_mismatch_count) parts.push(`Name mismatches=${h.name_mismatch_count}`);
      if (h.faithfulness_violation_count) parts.push(`Faithfulness violations=${h.faithfulness_violation_count}`);
      if (h.mos_score !== undefined && h.mos_score !== null) parts.push(`MOS=${h.mos_score}`);
      if (h.longest_pause_sec) parts.push(`Longest pause=${h.longest_pause_sec}s`);
      if (h.max_within_phrase_gap_sec) parts.push(`Max within-phrase gap=${h.max_within_phrase_gap_sec}s`);
      if (h.speaking_rate_wps) parts.push(`Rate=${h.speaking_rate_wps} wps`);
      if (h.pause_flag_count) parts.push(`Pause flags=${h.pause_flag_count}`);
      if (h.artifact_count) parts.push(`Artifacts=${h.artifact_count}`);
      if (parts.length) {
        const flags = document.createElement("div");
        flags.className = "case-flags";
        flags.textContent = `Highlights: ${parts.join(" · ")}`;
        body.appendChild(flags);
      }
    }

    if (r.audio_rel_path) {
      const audioWrap = document.createElement("div");
      audioWrap.className = "case-audio";
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.preload = "none";
      audio.src = `/eval/audio/${encodeURIComponent(r.suite_id || $("eval-suite").value)}/${r.audio_rel_path}`;
      audioWrap.appendChild(audio);
      body.appendChild(audioWrap);

      const pauseFlags = r.highlights?.pause_flags || [];
      if (Array.isArray(pauseFlags) && pauseFlags.length) {
        const list = document.createElement("div");
        list.className = "case-flags";
        list.textContent = "Pause flags (click to jump):";
        body.appendChild(list);

        for (const f of pauseFlags) {
          const row = document.createElement("div");
          row.className = "case-flags";
          const start = f.start_sec ?? f.gap_start_sec ?? f.gap_start ?? null;
          const dur = f.duration_sec ?? f.gap_sec ?? null;
          const label = `${f.type || "pause"} · ${dur ? dur + "s" : "—"} · ${start !== null ? "@" + start + "s" : ""}`.trim();
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "btn secondary";
          btn.style.padding = "6px 10px";
          btn.textContent = `Jump: ${label}`;
          btn.addEventListener("click", () => {
            const t = Number(start ?? 0);
            audio.currentTime = Math.max(0, t - 0.2);
            audio.scrollIntoView({ block: "nearest", behavior: "smooth" });
          });
          row.appendChild(btn);
          body.appendChild(row);
        }
      }
    }

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
  renderBaselineDelta(null);
  setHidden($("eval-secondary-actions"), true);
  setHidden($("eval-verdict-help"), true);

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
    renderTopFailures(summary.top_failures || []);
    setJson($("eval-json"), data);

    // Reveal secondary actions once a run exists.
    setHidden($("eval-secondary-actions"), false);
    const help = verdictHelpText("REVIEW");
    const helpEl = $("eval-verdict-help");
    if (helpEl) {
      helpEl.textContent = help + " Suite summary shows counts; use case cards for details.";
      setHidden(helpEl, false);
    }
  } catch (e) {
    setJson($("eval-json"), { error: String(e) });
    setSummary($("eval-summary"), "Error");
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

    const helpEl = $("single-verdict-help");
    if (helpEl) {
      helpEl.textContent = verdictHelpText(data.verdict);
      setHidden(helpEl, false);
    }

    // Why flagged
    renderList($("single-failures"), (data.failures || []).slice(0, 10));

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

    // Transcript comparison: show top non-equal diff ops
    const diffOps = data?.metrics?.accuracy?.diff_ops || [];
    const diffs = [];
    if (Array.isArray(diffOps)) {
      for (const op of diffOps) {
        if (!op || op.op === "equal") continue;
        diffs.push(`${op.op}: expected="${op.expected}" actual="${op.actual}"`);
        if (diffs.length >= 6) break;
      }
    }
    renderList($("single-diff"), diffs);

    // Key metrics
    const m = [];
    const acc = data?.metrics?.accuracy || {};
    if (acc?.wer !== undefined) m.push(`WER: ${acc.wer}`);
    if (acc?.accuracy_pct !== undefined) m.push(`Accuracy: ${acc.accuracy_pct}%`);
    const mos = data?.metrics?.mos?.mos_score;
    if (mos !== undefined && mos !== null) m.push(`MOS: ${mos}`);
    const tc = data?.metrics?.transcript_confidence || data?.transcript_confidence;
    if (tc) m.push(`Transcript confidence: ${tc}`);
    const ent = data?.metrics?.entity_fidelity || {};
    if (ent?.mismatch_count) m.push(`Entity mismatches: ${ent.mismatch_count}`);
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
