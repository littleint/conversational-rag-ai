/**
 * LlamaReader AI — Full Frontend Application Logic
 * Supports JWT Auth, Persistent Conversation History, Document Indexing, and Markdown RAG Streaming
 */

// ================= DOM ELEMENTS =================
const authModal = document.getElementById("authModal");
const authForm = document.getElementById("authForm");
const tabLogin = document.getElementById("tabLogin");
const tabRegister = document.getElementById("tabRegister");
const authUsername = document.getElementById("authUsername");
const authPassword = document.getElementById("authPassword");
const authSubmitBtn = document.getElementById("authSubmitBtn");
const authAlert = document.getElementById("authAlert");

const userAvatar = document.getElementById("userAvatar");
const userNameDisplay = document.getElementById("userNameDisplay");
const logoutBtn = document.getElementById("logoutBtn");

const sidebar = document.getElementById("sidebar");
const sidebarCollapseBtn = document.getElementById("sidebarCollapseBtn");
const mobileMenuBtn = document.getElementById("mobileMenuBtn");
const newChatBtn = document.getElementById("newChatBtn");
const conversationList = document.getElementById("conversationList");

const currentChatTitle = document.getElementById("currentChatTitle");
const editTitleBtn = document.getElementById("editTitleBtn");
const sourceBadge = document.getElementById("sourceBadge");
const sourceBadgeText = document.getElementById("sourceBadgeText");
const toggleDrawerBtn = document.getElementById("toggleDrawerBtn");
const closeDrawerBtn = document.getElementById("closeDrawerBtn");
const sourceDrawer = document.getElementById("sourceDrawer");

const tabUrlBtn = document.getElementById("tabUrlBtn");
const tabFileBtn = document.getElementById("tabFileBtn");
const urlContent = document.getElementById("urlContent");
const fileContent = document.getElementById("fileContent");
const urlIndexForm = document.getElementById("urlIndexForm");
const urlInput = document.getElementById("urlInput");
const indexUrlBtn = document.getElementById("indexUrlBtn");

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const fileSelectedBar = document.getElementById("fileSelectedBar");
const selectedFileName = document.getElementById("selectedFileName");
const cancelFileBtn = document.getElementById("cancelFileBtn");
const uploadFileBtn = document.getElementById("uploadFileBtn");

const messagesContainer = document.getElementById("messagesContainer");
const welcomeHero = document.getElementById("welcomeHero");
const messagesList = document.getElementById("messagesList");
const typingIndicator = document.getElementById("typingIndicator");

const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const sendIcon = sendBtn ? sendBtn.querySelector(".send-icon") : null;
const stopIcon = sendBtn ? sendBtn.querySelector(".stop-icon") : null;
const stopPillContainer = document.getElementById("stopPillContainer");
const stopGeneratingBtn = document.getElementById("stopGeneratingBtn");
const promptAttachBtn = document.getElementById("promptAttachBtn");

const renameModal = document.getElementById("renameModal");
const renameForm = document.getElementById("renameForm");
const renameInput = document.getElementById("renameInput");
const cancelRenameBtn = document.getElementById("cancelRenameBtn");
const toast = document.getElementById("toast");

// ================= APPLICATION STATE =================
let currentUser = null;
let activeConversationId = null;
let conversations = [];
let authMode = "login"; // "login" or "register"
let selectedFile = null;
let conversationToRename = null;
let currentAbortController = null;
let isGenerating = false;

// Configure Marked.js
if (typeof marked !== "undefined") {
    marked.setOptions({
        breaks: true,
        gfm: true,
        highlight: function (code, lang) {
            if (typeof hljs !== "undefined" && lang && hljs.getLanguage(lang)) {
                return hljs.highlight(code, { language: lang }).value;
            }
            return typeof hljs !== "undefined" ? hljs.highlightAuto(code).value : code;
        }
    });
}

