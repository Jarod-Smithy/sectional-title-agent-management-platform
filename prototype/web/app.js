"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

function esc(s) {
  return (s ?? "").replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c],
  );
}

// ── Tabs ─────────────────────────────────────────────────────────────────────
$$(".tabs button").forEach((btn) =>
  btn.addEventListener("click", () => {
    $$(".tabs button").forEach((b) => b.classList.remove("active"));
    $$(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
    refresh(btn.dataset.tab);
  }),
);

// ── Inbox / drafts ───────────────────────────────────────────────────────────
$("#email-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const payload = {
    sender: f.sender.value,
    from_unit: f.from_unit.value,
    subject: f.subject.value,
    body: f.body.value,
  };
  try {
    const out = await api("/api/inbox", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    f.subject.value = "";
    f.body.value = "";
    if (out && out.kind === "task") {
      await loadBoard();
      toast(
        "Chairman task created on the board: “" +
          (out.ticket?.title || "task") +
          "”.",
      );
    } else {
      await loadDrafts();
    }
  } catch (err) {
    alert("Error: " + err.message);
  }
});

function findingHtml(f) {
  return `<div class="finding ${esc(f.severity)}"><strong>${esc(
    f.severity.toUpperCase(),
  )}</strong> · ${esc(f.message)}</div>`;
}

function inboundHtml(d) {
  if (!d.inbound_subject && !d.inbound_snippet) return "";
  const about =
    d.unit && d.unit !== d.from_unit
      ? ` · about <strong>${esc(d.unit)}</strong>`
      : "";
  const from = d.from_unit ? ` (${esc(d.from_unit)})` : "";
  return `<div class="inbound">
    <div class="inbound-head">From <strong>${esc(
      d.party,
    )}</strong>${from}${about}</div>
    <div class="inbound-subj">${esc(d.inbound_subject)}</div>
    <div class="inbound-snip">${esc(d.inbound_snippet)}</div>
  </div>`;
}

function tagsHtml(d) {
  return `<div class="row">
    <span class="tag intent">${esc(d.intent)}</span>
    <span class="tag ${d.priority === "high" ? "high" : ""}">${esc(
      d.priority,
    )}</span>
    ${d.unit ? `<span class="tag">${esc(d.unit)}</span>` : ""}
    <span class="tag">${esc(d.case_ref)}</span>
  </div>`;
}

function sourcesHtml(d) {
  return d.sources.length
    ? `<div class="sources"><strong>Grounded in:</strong><ul>${d.sources
        .map((s) => `<li>${esc(s.title)} <em>(${esc(s.kind)})</em></li>`)
        .join("")}</ul></div>`
    : "";
}

function pendingDraftHtml(d) {
  const blocked = d.findings.some((f) => f.severity === "block");
  return `<div class="draft" data-id="${d.id}">
    ${tagsHtml(d)}
    ${inboundHtml(d)}
    ${d.findings.map(findingHtml).join("")}
    <textarea rows="8">${esc(d.body)}</textarea>
    ${sourcesHtml(d)}
    <div class="actions">
      <button class="small" data-act="save">Save edit</button>
      <button class="small approve" data-act="approve" ${
        blocked ? "disabled title='Resolve BLOCK findings first'" : ""
      }>Approve — file &amp; raise task</button>
      <button class="small ghost danger" data-act="discard">Not needed</button>
    </div>
  </div>`;
}

function filedDraftHtml(d) {
  const auto = d.status === "auto_filed";
  const badge = auto
    ? `<span class="tag auto">auto-filed</span>`
    : `<span class="tag filed">filed</span>`;
  return `<div class="draft filed-card" data-id="${d.id}">
    <div class="row">
      <span class="tag intent">${esc(d.intent)}</span>
      ${d.unit ? `<span class="tag">${esc(d.unit)}</span>` : ""}
      <span class="tag">${esc(d.case_ref)}</span>
      ${badge}
    </div>
    ${inboundHtml(d)}
    <pre class="reply">${esc(d.body)}</pre>
  </div>`;
}

