/* EasySpend Mini App */
(() => {
  'use strict';
  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg) { try { tg.ready(); tg.expand(); } catch (e) {} }

  /* ───────── Matnlar ───────── */
  const I = {
    uz: {
      cur: "so'm", hello: 'Salom', spent: 'Oylik chiqim', income: 'Kirim', balance: 'Qoldiq',
      today: 'Bugun', week: 'Shu hafta', recent: "So'nggi chiqimlar", all: 'Hammasi',
      home: 'Bosh', hist: 'Tarix', stats: 'Statistika', me: 'Profil',
      expense: 'Chiqim', inc: 'Kirim', addTitle: "Qo'shish", editTitle: 'Tahrirlash',
      amount: 'Summa', name: 'Nomi', cat: 'Kategoriya', date: 'Sana', auto: 'Avto', save: 'Saqlash', del: "O'chirish",
      cancel: 'Bekor', sureDel: "O'chirilsinmi?", empty: "Hali yozuv yo'q", emptyHint: "Botga yozing yoki + tugmasini bosing",
      byCat: "Kategoriyalar bo'yicha", byDay: "Kunlar bo'yicha", avg: "O'rtacha/kun", max: 'Eng ko‘p', cnt: 'Yozuvlar',
      total: 'Jami', lang: 'Til', limit: 'Oylik limit', limitHint: "Limitga yaqinlashsangiz bot ogohlantiradi",
      limitOff: 'Limit belgilanmagan', setLimit: 'Belgilash', ofLimit: 'limitdan', left: 'qoldi', over: 'oshdi',
      rec: 'Takroriy chiqimlar', recHint: 'Ijara, internet, obuna — har oy o‘zi yoziladi', recAdd: "Takroriy qo'shish",
      dom: 'Oyning kuni', everyMonth: 'har oy', saved: 'Saqlandi ✓', deleted: "O'chirildi", err: 'Xatolik, qayta urining',
      badAmount: "Summani to'g'ri yozing", openTg: 'Telegram ichida oching', openTgP: 'Bu ilova faqat Telegram bot orqali ishlaydi.',
      notReg: "Avval botda ro'yxatdan o'ting", notRegP: "Botga /start yuboring, keyin ilovani qayta oching.",
      yesterday: 'Kecha', noExp: "Bu oyda chiqim yo'q", noInc: "Bu oyda kirim yo'q", incName: 'Kirim',
      namePh: 'Masalan: non, taksi, maosh', top: 'Eng katta toifa',
      months: ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentabr','Oktabr','Noyabr','Dekabr'],
      cats: { food: 'Oziq-ovqat', transport: 'Transport', home: 'Uy va kommunal', health: 'Salomatlik', shopping: 'Xaridlar', fun: "Ko'ngilochar", edu: "Ta'lim", other: 'Boshqa' },
    },
    ru: {
      cur: 'сум', hello: 'Привет', spent: 'Расходы за месяц', income: 'Доход', balance: 'Остаток',
      today: 'Сегодня', week: 'Эта неделя', recent: 'Последние расходы', all: 'Все',
      home: 'Главная', hist: 'История', stats: 'Статистика', me: 'Профиль',
      expense: 'Расход', inc: 'Доход', addTitle: 'Добавить', editTitle: 'Изменить',
      amount: 'Сумма', name: 'Название', cat: 'Категория', date: 'Дата', auto: 'Авто', save: 'Сохранить', del: 'Удалить',
      cancel: 'Отмена', sureDel: 'Удалить?', empty: 'Записей пока нет', emptyHint: 'Напишите боту или нажмите +',
      byCat: 'По категориям', byDay: 'По дням', avg: 'В среднем/день', max: 'Максимум', cnt: 'Записей',
      total: 'Всего', lang: 'Язык', limit: 'Месячный лимит', limitHint: 'Бот предупредит, когда лимит будет близко',
      limitOff: 'Лимит не задан', setLimit: 'Задать', ofLimit: 'от лимита', left: 'осталось', over: 'сверх лимита',
      rec: 'Регулярные расходы', recHint: 'Аренда, интернет, подписки — записываются сами каждый месяц', recAdd: 'Добавить регулярный',
      dom: 'День месяца', everyMonth: 'каждый месяц', saved: 'Сохранено ✓', deleted: 'Удалено', err: 'Ошибка, попробуйте ещё раз',
      badAmount: 'Введите сумму правильно', openTg: 'Откройте в Telegram', openTgP: 'Приложение работает только через бота в Telegram.',
      notReg: 'Сначала зарегистрируйтесь в боте', notRegP: 'Отправьте боту /start и откройте приложение снова.',
      yesterday: 'Вчера', noExp: 'В этом месяце расходов нет', noInc: 'В этом месяце доходов нет', incName: 'Доход',
      namePh: 'Например: хлеб, такси, зарплата', top: 'Главная категория',
      months: ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'],
      mg: ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'],
      cats: { food: 'Еда', transport: 'Транспорт', home: 'Дом и коммунальные', health: 'Здоровье', shopping: 'Покупки', fun: 'Развлечения', edu: 'Образование', other: 'Другое' },
    },
    en: {
      cur: 'UZS', hello: 'Hi', spent: 'Spent this month', income: 'Income', balance: 'Balance',
      today: 'Today', week: 'This week', recent: 'Recent expenses', all: 'All',
      home: 'Home', hist: 'History', stats: 'Stats', me: 'Profile',
      expense: 'Expense', inc: 'Income', addTitle: 'Add', editTitle: 'Edit',
      amount: 'Amount', name: 'Name', cat: 'Category', date: 'Date', auto: 'Auto', save: 'Save', del: 'Delete',
      cancel: 'Cancel', sureDel: 'Delete this?', empty: 'No entries yet', emptyHint: 'Message the bot or tap +',
      byCat: 'By category', byDay: 'By day', avg: 'Avg / day', max: 'Highest', cnt: 'Entries',
      total: 'Total', lang: 'Language', limit: 'Monthly budget', limitHint: "The bot warns you as you approach the budget",
      limitOff: 'No budget set', setLimit: 'Set', ofLimit: 'of budget', left: 'left', over: 'over budget',
      rec: 'Recurring expenses', recHint: 'Rent, internet, subscriptions — logged automatically each month', recAdd: 'Add recurring',
      dom: 'Day of month', everyMonth: 'monthly', saved: 'Saved ✓', deleted: 'Deleted', err: 'Something went wrong, try again',
      badAmount: 'Enter a valid amount', openTg: 'Open inside Telegram', openTgP: 'This app only works through the Telegram bot.',
      notReg: 'Please register in the bot first', notRegP: 'Send /start to the bot, then reopen the app.',
      yesterday: 'Yesterday', noExp: 'No expenses this month', noInc: 'No income this month', incName: 'Income',
      namePh: 'e.g. bread, taxi, salary', top: 'Top category',
      months: ['January','February','March','April','May','June','July','August','September','October','November','December'],
      cats: { food: 'Food', transport: 'Transport', home: 'Home & bills', health: 'Health', shopping: 'Shopping', fun: 'Fun', edu: 'Education', other: 'Other' },
    },
  };
  I.uz.mg = I.uz.months.map(s => s.toLowerCase());
  I.en.mg = I.en.months;

  const CATS = {
    food: { e: '🍽️', c: '#35d49a' }, transport: { e: '🚕', c: '#4da3ff' }, home: { e: '🏠', c: '#b58cff' },
    health: { e: '💊', c: '#ff6b8a' }, shopping: { e: '🛍️', c: '#ffb347' }, fun: { e: '🎬', c: '#ff8f5a' },
    edu: { e: '📚', c: '#4fd1d1' }, other: { e: '📦', c: '#8a94a7' },
  };
  const CAT_KEYS = Object.keys(CATS);

  /* ───────── Holat ───────── */
  const S = { tab: 'home', data: null, month: null, hist: 'exp', lang: 'uz', loaded: false };
  const $ = (s) => document.querySelector(s);
  const t = () => I[S.lang] || I.uz;
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = (n) => String(Math.round(n || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const money = (n) => num(n) + ' ' + t().cur;
  const short = (n) => {
    n = Math.abs(n);
    if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace('.0', '') + (S.lang === 'ru' ? ' млн' : S.lang === 'en' ? 'M' : ' mln');
    if (n >= 1e3) return Math.round(n / 1e3) + (S.lang === 'ru' ? ' тыс' : S.lang === 'en' ? 'K' : ' ming');
    return String(Math.round(n));
  };
  const pad = (n) => String(n).padStart(2, '0');
  const iso = (d) => d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  const parseISO = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };

  function haptic(kind) {
    try {
      if (!tg || !tg.HapticFeedback) return;
      if (kind === 'ok' || kind === 'err') tg.HapticFeedback.notificationOccurred(kind === 'ok' ? 'success' : 'error');
      else tg.HapticFeedback.impactOccurred('light');
    } catch (e) {}
  }
  let toastT;
  function toast(msg, isErr) {
    const el = $('#toast');
    el.textContent = msg;
    el.className = 'show' + (isErr ? ' err' : '');
    clearTimeout(toastT);
    toastT = setTimeout(() => (el.className = ''), 2200);
  }

  /* ───────── Mavzu ───────── */
  function applyTheme() {
    const scheme = (tg && tg.colorScheme) || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.dataset.theme = scheme === 'light' ? 'light' : 'dark';
    const bg = scheme === 'light' ? '#f3f5f9' : '#0d1117';
    try { tg && tg.setHeaderColor && tg.setHeaderColor(bg); tg && tg.setBackgroundColor && tg.setBackgroundColor(bg); tg && tg.setBottomBarColor && tg.setBottomBarColor(bg); } catch (e) {}
  }
  applyTheme();
  if (tg && tg.onEvent) tg.onEvent('themeChanged', applyTheme);

  /* ───────── API ───────── */
  async function api(path, body) {
    const r = await fetch('/api/' + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Init-Data': (tg && tg.initData) || '' },
      body: JSON.stringify(body || {}),
    });
    let j = {};
    try { j = await r.json(); } catch (e) {}
    if (!r.ok) { const e = new Error(j.error || 'error'); e.status = r.status; e.code = j.error; throw e; }
    return j;
  }
  async function load() {
    const d = await api('init', { month: S.month });
    S.data = d;
    S.month = d.month;
    S.lang = d.user.lang === 'ru' ? 'ru' : d.user.lang === 'en' ? 'en' : 'uz';
    document.documentElement.lang = S.lang;
    S.loaded = true;
  }
  async function act(path, body, okMsg) {
    try {
      await api(path, body);
      await load();
      haptic('ok');
      if (okMsg) toast(okMsg);
      return true;
    } catch (e) {
      haptic('err');
      toast(e.code === 'bad_amount' ? t().badAmount : t().err, true);
      return false;
    }
  }

  /* ───────── Rasm elementlari ───────── */
  const ICON = {
    home: '<svg viewBox="0 0 24 24"><path d="M3 11l9-7.5L21 11v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>',
    hist: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    stats: '<svg viewBox="0 0 24 24"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
    me: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>',
    plus: '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>',
  };
  function catIcon(cat) {
    const c = CATS[cat] || CATS.other;
    return `<div class="ico" style="background:${c.c}26">${c.e}</div>`;
  }
  function dayLabel(dStr) {
    const d = parseISO(dStr), today = parseISO(S.data.today);
    const diff = Math.round((today - d) / 86400000);
    if (diff === 0) return t().today;
    if (diff === 1) return t().yesterday;
    const mg = t().mg;
    return S.lang === 'en' ? `${mg[d.getMonth()]} ${d.getDate()}` : `${d.getDate()} ${mg[d.getMonth()]}`;
  }

  function monthBar() {
    const [y, m] = S.month.split('-').map(Number);
    const yr = y === new Date().getFullYear() ? '' : ' ' + y;
    return `<div class="monthbar"><button data-act="prev" aria-label="prev">‹</button><span>${t().months[m - 1]}${yr}</span><button data-act="next" aria-label="next">›</button></div>`;
  }

  /* ───────── Sahifalar ───────── */
  function viewHome() {
    const d = S.data, T = t();
    const budget = d.user.budget;
    let budgetHtml;
    if (budget > 0) {
      const pct = d.spent / budget * 100;
      const cls = pct >= 100 ? 'over' : pct >= 80 ? 'warn' : '';
      const diff = budget - d.spent;
      budgetHtml = `<div class="bar ${cls}"><i style="width:${Math.min(100, pct).toFixed(1)}%"></i></div>
        <div class="barinfo"><span><b>${Math.round(pct)}%</b> ${T.ofLimit}</span><span><b>${short(Math.abs(diff))}</b> ${diff >= 0 ? T.left : T.over}</span></div>`;
    } else {
      budgetHtml = `<div class="hint">${T.limitOff} · <button data-act="goto-profile">${T.setLimit}</button></div>`;
    }
    const top = d.by_category.slice(0, 3);
    const topHtml = top.length ? `<div class="sec"><h3>${T.byCat}</h3><button data-act="goto-stats">${T.all}</button></div>
      <div class="list catbars">${top.map((c) => catBar(c, d.spent)).join('')}</div>` : '';
    const recent = d.expenses.slice(0, 5);
    const recentHtml = `<div class="sec"><h3>${T.recent}</h3>${d.expenses.length ? `<button data-act="goto-hist">${T.all}</button>` : ''}</div>` +
      (recent.length ? `<div class="list">${recent.map(expRow).join('')}</div>` : emptyBox());
    const photo = tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.photo_url;
    return `<div class="view">
      <div class="top">
        <div class="avatar" ${photo ? `style="background-image:url('${esc(photo)}')"` : ''}>${photo ? '' : esc((d.user.name || '?').slice(0, 1).toUpperCase())}</div>
        <div class="hello"><small>${T.hello} 👋</small><b>${esc(d.user.name)}</b></div>
        ${monthBar()}
      </div>
      <div class="hero">
        <div class="lbl">${T.spent}</div>
        <div class="big">${num(d.spent)}<small>${T.cur}</small></div>
        ${budgetHtml}
        <div class="chips">
          <div class="chip"><small>${T.income}</small><b class="pos">+${short(d.income)}</b></div>
          <div class="chip"><small>${T.balance}</small><b class="${d.balance < 0 ? 'neg' : 'pos'}">${d.balance < 0 ? '−' : ''}${short(d.balance)}</b></div>
        </div>
      </div>
      <div class="grid2">
        <div class="card stat"><small>${T.today}</small><b>${money(d.today_sum)}</b></div>
        <div class="card stat"><small>${T.week}</small><b>${money(d.week_sum)}</b></div>
      </div>
      ${topHtml}${recentHtml}
    </div>`;
  }

  function catBar(c, total) {
    const meta = CATS[c.cat] || CATS.other, pct = total ? c.sum / total * 100 : 0;
    return `<div class="cb"><div class="h"><span>${meta.e}</span><span>${esc(t().cats[c.cat] || c.cat)}</span><span>${money(c.sum)}</span></div>
      <div class="bar"><i style="width:${pct.toFixed(1)}%;background:${meta.c}"></i></div></div>`;
  }
  function expRow(e) {
    const nm = e.name || t().cats[e.category];
    return `<button class="row" data-act="edit-exp" data-id="${e.id}">${catIcon(e.category)}
      <div class="rmid"><b>${esc(nm)}</b><small>${esc(t().cats[e.category] || '')} · ${esc(dayLabel(e.day))}</small></div>
      <div class="ramt">−${num(e.amount)}</div></button>`;
  }
  function incRow(e) {
    return `<button class="row" data-act="edit-inc" data-id="${e.id}"><div class="ico" style="background:rgba(53,212,154,.15)">💰</div>
      <div class="rmid"><b>${esc(e.name || t().incName)}</b><small>${esc(dayLabel(e.day))}</small></div>
      <div class="ramt pos">+${num(e.amount)}</div></button>`;
  }
  function emptyBox() {
    return `<div class="card empty"><span class="em">🧾</span><b>${t().empty}</b><div class="hint">${t().emptyHint}</div></div>`;
  }

  function viewHist() {
    const d = S.data, T = t();
    const isExp = S.hist === 'exp';
    const items = isExp ? d.expenses : d.incomes;
    let html = '';
    if (!items.length) html = `<div class="card empty"><span class="em">${isExp ? '🧾' : '💰'}</span><b>${isExp ? T.noExp : T.noInc}</b></div>`;
    else {
      const groups = {};
      items.forEach((e) => (groups[e.day] = groups[e.day] || []).push(e));
      html = Object.keys(groups).sort().reverse().map((day) => {
        const sum = groups[day].reduce((a, e) => a + e.amount, 0);
        return `<div class="dayhead"><span>${esc(dayLabel(day))}</span><span>${isExp ? '−' : '+'}${num(sum)}</span></div>
          <div class="list">${groups[day].map(isExp ? expRow : incRow).join('')}</div>`;
      }).join('');
    }
    return `<div class="view">
      <div class="top"><div class="hello"><b style="font-size:22px">${T.hist}</b></div>${monthBar()}</div>
      <div class="seg"><button class="${isExp ? 'on' : ''}" data-act="hist" data-v="exp">${T.expense}</button><button class="${!isExp ? 'on' : ''}" data-act="hist" data-v="inc">${T.inc}</button></div>
      ${html}</div>`;
  }

  function donut(cats, total) {
    const R = 52, C = 2 * Math.PI * R;
    let off = 0, segs = '';
    cats.forEach((c) => {
      const len = total ? c.sum / total * C : 0;
      segs += `<circle cx="70" cy="70" r="${R}" fill="none" stroke="${(CATS[c.cat] || CATS.other).c}" stroke-width="17" stroke-dasharray="${Math.max(0, len - 2).toFixed(2)} ${(C - Math.max(0, len - 2)).toFixed(2)}" stroke-dashoffset="${(-off).toFixed(2)}" stroke-linecap="butt"/>`;
      off += len;
    });
    return `<div class="donut"><svg viewBox="0 0 140 140"><circle cx="70" cy="70" r="${R}" fill="none" stroke="var(--line)" stroke-width="17"/>${segs}</svg>
      <div class="mid"><b>${short(total)}</b><small>${t().total}</small></div></div>`;
  }

  function viewStats() {
    const d = S.data, T = t();
    const total = d.spent;
    let body;
    if (!total) body = `<div class="card empty"><span class="em">📊</span><b>${T.noExp}</b></div>`;
    else {
      const legend = d.by_category.map((c) => `<div><i style="background:${(CATS[c.cat] || CATS.other).c}"></i>${esc(T.cats[c.cat] || c.cat)}<span>${Math.round(c.sum / total * 100)}%</span></div>`).join('');
      const max = Math.max(...d.by_day.map((x) => x.sum), 1);
      const days = d.by_day.length;
      const upto = d.is_current ? Math.max(1, parseISO(d.today).getDate()) : days;
      const maxDay = d.by_day.reduce((a, b) => (b.sum > a.sum ? b : a), d.by_day[0]);
      const cols = d.by_day.map((x) => `<div class="col ${x.sum ? '' : 'zero'} ${x.day === d.today ? 'now' : ''}" title="${esc(x.day)}: ${num(x.sum)}"><i style="height:${x.sum ? Math.max(3, x.sum / max * 100) : 2}%"></i></div>`).join('');
      body = `<div class="card"><div class="donutwrap">${donut(d.by_category, total)}<div class="legend">${legend}</div></div></div>
        <div class="sec"><h3>${T.byCat}</h3></div><div class="list catbars">${d.by_category.map((c) => catBar(c, total)).join('')}</div>
        <div class="sec"><h3>${T.byDay}</h3></div>
        <div class="card"><div class="chart">${cols}</div><div class="axis"><span>1</span><span>${Math.ceil(days / 2)}</span><span>${days}</span></div>
        <div class="kpis"><div><small>${T.avg}</small><b>${short(total / upto)}</b></div><div><small>${T.max}</small><b>${short(maxDay.sum)}</b></div><div><small>${T.cnt}</small><b>${d.expenses.length}</b></div></div></div>`;
    }
    return `<div class="view"><div class="top"><div class="hello"><b style="font-size:22px">${T.stats}</b></div>${monthBar()}</div>${body}</div>`;
  }

  function viewProfile() {
    const d = S.data, T = t();
    const u = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
    const photo = u && u.photo_url;
    const rec = d.recurring.map((r) => `<div class="row">${catIcon(r.category)}<div class="rmid"><b>${esc(r.name)}</b><small>${T.everyMonth} · ${r.dom}</small></div><div class="ramt">${num(r.amount)}</div><button class="ico-btn" data-act="del-rec" data-id="${r.id}">✕</button></div>`).join('');
    return `<div class="view">
      <div class="profile card"><div class="avatar" ${photo ? `style="background-image:url('${esc(photo)}')"` : ''}>${photo ? '' : esc((d.user.name || '?').slice(0, 1).toUpperCase())}</div>
        <div><b>${esc(d.user.name)}</b><small>${u && u.username ? '@' + esc(u.username) : 'EasySpend'}</small></div></div>
      <div class="sec"><h3>${T.limit}</h3></div>
      <div class="card"><div class="inline"><input id="limit" class="inp" inputmode="numeric" placeholder="3 000 000" value="${d.user.budget ? num(d.user.budget) : ''}"><button class="btn" data-act="save-limit">${T.save}</button></div>
        <div class="hint" style="margin-top:8px">${T.limitHint}</div></div>
      <div class="sec"><h3>${T.rec}</h3></div>
      ${rec ? `<div class="list">${rec}</div>` : `<div class="card hint">${T.recHint}</div>`}
      <button class="btn ghost block mt" data-act="add-rec">＋ ${T.recAdd}</button>
      <div class="sec"><h3>${T.lang}</h3></div>
      <div class="seg">${['uz', 'ru', 'en'].map((l) => `<button class="${S.lang === l ? 'on' : ''}" data-act="lang" data-v="${l}">${{ uz: "O'zbekcha", ru: 'Русский', en: 'English' }[l]}</button>`).join('')}</div>
    </div>`;
  }

  function render() {
    const T = t();
    const nav = $('#nav');
    nav.hidden = false;
    const nb = (k, label) => `<button class="nb ${S.tab === k ? 'on' : ''}" data-act="tab" data-v="${k}">${ICON[k]}<span>${label}</span></button>`;
    nav.innerHTML = nb('home', T.home) + nb('hist', T.hist) + `<button class="fab" data-act="add" aria-label="${T.addTitle}">${ICON.plus}</button>` + nb('stats', T.stats) + nb('me', T.me);
    const v = { home: viewHome, hist: viewHist, stats: viewStats, me: viewProfile }[S.tab];
    const y = window.scrollY;
    $('#app').innerHTML = v();
    window.scrollTo(0, y);
  }

  /* ───────── Pastdan chiqadigan oyna ───────── */
  let sheetEl, ovEl;
  function openSheet(html) {
    closeSheet(true);
    ovEl = document.createElement('div'); ovEl.className = 'ov';
    sheetEl = document.createElement('div'); sheetEl.className = 'sheet';
    sheetEl.innerHTML = '<div class="grab"></div>' + html;
    $('#sheet-root').append(ovEl, sheetEl);
    ovEl.onclick = () => closeSheet();
    requestAnimationFrame(() => { ovEl.classList.add('in'); sheetEl.classList.add('in'); });
    return sheetEl;
  }
  function closeSheet(now) {
    if (!sheetEl) return;
    const s = sheetEl, o = ovEl;
    sheetEl = ovEl = null;
    s.classList.remove('in'); o.classList.remove('in');
    setTimeout(() => { s.remove(); o.remove(); }, now ? 0 : 280);
  }
  function catChips(sel, withAuto) {
    const T = t();
    return (withAuto ? `<button type="button" class="cat ${sel === 'auto' ? 'on' : ''}" data-cat="auto">✨ ${T.auto}</button>` : '') +
      CAT_KEYS.map((k) => `<button type="button" class="cat ${sel === k ? 'on' : ''}" data-cat="${k}">${CATS[k].e} ${esc(T.cats[k])}</button>`).join('');
  }
  function wireSheet(el, state) {
    const amt = el.querySelector('#f-amount');
    if (amt) {
      amt.addEventListener('input', () => { amt.value = num(parseInt(amt.value.replace(/\D/g, '') || '0', 10)).replace(/^0$/, ''); });
      setTimeout(() => amt.focus(), 320);
    }
    el.querySelectorAll('[data-cat]').forEach((b) => b.addEventListener('click', () => {
      state.cat = b.dataset.cat;
      el.querySelectorAll('[data-cat]').forEach((x) => x.classList.toggle('on', x === b));
      haptic();
    }));
    el.querySelectorAll('[data-kind]').forEach((b) => b.addEventListener('click', () => {
      state.kind = b.dataset.kind;
      el.querySelectorAll('[data-kind]').forEach((x) => x.classList.toggle('on', x === b));
      el.querySelector('#cat-box').hidden = state.kind !== 'exp';
      haptic();
    }));
  }
  const readAmount = (el) => parseInt((el.querySelector('#f-amount').value || '').replace(/\D/g, '') || '0', 10);

  function openAdd() {
    const T = t(), st = { kind: S.tab === 'hist' && S.hist === 'inc' ? 'inc' : 'exp', cat: 'auto' };
    const el = openSheet(`<h2>${T.addTitle}</h2>
      <div class="seg"><button data-kind="exp" class="${st.kind === 'exp' ? 'on' : ''}">${T.expense}</button><button data-kind="inc" class="${st.kind === 'inc' ? 'on' : ''}">${T.inc}</button></div>
      <div class="field mt"><label>${T.amount} (${T.cur})</label><input id="f-amount" class="inp amount" inputmode="numeric" placeholder="0" autocomplete="off"></div>
      <div class="field"><label>${T.name}</label><input id="f-name" class="inp" maxlength="100" placeholder="${esc(T.namePh)}" autocomplete="off"></div>
      <div class="field" id="cat-box" ${st.kind === 'exp' ? '' : 'hidden'}><label>${T.cat}</label><div class="cats">${catChips('auto', true)}</div></div>
      <div class="field"><label>${T.date}</label><input id="f-date" type="date" class="inp" value="${S.data.today}"></div>
      <button class="btn block" id="f-save">${T.save}</button>`);
    wireSheet(el, st);
    el.querySelector('#f-save').onclick = async () => {
      const amount = readAmount(el);
      if (!amount) { toast(T.badAmount, true); haptic('err'); return; }
      const body = { amount, name: el.querySelector('#f-name').value, day: el.querySelector('#f-date').value || S.data.today };
      if (st.kind === 'exp') body.category = st.cat;
      if (await act(st.kind === 'exp' ? 'expense_add' : 'income_add', body, T.saved)) { closeSheet(); render(); }
    };
  }

  function openEdit(id) {
    const T = t(), e = S.data.expenses.find((x) => x.id === id);
    if (!e) return;
    const st = { cat: e.category };
    const el = openSheet(`<h2>${T.editTitle}</h2>
      <div class="field"><label>${T.amount} (${T.cur})</label><input id="f-amount" class="inp amount" inputmode="numeric" value="${num(e.amount)}" autocomplete="off"></div>
      <div class="field"><label>${T.name}</label><input id="f-name" class="inp" maxlength="100" value="${esc(e.name)}" autocomplete="off"></div>
      <div class="field"><label>${T.cat}</label><div class="cats">${catChips(e.category, false)}</div></div>
      <div class="field"><label>${T.date}</label><input id="f-date" type="date" class="inp" value="${esc(e.day)}"></div>
      <div class="btnrow"><button class="btn danger" id="f-del">${T.del}</button><button class="btn" id="f-save">${T.save}</button></div>`);
    wireSheet(el, st);
    el.querySelector('#f-save').onclick = async () => {
      const amount = readAmount(el);
      if (!amount) { toast(T.badAmount, true); haptic('err'); return; }
      if (await act('expense_update', { id, amount, name: el.querySelector('#f-name').value, category: st.cat, day: el.querySelector('#f-date').value }, T.saved)) { closeSheet(); render(); }
    };
    el.querySelector('#f-del').onclick = () => confirmDel(async () => { if (await act('expense_delete', { id }, T.deleted)) { closeSheet(); render(); } });
  }

  function openEditInc(id) {
    const T = t(), e = S.data.incomes.find((x) => x.id === id);
    if (!e) return;
    const el = openSheet(`<h2>${esc(e.name || T.incName)}</h2>
      <div class="card" style="margin-bottom:14px"><div class="hint">${esc(dayLabel(e.day))}</div><b class="pos" style="font-size:26px">+${money(e.amount)}</b></div>
      <button class="btn danger block" id="f-del">${T.del}</button>`);
    el.querySelector('#f-del').onclick = () => confirmDel(async () => { if (await act('income_delete', { id }, T.deleted)) { closeSheet(); render(); } });
  }

  function openAddRec() {
    const T = t(), st = { cat: 'auto' };
    const el = openSheet(`<h2>${T.recAdd}</h2>
      <div class="field"><label>${T.name}</label><input id="f-name" class="inp" maxlength="100" placeholder="Internet, ijara..." autocomplete="off"></div>
      <div class="field"><label>${T.amount} (${T.cur})</label><input id="f-amount" class="inp amount" inputmode="numeric" placeholder="0" autocomplete="off"></div>
      <div class="field"><label>${T.dom} (1–31)</label><input id="f-dom" class="inp" type="number" min="1" max="31" value="1" inputmode="numeric"></div>
      <div class="field"><label>${T.cat}</label><div class="cats">${catChips('auto', true)}</div></div>
      <button class="btn block" id="f-save">${T.save}</button>`);
    wireSheet(el, st);
    el.querySelector('#f-save').onclick = async () => {
      const amount = readAmount(el), name = el.querySelector('#f-name').value.trim();
      const dom = parseInt(el.querySelector('#f-dom').value, 10);
      if (!amount || !name || !(dom >= 1 && dom <= 31)) { toast(T.badAmount, true); haptic('err'); return; }
      if (await act('recurring_add', { name, amount, dom, category: st.cat }, T.saved)) { closeSheet(); render(); }
    };
  }

  function confirmDel(fn) {
    const T = t();
    if (tg && tg.showConfirm) tg.showConfirm(T.sureDel, (ok) => ok && fn());
    else if (window.confirm(T.sureDel)) fn();
  }

  /* ───────── Hodisalar ───────── */
  function shiftMonth(delta) {
    const [y, m] = S.month.split('-').map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    S.month = d.getFullYear() + '-' + pad(d.getMonth() + 1);
    load().then(render).catch(() => toast(t().err, true));
  }

  document.addEventListener('click', async (ev) => {
    const el = ev.target.closest('[data-act]');
    if (!el || el.closest('.sheet')) return;
    const a = el.dataset.act;
    haptic();
    if (a === 'tab') { S.tab = el.dataset.v; window.scrollTo(0, 0); render(); }
    else if (a === 'goto-hist') { S.tab = 'hist'; render(); }
    else if (a === 'goto-stats') { S.tab = 'stats'; render(); }
    else if (a === 'goto-profile') { S.tab = 'me'; render(); }
    else if (a === 'prev') shiftMonth(-1);
    else if (a === 'next') shiftMonth(1);
    else if (a === 'hist') { S.hist = el.dataset.v; render(); }
    else if (a === 'add') openAdd();
    else if (a === 'edit-exp') openEdit(+el.dataset.id);
    else if (a === 'edit-inc') openEditInc(+el.dataset.id);
    else if (a === 'add-rec') openAddRec();
    else if (a === 'del-rec') confirmDel(async () => { if (await act('recurring_delete', { id: +el.dataset.id }, t().deleted)) render(); });
    else if (a === 'save-limit') {
      const v = parseInt(($('#limit').value || '').replace(/\D/g, '') || '0', 10);
      if (await act('budget_set', { budget: v }, t().saved)) render();
    } else if (a === 'lang') {
      if (await act('lang_set', { lang: el.dataset.v })) render();
    }
  });
  document.addEventListener('input', (ev) => {
    if (ev.target.id === 'limit') ev.target.value = num(parseInt(ev.target.value.replace(/\D/g, '') || '0', 10)).replace(/^0$/, '');
  });

  /* ───────── Boshlash ───────── */
  function showMsg(em, h, p) {
    $('#nav').hidden = true;
    $('#app').innerHTML = `<div class="msg"><div class="em">${em}</div><h2>${esc(h)}</h2><p>${esc(p)}</p></div>`;
  }
  (async function start() {
    if (!tg || !tg.initData) { showMsg('📲', I.uz.openTg + ' / ' + I.en.openTg, I.uz.openTgP); return; }
    try {
      await load();
      render();
    } catch (e) {
      if (e.code === 'not_registered') showMsg('👋', I.uz.notReg, I.uz.notRegP);
      else if (e.status === 401) showMsg('🔒', I.uz.openTg, I.uz.openTgP);
      else showMsg('⚠️', I.uz.err, '');
    }
  })();
})();
