/**
 * Serverless To-Do List — Frontend Application
 * 
 * Communicates with AWS API Gateway → Lambda → DynamoDB.
 * Replace API_ENDPOINT with your deployed API Gateway URL.
 */

// ============================================================
// Configuration
// Auto-detects local dev (same-origin) vs production (API Gateway).
// For deployment: replace the production URL with your API Gateway URL.
// ============================================================
const API_ENDPOINT = window.location.hostname === "localhost"
    ? ""  // Local dev — same origin (local_server.py serves API + frontend)
    : "https://YOUR_API_ID.execute-api.REGION.amazonaws.com/Prod";

// ============================================================
// TodoApp Module (IIFE for encapsulation)
// ============================================================
const TodoApp = (() => {
    // Local state
    let todos = [];
    let currentFilter = "all";

    // DOM references (cached for performance)
    const dom = {
        form: document.getElementById("todo-form"),
        input: document.getElementById("todo-input"),
        list: document.getElementById("todo-list"),
        loading: document.getElementById("loading-state"),
        empty: document.getElementById("empty-state"),
        error: document.getElementById("error-state"),
        errorMsg: document.getElementById("error-message"),
        toastContainer: document.getElementById("toast-container"),
        statTotal: document.getElementById("stat-total"),
        statActive: document.getElementById("stat-active"),
        statCompleted: document.getElementById("stat-completed"),
        progressRing: document.getElementById("progress-ring"),
        progressText: document.getElementById("progress-text"),
        filterBtns: document.querySelectorAll(".filter-btn"),
    };

    // --------------------------------------------------------
    // API Helper — Wraps fetch with error handling
    // --------------------------------------------------------
    async function apiRequest(path, options = {}) {
        const url = `${API_ENDPOINT}${path}`;
        const config = {
            headers: { "Content-Type": "application/json" },
            ...options,
        };

        const response = await fetch(url, config);

        if (!response.ok) {
            const errorBody = await response.text();
            throw new Error(errorBody || `HTTP ${response.status}`);
        }

        return response.json();
    }

    // --------------------------------------------------------
    // CRUD Operations
    // --------------------------------------------------------

    /** Fetch all todos from the API */
    async function loadTodos() {
        showState("loading");
        try {
            const data = await apiRequest("/todos");
            todos = data.todos || data || [];
            // Sort: incomplete first, then by creation date (newest first)
            todos.sort((a, b) => {
                if (a.completed !== b.completed) return a.completed ? 1 : -1;
                return (b.createdAt || 0) - (a.createdAt || 0);
            });
            renderTodos();
            updateStats();
        } catch (err) {
            showState("error", err.message);
        }
    }

    /** Create a new todo */
    async function createTodo(title) {
        try {
            const data = await apiRequest("/todos", {
                method: "POST",
                body: JSON.stringify({ title }),
            });
            const newTodo = data.todo || data;
            todos.unshift(newTodo);
            renderTodos();
            updateStats();
            showToast("Task added!", "success");
        } catch (err) {
            showToast("Failed to add task.", "error");
        }
    }

    /** Toggle the completed status of a todo */
    async function toggleTodo(id, completed) {
        try {
            await apiRequest(`/todos/${id}`, {
                method: "PUT",
                body: JSON.stringify({ completed }),
            });
            const todo = todos.find((t) => t.id === id);
            if (todo) todo.completed = completed;
            // Re-sort after toggling
            todos.sort((a, b) => {
                if (a.completed !== b.completed) return a.completed ? 1 : -1;
                return (b.createdAt || 0) - (a.createdAt || 0);
            });
            renderTodos();
            updateStats();
            showToast(completed ? "Task completed!" : "Task reopened.", "success");
        } catch (err) {
            showToast("Failed to update task.", "error");
        }
    }

    /** Delete a todo */
    async function deleteTodo(id) {
        // Optimistic removal with animation
        const el = document.querySelector(`[data-id="${id}"]`);
        if (el) el.classList.add("removing");

        try {
            await apiRequest(`/todos/${id}`, { method: "DELETE" });
            todos = todos.filter((t) => t.id !== id);
            // Brief delay to allow the animation to play
            setTimeout(() => {
                renderTodos();
                updateStats();
            }, 280);
            showToast("Task deleted.", "success");
        } catch (err) {
            if (el) el.classList.remove("removing");
            showToast("Failed to delete task.", "error");
        }
    }

    // --------------------------------------------------------
    // Rendering
    // --------------------------------------------------------

    /** Render the todo list based on current filter */
    function renderTodos() {
        const filtered = todos.filter((t) => {
            if (currentFilter === "active") return !t.completed;
            if (currentFilter === "completed") return t.completed;
            return true;
        });

        if (todos.length === 0) {
            showState("empty");
            return;
        }

        if (filtered.length === 0) {
            dom.list.innerHTML = "";
            showState("empty");
            return;
        }

        showState("list");

        dom.list.innerHTML = filtered
            .map(
                (todo, i) => `
            <li class="todo-item ${todo.completed ? "completed" : ""}" 
                data-id="${todo.id}" 
                style="animation-delay: ${i * 0.04}s">
                <label class="todo-checkbox">
                    <input type="checkbox" 
                           ${todo.completed ? "checked" : ""} 
                           onchange="TodoApp.toggleTodo('${todo.id}', this.checked)"
                           aria-label="Toggle ${escapeHtml(todo.title)}">
                    <span class="checkmark">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" 
                             stroke="currentColor" stroke-width="3" stroke-linecap="round" 
                             stroke-linejoin="round">
                            <polyline points="20 6 9 17 4 12"/>
                        </svg>
                    </span>
                </label>
                <span class="todo-text">${escapeHtml(todo.title)}</span>
                <span class="todo-timestamp">${formatTime(todo.createdAt)}</span>
                <button class="btn-delete" 
                        onclick="TodoApp.deleteTodo('${todo.id}')" 
                        aria-label="Delete ${escapeHtml(todo.title)}">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" 
                         stroke="currentColor" stroke-width="2" stroke-linecap="round" 
                         stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </li>`
            )
            .join("");
    }

    // --------------------------------------------------------
    // Stats & Progress Ring
    // --------------------------------------------------------

    function updateStats() {
        const total = todos.length;
        const completed = todos.filter((t) => t.completed).length;
        const active = total - completed;
        const pct = total === 0 ? 0 : Math.round((completed / total) * 100);

        // Animate number changes
        animateNumber(dom.statTotal, total);
        animateNumber(dom.statActive, active);
        animateNumber(dom.statCompleted, completed);

        // Update progress ring (circumference = 2 * PI * 16 ≈ 100.53)
        const circumference = 100.53;
        const offset = circumference - (pct / 100) * circumference;
        dom.progressRing.style.strokeDashoffset = offset;
        dom.progressText.textContent = `${pct}%`;
    }

    function animateNumber(el, target) {
        const current = parseInt(el.textContent) || 0;
        if (current === target) return;
        el.textContent = target;
        el.style.transform = "scale(1.3)";
        el.style.color = "var(--accent-secondary)";
        setTimeout(() => {
            el.style.transform = "scale(1)";
            el.style.color = "";
        }, 200);
    }

    // --------------------------------------------------------
    // UI State Management
    // --------------------------------------------------------

    function showState(state, message) {
        dom.loading.classList.add("hidden");
        dom.empty.classList.add("hidden");
        dom.error.classList.add("hidden");
        dom.list.innerHTML = "";

        switch (state) {
            case "loading":
                dom.loading.classList.remove("hidden");
                break;
            case "empty":
                dom.empty.classList.remove("hidden");
                break;
            case "error":
                dom.error.classList.remove("hidden");
                if (message) dom.errorMsg.textContent = message;
                break;
            case "list":
                // List content is rendered separately
                break;
        }
    }

    // --------------------------------------------------------
    // Toast Notifications
    // --------------------------------------------------------

    function showToast(message, type = "success") {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        const icon =
            type === "success"
                ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`
                : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;
        toast.innerHTML = `${icon}<span>${escapeHtml(message)}</span>`;
        dom.toastContainer.appendChild(toast);

        // Auto-dismiss after 3 seconds
        setTimeout(() => {
            toast.classList.add("toast-out");
            toast.addEventListener("animationend", () => toast.remove());
        }, 3000);
    }

    // --------------------------------------------------------
    // Helpers
    // --------------------------------------------------------

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function formatTime(timestamp) {
        if (!timestamp) return "";
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMin = Math.floor(diffMs / 60000);
        const diffHr = Math.floor(diffMs / 3600000);
        const diffDay = Math.floor(diffMs / 86400000);

        if (diffMin < 1) return "just now";
        if (diffMin < 60) return `${diffMin}m ago`;
        if (diffHr < 24) return `${diffHr}h ago`;
        if (diffDay < 7) return `${diffDay}d ago`;
        return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    }

    // --------------------------------------------------------
    // Event Listeners
    // --------------------------------------------------------

    function init() {
        // Form submission — create a new todo
        dom.form.addEventListener("submit", (e) => {
            e.preventDefault();
            const title = dom.input.value.trim();
            if (!title) return;
            createTodo(title);
            dom.input.value = "";
            dom.input.focus();
        });

        // Filter tabs
        dom.filterBtns.forEach((btn) => {
            btn.addEventListener("click", () => {
                dom.filterBtns.forEach((b) => b.classList.remove("active"));
                btn.classList.add("active");
                currentFilter = btn.dataset.filter;
                renderTodos();
            });
        });

        // Initial load
        loadTodos();
    }

    // Boot the app once DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

    // Public API (exposed for inline event handlers)
    return { loadTodos, toggleTodo, deleteTodo };
})();
