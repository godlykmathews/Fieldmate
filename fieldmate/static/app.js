"use strict";
const $ = (selector) => document.querySelector(selector);
const icons = {
  chat: '<path d="M14 14H7l-4 3V4h13v6M10 18h7l4 3V10h-3"/>',
  panel: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',
  spark:
    '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  book: '<path d="M12 5v15M3 4h5a4 4 0 0 1 4 3 4 4 0 0 1 4-3h5v15h-5a4 4 0 0 0-4 2 4 4 0 0 0-4-2H3Z"/>',
  note: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
  settings:
    '<circle cx="12" cy="12" r="3"/><path d="m9 3-1 3-3 1-2 3 2 2-1 3 3 2 1 3h4l2-2 3 1 2-3-1-3 2-2-2-3-3-1-2-3Z"/>',
  headphones:
    '<path d="M4 14v-3a8 8 0 0 1 16 0v3"/><rect x="3" y="12" width="4" height="8" rx="2"/><rect x="17" y="12" width="4" height="8" rx="2"/>',
  mic: '<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8"/>',
  arrow: '<path d="M12 19V5m-6 6 6-6 6 6"/>',
  globe:
    '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
};
const icon = (name) =>
  `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.note}</svg>`;
document
  .querySelectorAll("[data-icon]")
  .forEach((el) => (el.innerHTML = icon(el.dataset.icon)));
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const state = {
  view: "chat",
  thread: null,
  threads: [],
  categories: [],
  models: [],
  preferences: null,
  status: null,
  busy: false,
  speaking: false,
  web: false,
  documents: [],
  drafts: new Map(),
};
let toastTimer;
function toast(text, error = false) {
  const el = $("#toast");
  el.textContent = text;
  el.className = "toast" + (error ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(
    () => el.classList.add("hidden"),
    error ? 9000 : 4000,
  );
}
async function api(path, options = {}) {
  const r = await fetch(path, options);
  if (!r.ok) {
    let detail = "Something went wrong. Please try again.";
    try {
      const data = await r.json();
      detail =
        typeof data.detail === "string"
          ? data.detail
          : "Check the fields and try again.";
    } catch {}
    throw new Error(detail);
  }
  return r.json();
}
const jsonOptions = (body, method = "POST") => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
const on = (selector, event, fn) =>
  $(selector).addEventListener(event, (e) =>
    Promise.resolve(fn(e)).catch((error) => toast(error.message, true)),
  );
const categoryName = (id) =>
  state.categories.find((c) => c.id === id)?.name || "General";
function option(value, label, selected) {
  return `<option value="${esc(value)}"${value === selected ? " selected" : ""}>${esc(label)}</option>`;
}
function categoryOptions(selected, shared = false) {
  return (
    (shared ? option("", "Shared · all categories", selected) : "") +
    state.categories.map((c) => option(c.id, c.name, selected)).join("")
  );
}
function modelOptions(selected) {
  return [...new Set([...state.models, selected].filter(Boolean))]
    .map((m) => option(m, m, selected))
    .join("");
}
function isWorking() {
  if (!state.preferences || state.busy || voice.recording || voice.finishing) {
    toast("Finish this response or recording first.");
    return true;
  }
  return false;
}
function setBusy(value) {
  state.busy = value;
  for (const id of [
    "send",
    "message",
    "model",
    "category",
    "web-toggle",
    "record",
    "handsfree",
  ])
    $("#" + id).disabled = value || !!state.thread?.closed;
  $("#chat-view").setAttribute("aria-busy", String(value));
}
async function refreshStatus() {
  try {
    state.status = await api("/api/status");
    const ready = state.status.ollama.connected;
    $("#connection").innerHTML =
      "<i></i>" + (ready ? "Local models connected" : "Open Ollama to connect");
    $("#connection").classList.toggle("warning", !ready);
    $("#doc-count").textContent = state.status.document_count;
  } catch (error) {
    $("#connection").innerHTML = "<i></i>App connection lost";
    $("#connection").classList.add("warning");
    throw error;
  }
}
function renderThreads() {
  let closed = false;
  $("#thread-list").innerHTML = state.threads
    .map((t) => {
      let heading = "";
      if (t.closed && !closed) {
        heading = '<div class="thread-section">Closed conversations</div>';
        closed = true;
      }
      return (
        heading +
        `<button class="thread-link ${t.id === state.thread?.id ? "active" : ""}" data-thread="${esc(t.id)}" title="${esc(t.title)}"><strong>${esc(t.title)}</strong><small>${esc(categoryName(t.category_id))}${t.closed ? " · closed" : ""}</small></button>`
      );
    })
    .join("");
  $("#thread-list")
    .querySelectorAll("[data-thread]")
    .forEach((b) =>
      b.addEventListener("click", () =>
        selectThread(b.dataset.thread).catch((e) => toast(e.message, true)),
      ),
    );
}
async function refreshThreads() {
  state.threads = await api("/api/threads");
  renderThreads();
}
function renderThreadControls() {
  const t = state.thread;
  $("#thread-title").textContent = t?.title || "New chat";
  $("#category").innerHTML = categoryOptions(t?.category_id || "general");
  $("#model").innerHTML = modelOptions(
    t?.model || state.preferences.default_model,
  );
  $("#closed-banner").classList.toggle("hidden", !t?.closed);
  $("#chat-form").classList.toggle("hidden", !!t?.closed);
  $("#suggestions").classList.toggle("hidden", !!t?.closed);
  $(".voice-toolbar").classList.toggle("hidden", !!t?.closed);
  setBusy(state.busy);
}
async function selectThread(id) {
  if (isWorking()) return;
  stopSession();
  stopRecording(true);
  stopSpeaking();
  if (state.thread) state.drafts.set(state.thread.id, $("#message").value);
  const data = await api("/api/threads/" + id);
  state.thread = data.thread;
  localStorage.setItem("fieldmate-thread", id);
  state.web = false;
  $("#web-toggle").setAttribute("aria-pressed", "false");
  $("#message").value = state.drafts.get(id) || "";
  $("#conversation").replaceChildren();
  $("#chat-view").classList.toggle("empty", !data.exchanges.length);
  const pending = new Set(data.permissions.map((p) => p.id));
  for (const e of data.exchanges) {
    addMessage("user", e.request.text);
    addMessage(
      "assistant",
      e.response.text,
      e.response,
      pending.has(e.response.permission?.id),
    );
  }
  renderThreadControls();
  renderThreads();
  await changeView("chat");
  document.body.classList.remove("sidebar-mobile");
  scrollConversation();
}
async function newThread() {
  if (isWorking()) return;
  const thread = await api(
    "/api/threads",
    jsonOptions({
      category_id: state.thread?.category_id || "general",
      model: state.preferences.default_model,
    }),
  );
  await refreshThreads();
  await selectThread(thread.id);
  $("#message").focus();
}
async function changeView(view) {
  state.view = view;
  $("#chat-view").classList.toggle("hidden", view !== "chat");
  $("#documents-view").classList.toggle("hidden", view !== "documents");
  document
    .querySelectorAll("[data-view]")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  if (view !== "chat") {
    stopSession();
    stopRecording(true);
    stopSpeaking();
    await loadDocuments();
  }
}
document
  .querySelectorAll("[data-view]")
  .forEach((b) =>
    b.addEventListener("click", () =>
      changeView(b.dataset.view).catch((e) => toast(e.message, true)),
    ),
  );
on("#new-thread", "click", newThread);
on("#attach", "click", () => changeView("documents"));
on("#collapse-sidebar", "click", () => {
  document.body.classList.add("sidebar-collapsed");
  document.body.classList.remove("sidebar-mobile");
});
on("#open-sidebar", "click", () => {
  document.body.classList.remove("sidebar-collapsed");
  document.body.classList.toggle("sidebar-mobile");
});
on("#category", "change", async () => {
  if (isWorking()) return;
  state.thread = await api(
    "/api/threads/" + state.thread.id,
    jsonOptions({ category_id: $("#category").value }, "PATCH"),
  );
  await refreshThreads();
  toast("Category changed. Your conversation context is kept.");
});
on("#model", "change", async () => {
  if (isWorking()) return;
  try {
    state.thread = await api(
      "/api/threads/" + state.thread.id,
      jsonOptions({ model: $("#model").value }, "PATCH"),
    );
    toast("Using " + state.thread.model + ". Conversation context is kept.");
  } finally {
    renderThreadControls();
  }
});
on("#web-toggle", "click", () => {
  if (state.preferences.web_mode === "off") {
    toast("Enable search in Settings first.");
    return;
  }
  state.web = !state.web;
  $("#web-toggle").setAttribute("aria-pressed", String(state.web));
  toast(
    state.web
      ? "Your next message will request a web search. You will review the query first."
      : "Web search request off.",
  );
});
function scrollConversation() {
  const box = $("#conversation");
  box.scrollTop = box.scrollHeight;
}
function plainReply(text) {
  return text
    .replace(/!?\[([^\]\n]+)\]\(https?:\/\/[^\s)]+\)/g, '$1')
    .replace(/(?<![\w=])\[(?:D\d+|web-\d+|\d+)(?:\s*[,;]\s*(?:D\d+|web-\d+))*\]/g, '')
    .replace(/^\s{0,3}(?:`{3,}|~{3,})[^\n]*$/gm, '')
    .replace(/^\s{0,3}(?:[-*_][ \t]*){3,}$/gm, '')
    .replace(/^\s{0,3}#{1,6}[ \t]+|^\s{0,3}>[ \t]+/gm, '')
    .replace(/^[ \t]*[-+*•][ \t]+(?:\[[ xX]\][ \t]+)?/gm, '')
    .replace(/(?<!\w)(?:\*\*(\S(?:.*?\S)?)\*\*|__(\S(?:.*?\S)?)__|~~(\S(?:.*?\S)?)~~)(?!\w)/gs, (_, bold, underline, strike) => bold ?? underline ?? strike)
    .replace(/(?<!\w)\*([^\s*](?:[^*\n]*[^\s*])?)\*(?!\w)/g, '$1')
    .replace(/(?<!\w)_([^\s_](?:[^_\n]*[^\s_])?)_(?!\w)/g, '$1')
    .replace(/`/g, '')
    .replace(/[ \t]+([,.!?;:])/g, '$1')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}