async function loadDrafts() {
  const drafts = await api("/api/drafts");
  const pending = drafts.filter((d) => d.status === "pending");
  const filed = drafts.filter(
    (d) => d.status === "filed" || d.status === "auto_filed",
  );

  const pendEl = $("#drafts");
  pendEl.innerHTML = pending.length
    ? pending.map(pendingDraftHtml).join("")
    : `<p class="empty">No drafts awaiting approval.</p>`;

  const filedEl = $("#filed");
  filedEl.innerHTML = filed.length
    ? filed.map(filedDraftHtml).join("")
    : `<p class="empty">Nothing filed yet.</p>`;

  $$(".draft", pendEl).forEach((card) => {
    const id = card.dataset.id;
    const ta = $("textarea", card);
    const save = $('[data-act="save"]', card);
    const approve = $('[data-act="approve"]', card);
    const discard = $('[data-act="discard"]', card);
    if (save)
      save.addEventListener("click", async () => {
        await api(`/api/drafts/${id}`, {
          method: "PUT",
          body: JSON.stringify({ body: ta.value }),
        });
        await loadDrafts();
      });
    if (approve)
      approve.addEventListener("click", async () => {
        // A WARN (e.g. potential defamation) is the human's call — make them
        // take explicit responsibility before it is filed.
        const card2 = approve.closest(".draft");
        const hasWarn = $$(".finding.warn", card2).length > 0;
        if (
          hasWarn &&
          !confirm(
            "This reply triggered a wording WARNING (e.g. possible defamation). " +
              "You are responsible for this wording. File it anyway?",
          )
        )
          return;
        try {
          // Always send the on-screen text; the server re-screens it so an
          // in-place edit can never bypass the Governance Guardian.
          await api(`/api/drafts/${id}/approve`, {
            method: "POST",
            body: JSON.stringify({ body: ta.value }),
          });
          await loadDrafts();
          await loadBoard();
          toast(
            "Reply filed to the " +
              (card2.querySelector(".tag:nth-child(3)")?.textContent ||
                "scheme") +
              " record and a task was created. Nothing was emailed.",
          );
        } catch (err) {
          alert("Blocked: " + err.message);
          await loadDrafts();
        }
      });
    if (discard)
      discard.addEventListener("click", async () => {
        if (!confirm("Discard this draft as not needed?")) return;
        await api(`/api/drafts/${id}/discard`, { method: "POST" });
        await loadDrafts();
      });
  });
}

function toast(msg) {
  let el = $("#toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 4000);
}

// ── Board ────────────────────────────────────────────────────────────────────
async function loadBoard() {
  const tickets = await api("/api/tickets");
  $$(".board .col").forEach((col) => {
    const status = col.dataset.status;
    const cards = $(".cards", col);
    const mine = tickets
      .filter((t) => t.status === status)
      .sort((a, b) => (b.priority === "high") - (a.priority === "high"));
    cards.innerHTML = mine.length
      ? mine.map(ticketHtml).join("")
      : `<p class="empty">—</p>`;
  });
  $$(".card [data-move]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      await api(`/api/tickets/${btn.dataset.id}/status`, {
        method: "POST",
        body: JSON.stringify({ status: btn.dataset.move }),
      });
      await loadBoard();
    }),
  );
  $$(".card [data-assist]").forEach((btn) =>
    btn.addEventListener("click", () => runAssist(btn.dataset.assist, btn)),
  );
}

const SOURCE_LABEL = {
  email: "from reply",
  chair_email: "chairman email",
  manual: "added manually",
  resolution: "from resolution",
};

// ── Specialist agent assist ──────────────────────────────────────────────────
let ASSIST = { available: false, enabled: false, kill_switch: false };

const SPECIALIST_NAMES = {
  legal_compliance: "Legal & Compliance Analyst",
  financial_oversight: "Financial Oversight Analyst",
  maintenance: "Maintenance Coordinator",
  knowledge_auditor: "Knowledge Auditor",
  trustee_copilot: "Trustee Copilot",
};

const KIND_LABEL = {
  document: "document",
  research_brief: "research",
  action_plan: "action plan",
  correspondence: "correspondence",
  calculation: "calculation",
};

// Plain-language nouns for the value summary line.
const KIND_NOUN = {
  document: "draft document",
  research_brief: "research brief",
  action_plan: "action plan",
  correspondence: "draft reply",
  calculation: "calculation",
};

// Plain-language description of the tool each specialist used (no jargon).
const TOOL_LABEL = {
  code_interpreter: "worked out the figures",
  browser: "researched online sources",
  "gateway/document_brain": "used the scheme's records",
  memory: "used the scheme's history",
};

