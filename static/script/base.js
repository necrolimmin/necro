(function(){
  // ---------------------------
  // Theme icons
  // ---------------------------
  const ICON_SUN = `
    <svg class="icon" viewBox="0 0 24 24" fill="none">
      <path d="M12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12Z" stroke="currentColor" stroke-width="2"/>
      <path d="M12 2v2M12 20v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M2 12h2M20 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"
            stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>`;
  const ICON_MOON = `
    <svg class="icon" viewBox="0 0 24 24" fill="none">
      <path d="M21 14.5A8.5 8.5 0 0 1 9.5 3a7 7 0 1 0 11.5 11.5Z"
            stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
    </svg>`;

  const html = document.documentElement;

  // IMPORTANT: keys (do not change if pages use them)
  const THEME_KEY = "theme";
  const LANG_KEY  = "lang";

  // ---------------------------
  // Theme
  // ---------------------------
  const themeBtn = document.getElementById('themeBtn');
  const themeIconHolder = document.getElementById('themeIconHolder');

  function renderThemeIcon(currentTheme){
    // show NEXT theme icon (better UX)
    if (!themeIconHolder) return;
    themeIconHolder.innerHTML = (currentTheme === 'dark') ? ICON_SUN : ICON_MOON;
  }

  function applyTheme(theme){
    const t = (theme === 'dark') ? 'dark' : 'light';
    html.setAttribute('data-theme', t);
    localStorage.setItem(THEME_KEY, t);
    renderThemeIcon(t);
  }

  // default MUST be light
  const savedTheme = localStorage.getItem(THEME_KEY);
  applyTheme(savedTheme ? savedTheme : 'light');

  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const cur = (html.getAttribute('data-theme') === 'dark') ? 'dark' : 'light';
      applyTheme(cur === 'dark' ? 'light' : 'dark');
    });
  }

  // ---------------------------
  // Language (RU <-> UZ)
  // ---------------------------
  const langBtn = document.getElementById('langBtn');

  const dict = {
    ru: {
      brand:  "\"O‘ztemiryo‘lkonteyner\" AJ",
      subtitle: "Платформа контейнерных операций",
      menu: "Меню",
      dash: "Dashboard",
      r1: "Отчёт 1",
      r2: "Отчёт 2",
      q: "Квартальный",
      branches: "Филиалы",
      admin: "Админ",
      user: "Фылиыл",
      account: "Аккаунт",
      logout: "Выйти"
    },
    uz: {
      brand: "\"O‘ztemiryo‘lkonteyner\" AJ",
      subtitle: "Konteyner operatsiyalar platformasi",
      menu: "Menyu",
      dash: "Dashboard",
      r1: "Hisobot 1",
      r2: "Hisobot 2",
      q: "Kvartalniy",
      branches: "Filiallar",
      admin: "ADMIN",
      user: "filiali",
      account: "Hisob",
      logout: "Chiqish"
    }
  };

  function applyLang(lang){
    const l = (lang === 'uz') ? 'uz' : 'ru';
    html.setAttribute('data-lang', l);
    localStorage.setItem(LANG_KEY, l);

    const t = dict[l] || dict.ru;
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (t[key] !== undefined) el.textContent = t[key];
    });

    if (langBtn) {
      try{
        langBtn.animate(
          [{transform:'translateY(0)'},{transform:'translateY(-2px)'},{transform:'translateY(0)'}],
          {duration:220, easing:'ease-out'}
        );
      }catch(e){}
    }
  }

  applyLang(localStorage.getItem(LANG_KEY) || 'uz');

  if (langBtn) {
    langBtn.addEventListener('click', () => {
      const current = html.getAttribute('data-lang') || 'ru';
      applyLang(current === 'ru' ? 'uz' : 'ru');
    });
  }

  // ---------------------------
  // Admin dropdown
  // ---------------------------
  const adminToggle = document.getElementById('adminToggle');
  const adminMenu = document.getElementById('adminMenu');

  function closeAdminMenu(){
    if (adminMenu) adminMenu.classList.remove('open');
  }

  if (adminToggle && adminMenu) {
    adminToggle.addEventListener('click', () => {
      adminMenu.classList.toggle('open');
    });

    adminToggle.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') adminMenu.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
      if (!adminMenu.contains(e.target) && !adminToggle.contains(e.target)) {
        closeAdminMenu();
      }
    });
  }

  // ---------------------------
  // Active nav highlight
  // ---------------------------
  const path = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(a => {
    if (a.getAttribute('href') === path) a.classList.add('active');
  });

  // ---------------------------
  // Mobile nav toggle
  // ---------------------------
  const navToggle = document.getElementById('navToggle');
  const centerNav = document.getElementById('centerNav');

  if (navToggle && centerNav) {
    navToggle.addEventListener('click', () => {
      centerNav.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
      if (!centerNav.contains(e.target) && !navToggle.contains(e.target)) {
        centerNav.classList.remove('open');
      }
    });
  }
})();