// Math / LaTeX rendering helper via KaTeX
function renderMathInElementWrapper(element) {
    if (typeof renderMathInElement !== "undefined" && element) {
        try {
            renderMathInElement(element, {
                delimiters: [
                    { left: "$$", right: "$$", display: true },
                    { left: "\\[", right: "\\]", display: true },
                    { left: "$", right: "$", display: false },
                    { left: "\\(", right: "\\)", display: false }
                ],
                throwOnError: false
            });
        } catch (e) {
            console.warn("KaTeX render error:", e);
        }
    }
}

// ================= AUTHENTICATION HELPERS =================
function getToken() {
    return localStorage.getItem("llamareader_token");
}

function setToken(token) {
    localStorage.setItem("llamareader_token", token);
}

function removeToken() {
    localStorage.removeItem("llamareader_token");
}

function authHeaders() {
    const token = getToken();
    return token ? { "Authorization": `Bearer ${token}` } : {};
}

// Show Toast message
function showToast(message, duration = 3000) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.remove("hidden");
    setTimeout(() => {
        toast.classList.add("hidden");
    }, duration);
}

// ================= AUTHENTICATION LIFECYCLE =================
async function initAuth() {
    const token = getToken();
    if (!token) {
        showAuthModal("login");
        return;
    }

    try {
        const res = await fetch("/api/auth/me", { headers: authHeaders() });
        if (res.ok) {
            const data = await res.json();
            currentUser = data;
            onAuthSuccess(data);
        } else {
            removeToken();
            showAuthModal("login");
        }
    } catch (e) {
        console.error("Auth check failed:", e);
        showAuthModal("login");
    }
}

function showAuthModal(mode = "login") {
    authMode = mode;
    authModal.classList.remove("hidden");
    authAlert.classList.add("hidden");
    authUsername.value = "";
    authPassword.value = "";

    if (mode === "login") {
        tabLogin.classList.add("active");
        tabRegister.classList.remove("active");
        authSubmitBtn.querySelector(".btn-text").textContent = "Sign In";
    } else {
        tabRegister.classList.add("active");
        tabLogin.classList.remove("active");
        authSubmitBtn.querySelector(".btn-text").textContent = "Create Account";
    }
}

function hideAuthModal() {
    authModal.classList.add("hidden");
}

function onAuthSuccess(user) {
    hideAuthModal();
    userNameDisplay.textContent = user.username;
    userAvatar.textContent = user.username.charAt(0).toUpperCase();
    loadConversations();
}

// Auth Tab Switching
tabLogin.addEventListener("click", () => showAuthModal("login"));
tabRegister.addEventListener("click", () => showAuthModal("register"));

// Auth Form Submission
authForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = authUsername.value.trim();
    const password = authPassword.value;

    if (!username || !password) {
        showAuthError("Please fill in both fields.");
        return;
    }

    const endpoint = authMode === "login" ? "/api/auth/login" : "/api/auth/register";
    const btnText = authSubmitBtn.querySelector(".btn-text");
    const btnSpinner = authSubmitBtn.querySelector(".btn-spinner");

    btnText.style.display = "none";
    btnSpinner.classList.remove("hidden");
    authSubmitBtn.disabled = true;
    authAlert.classList.add("hidden");

    try {
        const res = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();

        if (res.ok && data.token) {
            setToken(data.token);
            currentUser = { username: data.username };
            onAuthSuccess(currentUser);
            showToast(authMode === "login" ? "Logged in successfully!" : "Account created successfully!");
        } else {
            showAuthError(data.detail || "Authentication failed.");
        }
    } catch (err) {
        showAuthError("Server connection error. Please verify the server is running.");
    } finally {
        btnText.style.display = "inline";
        btnSpinner.classList.add("hidden");
        authSubmitBtn.disabled = false;
    }
});

function showAuthError(msg) {
    authAlert.textContent = msg;
    authAlert.className = "auth-alert";
    authAlert.classList.remove("hidden");
}