// Rough USD→ZAR display rate so cost reads in Rand like everything else.
const ZAR_RATE = 18.5;

async function loadAssistConfig() {
  try {
    ASSIST = await api("/api/assist/config");
  } catch (_) {}
  const en = $("#assist-enabled");
  const kill = $("#assist-kill");
  if (en) en.checked = !!ASSIST.enabled;
  if (kill) kill.checked = !!ASSIST.kill_switch;
}

async function setAssistConfig(patch) {
  ASSIST = await api("/api/assist/config", {
    method: "POST",
    body: JSON.stringify(patch),
  });
  $("#assist-enabled").checked = !!ASSIST.enabled;
  $("#assist-kill").checked = !!ASSIST.kill_switch;
  loadBoard();
}

async function runAssist(id, btn) {
  const box = $(`#assist-${id}`);
  if (box && !box.hidden && box.innerHTML.trim()) {
    if (
      !confirm(
        "Run the agent team again? This starts a fresh analysis and replaces the current result.",
      )
    ) {
      return;
    }
  }
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Agents working…";
  if (box) {
    box.hidden = false;
    box.innerHTML = `<div class="assist-skeleton"><span class="spin"></span> Your agent team is working on this task…</div>`;
  }
  try {
    const run = await api(`/api/tickets/${id}/assist`, { method: "POST" });
    let threads = { threads: [] };
    try {
      threads = await api(`/api/tickets/${id}/threads`);
    } catch (_) {}
    box.innerHTML = assistHtml(run, threads);
    wireAssistSend(box, id);
  } catch (e) {
    if (box) box.innerHTML = "";
    toast(e.message || "Agent assist failed.");
  }
  btn.disabled = false;
  btn.textContent = label;
}

function aOrAn(noun) {
  return /^[aeiou]/i.test(noun) ? "an " : "a ";
}

function friendlyList(items) {
  if (items.length <= 1) return items[0] || "";
  return items.slice(0, -1).join(", ") + " and " + items[items.length - 1];
}

function assistValueLine(run) {
  const counts = {};
  run.artifacts.forEach((a) => {
    const n = KIND_NOUN[a.kind] || a.kind;
    counts[n] = (counts[n] || 0) + 1;
  });
  const parts = Object.entries(counts).map(([n, c]) =>
    c > 1 ? `${c} ${n}s` : aOrAn(n) + n,
  );
  const what = friendlyList(parts) || "a summary";
  return run.status === "blocked"
    ? `<div class="assist-value warn">⚠ Your agent team prepared ${esc(
        what,
      )}, but one item needs your attention before it can be sent.</div>`
    : `<div class="assist-value">✅ Your agent team prepared ${esc(
        what,
      )} — ready for you to review.</div>`;
}

function assistHtml(run, threads) {
  const value = assistValueLine(run);
  const rand = (Number(run.cost_estimate) * ZAR_RATE).toFixed(2);
  const meta = `<div class="assist-meta" title="The orchestrator picks the cheapest capable AI model for the task and tracks an estimated cost.">${esc(
    run.model,
  )} · ${esc(run.complexity)} task · est. ~R${esc(rand)}</div>`;
  const team = run.specialists
    .map(
      (k) => `<span class="tag team">${esc(SPECIALIST_NAMES[k] || k)}</span>`,
    )
    .join("");
  const plan = `<details class="assist-plan-wrap"><summary>What the agents did, step by step</summary>
    <ol class="assist-plan">${run.plan
      .map((s) => `<li>${esc(s)}</li>`)
      .join("")}</ol></details>`;
  const arts = run.artifacts.map((a, i) => artifactHtml(a, run.id, i)).join("");
  const findings = run.findings.length
    ? `<div class="assist-findings">${run.findings
        .map(assistFindingHtml)
        .join("")}</div>`
    : "";
  const pt = run.proposed_tool
    ? `<details class="pt-wrap"><summary>⚙ Technical — a tool request for the developers</summary>${proposedToolHtml(
        run.proposed_tool,
      )}</details>`
    : "";
  const rel =
    threads.threads && threads.threads.length
      ? `<div class="related">
          <div class="rel-head">🧵 Related correspondence across ${
            threads.threads.length
          } thread(s) — same matter</div>
          ${threads.threads
            .map(
              (t) =>
                `<div class="rel-item"><span class="tag dir">${esc(
                  t.direction,
                )}</span>${esc(t.subject)}</div>`,
            )
            .join("")}
        </div>`
      : "";
  return `${value}<div class="assist-team">Engaged: ${team}</div>${plan}
    <div class="assist-artifacts">${arts}</div>${findings}${pt}${rel}
    ${meta}
    <div class="assist-foot">The agent prepares and recommends — the Chairperson decides, signs and sends.</div>`;
}

