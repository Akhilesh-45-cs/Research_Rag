const API = "";
let currentChatId = null;
let expandedSessionId = null;

function showConfirmModal(title, message) {
    return new Promise((resolve) => {
        const overlay = document.getElementById("confirm-modal");
        document.getElementById("modal-title").textContent = title;
        document.getElementById("modal-message").textContent = message;

        overlay.classList.add("active");

        const cancelBtn = document.getElementById("modal-cancel");
        const confirmBtn = document.getElementById("modal-confirm");

        function cleanup(result) {
            overlay.classList.remove("active");
            cancelBtn.removeEventListener("click", onCancel);
            confirmBtn.removeEventListener("click", onConfirm);
            resolve(result);
        }
        function onCancel() { cleanup(false); }
        function onConfirm() { cleanup(true); }

        cancelBtn.addEventListener("click", onCancel);
        confirmBtn.addEventListener("click", onConfirm);
    });
}

// ---------- Tab switching ----------
document.querySelectorAll(".sidebar-tab").forEach(tab => {
    tab.addEventListener("click", () => {
        document.querySelectorAll(".sidebar-tab").forEach(t => t.classList.remove("active"));
        document.querySelectorAll(".sidebar-panel").forEach(p => p.classList.remove("active"));
        tab.classList.add("active");
        document.getElementById(`panel-${tab.dataset.tab}`).classList.add("active");

        if (tab.dataset.tab === "sessions") loadSessions();
    });
});

// ---------- Chats ----------
async function loadChats() {
    const res = await fetch(`${API}/api/chats`);
    const chats = await res.json();
    const list = document.getElementById("chat-list");
    list.innerHTML = "";

    chats.forEach(chat => {
        const div = document.createElement("div");
        div.className = "chat-item" + (chat.chat_id === currentChatId ? " active" : "");
        const title = chat.title === "New Chat" ? "New chat (empty)" : chat.title;
        div.innerHTML = `<span>${escapeHtml(title)}</span><span class="del-btn" data-id="${chat.chat_id}">✕</span>`;
        div.querySelector("span:first-child").addEventListener("click", () => selectChat(chat.chat_id));
        div.querySelector(".del-btn").addEventListener("click", async (e) => {
            e.stopPropagation();
            await fetch(`${API}/api/chats/${chat.chat_id}`, { method: "DELETE" });
            if (chat.chat_id === currentChatId) currentChatId = null;
            loadChats();
            if (!currentChatId) document.getElementById("chat-window").innerHTML = `<div class="empty-state">Select or start a chat to begin.</div>`;
        });
        list.appendChild(div);
    });
}

async function createNewChat() {
    const res = await fetch(`${API}/api/chats`, { method: "POST" });
    const data = await res.json();
    currentChatId = data.chat_id;
    await loadChats();
    renderMessages([]);
}

async function selectChat(chatId) {
    currentChatId = chatId;
    const res = await fetch(`${API}/api/chats/${chatId}`);
    const chat = await res.json();
    await loadChats();
    renderMessages(chat.messages);
}

document.getElementById("new-chat-btn").addEventListener("click", createNewChat);

// ---------- Messages ----------
function renderMessages(messages) {
    const win = document.getElementById("chat-window");
    win.innerHTML = "";

    if (messages.length === 0) {
        win.innerHTML = `<div class="empty-state">Ask a question about your papers to begin.</div>`;
        return;
    }

    messages.forEach(msg => {
        const div = document.createElement("div");
        div.className = `message ${msg.role}`;

        if (msg.role === "user") {
            div.innerHTML = `<div class="bubble">${escapeHtml(msg.content)}</div>`;
        } else {
            const routeLabel = msg.route ? `<div class="route-label">${escapeHtml(msg.route)}</div>` : "";
            const citations = renderCitations(msg.sources || []);
            div.innerHTML = `<div class="bubble">${routeLabel}${marked.parse(msg.content)}${citations}</div>`;
        }
        win.appendChild(div);
    });

    win.scrollTop = win.scrollHeight;
}

function renderCitations(sources) {
    if (!sources || sources.length === 0) return "";
    const entries = sources.map((s, i) =>
        `<div class="citation-entry"><sup>${i + 1}</sup>${escapeHtml(s)}</div>`
    ).join("");
    return `<div class="citations">${entries}</div>`;
}

