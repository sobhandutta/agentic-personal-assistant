/**
 * app.js — WebSocket streaming chat client
 *
 * Protocol (client → server):
 *   {"message": "...", "history": [{role, content}, ...]}
 *
 * Protocol (server → client, streamed chunks):
 *   {"type": "status", "text": "Searching knowledge base..."}
 *   {"type": "token",  "text": "Hello"}
 *   {"type": "done"}
 *   {"type": "error",  "text": "..."}
 *
 * History is managed client-side and sent with every message.
 * The server is stateless — ConversationMemory trims to MAX_MEMORY_TURNS.
 */

(function () {
    "use strict";

    // ── DOM refs ──────────────────────────────────────────────────────────────
    const chatWindow = document.getElementById("chat-window");
    const userInput  = document.getElementById("user-input");
    const sendBtn    = document.getElementById("send-btn");
    const statusDot  = document.getElementById("status-dot");

    // ── State ─────────────────────────────────────────────────────────────────
    // History in Gradio-5 / Anthropic format: [{role, content}, ...]
    // Sent with every message so the server stays stateless.
    let history = [];

    let socket               = null;
    let isStreaming          = false;
    let assistantBubble      = null;   // <div> accumulating streamed tokens
    let statusBubble         = null;   // transient status message element
    let reconnectTimeout     = null;

    const WS_URL = `ws://${location.host}/ws/chat`;

    // ── WebSocket lifecycle ───────────────────────────────────────────────────

    function connect() {
        if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
            reconnectTimeout = null;
        }

        socket = new WebSocket(WS_URL);

        socket.onopen = () => {
            setDot(true);
        };

        socket.onclose = () => {
            setDot(false);
            // Auto-reconnect after 3 s — handles server restarts gracefully
            reconnectTimeout = setTimeout(connect, 3000);
        };

        socket.onerror = () => {
            // onclose fires right after onerror, so reconnect is handled there
            setDot(false);
        };

        socket.onmessage = (event) => {
            try {
                handleChunk(JSON.parse(event.data));
            } catch (e) {
                console.error("Failed to parse server message:", event.data, e);
            }
        };
    }

    function setDot(connected) {
        statusDot.className = "dot " + (connected ? "connected" : "disconnected");
        statusDot.title = connected ? "Connected" : "Disconnected — reconnecting…";
    }

    // ── Chunk handler ─────────────────────────────────────────────────────────

    function handleChunk(chunk) {
        switch (chunk.type) {

            case "status":
                // Replace existing status bubble instead of stacking multiple ones
                if (statusBubble) {
                    statusBubble.textContent = chunk.text;
                } else {
                    statusBubble = appendBubble("status", chunk.text);
                }
                scrollDown();
                break;

            case "token":
                // First token: remove status bubble, create assistant bubble
                if (!assistantBubble) {
                    removeStatusBubble();
                    assistantBubble = appendBubble("assistant", "");
                    assistantBubble.classList.add("streaming");
                }
                assistantBubble.textContent += chunk.text;
                scrollDown();
                break;

            case "done":
                if (assistantBubble) {
                    assistantBubble.classList.remove("streaming");
                    history.push({ role: "assistant", content: assistantBubble.textContent });
                    assistantBubble = null;
                }
                removeStatusBubble();
                setStreaming(false);
                scrollDown();
                break;

            case "error":
                removeStatusBubble();
                if (assistantBubble) {
                    assistantBubble.remove();
                    assistantBubble = null;
                }
                appendBubble("assistant", "Error: " + chunk.text);
                setStreaming(false);
                scrollDown();
                break;
        }
    }

    // ── Send ──────────────────────────────────────────────────────────────────

    function send() {
        const text = userInput.value.trim();
        if (!text || isStreaming) return;

        if (!socket || socket.readyState !== WebSocket.OPEN) {
            appendBubble("status", "Not connected — please wait…");
            return;
        }

        // Show user bubble immediately (optimistic UI)
        appendBubble("user", text);
        history.push({ role: "user", content: text });

        userInput.value = "";
        resizeTextarea();
        setStreaming(true);
        scrollDown();

        socket.send(JSON.stringify({ message: text, history }));
    }

    // ── UI helpers ────────────────────────────────────────────────────────────

    function appendBubble(role, text) {
        const div = document.createElement("div");
        div.className = "message " + role;
        div.textContent = text;
        chatWindow.appendChild(div);
        return div;
    }

    function removeStatusBubble() {
        if (statusBubble) {
            statusBubble.remove();
            statusBubble = null;
        }
    }

    function scrollDown() {
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function setStreaming(active) {
        isStreaming = active;
        sendBtn.disabled = active;
        userInput.disabled = active;
        if (!active) userInput.focus();
    }

    function resizeTextarea() {
        userInput.style.height = "auto";
        userInput.style.height = Math.min(userInput.scrollHeight, 128) + "px";
    }

    // ── Event listeners ───────────────────────────────────────────────────────

    sendBtn.addEventListener("click", send);

    userInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
        }
    });

    userInput.addEventListener("input", resizeTextarea);

    // ── Boot ──────────────────────────────────────────────────────────────────
    connect();
    scrollDown();

})();