function assistFindingHtml(f) {
  const block = f.severity === "block";
  const lead = block ? "Stopped" : "Heads-up — you can still send";
  return `<div class="finding ${esc(
    f.severity,
  )}"><strong>${lead}:</strong> ${esc(f.message)}</div>`;
}

function artifactHtml(a, runId, idx) {
  const how = a.tool_used
    ? `<span class="art-how">· ${esc(
        TOOL_LABEL[a.tool_used] || a.tool_used,
      )}</span>`
    : "";
  const top = `<div class="art-top">
      <span class="tag kind">${esc(KIND_LABEL[a.kind] || a.kind)}</span>
      <strong>${esc(a.title)}</strong>
      <span class="muted">${esc(a.specialist)}</span>${how}
    </div>`;
  if (a.kind === "correspondence") {
    const actions = a.sent
      ? `<span class="tag sent">sent (demo)</span>`
      : `<button class="ghost small" data-copy="${idx}">Copy</button>
         <button class="primary small" data-send="${runId}" data-idx="${idx}">✉ Send (demo)</button>
         <span class="muted send-hint">Fill any [bracketed] parts first — then it can be sent.</span>`;
    return `<div class="artifact">
      ${top}
      <textarea class="art-edit" data-idx="${idx}" rows="9" ${
        a.sent ? "disabled" : ""
      }>${esc(a.body)}</textarea>
      <div class="art-actions">${actions}</div>
    </div>`;
  }
  const code =
    a.kind === "calculation" && a.code
      ? `<pre class="code">${esc(a.code)}</pre>`
      : "";
  return `<div class="artifact">
    ${top}
    ${code}
    <pre class="art-body">${esc(a.body)}</pre>
  </div>`;
}

function proposedToolHtml(pt) {
  return `<div class="proposed-tool">
    <div class="pt-head">⚙ Proposed permanent tool — draft pull request</div>
    <div>${esc(pt.reason)}</div>
    <div class="muted">branch <code>${esc(pt.branch)}</code> · <code>${esc(
      pt.file_path,
    )}</code></div>
    <details>
      <summary>${esc(pt.pr_title)}</summary>
      <pre class="art-body">${esc(pt.pr_body)}</pre>
      <pre class="code">${esc(pt.file_content)}</pre>
    </details>
    <span class="tag sim">simulated — human-merge &amp; CI-gated, nothing was pushed</span>
  </div>`;
}

function wireAssistSend(box, ticketId) {
  box.querySelectorAll("[data-copy]").forEach((b) =>
    b.addEventListener("click", () => {
      const ta = box.querySelector(`textarea[data-idx="${b.dataset.copy}"]`);
      if (!ta) return;
      if (navigator.clipboard) navigator.clipboard.writeText(ta.value);
      toast("Draft reply copied to clipboard.");
    }),
  );
  box.querySelectorAll("[data-send]").forEach((b) =>
    b.addEventListener("click", async () => {
      const ta = box.querySelector(`textarea[data-idx="${b.dataset.idx}"]`);
      const text = ta ? ta.value : "";
      if (/\[[^\]]+\]/.test(text)) {
        toast("Please fill in the [bracketed] parts before sending.");
        if (ta) ta.focus();
        return;
      }
      b.disabled = true;
      try {
        await api(`/api/assist/${b.dataset.send}/send`, {
          method: "POST",
          body: JSON.stringify({
            artifact_index: Number(b.dataset.idx),
            body: text,
          }),
        });
        const acts = b.closest(".art-actions");
        if (acts) acts.innerHTML = `<span class="tag sent">sent (demo)</span>`;
        if (ta) ta.disabled = true;
        toast("Reply filed to your sent records (demo).");
      } catch (e) {
        b.disabled = false;
        toast(e.message || "Guardrails blocked this send.");
      }
    }),
  );
}