function addMessage(role, text, response = null, pending = true) {
  if (role === 'assistant') text = plainReply(text);
  $("#chat-view").classList.remove("empty");
  const row = document.createElement("article");
  row.className = "message-row" + (role === "user" ? " user-row" : "");
  row.innerHTML =
    (role === "assistant"
      ? `<div class="message-avatar">${icon("spark")}</div>`
      : "") +
    '<div class="message-body"><div class="message-text"></div></div>';
  row.querySelector(".message-text").textContent = text;
  const body = row.querySelector(".message-body");
  if (response) {
    const labels = {
      knowledge: "Model knowledge · not document-verified",
      documents: "Document sources",
      mixed: "Documents + model knowledge",
      uncertain: "Uncertain",
      action: "Saved locally",
      clarification: "Clarification",
      permission: pending ? "Waiting for your permission" : "Search request resolved",
    };
    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent =
      (["list_tasks", "search_notes"].includes(response.action)
        ? "Notebook"
        : labels[response.basis] ||
          response.basis ||
          (response.grounded ? "Document sources" : "Local reply")) +
      (response.model ? " · " + response.model : "");
    body.append(meta);
    if (response.web_results?.length && !response.sources?.some(s => s.kind === 'web')) {
      meta.textContent = 'Web results consulted · claims not verified' + (response.model ? ' · ' + response.model : '');
    }
    if (response.document_check === "conflicts") {
      const n = document.createElement("div");
      n.className = "notice";
      n.textContent =
        "Potential conflict with your documents — review the sources.";
      body.append(n);
    }
    if (response.sources?.length) {
      const box = document.createElement("div");
      box.className = "sources";
      box.innerHTML = response.sources
        .map(
          (s, i) =>
            `<details><summary>[${esc(/^(D\d+|web-\d+)$/.test(s.id) ? s.id : i + 1)}] ${esc(s.document)}${s.page ? " · page " + s.page : ""}</summary><p>${esc(s.excerpt)}</p>${s.url && /^https?:\/\//.test(s.url) ? `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">Open source ↗</a>` : ""}</details>`,
        )
        .join("");
      body.append(box);
    }
    for (const message of [response.notice, response.web_status]) {
      if (message) {
        const n = document.createElement("div");
        n.className = "notice";
        n.textContent = message;
        body.append(n);
      }
    }
    if (response.web_results?.length) {
      const box = document.createElement("details");
      box.className = "sources";
      box.innerHTML =
        "<summary>Web search results (snippets)</summary>" +
        response.web_results
          .filter((r) => /^https?:\/\//.test(r.url))
          .map(
            (r) =>
              `<p><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.title)}</a></p>`,
          )
          .join("");
      body.append(box);
    }
    if (response.permission && pending)
      renderPermission(body, response.permission);
    else if (response.permission) {
      const n = document.createElement("div");
      n.className = "message-meta";
      n.textContent = "Search permission resolved or cancelled.";
      body.append(n);
    }
    if (!response.permission) {
      const actions = document.createElement("div");
      actions.className = "message-actions";
      const copy = document.createElement("button");
      copy.textContent = "Copy";
      copy.onclick = () =>
        navigator.clipboard
          .writeText(text)
          .then(() => toast("Copied."))
          .catch(() => toast("Copy is unavailable in this browser.", true));
      const read = document.createElement("button");
      read.textContent = "Read aloud";
      read.onclick = () => speak(text);
      actions.append(copy, read);
      body.append(actions);
    }
  }
  $("#conversation").append(row);
  scrollConversation();
  return row;
}
function renderPermission(body, permission) {
  const card = document.createElement("div");
  card.className = "permission-card";
  card.innerHTML = `<label>Search query<input value="${esc(permission.query)}" maxlength="1200" aria-label="Web search query"></label><p>Only this query goes to DuckDuckGo. Your chat and documents stay here. Remove any personal details before approving.</p><div class="permission-actions"><button class="primary" data-approve>Allow this search</button><button class="secondary" data-decline>Continue offline</button></div>`;
  for (const [selector, approve] of [
    ["[data-approve]", true],
    ["[data-decline]", false],
  ])
    card.querySelector(selector).onclick = async () => {
      if (isWorking()) return;
      const query = card.querySelector("input").value.trim();
      if (approve && !query) {
        toast("Enter a search query first.");
        return;
      }
      stopSession();
      stopSpeaking();
      setBusy(true);
      card.querySelectorAll("button,input").forEach((b) => (b.disabled = true));
      const pendingRow = addMessage(
        "assistant",
        approve ? "Searching with your permission…" : "Continuing offline…",
      );
      pendingRow.querySelector(".message-text").classList.add("thinking");
      try {
        const response = await api(
          "/api/search/" + permission.id,
          jsonOptions({ thread_id: state.thread.id, approve, query }),
        );
        pendingRow.remove();
        addMessage(
          "user",
          approve ? "Search approved: " + query : "Continue offline",
        );
        addMessage("assistant", response.text, response);
        body.querySelector('.message-meta').textContent = approve ? 'Search approved' : 'Search declined';
        card.replaceChildren(
          Object.assign(document.createElement("span"), {
            textContent: approve
              ? "Search permission used."
              : "Search declined. Nothing sent online.",
          }),
        );
        await refreshThreads();
      } catch (error) {
        pendingRow.remove();
        toast(error.message, true);
        const button = document.createElement("button");
        button.textContent = "Reload conversation";
        button.onclick = () => selectThread(state.thread.id);
        card.replaceChildren(button);
      } finally {
        setBusy(false);
      }
    };
  body.append(card);
}
async function sendMessage(
  text,
  requestId = crypto.randomUUID(),
  retryRow = null,
  web = state.web,
) {
  text = text.trim();
  if (!text || state.busy || state.thread.closed) return;
  if (retryRow) retryRow.remove();
  else addMessage("user", text);
  const threadId = state.thread.id;
  const pending = addMessage(
    "assistant",
    "Thinking with your conversation and documents…",
  );
  pending.querySelector(".message-text").classList.add("thinking");
  setBusy(true);
  voiceState("Working on it…");
  state.web = false;
  $("#web-toggle").setAttribute("aria-pressed", "false");
  try {
    const result = await api(
      "/api/chat",
      jsonOptions({
        request_id: requestId,
        thread_id: threadId,
        text,
        request_web: web,
      }),
    );
    pending.remove();
    addMessage("assistant", result.text, result);
    if (result.permission) stopSession();
    await refreshThreads();
    state.thread = state.threads.find((t) => t.id === threadId) || state.thread;
    $("#thread-title").textContent = state.thread.title;
    if ($("#read-aloud").checked && state.status?.voice.speech)
      await speak(result.text);
  } catch (error) {
    pending.remove();
    const row = addMessage("assistant", error.message);
    row.querySelector(".message-text").classList.add("error-text");
    const retry = document.createElement("button");
    retry.className = "secondary";
    retry.textContent = "Try again";
    retry.onclick = () => sendMessage(text, requestId, row, web);
    row.querySelector(".message-body").append(retry);
    stopSession();
  } finally {
    setBusy(false);
    if (!voice.session) {
      voiceState("On your laptop. Web searches always ask first.");
      $("#message").focus();
    } else {
      voice.resumeAfter = performance.now() + 650;
      voiceState("Listening for your next thought…");
    }
  }
}
on("#chat-form", "submit", (e) => {
  e.preventDefault();
  if (state.busy || !$("#message").value.trim()) return;
  const text = $("#message").value;
  $("#message").value = "";
  state.drafts.delete(state.thread.id);
  $("#message").style.height = "auto";
  return sendMessage(text);
});
on("#message", "keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    $("#chat-form").requestSubmit();
  }
});
on("#message", "input", () => {
  $("#message").style.height = "auto";
  $("#message").style.height = Math.min($("#message").scrollHeight, 140) + "px";
});
document.querySelectorAll("[data-prompt]").forEach((b) =>
  b.addEventListener("click", () => {
    $("#message").value = b.dataset.prompt;
    $("#message").focus();
  }),
);
async function loadDocuments() {
  state.documents = await api("/api/documents");
  $("#doc-count").textContent = state.documents.length;
  const filter = $("#document-filter").value;
  $("#document-filter").innerHTML =
    option("", "All categories", filter) +
    option("shared", "Shared", filter) +
    categoryOptions(filter);
  const docs = state.documents.filter(
    (d) =>
      !filter ||
      (filter === "shared" ? !d.category_id : d.category_id === filter),
  );
  $("#document-total").textContent =
    docs.length + " document" + (docs.length === 1 ? "" : "s");
  $("#document-list").innerHTML = docs.length
    ? docs
        .map(
          (d) =>
            `<article class="document-card"><div class="file-icon">${icon("book")}</div><div class="document-info"><strong>${esc(d.name)}</strong><small>${d.pages} pages · ${d.chunks} passages · indexed locally</small><button data-document="${esc(d.id)}">View extracted text ↗</button></div><select data-doc-category="${esc(d.id)}" aria-label="Category for ${esc(d.name)}">${categoryOptions(d.category_id || "", true)}</select><button class="icon-button" data-delete="${esc(d.id)}" aria-label="Remove ${esc(d.name)}" title="Remove document">×</button></article>`,
        )
        .join("")
    : `<div class="empty-state">${icon("book")}Your knowledge starts here.<br>Add a guide, reference, or set of notes.</div>`;
  $("#document-list")
    .querySelectorAll("[data-document]")
    .forEach(
      (b) =>
        (b.onclick = async () => {
          try {
            const r = await api("/api/documents/" + b.dataset.document);
            $("#dialog-title").textContent = r.document.name;
            $("#dialog-content").innerHTML = r.passages
              .map(
                (p) =>
                  `<article><small>PAGE ${p.page}</small><p>${esc(p.text)}</p></article>`,
              )
              .join("");
            $("#document-dialog").showModal();
          } catch (e) {
            toast(e.message, true);
          }
        }),
    );
  $("#document-list")
    .querySelectorAll("[data-doc-category]")
    .forEach(
      (b) =>
        (b.onchange = async () => {
          try {
            await api(
              "/api/documents/" + b.dataset.docCategory,
              jsonOptions({ category_id: b.value || null }, "PATCH"),
            );
            toast("Document category updated.");
            await loadDocuments();
          } catch (e) {
            toast(e.message, true);
          }
        }),
    );
  $("#document-list")
    .querySelectorAll("[data-delete]")
    .forEach(
      (b) =>
        (b.onclick = async () => {
          if (!confirm("Remove this document from the local index?")) return;
          try {
            await api("/api/documents/" + b.dataset.delete, {
              method: "DELETE",
            });
            await loadDocuments();
          } catch (e) {
            toast(e.message, true);
          }
        }),
    );
}
on("#document-filter", "change", loadDocuments);
on("#upload-button", "click", () => $("#file-input").click());
on("#file-input", "change", async () => {
  const files = [...$("#file-input").files];
  $("#upload-button").disabled = true;
  $("#upload-progress").classList.remove("hidden");
  try {
    for (const file of files) {
      $("#upload-progress").textContent =
        "Indexing " + file.name + " on this laptop…";
      if (file.size > 20 * 1024 * 1024)
        throw new Error(file.name + " is over 20 MB.");
      const form = new FormData();
      form.append("file", file);
      const result = await api("/api/documents", {
        method: "POST",
        body: form,
      });
      const selected = $("#document-filter").value;
      if (!result.duplicate && selected && selected !== "shared")
        await api(
          "/api/documents/" + result.id,
          jsonOptions({ category_id: selected }, "PATCH"),
        );
      toast(
        result.duplicate
          ? file.name + " is already indexed."
          : file.name + " added.",
      );
      await loadDocuments();
    }
  } finally {
    $("#upload-button").disabled = false;
    $("#file-input").value = "";
    $("#upload-progress").classList.add("hidden");
  }
});
function settingsTab(tab) {
  document
    .querySelectorAll("[data-settings]")
    .forEach((b) => b.classList.toggle("active", b.dataset.settings === tab));
  for (const [id, key] of [
    ["general-settings", "general"],
    ["thread-settings", "thread"],
    ["category-settings", "categories"],
  ])
    $("#" + id).classList.toggle("hidden", key !== tab);
}
function categoryEditor(id) {
  $("#manage-category").innerHTML =
    option("", "New category", id) + categoryOptions(id);
  const c = state.categories.find((c) => c.id === id);
  $("#category-name").value = c?.name || "";
  $("#category-prompt").value = c?.prompt || "";
}
async function openSettings(tab = "general") {
  if (isWorking()) return;
  state.preferences = await api("/api/settings");
  const p = state.preferences,
    t = state.thread;
  $("#default-model").innerHTML = modelOptions(p.default_model);
  $("#system-prompt").value = p.system_prompt;
  $("#web-mode").value = p.web_mode;
  $("#decision-engine").value = p.decision_engine;
  $("#edit-title").value = t.title;
  $("#edit-category").innerHTML = categoryOptions(t.category_id);
  $("#thread-prompt").value = t.custom_prompt;
  $("#thread-site").value = t.site;
  $("#close-thread").textContent = t.closed
    ? "Reopen conversation"
    : "Close conversation";
  await refreshStatus();
  $("#decision-status").textContent = state.status.decision.ready
    ? "Laya checkpoint available locally. Ollama phrases clarifying questions."
    : (state.status.decision.error || state.status.decision.setup) +
      ". Ollama decisions remain available.";
  $("#setup-status").textContent =
    `Voice input: ${state.status.voice.transcription ? "ready" : "needs setup"} · Voice output: ${state.status.voice.speech ? "ready" : "needs setup"} · Embeddings: ${state.status.embed_model}`;
  $("#settings-feedback").textContent = "";
  categoryEditor(t.category_id);
  settingsTab(tab);
  $("#settings-dialog").showModal();
}
document
  .querySelectorAll("[data-settings]")
  .forEach((b) => (b.onclick = () => settingsTab(b.dataset.settings)));
