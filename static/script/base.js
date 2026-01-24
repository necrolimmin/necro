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

  function applyTheme(theme){
    const t = (theme === 'dark') ? 'dark' : 'light';
    html.setAttribute('data-theme', t);
    localStorage.setItem(THEME_KEY, t);
    if (themeIconHolder) themeIconHolder.innerHTML = (t === 'dark') ? ICON_MOON : ICON_SUN;
  }

  applyTheme(localStorage.getItem(THEME_KEY) || 'light');

  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const cur = html.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
      applyTheme(cur === 'dark' ? 'light' : 'dark');
    });
  }

  // ---------------------------
  // Language (RU <-> UZ)
  // ---------------------------
  const langBtn = document.getElementById('langBtn');

  const dict = {
    ru: {
      brand:  "O‘ztemiryo‘lkonteyner AJ",
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
      brand: "O‘ztemiryo‘lkonteyner AJ",
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

    // small animation
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

    // outside click closes
    document.addEventListener('click', (e) => {
      if (!centerNav.contains(e.target) && !navToggle.contains(e.target)) {
        centerNav.classList.remove('open');
      }
    });
  }
})();