const quickDemoBtn = document.getElementById("quickDemoBtn");
if (quickDemoBtn) {
    quickDemoBtn.addEventListener("click", async () => {
        quickDemoBtn.disabled = true;
        quickDemoBtn.textContent = "Entering workspace...";
        try {
            let res = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: "demo_user", password: "demopassword123" })
            });
            let data = await res.json();
            if (!res.ok) {
                res = await fetch("/api/auth/register", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ username: "demo_user", password: "demopassword123" })
                });
                data = await res.json();
            }
            if (data.token) {
                setToken(data.token);
                currentUser = { username: data.username };
                onAuthSuccess(currentUser);
                showToast("Logged in as demo_user!");
            } else {
                showAuthError("Demo login failed.");
            }
        } catch (e) {
            showAuthError("Connection error.");
        } finally {
            quickDemoBtn.disabled = false;
            quickDemoBtn.textContent = "⚡ Quick Demo Login (Instant Access)";
        }
    });
}

// Logout
logoutBtn.addEventListener("click", () => {
    if (confirm("Are you sure you want to log out?")) {
        removeToken();
        currentUser = null;
        activeConversationId = null;
        conversations = [];
        messagesList.innerHTML = "";
        showAuthModal("login");
    }
});

// ================= CONVERSATION MANAGEMENT =================
async function loadConversations() {
    conversationList.innerHTML = `
        <div class="history-loading">
            <div class="spinner-small"></div>
            <span>Loading conversations...</span>
        </div>`;

    try {
        const res = await fetch("/api/conversations", { headers: authHeaders() });
        if (!res.ok) throw new Error("Failed to fetch conversations");
        conversations = await res.json();

        if (conversations.length === 0) {
            // Automatically create a new empty chat for user
            await createNewConversation(false);
            return;
        }

        renderConversationList();

        // Select the most recent conversation if none active
        if (!activeConversationId || !conversations.some(c => c.id === activeConversationId)) {
            selectConversation(conversations[0].id);
        } else {
            selectConversation(activeConversationId);
        }
    } catch (e) {
        console.error("Error loading conversations:", e);
        conversationList.innerHTML = `<div class="history-loading" style="color:var(--danger)">Failed to load conversations.</div>`;
    }
}

function renderConversationList() {
    if (conversations.length === 0) {
        conversationList.innerHTML = `<div class="history-loading">No conversations yet.</div>`;
        return;
    }

    // Group conversations by date (Today, Previous 7 Days, Older)
    const now = new Date();
    const today = [];
    const last7Days = [];
    const older = [];

    conversations.forEach(c => {
        const date = new Date(c.updated_at || c.created_at);
        const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
        if (diffDays === 0) today.push(c);
        else if (diffDays <= 7) last7Days.push(c);
        else older.push(c);
    });

    let html = "";
    if (today.length > 0) {
        html += `<div class="history-group-title">Today</div>`;
        today.forEach(c => html += renderConversationItem(c));
    }
    if (last7Days.length > 0) {
        html += `<div class="history-group-title">Previous 7 Days</div>`;
        last7Days.forEach(c => html += renderConversationItem(c));
    }
    if (older.length > 0) {
        html += `<div class="history-group-title">Older</div>`;
        older.forEach(c => html += renderConversationItem(c));
    }

    conversationList.innerHTML = html;

    // Attach click and action listeners
    conversationList.querySelectorAll(".conversation-item").forEach(item => {
        const id = item.dataset.id;
        item.addEventListener("click", (e) => {
            if (e.target.closest(".action-icon-btn")) return;
            selectConversation(id);
            if (window.innerWidth <= 768) {
                sidebar.classList.remove("mobile-open");
            }
        });

        const renameBtn = item.querySelector(".rename-chat-btn");
        if (renameBtn) {
            renameBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                openRenameModal(id);
            });
        }

        const deleteBtn = item.querySelector(".delete-btn");
        if (deleteBtn) {
            deleteBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                deleteConversation(id);
            });
        }
    });
}

