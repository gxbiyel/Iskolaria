// Shared helpers: session, API calls, navigation bar and footer.

const session = {
    get token() {
        return localStorage.getItem("sh_token");
    },
    get user() {
        try {
        return JSON.parse(localStorage.getItem("sh_user"));
        } catch (e) {
        return null;
        }
    },
    save(d) {
        localStorage.setItem("sh_token", d.token);
        localStorage.setItem(
        "sh_user",
        JSON.stringify({ role: d.role, full_name: d.full_name }),
        );
    },
    clear() {
        localStorage.removeItem("sh_token");
        localStorage.removeItem("sh_user");
    },
};

// Escape anything that came from the server before putting it in innerHTML
function esc(s) {
    return String(s == null ? "" : s).replace(
        /[&<>"']/g,
        (c) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
            c
        ],
    );
}

const STATUS = {
    submitted: "Submitted",
    under_review: "Under review",
    approved: "Approved",
    rejected: "Rejected",
    waitlisted: "Waitlisted",
    cancelled: "Cancelled",
    removed: "Removed",
};

const badge = (s) =>
    `<span class="badge ${esc(s)}">${esc(STATUS[s] || s)}</span>`;

const day = (s) => String(s || "").slice(0, 10);

const money = (n) => Number(n).toLocaleString("en-PH");

const label = (k) => {
    const t = String(k).replace(/_/g, " ");
    return t.charAt(0).toUpperCase() + t.slice(1);
};

function errText(data, fallback) {
    const d = data && data.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => x.msg).join("; ");
    return fallback;
}

// path is relative to /api, e.g. api('/auth/login', {method:'POST', body:{...}})
async function api(path, { method = "GET", body } = {}) {
    const headers = {};
    if (session.token) headers.Authorization = "Bearer " + session.token;
    const isForm = body instanceof FormData;
    if (body && !isForm) headers["Content-Type"] = "application/json";
    const res = await fetch("/api" + path, {
        method,
        headers,
        body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401 && session.token) {
        // token expired or invalid
        session.clear();
        location.href =
        "login.html?next=" +
        encodeURIComponent(location.pathname.split("/").pop() + location.search);
    }
    if (!res.ok)
        throw Object.assign(
        new Error(errText(data, "Request failed (" + res.status + ")")),
        { status: res.status, data },
        );
    return data;
}

// Returns true if the visitor may stay on this page; otherwise redirects.
function requireLogin(role) {
    const u = session.user;
    if (!session.token || !u) {
        location.href =
        "login.html?next=" +
        encodeURIComponent(location.pathname.split("/").pop() + location.search);
        return false;
    }
    if (role && u.role !== role) {
        location.href = "index.html";
        return false;
    }
    return true;
}

function show(el, text, type) {
    el.className = "msg " + (type || "info");
    el.textContent = text;
    // Bring feedback into view on long pages (e.g. admin board)
    if (el.scrollIntoView)
        el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function showHtml(el, html, type) {
    el.className = "msg " + (type || "info");
    el.innerHTML = html;
    if (el.scrollIntoView)
        el.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// Admin-only: files need the token, so fetch them and open as a blob
async function openFile(id) {
    const res = await fetch("/api/uploads/files/" + id, {
        headers: { Authorization: "Bearer " + session.token },
    });
    if (!res.ok) {
        alert("Could not open this document.");
        return;
    }
    window.open(URL.createObjectURL(await res.blob()), "_blank");
}

const LOGO = `<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="9" fill="#0b3b3a"/><path d="M16 7 4.5 13 16 19l8.5-4.4V21h2v-8L16 7Z" fill="#fff"/><path d="M9 17.2v3.6c0 1.5 3.1 3.2 7 3.2s7-1.7 7-3.2v-3.6L16 21l-7-3.8Z" fill="#f2b134"/></svg>`;

function renderLayout() {
    const u = session.user,
        on = !!(session.token && u);
    const page = location.pathname.split("/").pop() || "index.html";
    const link = (href, text) =>
        `<a href="${href}"${page === href ? ' aria-current="page"' : ""}>${text}</a>`;

    let links = link("index.html", "Scholarships");
    if (on && u.role === "applicant") links += link("my.html", "My applications");
    if (on && u.role === "admin") links += link("admin.html", "Review board");
    if (!on)
        links += link("login.html", "Log in") + link("register.html", "Register");

    const user = on
        ? `<span class="who"><span class="avatar" aria-hidden="true">${esc((u.full_name || "?").trim().charAt(0).toUpperCase())}</span>${esc(u.full_name)}</span>
            <button class="linklike" id="logout">Log out</button>`
        : "";

    document.getElementById("nav").innerHTML =
        `<div class="in"><a class="brand" href="index.html">${LOGO}Iskolaria</a>
            <nav class="links" aria-label="Main">${links}</nav>${user}</div>`;

    const lo = document.getElementById("logout");
    if (lo)
        lo.onclick = () => {
        session.clear();
        location.href = "login.html";
        };

    document.getElementById("footer").innerHTML =
        `Iskolaria · build <strong>${esc(window.BUILD_NUMBER || "dev")}</strong>`;
}

document.addEventListener("DOMContentLoaded", renderLayout);