function ticketHtml(t) {
  const moves = [];
  if (t.status !== "todo") moves.push(["todo", "← To do"]);
  if (t.status !== "in_progress") moves.push(["in_progress", "In progress"]);
  if (t.status !== "done") moves.push(["done", "Done ✓"]);
  const flag =
    t.priority === "high" ? `<span class="prio-flag">⚑ high</span>` : "";
  const today = new Date().toISOString().slice(0, 10);
  const overdue = t.due_date && t.status !== "done" && t.due_date < today;
  const due = t.due_date
    ? `<span class="due${overdue ? " overdue" : ""}">${
        overdue ? "⚠ overdue " : "due "
      }${esc(t.due_date)}</span>`
    : "";
  const desc = t.description
    ? `<div class="card-desc">${esc(t.description)}</div>`
    : "";
  const src = SOURCE_LABEL[t.source]
    ? `<span class="tag src">${esc(SOURCE_LABEL[t.source])}</span>`
    : "";
  const scope = t.unit
    ? `<span class="tag">${esc(t.unit)}</span>`
    : `<span class="tag scheme">scheme-wide</span>`;
  const assistBtn = ASSIST.available
    ? `<button class="ghost small assist-btn" data-assist="${t.id}">🤝 Get agent help</button>`
    : `<button class="ghost small" disabled title="Agent assist is turned off in the footer">🤝 agent help off</button>`;
  return `<div class="card${t.priority === "high" ? " high" : ""}${
    overdue ? " overdue-card" : ""
  }">
    <div class="card-top">${flag}<strong>${esc(t.title)}</strong></div>
    ${desc}
    <div class="ref">${esc(t.case_ref)} · ${esc(t.assignee)}</div>
    <div class="row">${scope}${src}${due}</div>
    <div class="move">${moves
      .map(
        ([s, label]) =>
          `<button class="ghost small" data-move="${s}" data-id="${t.id}">${label}</button>`,
      )
      .join("")}${assistBtn}</div>
    <div class="assist" id="assist-${t.id}" hidden></div>
  </div>`;
}

// ── Add-task form (manual + resolution-seeded) ───────────────────────────────
function resetTaskForm() {
  const f = $("#task-form");
  f.reset();
  f.source.value = "manual";
  f.source_resolution_id.value = "";
  $("#task-source-note").hidden = true;
  $("#task-source-note").textContent = "";
}

$("#task-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const payload = {
    title: f.title.value.trim(),
    type: f.type.value,
    priority: f.priority.value,
    unit: f.unit.value.trim(),
    due_date: f.due_date.value,
    description: f.description.value.trim(),
    source: f.source.value || "manual",
    source_resolution_id: f.source_resolution_id.value
      ? Number(f.source_resolution_id.value)
      : null,
  };
  if (!payload.title) {
    toast("A task needs a title.");
    f.title.focus();
    return;
  }
  try {
    const t = await api("/api/tickets", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    resetTaskForm();
    await loadBoard();
    toast("Task added for the Chairperson: “" + (t.title || "task") + "”.");
  } catch (err) {
    alert("Couldn't add task: " + err.message);
  }
});

$("#task-reset").addEventListener("click", resetTaskForm);

function prefillTaskFromResolution(res) {
  const f = $("#task-form");
  f.title.value = "Act on resolution: " + res.title;
  f.type.value = "governance";
  f.priority.value = "normal";
  f.unit.value = res.unit || "";
  f.due_date.value = "";
  f.description.value = res.summary || "";
  f.source.value = "resolution";
  f.source_resolution_id.value = res.id;
  const note = $("#task-source-note");
  note.textContent = "Seeded from resolution #" + res.id + " — review and add.";
  note.hidden = false;
  // Switch to the Board tab so the trustee can review the prefilled form.
  const boardBtn = $('.tabs button[data-tab="board"]');
  if (boardBtn) boardBtn.click();
  f.title.focus();
}

// ── Resolutions ──────────────────────────────────────────────────────────────
let RESOLUTIONS = [];

async function loadResolutions() {
  RESOLUTIONS = await api("/api/resolutions");
  const el = $("#resolutions");
  el.innerHTML = RESOLUTIONS.length
    ? RESOLUTIONS.map(resolutionHtml).join("")
    : `<p class="empty">No resolutions on record.</p>`;
  $$("[data-res-task]", el).forEach((btn) =>
    btn.addEventListener("click", () => {
      const res = RESOLUTIONS.find((r) => String(r.id) === btn.dataset.resTask);
      if (res) prefillTaskFromResolution(res);
    }),
  );
}