/* ============================================================
   BASE.JS — Notifications Bell (Admin -> All stations)
   - Green glow 16:00-19:00 if no unread (soft reminder)
   - New message: glow + dot + sound
   - Unread persists until user opens/acks
   - Backend APIs:
       GET  /api/notifications/latest/
       POST /api/notifications/ack/
       POST /api/notifications/send/   (admin only)
   ============================================================ */
(function () {
  "use strict";

  // ---------------------------
  // Config
  // ---------------------------
  const API_LATEST = "/api/notifications/latest/";
  const API_ACK = "/api/notifications/ack/";
  const API_SEND = "/api/notifications/send/";

  // LocalStorage keys
  const LS_IN = "notif:last_incoming_id"; // latest incoming notification id we know
  const LS_RD = "notif:last_read_id";     // last read/acked notification id
  const LS_TX = "notif:last_text";        // last message text cache

  // Polling
  const POLL_MS = 15000; // 15s

  // Reminder window (local time)
  const REM_H1 = 16;
  const REM_H2 = 19; // up to 19:00

  // ---------------------------
  // Helpers
  // ---------------------------
  function $(sel, root = document) {
    return root.querySelector(sel);
  }

  function getCSRF() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  }

  function isAdmin() {
    // Siz xohlasangiz buni serverdan data-attr bilan ham berasiz.
    // Hozircha: topbarda ADMIN yozuvi bo‘lsa admin deb olamiz.
    const t = document.body.innerText || "";
    return t.includes("ADMIN");
  }

  function nowInReminderWindow() {
    const d = new Date();
    const h = d.getHours();
    // 16:00 <= time < 19:00
    return h >= REM_H1 && h < REM_H2;
  }

  function toInt(x, fallback = 0) {
    const n = Number(x);
    return Number.isFinite(n) ? n : fallback;
  }

  function lastIncomingId() {
    return toInt(localStorage.getItem(LS_IN), 0);
  }

  function lastReadId() {
    return toInt(localStorage.getItem(LS_RD), 0);
  }

  function isUnread() {
    return lastIncomingId() > lastReadId();
  }

  // ---------------------------
  // UI Inject (Bell + Modal)
  // ---------------------------
  // Sizda bell button HTML oldin qo‘yilgan bo‘lishi mumkin.
  // Agar yo‘q bo‘lsa, JS avtomatik yaratib beradi.
  function ensureBellUI() {
    const tools = document.querySelector(".right-tools");
    if (!tools) return null;

    let bell = $("#notifBell");
    if (!bell) {
      bell = document.createElement("button");
      bell.type = "button";
      bell.id = "notifBell";
      bell.className = "icon-btn notif-bell";
      bell.title = "Habarnoma";

      bell.innerHTML = `
        <span class="notif-dot" id="notifDot" aria-hidden="true"></span>
        <svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Z" stroke="currentColor" stroke-width="2"/>
          <path d="M18 16v-5a6 6 0 1 0-12 0v5l-2 2h16l-2-2Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        </svg>
      `;
      // O'ng tool'lar ichida lang/theme yoniga qo‘shiladi (oxiridan oldin)
      tools.insertBefore(bell, tools.firstChild);
    }

    // Modal (shared)
    let modal = $("#notifModal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "notifModal";
      modal.className = "notif-modal";
      modal.setAttribute("aria-hidden", "true");
      modal.innerHTML = `
        <div class="notif-backdrop" data-close="1"></div>
        <div class="notif-panel" role="dialog" aria-modal="true" aria-labelledby="notifTitle">
          <div class="notif-head">
            <div class="notif-avatar" aria-hidden="true">🤖</div>
            <div class="notif-headtxt">
              <div class="notif-title" id="notifTitle">Habarnoma</div>
              <div class="notif-sub">Hisobotlarni vaqtida topshiring</div>
            </div>
            <button class="notif-x" type="button" data-close="1" aria-label="Close">✕</button>
          </div>

          <div class="notif-body">
            <div class="notif-msg" id="notifMsg">Hozircha xabar yo‘q.</div>

            <div class="notif-adminbox" id="notifAdminBox" style="display:none;">
              <label class="notif-label" for="notifInput">Admin xabari</label>
              <textarea id="notifInput" class="notif-input" rows="3" placeholder="Masalan: Hisobot 1 ni 18:00 gacha topshiring..."></textarea>
              <div class="notif-actions">
                <button type="button" class="notif-btn ghost" id="notifCancel">Bekor</button>
                <button type="button" class="notif-btn primary" id="notifSend">Yuborish</button>
              </div>
            </div>

            <div class="notif-actions" id="notifUserActions">
              <button type="button" class="notif-btn primary" id="notifAck">Tushunarli</button>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
    }

    // Minimal CSS (agar siz base.css ga qo‘shmagan bo‘lsangiz ham ishlasin)
    // Xohlasangiz keyin buni base.css ga ko‘chirasiz.
    if (!$("#notifStyle")) {
      const st = document.createElement("style");
      st.id = "notifStyle";
      st.textContent = `
        .notif-bell{ position:relative; }
        .notif-dot{
          position:absolute; top:9px; right:10px;
          width:9px; height:9px; border-radius:99px;
          background:#22c55e; box-shadow:0 0 0 6px rgba(34,197,94,.18);
          opacity:0; transform:scale(.85);
          transition:opacity .18s ease, transform .18s ease;
          pointer-events:none;
        }
        .notif-bell.is-unread .notif-dot{
          opacity:1; transform:scale(1);
          animation: notifPulse 1.2s ease-in-out infinite;
        }
        @keyframes notifPulse{
          0%,100%{ box-shadow:0 0 0 6px rgba(34,197,94,.16); }
          50%{ box-shadow:0 0 0 10px rgba(34,197,94,.10); }
        }
        .notif-bell.glow{
          box-shadow: 0 0 0 4px rgba(34,197,94,.14), 0 18px 48px rgba(15,23,42,.12);
        }
        .notif-bell.glow::after{
          content:"";
          position:absolute; inset:-10px;
          border-radius:18px;
          background: radial-gradient(circle at 30% 30%, rgba(34,197,94,.22), transparent 55%);
          filter: blur(6px);
          opacity:.9;
          pointer-events:none;
        }

        .notif-modal{ position:fixed; inset:0; display:none; z-index:999; }
        .notif-modal.open{ display:block; }
        .notif-backdrop{ position:absolute; inset:0; background:rgba(2,6,23,.45); backdrop-filter: blur(6px); }
        .notif-panel{
          position:absolute; top:80px; right:18px;
          width:min(420px, calc(100% - 36px));
          border-radius:18px;
          background: rgba(255,255,255,.92);
          border:1px solid rgba(15,23,42,.10);
          box-shadow: 0 30px 110px rgba(0,0,0,.22);
          overflow:hidden;
        }
        html[data-theme="dark"] .notif-panel{
          background: rgba(11,18,34,.92);
          border:1px solid rgba(255,255,255,.14);
        }
        .notif-head{ display:flex; align-items:center; gap:12px; padding:14px; border-bottom:1px solid rgba(15,23,42,.08); }
        html[data-theme="dark"] .notif-head{ border-bottom:1px solid rgba(255,255,255,.10); }
        .notif-avatar{
          width:42px; height:42px; border-radius:14px;
          display:flex; align-items:center; justify-content:center;
          background: linear-gradient(135deg, rgba(34,197,94,.18), rgba(79,70,229,.14));
          border:1px solid rgba(15,23,42,.08);
          font-size:20px;
        }
        .notif-title{ font-weight:900; font-size:14px; color:var(--text, #0f172a); }
        .notif-sub{ font-size:12px; color:var(--muted, #475569); margin-top:2px; }
        .notif-x{
          margin-left:auto;
          width:34px; height:34px; border-radius:12px;
          border:1px solid rgba(15,23,42,.10);
          background: rgba(255,255,255,.60);
          cursor:pointer;
        }
        html[data-theme="dark"] .notif-x{ background: rgba(255,255,255,.06); border-color: rgba(255,255,255,.14); color: var(--text,#e5e7eb); }

        .notif-body{ padding:14px; }
        .notif-msg{
          font-size:13px; line-height:1.45;
          color: var(--text, #0f172a);
          background: rgba(34,197,94,.08);
          border:1px solid rgba(34,197,94,.18);
          padding:12px 12px;
          border-radius:14px;
          white-space: pre-wrap;
        }
        html[data-theme="dark"] .notif-msg{
          background: rgba(34,197,94,.10);
          border-color: rgba(34,197,94,.20);
        }

        .notif-label{ display:block; margin:12px 0 6px; font-size:12px; font-weight:800; color:var(--muted,#475569); }
        .notif-input{
          width:100%;
          border-radius:14px;
          border:1px solid rgba(15,23,42,.12);
          background: rgba(255,255,255,.65);
          padding:10px 12px;
          outline:none;
          font-size:13px;
          color: var(--text,#0f172a);
          resize: vertical;
          min-height:84px;
        }
        html[data-theme="dark"] .notif-input{
          background: rgba(255,255,255,.06);
          border-color: rgba(255,255,255,.14);
          color: var(--text,#e5e7eb);
        }
        .notif-actions{ display:flex; gap:10px; justify-content:flex-end; margin-top:12px; }
        .notif-btn{
          height:38px; padding:0 14px;
          border-radius:999px;
          border:1px solid rgba(15,23,42,.12);
          background: rgba(255,255,255,.65);
          cursor:pointer;
          font-weight:850;
          font-size:13px;
        }
        html[data-theme="dark"] .notif-btn{ background: rgba(255,255,255,.06); border-color: rgba(255,255,255,.14); color: var(--text,#e5e7eb); }
        .notif-btn.primary{
          border-color: rgba(34,197,94,.25);
          background: linear-gradient(135deg, rgba(34,197,94,.18), rgba(79,70,229,.14));
        }
        .notif-btn.ghost{ opacity:.85; }
      `;
      document.head.appendChild(st);
    }

    return { bell, modal };
  }

  // ---------------------------
  // Modal control
  // ---------------------------
  function openModal() {
    const modal = $("#notifModal");
    if (!modal) return;
    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
  }

  function closeModal() {
    const modal = $("#notifModal");
    if (!modal) return;
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
  }

  function setMessageText(txt) {
    const el = $("#notifMsg");
    if (el) el.textContent = (txt && txt.trim()) ? txt.trim() : "Hozircha xabar yo‘q.";
  }

  // ---------------------------
  // Sound (beep)
  // ---------------------------
  function playBeep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = "sine";
      o.frequency.value = 880;
      g.gain.value = 0.08;
      o.connect(g);
      g.connect(ctx.destination);
      o.start();
      setTimeout(() => {
        o.stop();
        ctx.close();
      }, 160);
    } catch (e) {
      // ignore
    }
  }

  // ---------------------------
  // Bell visual states
  // ---------------------------
  function setUnreadUI(on) {
    const bell = $("#notifBell");
    if (!bell) return;
    bell.classList.toggle("is-unread", !!on);
  }

  function setGlow(on) {
    const bell = $("#notifBell");
    if (!bell) return;
    bell.classList.toggle("glow", !!on);
  }

  // ---------------------------
  // Backend fetchers
  // ---------------------------
  async function fetchLatest() {
    try {
      const res = await fetch(API_LATEST, { method: "GET" });
      const data = await res.json();
      if (!data || !data.ok) return;

      const n = data.notification;
      if (!n) return;

      const incomingId = toInt(n.id, 0);
      if (!incomingId) return;

      // Store latest
      const prevIn = lastIncomingId();
      if (incomingId > prevIn) {
        localStorage.setItem(LS_IN, String(incomingId));
        localStorage.setItem(LS_TX, String(n.message || ""));
      }

      // If server says unread=false, sync read marker to this id (optional)
      // Lekin talab: "o‘qimaguncha glow o‘chmasin" — demak faqat ack qilganda RD yozamiz.
      // Shuning uchun bu yerda RD ni majburan ko‘tarmaymiz.
    } catch (e) {}
  }

  async function sendNotification(text) {
    const msg = (text || "").trim();
    if (!msg) return { ok: false, detail: "empty" };

    const res = await fetch(API_SEND, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      body: JSON.stringify({ message: msg }),
    });

    const data = await res.json().catch(() => ({}));
    return data || { ok: false };
  }

  async function ackNotification(id) {
    const res = await fetch(API_ACK, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCSRF(),
      },
      body: JSON.stringify({ id }),
    });
    return await res.json().catch(() => ({}));
  }

  // ---------------------------
  // Core tick loop
  // ---------------------------
  let prevUnread = false;

  async function tick() {
    await fetchLatest();

    const unread = isUnread();
    setUnreadUI(unread);

    // Soft reminder glow in 16-19 only when no unread
    if (!unread) {
      setGlow(nowInReminderWindow());
    } else {
      // Unread => always glow
      setGlow(true);
    }

    // New arrived (transition false->true)
    if (unread && !prevUnread) {
      playBeep();
    }
    prevUnread = unread;
  }

  // ---------------------------
  // Wire events
  // ---------------------------
  function wireEvents() {
    const bell = $("#notifBell");
    const modal = $("#notifModal");
    if (!bell || !modal) return;

    bell.addEventListener("click", () => {
      // show current message
      setMessageText(localStorage.getItem(LS_TX) || "");
      openModal();

      // admin?
      const adminBox = $("#notifAdminBox");
      const userActions = $("#notifUserActions");
      if (adminBox && userActions) {
        if (isAdmin()) {
          adminBox.style.display = "block";
          userActions.style.display = "none";
        } else {
          adminBox.style.display = "none";
          userActions.style.display = "flex";
        }
      }
    });

    modal.addEventListener("click", (e) => {
      const t = e.target;
      if (t && t.getAttribute && t.getAttribute("data-close") === "1") {
        closeModal();
      }
    });

    // User ACK
    const ackBtn = $("#notifAck");
    if (ackBtn) {
      ackBtn.addEventListener("click", async () => {
        const id = lastIncomingId();
        // local mark read
        localStorage.setItem(LS_RD, String(id));
        setUnreadUI(false);

        // backend ack
        try { await ackNotification(id); } catch (e) {}

        // glow off unless in reminder window
        setGlow(nowInReminderWindow());
        closeModal();
      });
    }

    // Admin send
    const sendBtn = $("#notifSend");
    const cancelBtn = $("#notifCancel");
    const input = $("#notifInput");

    if (cancelBtn) cancelBtn.addEventListener("click", () => closeModal());

    if (sendBtn) {
      sendBtn.addEventListener("click", async () => {
        const text = input ? input.value : "";
        sendBtn.disabled = true;
        try {
          const data = await sendNotification(text);
          if (data && data.ok) {
            const id = toInt(data.notification?.id, Date.now());
            localStorage.setItem(LS_IN, String(id));
            localStorage.setItem(LS_TX, String(text || ""));
            localStorage.setItem(LS_RD, String(id)); // admin uchun unread bo‘lmasin

            if (input) input.value = "";
            closeModal();
            await tick(); // refresh state
          }
        } finally {
          sendBtn.disabled = false;
        }
      });
    }

    // Cross-tab sync
    window.addEventListener("storage", (e) => {
      if ([LS_IN, LS_RD, LS_TX].includes(e.key)) {
        tick();
      }
    });
  }

  // ---------------------------
  // Boot
  // ---------------------------
  const ui = ensureBellUI();
  if (!ui) return;

  wireEvents();
  tick();
  setInterval(tick, POLL_MS);
})();


