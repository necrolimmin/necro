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
      subtitle: "Платформа E-stat",
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
      subtitle: "E-stat platformasi",
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

  const API_LATEST = "/api/notifications/latest/";
  const API_ACK = "/api/notifications/ack/";
  const API_SEND = "/api/notifications/send/";

  const LS_IN = "notif:last_incoming_id";
  const LS_RD = "notif:last_read_id";
  const LS_TX = "notif:last_text";
  const LS_TM = "notif:last_time";
  const LS_AV = "notif:last_avatar";
  const LS_BY = "notif:last_sender";
  const LS_TOAST = "notif:last_admin_toast";

  // session only
  const SS_USER_SOUND_SEEN = "notif:user_sound_seen_id";
  const SS_ADMIN_READ_SEEN = "notif:admin_read_seen_marker";
  const SS_ADMIN_READ_ALERT = "notif:admin_read_alert_open";

  const POLL_MS = 12000;
  const REM_H1 = 16;
  const REM_H2 = 19;

  function $(sel, root = document) {
    return root.querySelector(sel);
  }

  function getCSRF() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  }

  function isAdmin() {
    const pill = document.querySelector(".admin-text b");
    if (!pill) return false;
    return (pill.textContent || "").trim().toUpperCase() === "ADMIN";
  }

  function nowInReminderWindow() {
    const d = new Date();
    const h = d.getHours();
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

  function getUserSoundSeenId() {
    return toInt(sessionStorage.getItem(SS_USER_SOUND_SEEN), 0);
  }

  function setUserSoundSeenId(id) {
    sessionStorage.setItem(SS_USER_SOUND_SEEN, String(toInt(id, 0)));
  }

  function getAdminReadSeenMarker() {
    return sessionStorage.getItem(SS_ADMIN_READ_SEEN) || "";
  }

  function setAdminReadSeenMarker(marker) {
    sessionStorage.setItem(SS_ADMIN_READ_SEEN, marker || "");
  }

  function isAdminReadAlertOn() {
    return sessionStorage.getItem(SS_ADMIN_READ_ALERT) === "1";
  }

  function setAdminReadAlert(on) {
    sessionStorage.setItem(SS_ADMIN_READ_ALERT, on ? "1" : "0");
  }

  function escapeHtml(s) {
    return String(s || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatMessageHtml(message, sender, timeText, avatarUrl) {
    return `
      <div class="notif-cardmsg">
        <div class="notif-msgside">
          <img class="notif-msgavatar" src="${avatarUrl || '/static/images/admin-bot.png'}" alt="admin avatar">
        </div>
        <div class="notif-msgmain">
          <div class="notif-msgsender">${escapeHtml(sender || "Admin")}</div>
          <div class="notif-msgtext">${escapeHtml(message || "Hozircha xabar yo‘q.")}</div>
          <div class="notif-msgtime">${escapeHtml(timeText || "")}</div>
        </div>
      </div>
    `;
  }

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
          <path d="M18 16v-5a6 6 0 1 0-12 0v5l-2 2h16l-2-2Z" stroke="currentColor" stroke-width="2"/>
        </svg>
      `;
      tools.insertBefore(bell, tools.firstChild);
    }

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
            <div class="notif-headleft">
              <div class="notif-title" id="notifTitle">Habarnoma</div>
              <div class="notif-sub">Hisobotlarni vaqtida topshiring</div>
            </div>
            <button class="notif-x" type="button" data-close="1" aria-label="Close">✕</button>
          </div>

          <div class="notif-body">
            <div class="notif-msg" id="notifMsg"></div>

            <div class="notif-adminbox" id="notifAdminBox" style="display:none;">
              <label class="notif-label" for="notifInput">Admin xabari</label>
              <textarea id="notifInput" class="notif-input" rows="4" placeholder="Masalan: Hisobotlarni 18:00 gacha topshiring..."></textarea>
              <div class="notif-actions">
                <button type="button" class="notif-btn ghost" id="notifCancel">Bekor</button>
                <button type="button" class="notif-btn primary" id="notifSend">Yuborish</button>
              </div>
              <div id="notifReadLog" class="notif-readlog"></div>
            </div>

            <div class="notif-actions" id="notifUserActions">
              <button type="button" class="notif-btn primary" id="notifAck">Tushunarli</button>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
    }

    let toast = $("#notifToast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "notifToast";
      toast.className = "notif-toast";
      document.body.appendChild(toast);
    }

    if (!$("#notifStyle")) {
      const st = document.createElement("style");
      st.id = "notifStyle";
      st.textContent = `
        .notif-bell{ position:relative; }
        .notif-dot{
          position:absolute; top:9px; right:10px;
          width:10px; height:10px; border-radius:999px;
          background:#22c55e;
          opacity:0; transform:scale(.85);
          transition:opacity .2s ease, transform .2s ease;
        }
        .notif-bell.is-unread .notif-dot{
          opacity:1; transform:scale(1);
          animation:notifPulse 1.2s ease-in-out infinite;
        }
        @keyframes notifPulse{
          0%{ box-shadow:0 0 0 0 rgba(34,197,94,.55); }
          70%{ box-shadow:0 0 0 14px rgba(34,197,94,0); }
          100%{ box-shadow:0 0 0 0 rgba(34,197,94,0); }
        }
        .notif-bell.glow{
          box-shadow: 0 0 0 4px rgba(34,197,94,.14), 0 0 24px rgba(34,197,94,.22), 0 18px 48px rgba(15,23,42,.12);
        }

        .notif-modal{ position:fixed; inset:0; display:none; z-index:9999; }
        .notif-modal.open{ display:block; }
        .notif-backdrop{ position:absolute; inset:0; background:rgba(2,6,23,.42); backdrop-filter:blur(6px); }
        .notif-panel{
          position:absolute; top:84px; right:18px;
          width:min(460px, calc(100% - 36px));
          border-radius:20px;
          overflow:hidden;
          background:rgba(255,255,255,.96);
          border:1px solid rgba(15,23,42,.10);
          box-shadow:0 28px 80px rgba(0,0,0,.20);
        }
        html[data-theme="dark"] .notif-panel{
          background:rgba(11,18,34,.96);
          border-color:rgba(255,255,255,.12);
        }

        .notif-head{
          display:flex; align-items:flex-start; justify-content:space-between;
          gap:12px; padding:14px 16px; border-bottom:1px solid rgba(15,23,42,.08);
        }
        html[data-theme="dark"] .notif-head{ border-bottom:1px solid rgba(255,255,255,.10); }

        .notif-title{ font-weight:900; font-size:16px; color:var(--text,#0f172a); }
        .notif-sub{ font-size:12px; color:var(--muted,#64748b); margin-top:4px; }

        .notif-x{
          width:36px; height:36px; border-radius:12px;
          border:1px solid rgba(15,23,42,.12);
          background:rgba(255,255,255,.75); cursor:pointer;
        }

        .notif-body{ padding:14px 16px 16px; }

        .notif-cardmsg{
          display:flex; gap:12px; align-items:flex-start;
          border:1px solid rgba(34,197,94,.18);
          background:rgba(34,197,94,.07);
          border-radius:16px; padding:12px;
        }
        .notif-msgavatar{
          width:48px; height:48px; border-radius:14px; object-fit:cover;
          border:1px solid rgba(15,23,42,.08);
          background:#fff;
          flex:0 0 48px;
        }
        .notif-msgmain{ min-width:0; flex:1; }
        .notif-msgsender{
          font-size:12px; font-weight:800; color:#22c55e; margin-bottom:4px;
        }
        .notif-msgtext{
          font-size:14px; line-height:1.45; color:var(--text,#0f172a); white-space:pre-wrap;
        }
        .notif-msgtime{
          margin-top:8px; font-size:11px; color:var(--muted,#64748b); font-weight:700;
        }

        .notif-label{ display:block; margin:14px 0 6px; font-size:12px; font-weight:800; color:var(--muted,#64748b); }
        .notif-input{
          width:100%; min-height:96px; resize:vertical;
          border-radius:14px; border:1px solid rgba(15,23,42,.12);
          background:rgba(255,255,255,.72); color:var(--text,#0f172a);
          padding:12px; outline:none; font-size:13px;
        }
        html[data-theme="dark"] .notif-input{
          background:rgba(255,255,255,.06);
          border-color:rgba(255,255,255,.12);
          color:var(--text,#e5e7eb);
        }

        .notif-actions{ display:flex; gap:10px; justify-content:flex-end; margin-top:12px; }
        .notif-btn{
          height:40px; padding:0 16px; border-radius:999px;
          border:1px solid rgba(15,23,42,.12);
          background:rgba(255,255,255,.72);
          font-size:13px; font-weight:850; cursor:pointer;
        }
        .notif-btn.primary{
          background:linear-gradient(135deg, rgba(34,197,94,.18), rgba(79,70,229,.12));
        }

        .notif-readlog{
          margin-top:14px;
          border-top:1px dashed rgba(15,23,42,.12);
          padding-top:12px;
          font-size:12px;
          color:var(--muted,#64748b);
          max-height:180px;
          overflow:auto;
        }
        .notif-readitem{
          padding:7px 0;
          border-bottom:1px solid rgba(15,23,42,.06);
        }
        .notif-readitem:last-child{ border-bottom:0; }

        .notif-toast{
          position:fixed;
          right:18px;
          bottom:18px;
          z-index:10000;
          min-width:260px;
          max-width:420px;
          padding:14px 16px;
          border-radius:16px;
          background:linear-gradient(135deg, rgba(34,197,94,.96), rgba(22,163,74,.96));
          color:#fff;
          font-weight:800;
          box-shadow:0 18px 48px rgba(34,197,94,.28);
          opacity:0;
          pointer-events:none;
          transform:translateY(12px);
          transition:all .25s ease;
        }
        .notif-toast.show{
          opacity:1;
          transform:translateY(0);
        }
      `;
      document.head.appendChild(st);
    }

    return { bell, modal };
  }

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

  function setMessageCard(message, sender, timeText, avatarUrl) {
    const el = $("#notifMsg");
    if (!el) return;
    el.innerHTML = formatMessageHtml(message, sender, timeText, avatarUrl);
  }

  function setReadLog(items) {
    const el = $("#notifReadLog");
    if (!el) return;
    if (!items || !items.length) {
      el.innerHTML = `<div class="notif-readitem">Hozircha hech kim o‘qimagan.</div>`;
      return;
    }
    el.innerHTML = items.map(x => `
      <div class="notif-readitem">
        <b>${escapeHtml(x.user_name)}</b> habarni o‘qidi —
        <span>${escapeHtml(x.read_at)}</span>
      </div>
    `).join("");
  }

  function showToast(text) {
    const el = $("#notifToast");
    if (!el) return;
    el.textContent = text || "";
    el.classList.add("show");
    setTimeout(() => {
      el.classList.remove("show");
    }, 5000);
  }

  async function playSound(type = "message") {
    try {
      const audio = new Audio(
        type === "read"
          ? "/static/sounds/read.mp3"
          : "/static/sounds/notify.mp3"
      );
      audio.volume = 0.9;
      await audio.play();
    } catch (e) {
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.type = type === "read" ? "triangle" : "sine";
        o.frequency.value = type === "read" ? 720 : 920;
        g.gain.value = 0.08;
        o.connect(g);
        g.connect(ctx.destination);
        o.start();
        setTimeout(() => {
          o.stop();
          ctx.close();
        }, 220);
      } catch (_) {}
    }
  }

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

  function refreshBellVisual() {
    const unread = isUnread();

    // user unread -> dot + glow
    if (!isAdmin()) {
      setUnreadUI(unread);
      if (unread) {
        setGlow(true);
      } else {
        setGlow(nowInReminderWindow());
      }
      return;
    }

    // admin taraf
    const adminReadAlert = isAdminReadAlertOn();
    setUnreadUI(adminReadAlert);
    setGlow(adminReadAlert);
  }

  async function fetchLatest() {
    try {
      const res = await fetch(API_LATEST, {
        method: "GET",
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" }
      });

      if (!res.ok) return null;
      const data = await res.json();
      if (!data || !data.ok) return null;
      return data;
    } catch (e) {
      return null;
    }
  }

  async function sendNotification(text) {
    const msg = (text || "").trim();
    if (!msg) return { ok: false, detail: "empty" };

    try {
      const res = await fetch(API_SEND, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRF(),
          "X-Requested-With": "XMLHttpRequest"
        },
        body: JSON.stringify({ message: msg }),
      });

      return await res.json();
    } catch (e) {
      return { ok: false, detail: "network_error" };
    }
  }

  async function ackNotification(id) {
    try {
      const res = await fetch(API_ACK, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRF(),
          "X-Requested-With": "XMLHttpRequest"
        },
        body: JSON.stringify({ id }),
      });

      return await res.json();
    } catch (e) {
      return { ok: false, detail: "network_error" };
    }
  }

  let prevReadLogHash = "";

  async function tick() {
    const data = await fetchLatest();
    if (!data) return;

    const n = data.notification;

    if (!n) {
      refreshBellVisual();
      return;
    }

    const incomingId = toInt(n.id, 0);
    const prevIn = lastIncomingId();

    if (incomingId >= prevIn) {
      localStorage.setItem(LS_IN, String(incomingId));
      localStorage.setItem(LS_TX, String(n.message || ""));
      localStorage.setItem(LS_TM, String(n.created_at || ""));
      localStorage.setItem(LS_AV, String(n.avatar_url || ""));
      localStorage.setItem(LS_BY, String(n.created_by_name || "Admin"));
    }

    setMessageCard(
      localStorage.getItem(LS_TX) || "",
      localStorage.getItem(LS_BY) || "Admin",
      localStorage.getItem(LS_TM) || "",
      localStorage.getItem(LS_AV) || "/static/images/admin-bot.png"
    );

    if (isAdmin()) {
      const readEvents = Array.isArray(data.read_events) ? data.read_events : [];
      setReadLog(readEvents);

      const hash = JSON.stringify(readEvents);
      if (hash !== prevReadLogHash && readEvents.length) {
        const latestRead = readEvents[0];
        const marker = `${latestRead.user_id}_${latestRead.read_at}`;
        const seenMarker = getAdminReadSeenMarker();

        if (marker !== seenMarker) {
          setAdminReadAlert(true);
          showToast(`${latestRead.user_name} habarni o‘qidi`);
          await playSound("read");
        }
      }
      prevReadLogHash = hash;
    } else {
      // USER taraf: unread bo‘lsa va bu sessionda hali shu habar uchun signal chalinmagan bo‘lsa -> play
      const seenSoundId = getUserSoundSeenId();
      if (isUnread() && incomingId > seenSoundId) {
        setUserSoundSeenId(incomingId);
        await playSound("message");
      }
    }

    refreshBellVisual();
  }

  function wireEvents() {
    const bell = $("#notifBell");
    const modal = $("#notifModal");
    if (!bell || !modal) return;

    bell.addEventListener("click", () => {
      setMessageCard(
        localStorage.getItem(LS_TX) || "",
        localStorage.getItem(LS_BY) || "Admin",
        localStorage.getItem(LS_TM) || "",
        localStorage.getItem(LS_AV) || "/static/images/admin-bot.png"
      );

      const adminBox = $("#notifAdminBox");
      const userActions = $("#notifUserActions");

      if (isAdmin()) {
        if (adminBox) adminBox.style.display = "block";
        if (userActions) userActions.style.display = "none";
      } else {
        if (adminBox) adminBox.style.display = "none";
        if (userActions) userActions.style.display = "flex";
      }

      openModal();
    });

    modal.addEventListener("click", (e) => {
      const t = e.target;
      if (t && t.getAttribute && t.getAttribute("data-close") === "1") {
        if (isAdmin()) {
          const currentHash = prevReadLogHash ? JSON.parse(prevReadLogHash) : [];
          if (currentHash.length) {
            const latestRead = currentHash[0];
            const marker = `${latestRead.user_id}_${latestRead.read_at}`;
            setAdminReadSeenMarker(marker);
          }
          setAdminReadAlert(false);
          refreshBellVisual();
        }
        closeModal();
      }
    });

    const ackBtn = $("#notifAck");
    if (ackBtn) {
      ackBtn.addEventListener("click", async () => {
        const id = lastIncomingId();
        if (!id) return;

        const res = await ackNotification(id);
        if (res && res.ok) {
          localStorage.setItem(LS_RD, String(id));
          refreshBellVisual();
          closeModal();
        }
      });
    }

    const sendBtn = $("#notifSend");
    const cancelBtn = $("#notifCancel");
    const input = $("#notifInput");

    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => {
        if (isAdmin()) {
          const readEventsEl = $("#notifReadLog");
          if (readEventsEl && prevReadLogHash) {
            const arr = JSON.parse(prevReadLogHash);
            if (arr.length) {
              const latestRead = arr[0];
              const marker = `${latestRead.user_id}_${latestRead.read_at}`;
              setAdminReadSeenMarker(marker);
            }
          }
          setAdminReadAlert(false);
          refreshBellVisual();
        }
        closeModal();
      });
    }

    if (sendBtn) {
      sendBtn.addEventListener("click", async () => {
        const txt = input ? input.value : "";
        sendBtn.disabled = true;

        try {
          const data = await sendNotification(txt);
          if (data && data.ok && data.notification) {
            const n = data.notification;

            localStorage.setItem(LS_IN, String(n.id));
            localStorage.setItem(LS_RD, String(n.id)); // admin o‘zi uchun unread emas
            localStorage.setItem(LS_TX, String(n.message || ""));
            localStorage.setItem(LS_TM, String(n.created_at || ""));
            localStorage.setItem(LS_AV, String(n.avatar_url || ""));
            localStorage.setItem(LS_BY, String(n.created_by_name || "Admin"));

            if (input) input.value = "";

            setMessageCard(
              n.message || "",
              n.created_by_name || "Admin",
              n.created_at || "",
              n.avatar_url || "/static/images/admin-bot.png"
            );

            refreshBellVisual();
            closeModal();
          }
        } finally {
          sendBtn.disabled = false;
        }
      });
    }

    window.addEventListener("storage", (e) => {
      if ([LS_IN, LS_RD, LS_TX, LS_TM, LS_AV, LS_BY, LS_TOAST].includes(e.key)) {
        setMessageCard(
          localStorage.getItem(LS_TX) || "",
          localStorage.getItem(LS_BY) || "Admin",
          localStorage.getItem(LS_TM) || "",
          localStorage.getItem(LS_AV) || "/static/images/admin-bot.png"
        );
        refreshBellVisual();
      }
    });
  }

  const ui = ensureBellUI();
  if (!ui) return;

  wireEvents();

  (async function init() {
    const data = await fetchLatest();

    if (data && data.notification) {
      const n = data.notification;
      const incomingId = toInt(n.id, 0);

      if (incomingId) {
        if (lastIncomingId() < incomingId) {
          localStorage.setItem(LS_IN, String(incomingId));
          localStorage.setItem(LS_TX, String(n.message || ""));
          localStorage.setItem(LS_TM, String(n.created_at || ""));
          localStorage.setItem(LS_AV, String(n.avatar_url || ""));
          localStorage.setItem(LS_BY, String(n.created_by_name || "Admin"));
        }

        // USER: login qilganda unread bo‘lsa darrov signal berish
        if (!isAdmin() && isUnread()) {
          const seenId = getUserSoundSeenId();
          if (incomingId > seenId) {
            setUserSoundSeenId(incomingId);
            await playSound("message");
          }
        }
      }

      // admin read log init
      if (isAdmin()) {
        const readEvents = Array.isArray(data.read_events) ? data.read_events : [];
        setReadLog(readEvents);
        prevReadLogHash = JSON.stringify(readEvents);
      }
    }

    refreshBellVisual();
    setInterval(tick, POLL_MS);
  })();
})();