document
  .querySelectorAll("[data-close]")
  .forEach((b) => (b.onclick = () => $("#" + b.dataset.close).close()));
on("#settings", "click", () => openSettings());
on("#thread-options", "click", () => openSettings("thread"));
on("#restore-prompt", "click", () => {
  $("#system-prompt").value = state.preferences.default_prompt;
});
on("#general-settings", "submit", async (e) => {
  e.preventDefault();
  if (isWorking()) return;
  state.preferences = {
    ...state.preferences,
    ...(await api(
      "/api/settings",
      jsonOptions(
        {
          default_model: $("#default-model").value,
          system_prompt: $("#system-prompt").value,
          web_mode: $("#web-mode").value,
          decision_engine: $("#decision-engine").value,
        },
        "PUT",
      ),
    )),
  };
  $("#settings-feedback").textContent = "Saved on this laptop";
  toast("Settings saved.");
});
on("#thread-settings", "submit", async (e) => {
  e.preventDefault();
  if (isWorking()) return;
  state.thread = await api(
    "/api/threads/" + state.thread.id,
    jsonOptions(
      {
        title: $("#edit-title").value,
        category_id: $("#edit-category").value,
        custom_prompt: $("#thread-prompt").value,
        site: $("#thread-site").value,
      },
      "PATCH",
    ),
  );
  await refreshThreads();
  renderThreadControls();
  $("#settings-dialog").close();
  toast("Conversation updated.");
});
async function toggleClosed() {
  if (isWorking()) return;
  stopSession();
  state.thread = await api(
    "/api/threads/" + state.thread.id,
    jsonOptions({ closed: !state.thread.closed }, "PATCH"),
  );
  $("#settings-dialog").close();
  await refreshThreads();
  await selectThread(state.thread.id);
}
on("#close-thread", "click", toggleClosed);
on("#reopen-thread", "click", toggleClosed);
on("#manage-category", "change", () =>
  categoryEditor($("#manage-category").value),
);
on("#new-category", "click", () => categoryEditor(""));
on("#category-settings", "submit", async (e) => {
  e.preventDefault();
  if (isWorking()) return;
  const id = $("#manage-category").value;
  const c = await api(
    "/api/categories" + (id ? "/" + id : ""),
    jsonOptions(
      { name: $("#category-name").value, prompt: $("#category-prompt").value },
      id ? "PUT" : "POST",
    ),
  );
  state.categories = await api("/api/categories");
  categoryEditor(c.id);
  renderThreadControls();
  renderThreads();
  $("#edit-category").innerHTML = categoryOptions(state.thread.category_id);
  toast("Category saved.");
});
async function loadNotebook() {
  const [tasks, notes] = await Promise.all([
    api("/api/tasks"),
    api("/api/notes"),
  ]);
  $("#notebook-content").innerHTML =
    "<h3>Tasks</h3>" +
    (tasks.length
      ? tasks
          .map(
            (t) =>
              `<label class="notebook-item task-row ${t.completed ? "completed" : ""}"><input type="checkbox" data-task="${esc(t.id)}"${t.completed ? " checked" : ""}><span>${esc(t.title)}<small>${esc([t.due_date, t.site].filter(Boolean).join(" · "))}</small></span></label>`,
          )
          .join("")
      : '<p class="field-help">No tasks yet. Try “Add a task: check the north gate tomorrow”.</p>') +
    "<h3>Notes</h3>" +
    (notes.length
      ? notes
          .map(
            (n) =>
              `<article class="notebook-item">${esc(n.text)}<small>${esc(n.site)} · ${esc(new Date(n.created_at).toLocaleDateString())}</small></article>`,
          )
          .join("")
      : '<p class="field-help">No notes yet. Try “Save a note: the east sensor was replaced”.</p>');
  $("#notebook-content")
    .querySelectorAll("[data-task]")
    .forEach(
      (c) =>
        (c.onchange = async () => {
          try {
            await api(
              "/api/tasks/" + c.dataset.task,
              jsonOptions({ completed: c.checked }, "PATCH"),
            );
            await loadNotebook();
          } catch (e) {
            toast(e.message, true);
          }
        }),
    );
}
on("#notebook", "click", async () => {
  await loadNotebook();
  $("#notebook-dialog").showModal();
});

