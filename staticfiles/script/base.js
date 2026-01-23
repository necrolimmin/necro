(function(){
      // ---------------------------
      // Icons for theme
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
      const themeBtn = document.getElementById('themeBtn');
      const themeIconHolder = document.getElementById('themeIconHolder');

      function applyTheme(theme){
        html.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        themeIconHolder.innerHTML = (theme === 'dark') ? ICON_MOON : ICON_SUN;
      }

      applyTheme(localStorage.getItem('theme') || 'light');

      themeBtn.addEventListener('click', () => {
        const t = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        applyTheme(t);
      });

      // ---------------------------
      // Language toggle (RU <-> UZ)
      // ---------------------------
      const langBtn = document.getElementById('langBtn');

      const dict = {
        ru: {
          brand:  "O‘ztemiryo‘lkonteyner AJ" ,
          subtitle: "Платформа контейнерных операций",
          dash: "Dashboard",
          r1: "Отчёт 1",
          r2: "Отчёт 2",
          q: "Квартальный",
          branches: "Филиалы",
          admin: "ADMIN",
          user: "FILIAL",
          account: "Аккаунт",
          logout: "Выйти",

          t1_title: "Таблица №1 — отчёты по датам",
          t1_help: "Нажмите на кнопку “Отправили X/Y”, чтобы увидеть кто отправил и кто нет.",
          col_no: "№",
          col_date: "Дата / Месяц / Год",
          col_status: "Статус филиалов",
          col_last: "Последняя отправка",
          col_action: "Действие",
          year: "Год",
          month: "Месяц",
          sent: "Отправили",
          not_sent: "Не отправили",
          details: "Подробнее",
          modal_title: "Статус филиалов",
          none_sent: "Никто не отправил",
          all_sent: "Все отправили",
          view: "Посмотреть",
          empty: "Пока нет отчётов Таблицы 1.",
          page: "Страница",
          total: "Всего",
          prev: "Назад",
          next: "Вперёд",

        },
        uz: {
          brand: "O‘ztemiryo‘lkonteyner AJ",
          subtitle: "Konteyner operatsiyalar platformasi",
          dash: "Dashboard",
          r1: "Hisobot 1",
          r2: "Hisobot 2",
          q: "Kvartalniy",
          branches: "Filiallar",
          admin: "ADMIN",
          account: "Hisob",
          logout: "Chiqish",
          user: "FILIAL",

          t1_title: "Hisobot №1 — sanalar bo‘yicha hisobotlar",
          t1_help: "“Jo‘natgan X/Y” tugmasini bosing — kim jo‘natgan, kim jo‘natmagan ko‘rasiz.",
          col_no: "№",
          col_date: "Sana / Oy / Yil",
          col_status: "Filiallar holati",
          col_last: "Oxirgi jo‘natish",
          col_action: "Amal",
          year: "Yil",
          month: "Oy",
          sent: "Jo‘natgan",
          not_sent: "Jo‘natmagan",
          details: "Batafsil",
          modal_title: "Filiallar holati",
          none_sent: "Hech kim jo‘natmagan",
          all_sent: "Hamma jo‘natgan",
          view: "Ko‘rish",
          empty: "Hali Jadval 1 bo‘yicha hisobot yo‘q.",
          page: "Sahifa",
          total: "Jami",
          prev: "Oldingi",
          next: "Keyingi",

        }
      };

      function applyLang(lang){
        html.setAttribute('data-lang', lang);
        localStorage.setItem('lang', lang);

        const t = dict[lang] || dict.ru;
        document.querySelectorAll('[data-i18n]').forEach(el => {
          const key = el.getAttribute('data-i18n');
          if (t[key] !== undefined) el.textContent = t[key];
        });

        // Optional: lang button "pulse" when switched
        langBtn.animate(
          [{transform:'translateY(0)'},{transform:'translateY(-2px)'},{transform:'translateY(0)'}],
          {duration:220, easing:'ease-out'}
        );
      }

      applyLang(localStorage.getItem('lang') || 'ru');

      langBtn.addEventListener('click', () => {
        const current = html.getAttribute('data-lang') || 'ru';
        applyLang(current === 'ru' ? 'uz' : 'ru');
      });

      // ---------------------------
      // Admin dropdown
      // ---------------------------
      const adminToggle = document.getElementById('adminToggle');
      const adminMenu = document.getElementById('adminMenu');

      function closeMenu(){ adminMenu.classList.remove('open'); }

      adminToggle.addEventListener('click', () => {
        adminMenu.classList.toggle('open');
      });

      adminToggle.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') adminMenu.classList.toggle('open');
      });

      document.addEventListener('click', (e) => {
        if (!adminMenu.contains(e.target) && !adminToggle.contains(e.target)){
          closeMenu();
        }
      });

      // ---------------------------
      // Active nav highlight (simple)
      // ---------------------------
      const path = window.location.pathname;
      document.querySelectorAll('.nav-link').forEach(a => {
        if (a.getAttribute('href') === path) a.classList.add('active');
      });

    })();