function resolutionHtml(r) {
  const scope = r.unit ? esc(r.unit) : "scheme-wide";
  const signed = r.signed
    ? `<span class="tag filed">signed</span>`
    : `<span class="tag">unsigned</span>`;
  return `<div class="resolution">
    <div class="row">
      ${signed}
      <span class="tag">${scope}</span>
      ${
        r.effective_date
          ? `<span class="tag">${esc(r.effective_date)}</span>`
          : ""
      }
    </div>
    <strong>${esc(r.title)}</strong>
    ${r.summary ? `<p class="res-summary">${esc(r.summary)}</p>` : ""}
    <div class="actions">
      <button class="small" data-res-task="${r.id}">Create task →</button>
    </div>
  </div>`;
}

// ── Ask ──────────────────────────────────────────────────────────────────────
$("#ask-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = e.target.question.value;
  $("#ask-answer").innerHTML = `<p class="empty">Thinking…</p>`;
  const out = await api("/api/ask", {
    method: "POST",
    body: JSON.stringify({ question: q }),
  });
  const sources = out.sources.length
    ? `<div class="sources"><strong>Sources:</strong><ul>${out.sources
        .map((s) => `<li>${esc(s.title)} <em>(${esc(s.kind)})</em></li>`)
        .join("")}</ul></div>`
    : "";
  $("#ask-answer").innerHTML = `<div class="answer-box">${esc(
    out.answer,
  )}${sources}</div>`;
});

// ── Documents ────────────────────────────────────────────────────────────────

// Manual fallback form (always available, in the <details>).
$("#doc-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  try {
    await api("/api/documents", {
      method: "POST",
      body: JSON.stringify({
        title: f.title.value,
        category: f.category.value,
        effective_date: f.effective_date.value,
        content: f.content.value,
      }),
    });
    f.reset();
    await loadDocuments();
    toast("Document added to your brain.");
  } catch (err) {
    alert("Couldn't add: " + err.message);
  }
});

// ── Smart upload (drag & drop → read → suggest → confirm) ────────────────────
const SMART = {
  OK_EXT: /\.(txt|md|markdown|text)$/i,
  MAX_BYTES: 2 * 1024 * 1024,
  content: "",
};

function smartReset() {
  $("#review-form").hidden = true;
  $("#upload-status").hidden = true;
  $("#dropzone").hidden = false;
  $("#file-input").value = "";
  SMART.content = "";
}

function smartStatus(text) {
  $("#dropzone").hidden = true;
  $("#review-form").hidden = true;
  $("#upload-status-text").textContent = text;
  $("#upload-status").hidden = false;
}

function readFileText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Could not read the file."));
    reader.readAsText(file);
  });
}

async function handleFile(file) {
  if (!file) return;
  const looksText = SMART.OK_EXT.test(file.name) || file.type === "text/plain";
  if (!looksText) {
    toast(
      "Sorry, only .txt and .md files can be read for now. PDF and Word aren't supported yet.",
    );
    return;
  }
  if (file.size > SMART.MAX_BYTES) {
    toast("That file is too large (max 2 MB). Please try a smaller document.");
    return;
  }
  smartStatus("Reading “" + file.name + "”…");
  let text;
  try {
    text = await readFileText(file);
  } catch (err) {
    smartReset();
    toast(err.message);
    return;
  }
  if (!text.trim()) {
    smartReset();
    toast("That file looks empty. Please choose a document with some text.");
    return;
  }
  SMART.content = text;
  smartStatus("Reading the document and suggesting a title…");
  try {
    const meta = await api("/api/documents/analyze", {
      method: "POST",
      body: JSON.stringify({ content: text, filename: file.name }),
    });
    showReview(meta);
  } catch (err) {
    // Even if analysis fails, let the trustee save manually rather than lose work.
    showReview({
      title: file.name.replace(SMART.OK_EXT, ""),
      category: "general",
      effective_date: new Date().toISOString().slice(0, 10),
      char_count: text.length,
      chunk_count: 0,
      preview: text.slice(0, 400),
    });
    toast("Couldn't auto-suggest — please check the title and category.");
  }
}