// Browser audio capture only. Recognition and synthesis run in the Python process.
const voice = {
  stream: null,
  recorder: null,
  context: null,
  frame: null,
  session: false,
  recording: false,
  finishing: false,
  discard: false,
  startedAt: 0,
  lastSpeech: 0,
  resumeAfter: 0,
  chunks: [],
  audio: null,
  abort: null,
  timer: null,
};
const voiceState = (text) => {
  $("#voice-state").textContent = text;
};
async function microphone() {
  if (!state.status?.voice.transcription)
    throw new Error(
      "Voice input needs setup. Run the voice setup command in the README.",
    );
  if (!navigator.mediaDevices?.getUserMedia)
    throw new Error(
      "This browser cannot record audio. Open Fieldmate on localhost in Chrome or Safari.",
    );
  if (!voice.stream)
    voice.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
  return voice.stream;
}
function releaseMicrophone() {
  if (voice.stream) {
    voice.stream.getTracks().forEach((track) => track.stop());
    voice.stream = null;
  }
  if (voice.frame) cancelAnimationFrame(voice.frame);
  voice.frame = null;
  if (voice.context) {
    voice.context.close().catch(() => {});
    voice.context = null;
  }
}
function beginRecording() {
  if (voice.finishing || voice.recording) return;
  voice.discard = false;
  voice.chunks = [];
  const mime = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find(
    (type) => MediaRecorder.isTypeSupported(type),
  );
  voice.recorder = new MediaRecorder(
    voice.stream,
    mime ? { mimeType: mime } : {},
  );
  voice.recorder.addEventListener("dataavailable", (event) => {
    if (event.data.size) voice.chunks.push(event.data);
  });
  voice.recorder.addEventListener("stop", async () => {
    const discarded = voice.discard;
    const blob = new Blob(voice.chunks, { type: voice.recorder.mimeType });
    voice.recording = false;
    voice.finishing = false;
    $("#record").classList.remove("recording");
    $("#record").setAttribute("aria-label", "Record a voice message");
    if (!voice.session) releaseMicrophone();
    if (discarded || blob.size < 100) return;
    setBusy(true);
    voiceState("Transcribing on this laptop…");
    try {
      const data = new FormData();
      data.append("file", blob, "voice-message");
      const result = await api("/api/transcribe", {
        method: "POST",
        body: data,
      });
      setBusy(false);
      if (result.text) {
        if (voice.session) await sendMessage(result.text);
        else {
          $("#message").value = result.text;
          $("#message").focus();
          voiceState("Check your words, then press send.");
        }
      } else voiceState("No speech detected. Try again.");
    } catch (error) {
      stopSession();
      toast(error.message, true);
      voiceState("Voice paused. You can still type.");
    } finally {
      setBusy(false);
      voice.resumeAfter = performance.now() + 700;
    }
  });
  voice.recorder.start(250);
  voice.recording = true;
  voice.startedAt = performance.now();
  voice.lastSpeech = voice.startedAt;
  $("#record").classList.add("recording");
  $("#record").setAttribute("aria-label", "Stop recording");
  voiceState("Listening… tap the mic to finish.");
}
function stopRecording(discard = false) {
  if (!voice.recording) return;
  clearTimeout(voice.timer);
  voice.discard = discard;
  voice.recording = false;
  voice.finishing = true;
  if (voice.recorder?.state === "recording") voice.recorder.stop();
}
$("#record").addEventListener("click", async () => {
  if (voice.recording) {
    stopRecording();
    return;
  }
  if (state.busy || voice.finishing || state.thread?.closed) return;
  if (voice.session) {
    stopSession();
    return;
  }
  try {
    stopSpeaking();
    await microphone();
    beginRecording();
    voice.timer = setTimeout(() => {
      if (voice.recording && !voice.session) stopRecording();
    }, 55000);
  } catch (error) {
    releaseMicrophone();
    toast(
      error.name === "NotAllowedError"
        ? "Microphone access was declined. Allow it in the browser to use voice."
        : error.message,
      true,
    );
  }
});
async function startSession() {
  if (state.busy || state.thread?.closed) return;
  try {
    await microphone();
    voice.session = true;
    $("#handsfree").innerHTML = icon("headphones") + "End hands-free session";
    $("#handsfree").classList.add("listening");
    voice.context = new AudioContext();
    await voice.context.resume();
    const analyser = voice.context.createAnalyser();
    analyser.fftSize = 2048;
    voice.context.createMediaStreamSource(voice.stream).connect(analyser);
    const samples = new Float32Array(analyser.fftSize);
    voice.resumeAfter = performance.now() + 600;
    let speechFrames = 0;
    voiceState("Listening for your next thought…");
    const detect = () => {
      if (!voice.session) return;
      analyser.getFloatTimeDomainData(samples);
      let total = 0;
      for (const sample of samples) total += sample * sample;
      const rms = Math.sqrt(total / samples.length);
      const now = performance.now();
      if (!state.busy && !state.speaking && now > voice.resumeAfter) {
        if (rms > 0.024) {
          speechFrames++;
          if (!voice.recording && speechFrames >= 3) beginRecording();
          if (voice.recording) voice.lastSpeech = now;
        } else speechFrames = 0;
        if (
          voice.recording &&
          ((now - voice.lastSpeech > 1100 && now - voice.startedAt > 600) ||
            now - voice.startedAt > 55000)
        )
          stopRecording();
      }
      voice.frame = requestAnimationFrame(detect);
    };
    detect();
  } catch (error) {
    stopSession();
    releaseMicrophone();
    toast(
      error.name === "NotAllowedError"
        ? "Allow microphone access to start a hands-free session."
        : error.message,
      true,
    );
  }
}
function stopSession() {
  if (!voice.session) return;
  voice.session = false;
  stopRecording(true);
  releaseMicrophone();
  $("#handsfree").innerHTML = icon("headphones") + "Start hands-free session";
  $("#handsfree").classList.remove("listening");
  voiceState("Hands-free session ended.");
}
$("#handsfree").addEventListener("click", () =>
  voice.session ? stopSession() : startSession(),
);
function stopSpeaking() {
  voice.abort?.abort();
  if (voice.audio) {
    voice.audio.pause();
    voice.audio.dispatchEvent(new Event("ended"));
    voice.audio = null;
  }
  state.speaking = false;
  $("#stop-speaking").classList.add("hidden");
}
async function speak(text) {
  stopSpeaking();
  state.speaking = true;
  $("#stop-speaking").classList.remove("hidden");
  voiceState("Speaking…");
  const controller = new AbortController();
  voice.abort = controller;
  let objectURL;
  try {
    const response = await fetch("/api/speak", {
      ...jsonOptions({ text: text.slice(0, 3500) }),
      signal: controller.signal,
    });
    if (!response.ok)
      throw new Error(
        "Voice output is unavailable. Your reply is shown above.",
      );
    objectURL = URL.createObjectURL(await response.blob());
    const audio = new Audio(objectURL);
    voice.audio = audio;
    await new Promise((resolve, reject) => {
      audio.addEventListener("ended", resolve, { once: true });
      audio.addEventListener("error", reject, { once: true });
      audio.play().catch(reject);
    });
  } catch (error) {
    if (error.name !== "AbortError")
      toast(
        error.message ||
          "Audio playback was blocked. Your reply is shown above.",
        true,
      );
  } finally {
    if (objectURL) URL.revokeObjectURL(objectURL);
    voice.audio = null;
    voice.abort = null;
    state.speaking = false;
    $("#stop-speaking").classList.add("hidden");
    voice.resumeAfter = performance.now() + 650;
  }
}
$("#stop-speaking").addEventListener("click", stopSpeaking);
$("#read-aloud").addEventListener("change", () => {
  if (!$("#read-aloud").checked) stopSpeaking();
});
window.addEventListener("beforeunload", () => {
  stopSession();
  stopRecording(true);
  releaseMicrophone();
  stopSpeaking();
});

async function boot() {
  try {
    const [preferences, categories] = await Promise.all([
      api("/api/settings"),
      api("/api/categories"),
    ]);
    state.preferences = preferences;
    state.categories = categories;
    await refreshStatus();
    try {
      state.models = await api("/api/models");
    } catch {
      state.models = [preferences.default_model];
    }
    await refreshThreads();
    const last = localStorage.getItem("fieldmate-thread");
    const target =
      state.threads.find((t) => t.id === last) ||
      state.threads.find((t) => !t.closed);
    if (target) await selectThread(target.id);
    else await newThread();
  } catch (error) {
    toast(error.message, true);
    $("#voice-state").textContent =
      "Could not connect to Fieldmate. Reload after starting the app.";
  }
}
boot();