function renderConversationItem(conv) {
    const isActive = conv.id === activeConversationId;
    return `
        <div class="conversation-item ${isActive ? "active" : ""}" data-id="${conv.id}">
            <span class="conversation-title-text" title="${escapeHtml(conv.title)}">
                ${escapeHtml(conv.title || "New Chat")}
            </span>
            <div class="conversation-actions">
                <button class="action-icon-btn rename-chat-btn" title="Rename">
                    <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none">
                        <path d="M12 20h9"></path>
                        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                    </svg>
                </button>
                <button class="action-icon-btn delete-btn" title="Delete">
                    <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                </button>
            </div>
        </div>
    `;
}

async function createNewConversation(shouldSelect = true) {
    try {
        const res = await fetch("/api/conversations", {
            method: "POST",
            headers: authHeaders()
        });
        if (!res.ok) throw new Error("Could not create conversation");
        const newConv = await res.json();
        conversations.unshift(newConv);
        renderConversationList();
        if (shouldSelect) {
            selectConversation(newConv.id);
        }
        return newConv;
    } catch (e) {
        console.error("Create conversation failed:", e);
        showToast("Error creating conversation.");
    }
}

newChatBtn.addEventListener("click", () => {
    createNewConversation(true);
});

async function selectConversation(convId) {
    activeConversationId = convId;
    renderConversationList();
    closeDrawer();

    messagesList.innerHTML = "";
    welcomeHero.classList.remove("hidden");
    currentChatTitle.textContent = "Loading...";

    try {
        const res = await fetch(`/api/conversations/${convId}`, { headers: authHeaders() });
        if (!res.ok) throw new Error("Conversation not found");
        const conv = await res.json();

        currentChatTitle.textContent = conv.title || "New Chat";
        updateSourceBadge(conv.source_type, conv.source_name);

        if (conv.messages && conv.messages.length > 0) {
            welcomeHero.classList.add("hidden");
            conv.messages.forEach(msg => {
                appendMessageBubble(msg.role, msg.content, false);
            });
            scrollToBottom();
        } else {
            welcomeHero.classList.remove("hidden");
        }
    } catch (e) {
        console.error("Failed to load conversation details:", e);
        showToast("Error loading conversation.");
    }
}

function updateSourceBadge(sourceType, sourceName) {
    if (sourceType && sourceName) {
        sourceBadge.classList.add("active");
        sourceBadge.classList.remove("empty");
        const icon = sourceType === "url" ? "🌐 " : "📄 ";
        const cleanName = sourceName.split("/").pop().split("\\").pop();
        sourceBadgeText.textContent = `${icon}${cleanName}`;
        sourceBadge.title = `Source: ${sourceName}`;
        toggleDrawerBtn.querySelector("span").textContent = "Change Document";
    } else {
        sourceBadge.classList.remove("active");
        sourceBadge.classList.add("empty");
        sourceBadgeText.textContent = "No document attached";
        sourceBadge.title = "No document attached to this chat";
        toggleDrawerBtn.querySelector("span").textContent = "Attach Document";
    }
}

// Rename conversation
function openRenameModal(convId) {
    conversationToRename = convId;
    const conv = conversations.find(c => c.id === convId);
    if (!conv) return;
    renameInput.value = conv.title || "New Chat";
    renameModal.classList.remove("hidden");
    renameInput.focus();
}

cancelRenameBtn.addEventListener("click", () => {
    renameModal.classList.add("hidden");
    conversationToRename = null;
});

editTitleBtn.addEventListener("click", () => {
    if (activeConversationId) openRenameModal(activeConversationId);
});

currentChatTitle.addEventListener("click", () => {
    if (activeConversationId) openRenameModal(activeConversationId);
});

renameForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!conversationToRename) return;
    const newTitle = renameInput.value.trim();
    if (!newTitle) return;

    try {
        const res = await fetch(`/api/conversations/${conversationToRename}`, {
            method: "PATCH",
            headers: {
                ...authHeaders(),
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ title: newTitle })
        });
        if (res.ok) {
            const conv = conversations.find(c => c.id === conversationToRename);
            if (conv) conv.title = newTitle;
            if (activeConversationId === conversationToRename) {
                currentChatTitle.textContent = newTitle;
            }
            renderConversationList();
            renameModal.classList.add("hidden");
            showToast("Conversation renamed.");
        }
    } catch (e) {
        console.error("Rename error:", e);
    }
});