function showReview(meta) {
  $("#dropzone").hidden = true;
  $("#upload-status").hidden = true;
  $("#review-title").value = meta.title || "";
  $("#review-category").value = meta.category || "general";
  $("#review-date").value =
    meta.effective_date || new Date().toISOString().slice(0, 10);
  $("#review-preview").textContent =
    meta.preview || SMART.content.slice(0, 400);
  const chunks = meta.chunk_count
    ? ` · will be stored as ${meta.chunk_count} searchable ${
        meta.chunk_count === 1 ? "piece" : "pieces"
      }`
    : "";
  $("#review-meta").textContent = `About ${(
    meta.char_count || SMART.content.length
  ).toLocaleString()} characters${chunks}.`;
  $("#review-form").hidden = false;
  $("#review-title").focus();
}

$("#review-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const payload = {
    title: f.title.value.trim(),
    category: f.category.value,
    effective_date: f.effective_date.value,
    content: SMART.content,
  };
  try {
    await api("/api/documents", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    smartReset();
    await loadDocuments();
    toast("Document added to your brain ✓ Nothing was emailed.");
  } catch (err) {
    if (/already exists/i.test(err.message)) {
      if (
        confirm(
          `A document titled “${payload.title}” already exists.\n\n` +
            "OK = replace it with this new version.\nCancel = go back and change the title.",
        )
      ) {
        payload.overwrite = true;
        try {
          await api("/api/documents", {
            method: "POST",
            body: JSON.stringify(payload),
          });
          smartReset();
          await loadDocuments();
          toast("Document replaced ✓");
          return;
        } catch (err2) {
          alert("Couldn't replace: " + err2.message);
          return;
        }
      }
      $("#review-title").focus();
      $("#review-title").select();
      return;
    }
    alert("Couldn't save: " + err.message);
  }
});

$("#review-cancel").addEventListener("click", smartReset);

(function wireDropzone() {
  const dz = $("#dropzone");
  const input = $("#file-input");
  if (!dz || !input) return;
  dz.addEventListener("click", () => input.click());
  dz.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      input.click();
    }
  });
  input.addEventListener("change", () => handleFile(input.files[0]));
  ["dragenter", "dragover"].forEach((evt) =>
    dz.addEventListener(evt, (e) => {
      e.preventDefault();
      dz.classList.add("dragging");
    }),
  );
  ["dragleave", "drop"].forEach((evt) =>
    dz.addEventListener(evt, (e) => {
      e.preventDefault();
      if (evt === "dragleave" && dz.contains(e.relatedTarget)) return;
      dz.classList.remove("dragging");
    }),
  );
  dz.addEventListener("drop", (e) => {
    const file = e.dataTransfer?.files?.[0];
    handleFile(file); // first file only
  });
})();

async function loadDocuments() {
  const docs = await api("/api/documents");
  $("#documents").innerHTML = docs.length
    ? docs
        .map(
          (d) =>
            `<div class="doc-item"><strong>${esc(d.title)}</strong>
              <div class="cat">${esc(d.category)}${
                d.effective_date ? " · " + esc(d.effective_date) : ""
              }</div></div>`,
        )
        .join("")
    : `<p class="empty">No documents.</p>`;
}

// ── Reseed + boot ────────────────────────────────────────────────────────────
$("#reseed").addEventListener("click", async () => {
  const typed = prompt(
    "This wipes all current data and restores the sample scheme.\n" +
      "Type RESET to confirm.",
  );
  if (typed !== "RESET") return;
  await api("/api/seed", { method: "POST" });
  await refresh("inbox");
  toast("Sample data restored.");
});

function refresh(tab) {
  if (tab === "inbox") loadDrafts();
  else if (tab === "board") loadBoard();
  else if (tab === "resolutions") loadResolutions();
  else if (tab === "documents") loadDocuments();
}

$("#assist-enabled").addEventListener("change", (e) =>
  setAssistConfig({ enabled: e.target.checked }),
);
$("#assist-kill").addEventListener("change", (e) =>
  setAssistConfig({ kill_switch: e.target.checked }),
);

(async function boot() {
  try {
    const health = await api("/api/health");
    $("#llm-badge").textContent = "engine: " + health.llm;
  } catch (_) {}
  await loadAssistConfig();
  loadDrafts();
})();