async function sendMessage() {
    const input = document.getElementById("message-input");
    const text = input.value.trim();
    if (!text) return;

    if (!currentChatId) await createNewChat();

    input.value = "";

    const win = document.getElementById("chat-window");
    if (win.querySelector(".empty-state")) win.innerHTML = "";
    const userDiv = document.createElement("div");
    userDiv.className = "message user";
    userDiv.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
    win.appendChild(userDiv);

    const thinkingDiv = document.createElement("div");
    thinkingDiv.className = "message assistant";
    thinkingDiv.innerHTML = `<div class="bubble"><span class="typing-dots"><span></span><span></span><span></span></span></div>`;
    win.appendChild(thinkingDiv);
    win.scrollTop = win.scrollHeight;

    const res = await fetch(`${API}/api/chats/${currentChatId}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text })
    });
    const data = await res.json();

    const chat = await (await fetch(`${API}/api/chats/${currentChatId}`)).json();
    renderMessages(chat.messages);
    loadChats();
}

document.getElementById("send-btn").addEventListener("click", sendMessage);
document.getElementById("message-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
});

// ---------- Sessions ----------
async function loadSessions() {
    const res = await fetch(`${API}/api/sessions`);
    const sessions = await res.json();
    const list = document.getElementById("session-list");
    list.innerHTML = "";

    if (sessions.length === 0) {
        list.innerHTML = `<div class="empty-state">No research sessions yet.</div>`;
        return;
    }

    sessions.forEach(session => {
        const card = document.createElement("div");
        card.className = "session-card";
        card.innerHTML = `
            <div class="session-card-header">
                <div>
                    <div class="session-card-title">${escapeHtml(session.topic_name)}</div>
                    <div class="session-card-meta">${session.papers.length} papers · ${session.reports.length} reports</div>
                </div>
                <div style="display: flex; gap: 10px; align-items: center; flex-shrink: 0;">
                    <div class="session-star ${session.starred ? "starred" : ""}" data-id="${session.session_id}">★</div>
                    <div class="session-delete" data-id="${session.session_id}" title="Delete session">✕</div>
                </div>
            </div>
            <div class="session-detail" id="detail-${session.session_id}"></div>
        `;

        card.querySelector(".session-card-header").addEventListener("click", (e) => {
            if (e.target.classList.contains("session-star") || e.target.classList.contains("session-delete")) return;
            toggleSessionDetail(session.session_id);
        });

        card.querySelector(".session-star").addEventListener("click", async (e) => {
            e.stopPropagation();
            await fetch(`${API}/api/sessions/${session.session_id}/star`, { method: "POST" });
            loadSessions();
        });

        card.querySelector(".session-delete").addEventListener("click", async (e) => {
            e.stopPropagation();
            const confirmed = await showConfirmModal(
                "Delete session?",
                `"${session.topic_name}" will be removed. Papers inside it stay in your library unless deleted individually.`
            );
            if (!confirmed) return;

            await fetch(`${API}/api/sessions/${session.session_id}`, { method: "DELETE" });
            loadSessions();
        });

        list.appendChild(card);
    });
}

async function toggleSessionDetail(sessionId) {
    const detailDiv = document.getElementById(`detail-${sessionId}`);
    const isExpanded = detailDiv.classList.contains("expanded");

    document.querySelectorAll(".session-detail").forEach(d => d.classList.remove("expanded"));

    if (isExpanded) return;

    const res = await fetch(`${API}/api/sessions/${sessionId}`);
    const session = await res.json();

    const papersRes = await fetch(`${API}/api/papers`);
    const allPapers = await papersRes.json();

    let html = "";
    session.papers.forEach(paperName => {
        const paperInfo = allPapers.find(p => p.source_name === paperName) || {};
        const origin = paperInfo.origin || "manual_upload";
        html += `
            <div class="paper-index-card">
                <div class="paper-tab ${origin}"></div>
                <div class="paper-title">${escapeHtml(paperName)}</div>
                <div class="paper-meta">${origin} · ${paperInfo.chunk_count || "?"} chunks</div>
                <div class="paper-actions">
                    <span class="delete-paper" data-name="${escapeHtml(paperName)}">Delete</span>
                </div>
            </div>
        `;
    });

    html += `<div style="font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-muted); margin: 14px 0 6px;">REPORTS</div>`;

    if (session.reports.length > 0) {
        session.reports.forEach(r => {
            html += `
                <div class="paper-index-card">
                    <div class="paper-title">${escapeHtml(r.title)}</div>
                    <div class="paper-meta">${r.created_at.slice(0, 16).replace("T", " ")}</div>
                    <div class="paper-actions">
                        <a href="/api/reports/download?path=${encodeURIComponent(r.filepath)}" target="_blank">Download</a>
                        <span class="delete-report" data-session="${sessionId}" data-report="${r.report_id}">Delete</span>
                    </div>
                </div>
            `;
        });
    } else {
        html += `<div style="font-size: 0.75rem; color: var(--text-faint); margin-bottom: 8px;">No reports generated yet.</div>`;
    }

    html += `<button class="btn-primary" id="gen-report-btn" style="margin-top: 6px;">Generate Report</button>
             <div id="report-status" style="font-family: var(--font-mono); font-size: 0.7rem; margin-top: 6px; color: var(--text-muted);"></div>`;

    detailDiv.innerHTML = html;
    detailDiv.classList.add("expanded");

    document.getElementById("gen-report-btn").addEventListener("click", async () => {
        const status = document.getElementById("report-status");
        status.textContent = "Generating report... this may take a minute.";

        const res = await fetch(`${API}/api/sessions/${sessionId}/generate_report`, { method: "POST" });

        if (!res.ok) {
            const err = await res.json();
            status.textContent = `Failed: ${err.detail}`;
            return;
        }

        status.textContent = "Report generated!";
        toggleSessionDetail(sessionId); // collapse
        toggleSessionDetail(sessionId); // re-expand with fresh data
        loadSessions();
    });

    detailDiv.querySelectorAll(".delete-paper").forEach(el => {
        el.addEventListener("click", async () => {
            await fetch(`${API}/api/papers?source_name=${encodeURIComponent(el.dataset.name)}`, { method: "DELETE" });
            toggleSessionDetail(sessionId);
            loadSessions();
        });
    });

    detailDiv.querySelectorAll(".delete-report").forEach(el => {
        el.addEventListener("click", async () => {
            const confirmed = await showConfirmModal("Delete report?", "This report file will be permanently removed.");
            if (!confirmed) return;
            await fetch(`${API}/api/sessions/${el.dataset.session}/reports/${el.dataset.report}`, { method: "DELETE" });
            toggleSessionDetail(sessionId);
            toggleSessionDetail(sessionId);
        });
    });
}

// ---------- Upload ----------
document.getElementById("upload-btn").addEventListener("click", async () => {
    const fileInput = document.getElementById("upload-file");
    const topic = document.getElementById("upload-topic").value.trim();
    const status = document.getElementById("upload-status");

    if (!fileInput.files[0]) { status.textContent = "Choose a file first."; return; }
    if (!topic) { status.textContent = "Enter a topic/session name."; return; }

    status.textContent = "Processing...";

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("topic", topic);

    const res = await fetch(`${API}/api/upload`, { method: "POST", body: formData });
    const data = await res.json();

    status.textContent = `Added: ${data.chunks} chunks, ${data.sections} sections.`;
    fileInput.value = "";
    fileDropLabel.textContent = "Select a PDF to catalog";
    fileDropZone.classList.remove("has-file");
    document.getElementById("upload-topic").value = "";
});

// ---------- Fetch by topic ----------
document.getElementById("fetch-btn").addEventListener("click", async () => {
    const topic = document.getElementById("fetch-topic").value.trim();
    const source = document.getElementById("fetch-source").value;
    const numPapers = parseInt(document.getElementById("fetch-count").value);
    const status = document.getElementById("fetch-status");

    if (!topic) { status.textContent = "Enter a topic first."; return; }

    status.textContent = "Searching and processing... this may take a while.";

    const res = await fetch(`${API}/api/fetch_topic`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, source, num_papers: numPapers })
    });
    const data = await res.json();

    status.innerHTML = data.results.map(r => `${r.status}: ${escapeHtml(r.title.slice(0, 50))}`).join("<br>");
});

// ---------- File drop zone ----------
const fileDropZone = document.getElementById("file-drop-zone");
const fileInput = document.getElementById("upload-file");
const fileDropLabel = document.getElementById("file-drop-label");

fileDropZone.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
    if (fileInput.files[0]) {
        fileDropLabel.textContent = fileInput.files[0].name;
        fileDropZone.classList.add("has-file");
    } else {
        fileDropLabel.textContent = "Select a PDF to catalog";
        fileDropZone.classList.remove("has-file");
    }
});

// ---------- Utility ----------
function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// ---------- Init ----------
loadChats();