// Delete conversation
async function deleteConversation(convId) {
    if (!confirm("Are you sure you want to delete this chat and its documents?")) return;

    try {
        const res = await fetch(`/api/conversations/${convId}`, {
            method: "DELETE",
            headers: authHeaders()
        });
        if (res.ok) {
            conversations = conversations.filter(c => c.id !== convId);
            showToast("Conversation deleted.");
            if (activeConversationId === convId) {
                if (conversations.length > 0) {
                    selectConversation(conversations[0].id);
                } else {
                    createNewConversation(true);
                }
            } else {
                renderConversationList();
            }
        }
    } catch (e) {
        console.error("Delete conversation error:", e);
    }
}

// ================= DOCUMENT DRAWER LOGIC =================
function toggleDrawer() {
    sourceDrawer.classList.toggle("hidden");
}

function closeDrawer() {
    sourceDrawer.classList.add("hidden");
}

toggleDrawerBtn.addEventListener("click", toggleDrawer);
closeDrawerBtn.addEventListener("click", closeDrawer);
promptAttachBtn.addEventListener("click", toggleDrawer);

// Drawer tabs
tabUrlBtn.addEventListener("click", () => {
    tabUrlBtn.classList.add("active");
    tabFileBtn.classList.remove("active");
    urlContent.classList.remove("hidden");
    fileContent.classList.add("hidden");
});

tabFileBtn.addEventListener("click", () => {
    tabFileBtn.classList.add("active");
    tabUrlBtn.classList.remove("active");
    fileContent.classList.remove("hidden");
    urlContent.classList.add("hidden");
});

// URL Indexing
urlIndexForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!activeConversationId) return;

    const url = urlInput.value.trim();
    if (!url) return;

    const btnText = indexUrlBtn.querySelector(".btn-text");
    const btnSpinner = indexUrlBtn.querySelector(".btn-spinner");

    btnText.style.display = "none";
    btnSpinner.classList.remove("hidden");
    indexUrlBtn.disabled = true;

    try {
        const res = await fetch(`/api/conversations/${activeConversationId}/index-url`, {
            method: "POST",
            headers: {
                ...authHeaders(),
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ url })
        });
        const text = await res.text();
        let data = {};
        try {
            data = JSON.parse(text);
        } catch {
            data = { detail: text || `Server error (${res.status})` };
        }

        if (res.ok) {
            updateSourceBadge("url", url);
            currentChatTitle.textContent = data.title;
            const conv = conversations.find(c => c.id === activeConversationId);
            if (conv) {
                conv.source_type = "url";
                conv.source_name = url;
                conv.title = data.title;
                renderConversationList();
            }
            closeDrawer();
            urlInput.value = "";
            showToast("Webpage successfully indexed!");
            appendMessageBubble("assistant", `I have indexed **${escapeHtml(url)}**. You can now ask questions about this webpage!`);
        } else {
            alert(data.detail || `Failed to index webpage (${res.status}).`);
        }
    } catch (err) {
        alert(err.message || "Network error indexing URL.");
    } finally {
        btnText.style.display = "inline";
        btnSpinner.classList.add("hidden");
        indexUrlBtn.disabled = false;
    }
});

// File Drop & Upload
dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
        handleFileSelect(e.dataTransfer.files[0]);
    }
});
fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
    }
});

function handleFileSelect(file) {
    selectedFile = file;
    selectedFileName.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    dropzone.classList.add("hidden");
    fileSelectedBar.classList.remove("hidden");
}

cancelFileBtn.addEventListener("click", () => {
    selectedFile = null;
    fileInput.value = "";
    dropzone.classList.remove("hidden");
    fileSelectedBar.classList.add("hidden");
});

uploadFileBtn.addEventListener("click", async () => {
    if (!selectedFile || !activeConversationId) return;

    const btnText = uploadFileBtn.querySelector(".btn-text");
    const btnSpinner = uploadFileBtn.querySelector(".btn-spinner");

    btnText.style.display = "none";
    btnSpinner.classList.remove("hidden");
    uploadFileBtn.disabled = true;

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
        const res = await fetch(`/api/conversations/${activeConversationId}/upload`, {
            method: "POST",
            headers: authHeaders(),
            body: formData
        });
        const data = await res.json();

        if (res.ok) {
            updateSourceBadge("file", selectedFile.name);
            currentChatTitle.textContent = data.title;
            const conv = conversations.find(c => c.id === activeConversationId);
            if (conv) {
                conv.source_type = "file";
                conv.source_name = selectedFile.name;
                conv.title = data.title;
                renderConversationList();
            }
            closeDrawer();
            cancelFileBtn.click();
            showToast("Document indexed successfully!");
            appendMessageBubble("assistant", `I have indexed **${escapeHtml(selectedFile.name)}**. Ask me anything about this document!`);
        } else {
            alert(data.detail || "Failed to upload document.");
        }
    } catch (e) {
        alert("Upload error.");
    } finally {
        btnText.style.display = "inline";
        btnSpinner.classList.add("hidden");
        uploadFileBtn.disabled = false;
    }
});

// ================= CHAT, STREAMING & CANCELLATION =================
function setGeneratingState(generating) {
    isGenerating = generating;
    if (generating) {
        if (stopPillContainer) stopPillContainer.classList.remove("hidden");
        sendBtn.classList.add("stop-mode");
        if (sendIcon) sendIcon.classList.add("hidden");
        if (stopIcon) stopIcon.classList.remove("hidden");
        sendBtn.title = "Stop generating";
        sendBtn.disabled = false;
    } else {
        if (stopPillContainer) stopPillContainer.classList.add("hidden");
        sendBtn.classList.remove("stop-mode");
        if (sendIcon) sendIcon.classList.remove("hidden");
        if (stopIcon) stopIcon.classList.add("hidden");
        sendBtn.title = "Send Message";
        sendBtn.disabled = messageInput.value.trim().length === 0;
    }
}

function stopGeneration() {
    if (currentAbortController) {
        currentAbortController.abort();
        currentAbortController = null;
    }
    setGeneratingState(false);
    typingIndicator.classList.add("hidden");
    messageInput.focus();
    showToast("Generation stopped.");
}

if (stopGeneratingBtn) {
    stopGeneratingBtn.addEventListener("click", stopGeneration);
}

chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    if (isGenerating) {
        stopGeneration();
    } else {
        sendMessage();
    }
});

// Auto-expand textarea & Enter key support
messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (isGenerating) {
            stopGeneration();
        } else {
            sendMessage();
        }
    }
});

messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 180)}px`;
    if (!isGenerating) {
        sendBtn.disabled = messageInput.value.trim().length === 0;
    }
});

function createAssistantMessageBubble() {
    const row = document.createElement("div");
    row.className = "message-row assistant";

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar assistant-avatar";
    avatar.textContent = "🦙";

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    bubble.innerHTML = '<div class="typing-bubble inline"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';

    row.appendChild(avatar);
    row.appendChild(bubble);

    messagesList.appendChild(row);
    return bubble;
}

async function sendMessage() {
    if (isGenerating) {
        stopGeneration();
        return;
    }

    const text = messageInput.value.trim();
    if (!text || !activeConversationId) return;

    messageInput.value = "";
    messageInput.style.height = "auto";
    welcomeHero.classList.add("hidden");

    // 1. Render user message bubble
    appendMessageBubble("user", text);
    scrollToBottom();

    // 2. Prepare assistant bubble and activate Stop button
    const assistantBubble = createAssistantMessageBubble();
    //typingIndicator.classList.remove("hidden");
    setGeneratingState(true);
    scrollToBottom();

    currentAbortController = new AbortController();

    try {
        const res = await fetch(`/api/conversations/${activeConversationId}/query`, {
            method: "POST",
            headers: {
                ...authHeaders(),
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ question: text, stream: true }),
            signal: currentAbortController.signal
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            typingIndicator.classList.add("hidden");
            assistantBubble.textContent = `⚠️ Error: ${errData.detail || "Query failed."}`;
            setGeneratingState(false);
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let accumulatedText = "";
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop(); // Hold partial line in buffer

            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed.startsWith("data:")) continue;
                const jsonStr = trimmed.slice(5).trim();
                if (!jsonStr) continue;

                try {
                    const data = JSON.parse(jsonStr);
                    if (data.token) {
                        typingIndicator.classList.add("hidden");
                        accumulatedText += data.token;
                        assistantBubble.innerHTML = typeof marked !== "undefined" ? marked.parse(accumulatedText) : escapeHtml(accumulatedText);
                        if (typeof hljs !== "undefined") {
                            assistantBubble.querySelectorAll("pre code").forEach(el => hljs.highlightElement(el));
                        }
                        scrollToBottom();
                    }
                    if (data.done) {
                        if (data.title) {
                            currentChatTitle.textContent = data.title;
                            const conv = conversations.find(c => c.id === activeConversationId);
                            if (conv) {
                                conv.title = data.title;
                                renderConversationList();
                            }
                        }
                    }
                    if (data.error) {
                        typingIndicator.classList.add("hidden");
                        assistantBubble.innerHTML += `<br><span style="color:var(--danger)">⚠️ ${escapeHtml(data.error)}</span>`;
                    }
                } catch (e) {
                    // Ignore JSON partial chunk parsing errors
                }
            }
        }
    } catch (err) {
        if (err.name === "AbortError") {
            console.log("Generation stopped immediately by user.");
            // Kept clean without error banner because user intentionally pressed Stop!
        } else {
            typingIndicator.classList.add("hidden");
            assistantBubble.textContent = "⚠️ Network Error: Connection interrupted.";
        }
    } finally {
        currentAbortController = null;
        setGeneratingState(false);
        typingIndicator.classList.add("hidden");
        if (assistantBubble) {
            renderMathInElementWrapper(assistantBubble);
        }
        scrollToBottom();
        messageInput.focus();
    }
}

function appendMessageBubble(role, content, shouldScroll = true) {
    const row = document.createElement("div");
    row.className = `message-row ${role}`;

    const avatar = document.createElement("div");
    avatar.className = `msg-avatar ${role === "user" ? "user-avatar" : "assistant-avatar"}`;
    avatar.textContent = role === "user" ? (currentUser ? currentUser.username.charAt(0).toUpperCase() : "U") : "🦙";

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    if (role === "assistant") {
        bubble.innerHTML = typeof marked !== "undefined" ? marked.parse(content) : escapeHtml(content);
        // Highlight code blocks
        if (typeof hljs !== "undefined") {
            bubble.querySelectorAll("pre code").forEach(el => hljs.highlightElement(el));
        }
        renderMathInElementWrapper(bubble);
    } else {
        bubble.textContent = content;
    }

    if (role === "user") {
        row.appendChild(bubble);
        row.appendChild(avatar);
    } else {
        row.appendChild(avatar);
        row.appendChild(bubble);
    }

    messagesList.appendChild(row);

    if (shouldScroll) {
        scrollToBottom();
    }
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

// Suggestion card clicks
document.querySelectorAll(".suggestion-card").forEach(card => {
    card.addEventListener("click", () => {
        const action = card.dataset.action;
        const prompt = card.dataset.prompt;

        if (action === "attach-url") {
            toggleDrawer();
            tabUrlBtn.click();
        } else if (action === "attach-file") {
            toggleDrawer();
            tabFileBtn.click();
        } else if (prompt) {
            messageInput.value = prompt;
            sendMessage();
        }
    });
});

// Sidebar collapse toggle
sidebarCollapseBtn.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
});

mobileMenuBtn.addEventListener("click", () => {
    if (window.innerWidth <= 768) {
        sidebar.classList.toggle("mobile-open");
    } else {
        sidebar.classList.toggle("collapsed");
    }
});

// ================= BOOTSTRAP =================
window.addEventListener("DOMContentLoaded", () => {
    initAuth();
});
