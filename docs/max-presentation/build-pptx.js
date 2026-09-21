/**
 * Builds presentation.pptx — the same deck as deck.html, for people who need to edit it
 * in PowerPoint rather than re-print the HTML.
 *
 *   npm install pptxgenjs --no-save && node build-pptx.js
 *
 * What pptxgenjs cannot draw - gradient fills, a repeating starfield, rounded image
 * corners - ships as images made by make-assets.py: bg-cover.jpg (also the HTML cover's
 * background), bg-dark.png, screen-*.png, bubble-owner.png, qr-bot.png. That is why the
 * dark slides, the cover and the closing slide look like their HTML counterparts.
 */

const pptxgen = require("pptxgenjs");

// --- palette -----------------------------------------------------------------------
const MAX_BLUE = "0077FF";
const MAX_VIOLET = "7B2CFF";
const INK = "0D1117";
const INK_2 = "4A5464";
const INK_3 = "79839A";
const LINE = "DDE4EE";
const SURFACE_2 = "F3F6FB";
const WHITE = "FFFFFF";
const ON_DARK = "EAF1FF";
const ON_DARK_2 = "A9B7CE";
const DARK_CARD = "141C2E";
const ACCENT_ON_DARK = "8EC4FF";
const PINK = "FF9AC4";

const FONT = "Calibri";
const W = 13.33;
const H = 7.5;
const M = 0.55; // slide margin
const CW = W - M * 2; // content width

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // must be set before any slide is added
pres.author = "AIRuntime";
pres.title = "Витрина — AIRuntime × MAX";

// --- building blocks ----------------------------------------------------------------

/** Footer + page number. The lockup is the only thing repeated on every slide. */
function chrome(slide, n, dark, label) {
  slide.addText(
    label
      ? [{ text: label, options: { bold: true } }]
      : [
          { text: "AIRUNTIME", options: { bold: true } },
          { text: "  ×  ", options: { color: dark ? "5C6B84" : INK_3 } },
          { text: "MAX", options: { bold: true } },
        ],
    {
      x: M,
      y: H - 0.52,
      w: 4,
      h: 0.3,
      fontFace: FONT,
      fontSize: 10,
      color: dark ? "8193AE" : INK_3,
      charSpacing: 1.2,
      isTextBox: true,
      margin: 0,
    }
  );
  slide.addText(String(n).padStart(2, "0"), {
    x: W - M - 1,
    y: H - 0.52,
    w: 1,
    h: 0.3,
    align: "right",
    fontFace: FONT,
    fontSize: 11,
    bold: true,
    color: dark ? "8193AE" : INK_3,
    isTextBox: true,
    margin: 0,
  });
}

function head(slide, eyebrow, title, sub, dark) {
  slide.addText(eyebrow.toUpperCase(), {
    x: M,
    y: 0.34,
    w: CW,
    h: 0.26,
    fontFace: FONT,
    fontSize: 11,
    bold: true,
    color: dark ? ACCENT_ON_DARK : MAX_BLUE,
    charSpacing: 2.2,
    isTextBox: true,
    margin: 0,
  });
  slide.addText(title, {
    x: M,
    y: 0.62,
    w: CW,
    h: 0.62,
    fontFace: FONT,
    fontSize: 34,
    bold: true,
    color: dark ? WHITE : INK,
    isTextBox: true,
    margin: 0,
  });
  if (sub) {
    slide.addText(sub, {
      x: M,
      y: 1.28,
      w: CW * 0.82,
      h: 0.34,
      fontFace: FONT,
      fontSize: 14,
      color: dark ? ON_DARK_2 : INK_2,
      isTextBox: true,
      margin: 0,
    });
  }
}

/** Rounded card. A tint and a shadow set it apart - never an edge stripe. */
function card(slide, o) {
  slide.addShape(pres.ShapeType.roundRect, {
    x: o.x,
    y: o.y,
    w: o.w,
    h: o.h,
    rectRadius: 0.1,
    fill: { color: o.dark ? DARK_CARD : o.tint ? "EAF1FE" : SURFACE_2 },
    line: { color: o.dark ? "2A3550" : o.tint ? "C7DBFB" : LINE, width: 1 },
    shadow: { type: "outer", color: "0B1730", blur: 10, offset: 2, angle: 90, opacity: 0.07 },
  });
}

/** Body text inside a card, with the title as its own bold run. */
function cardText(slide, o) {
  const runs = [];
  if (o.title) {
    runs.push({ text: o.title, options: { bold: true, fontSize: 15, color: o.dark ? WHITE : INK } });
    if (o.body) runs.push({ text: "\n", options: { fontSize: 6 } });
  }
  if (o.body) {
    runs.push({
      text: o.body,
      options: { fontSize: o.size || 12.5, color: o.dark ? ON_DARK_2 : INK_2 },
    });
  }
  slide.addText(runs, {
    x: o.x + 0.24,
    y: o.y + 0.2,
    w: o.w - 0.48,
    h: o.h - 0.4,
    fontFace: FONT,
    valign: "top",
    lineSpacingMultiple: 1.12,
    isTextBox: true,
    margin: 0,
  });
}

function bullets(slide, o) {
  const items = o.items.map((t, i) => ({
    text: t,
    options: {
      bullet: { code: "2022" },
      breakLine: i !== o.items.length - 1,
      paraSpaceAfter: 5,
    },
  }));
  slide.addText(items, {
    x: o.x,
    y: o.y,
    w: o.w,
    h: o.h,
    fontFace: FONT,
    fontSize: o.size || 12.5,
    color: o.dark ? ON_DARK_2 : INK_2,
    lineSpacingMultiple: 1.1,
    isTextBox: true,
    margin: 0,
  });
}

/** Big number + label. A headline figure needs no chart. */
function stat(slide, o) {
  card(slide, { x: o.x, y: o.y, w: o.w, h: o.h, dark: o.dark });
  slide.addText(
    [
      { text: o.value, options: { fontSize: 32, bold: true, color: o.dark ? WHITE : INK } },
      o.unit
        ? { text: " " + o.unit, options: { fontSize: 15, bold: true, color: o.dark ? ON_DARK_2 : INK_2 } }
        : { text: "" },
    ],
    {
      x: o.x + 0.22,
      y: o.y + 0.16,
      w: o.w - 0.44,
      h: 0.5,
      fontFace: FONT,
      isTextBox: true,
      margin: 0,
    }
  );
  slide.addText(o.label, {
    x: o.x + 0.22,
    y: o.y + 0.68,
    w: o.w - 0.44,
    h: o.h - 0.9,
    fontFace: FONT,
    fontSize: 11,
    color: o.dark ? ON_DARK_2 : INK_2,
    lineSpacingMultiple: 1.08,
    isTextBox: true,
    margin: 0,
  });
  if (o.src) {
    slide.addText(o.src, {
      x: o.x + 0.22,
      y: o.y + o.h - 0.32,
      w: o.w - 0.44,
      h: 0.24,
      fontFace: FONT,
      fontSize: 9,
      color: INK_3,
      isTextBox: true,
      margin: 0,
    });
  }
}

/** A numbered disc - the deck's one repeated ornament. */
function disc(slide, x, y, label, colour) {
  slide.addShape(pres.ShapeType.ellipse, {
    x,
    y,
    w: 0.36,
    h: 0.36,
    fill: { color: colour || MAX_BLUE },
    line: { color: colour || MAX_BLUE, width: 0 },
  });
  slide.addText(label, {
    x,
    y,
    w: 0.36,
    h: 0.36,
    align: "center",
    valign: "middle",
    fontFace: FONT,
    fontSize: 13,
    bold: true,
    color: WHITE,
    isTextBox: true,
    margin: 0,
  });
}

/** deck.html is laid out in CSS pixels on a 1280px slide; at 13.33in that is 96px to the
 *  inch, so the cover and closing slides take their boxes straight from the HTML. */
function px(v) {
  return v / 96;
}

// Text on the cover background, pre-blended from the HTML's rgba(234,241,255,a) over the
// dark field - a solid colour survives every PowerPoint version, text transparency not.
const ON_COVER_LEAD = "BDC4D2"; // .80
const ON_COVER_SUB = "A5ACBC"; // .70
const ON_COVER_FILL = "8F96A6"; // .60
const ON_COVER_MUTED = "7B8190"; // .50

/** AIRuntime mark and wordmark x the MAX mark, at the HTML lockup's position. */
function lockup(slide, top) {
  slide.addImage({ path: "mark-airuntime.png", x: px(72), y: top, w: px(32), h: px(32) });
  slide.addText("AIRUNTIME", {
    x: px(113), y: top, w: px(140), h: px(32), valign: "middle",
    fontFace: FONT, fontSize: 14.25, bold: true, color: WHITE, charSpacing: 0.8, isTextBox: true, margin: 0,
  });
  slide.addText("×", {
    x: px(226), y: top, w: px(14), h: px(32), align: "center", valign: "middle",
    fontFace: FONT, fontSize: 14, color: "9DA6BA", isTextBox: true, margin: 0,
  });
  slide.addShape(pres.ShapeType.ellipse, {
    x: px(249), y: top + px(4.5), w: px(23), h: px(23), fill: { color: WHITE }, line: { color: WHITE, width: 0 },
  });
  slide.addShape(pres.ShapeType.ellipse, {
    x: px(256.5), y: top + px(12), w: px(8), h: px(8), fill: { color: MAX_BLUE }, line: { color: MAX_BLUE, width: 0 },
  });
  slide.addText("max", {
    x: px(280), y: top, w: px(80), h: px(32), valign: "middle",
    fontFace: FONT, fontSize: 16, bold: true, color: WHITE, isTextBox: true, margin: 0,
  });
}

/**
 * A phone: rounded bezel with the screenshot inset in it. Same ratios as .phone in
 * deck.html - radius 8.2% and bezel 2.6% of the width - so the two decks match.
 * Returns the frame height, which is 1.948x the width; size frames by that height.
 */
function phone(slide, o) {
  const pad = o.w * 0.026;
  const sw = o.w - pad * 2;
  const h = sw * 2 + pad * 2;
  slide.addShape(pres.ShapeType.roundRect, {
    x: o.x,
    y: o.y,
    w: o.w,
    h,
    rectRadius: o.w * 0.082,
    fill: { color: o.dark ? "1E2638" : "DCE3EE" },
    line: { color: o.dark ? "39445E" : "CCD5E3", width: 0.75 },
    shadow: o.dark
      ? { type: "outer", color: "000000", blur: 30, offset: 12, angle: 90, opacity: 0.55 }
      : { type: "outer", color: "091228", blur: 16, offset: 6, angle: 90, opacity: 0.2 },
  });
  // Rounded corners are baked into screen-*.png (make-assets.py): pptxgenjs can only crop
  // an image to an ellipse.
  slide.addImage({ path: `screen-${o.name}.png`, x: o.x + pad, y: o.y + pad, w: sw, h: sw * 2 });
  return h;
}

function coverSlide() {
  const s = pres.addSlide();
  s.background = { path: "bg-cover.jpg" };
  return s;
}

function lightSlide() {
  const s = pres.addSlide();
  s.background = { color: WHITE };
  return s;
}

function darkSlide() {
  const s = pres.addSlide();
  s.background = { path: "bg-dark.png" };
  return s;
}

// ====================================================================================
// 1. Service slide
// ====================================================================================
{
  const s = lightSlide();
  head(s, "Слайд 1 · служебный · не оценивается", "Техническая информация для проверки");

  const rows = [
    ["Чат-бот в MAX", "https://max.ru/t403_hakaton_max_bot\n«Хакатон МАХ 403», user_id 395683755"],
    ["Мини-приложение", "https://airuntime.ru/max\nОткрывается кнопкой open_app и по ?startapp=<slug>"],
    ["Git-репозиторий", "github.com/airuntime-ru/airuntime"],
    ["Commit hash", "967024c · ветка main\n967024c0cb024ab93c623fc4e6189b29a17cfede"],
    ["Собственный API", "Не используется как отдельно проверяемый контракт\nВнутренние эндпоинты — /api/v1/max/*"],
    ["Тестовые записи", "Не требуются: вход — сам аккаунт MAX"],
  ];
  let y = 1.44;
  for (const [k, v] of rows) {
    const lines = v.split("\n");
    s.addText(k, {
      x: M, y, w: 1.85, h: 0.3, fontFace: FONT, fontSize: 11.5, color: INK_3,
      isTextBox: true, margin: 0,
    });
    s.addText(
      [
        { text: lines[0], options: { fontSize: 12, color: INK, bold: true } },
        ...(lines[1] ? [{ text: "\n" + lines[1], options: { fontSize: 10.5, color: INK_3 } }] : []),
      ],
      { x: M + 1.9, y, w: 4.5, h: 0.6, fontFace: FONT, isTextBox: true, margin: 0, lineSpacingMultiple: 1.05 }
    );
    y += lines[1] ? 0.68 : 0.5;
  }

  const cx = 7.35;
  card(s, { x: cx, y: 1.5, w: W - cx - M, h: 5.15, tint: true });
  s.addText("Порядок прохождения основного сценария", {
    x: cx + 0.28, y: 1.72, w: W - cx - M - 0.56, h: 0.3,
    fontFace: FONT, fontSize: 15, bold: true, color: INK, isTextBox: true, margin: 0,
  });
  bullets(s, {
    x: cx + 0.28, y: 2.16, w: W - cx - M - 0.56, h: 4.3, size: 12.5,
    items: [
      "Открыть max.ru/t403_hakaton_max_bot, нажать «Начать», затем «Открыть Витрину»",
      "В мини-приложении описать бизнес одним сообщением: «Автосервис на Лесной. Диагностика 1500, замена масла 900, шиномонтаж 2400. Работаем с 9 до 20» — и нажать «Собрать витрину»",
      "Через несколько секунд витрина опубликована: ссылка для клиентов, «Поделиться», «Посмотреть»",
      "Открыть эту ссылку с другого аккаунта MAX — это роль клиента",
      "Выбрать услугу и время, указать имя, нажать «Записаться»",
      "Владельцу в чат с ботом придёт заявка с кнопкой «Открыть заявки»",
      "Нажать «Подтвердить» в приложении — клиенту придёт уведомление в MAX",
    ],
  });

  card(s, { x: M, y: 5.3, w: 6.3, h: 1.35 });
  cardText(s, {
    x: M, y: 5.3, w: 6.3, h: 1.35,
    title: "Переменные окружения",
    size: 11,
    body: "MAX_BOT_TOKEN (передаётся отдельно) · MAX_BOT_USERNAME=t403_hakaton_max_bot · MAX_WEBHOOK_SECRET · MAX_MINIAPP_URL · OPENAI_API_KEY. Полный список — в .env.example",
  });
  chrome(s, 1, false);
}

// ====================================================================================
// 2. Cover
// ====================================================================================
// The owner's one message, the bot's answer with its button, and the storefront that
// button opens - the product told as the chat it happens in. Boxes are deck.html's.
{
  const s = coverSlide();
  const small = { fontFace: FONT, fontSize: 8.6, bold: true, charSpacing: 2, isTextBox: true, margin: 0 };

  lockup(s, px(140));
  s.addText("ТРЕК «ЭФФЕКТИВНЫЙ БИЗНЕС»", { ...small, x: px(72), y: px(204), w: px(520), h: px(20), color: ACCENT_ON_DARK });
  s.addText("Витрина", {
    x: px(68), y: px(226), w: px(560), h: px(124), valign: "top",
    fontFace: FONT, fontSize: 84, bold: true, color: WHITE, isTextBox: true, margin: 0,
  });
  s.addText(
    "Рабочий сервис записи в MAX из одного сообщения — без разработчика, без подрядчика, без ожидания.",
    {
      x: px(72), y: px(368), w: px(500), h: px(92), valign: "top",
      fontFace: FONT, fontSize: 16, color: ON_COVER_LEAD, lineSpacingMultiple: 1.15, isTextBox: true, margin: 0,
    }
  );

  // Team: still to be filled in, so it is drawn as a field rather than as finished copy.
  const field = { style: "dash", color: "59627A" };
  s.addText("КОМАНДА", { ...small, x: px(72), y: px(505), w: px(200), h: px(16), color: ON_COVER_MUTED });
  s.addText("[Название команды]", {
    x: px(72), y: px(528), w: px(210), h: px(24), fontFace: FONT, fontSize: 12.75, bold: true,
    color: ON_COVER_FILL, underline: field, isTextBox: true, margin: 0,
  });
  s.addText("[Участники и роли]", {
    x: px(72), y: px(556), w: px(210), h: px(20), fontFace: FONT, fontSize: 10,
    color: ON_COVER_FILL, underline: field, isTextBox: true, margin: 0,
  });
  s.addText("РЕШЕНИЕ", { ...small, x: px(298), y: px(505), w: px(250), h: px(16), color: ON_COVER_MUTED });
  s.addText("Чат-бот + мини-приложение", {
    x: px(298), y: px(528), w: px(270), h: px(24), fontFace: FONT, fontSize: 12.75, bold: true,
    color: WHITE, isTextBox: true, margin: 0,
  });
  s.addText("@t403_hakaton_max_bot", {
    x: px(298), y: px(556), w: px(270), h: px(20), fontFace: FONT, fontSize: 10,
    color: ON_COVER_SUB, isTextBox: true, margin: 0,
  });

  // The owner's message.
  s.addText("ВЛАДЕЛЕЦ ОПИСЫВАЕТ БИЗНЕС", { ...small, fontSize: 8.25, x: px(614), y: px(104), w: px(300), h: px(16), color: ON_COVER_MUTED });
  s.addImage({ path: "bubble-owner.png", x: px(614), y: px(132), w: px(272), h: px(110) });
  s.addText(
    "Автосервис на Лесной пр. 12. Диагностика подвески 1500, замена масла 900, шиномонтаж 2400. С\u00A09\u00A0до\u00A020, +7\u00A0812\u00A0000-00-00",
    {
      x: px(631), y: px(142), w: px(240), h: px(90), valign: "middle",
      fontFace: FONT, fontSize: 11, color: WHITE, lineSpacingMultiple: 1.1, isTextBox: true, margin: 0,
    }
  );

  // The storefront - before the answer, so the answer is drawn over its empty lower half.
  phone(s, { x: px(912), y: px(76), w: px(290), name: "storefront", dark: true });

  // The bot's answer, with the open_app button that opens the phone above.
  s.addShape(pres.ShapeType.roundRect, {
    x: px(640), y: px(404), w: px(300), h: px(146), rectRadius: px(20),
    fill: { color: WHITE }, line: { color: WHITE, width: 0 },
    shadow: { type: "outer", color: "000000", blur: 30, offset: 12, angle: 90, opacity: 0.5 },
  });
  s.addShape(pres.ShapeType.ellipse, {
    x: px(658), y: px(420), w: px(22), h: px(22), fill: { color: "1F8A55" }, line: { color: "1F8A55", width: 0 },
  });
  s.addText("✓", {
    x: px(658), y: px(420), w: px(22), h: px(22), align: "center", valign: "middle",
    fontFace: "Segoe UI Symbol", fontSize: 9.5, bold: true, color: WHITE, isTextBox: true, margin: 0,
  });
  s.addText("Витрина готова", {
    x: px(689), y: px(418), w: px(230), h: px(26), valign: "middle",
    fontFace: FONT, fontSize: 12.5, bold: true, color: INK, isTextBox: true, margin: 0,
  });
  s.addText("Клиенты записываются по ссылке, заявки приходят в чат с ботом.", {
    x: px(658), y: px(448), w: px(264), h: px(40), valign: "top",
    fontFace: FONT, fontSize: 10.5, color: INK_2, lineSpacingMultiple: 1.08, isTextBox: true, margin: 0,
  });
  s.addShape(pres.ShapeType.roundRect, {
    x: px(658), y: px(498), w: px(264), h: px(37), rectRadius: px(11),
    fill: { color: MAX_BLUE }, line: { color: MAX_BLUE, width: 0 },
  });
  s.addText("Поделиться ссылкой", {
    x: px(658), y: px(498), w: px(264), h: px(37), align: "center", valign: "middle",
    fontFace: FONT, fontSize: 11, bold: true, color: WHITE, isTextBox: true, margin: 0,
  });

  chrome(s, 2, true, "ХАКАТОН MAX  ·  2026");
}

// ====================================================================================
// 3. Executive summary
// ====================================================================================
{
  const s = lightSlide();
  head(s, "Executive summary", "Что мы сделали");
  s.addText(
    "Микробизнес услуг ведёт запись руками — в личных сообщениях и по телефону. Витрина превращает одно сообщение в мини-приложении MAX в работающую витрину с онлайн-записью, которую клиенты открывают прямо в MAX. Заявки приходят владельцу в чат с ботом.",
    { x: M, y: 1.35, w: CW, h: 0.78, fontFace: FONT, fontSize: 15, color: INK_2, lineSpacingMultiple: 1.15, isTextBox: true, margin: 0 }
  );

  const tw = (CW - 0.3 * 3) / 4;
  const tiles = [
    ["1", "", "сообщение от владельца до готовой витрины"],
    ["~10", "сек", "до ссылки, которую можно отправить клиенту"],
    ["2", "", "касания клиента: выбрать услугу и время"],
    ["0", "", "строк кода и сторонних сервисов у предпринимателя"],
  ];
  tiles.forEach(([v, u, l], i) => {
    stat(s, { x: M + i * (tw + 0.3), y: 2.35, w: tw, h: 1.7, value: v, unit: u, label: l });
  });

  const cw3 = (CW - 0.3 * 2) / 3;
  const cards = [
    ["Для кого", "Самозанятые и микро-ИП в услугах: автосервис, барбершоп, мастер маникюра, репетитор, клининг. 1–5 человек, без сайта и без CRM."],
    ["Что закрывает", "Ручную запись: заявки ночью, двойные брони, переписку вместо работы. Клиент и владелец остаются в MAX."],
    ["Почему именно MAX", "Витрина открывается внутри чат-бота, телефон берётся из аккаунта MAX, ответ приходит туда же, где клиент записывался."],
  ];
  cards.forEach(([t, b], i) => {
    const x = M + i * (cw3 + 0.3);
    card(s, { x, y: 4.35, w: cw3, h: 2.4, tint: true });
    cardText(s, { x, y: 4.35, w: cw3, h: 2.4, title: t, body: b, size: 13 });
  });
  chrome(s, 3, false);
}

// ====================================================================================
// 4. Audience & problem
// ====================================================================================
{
  const s = lightSlide();
  head(s, "Аудитория и проблема", "Кто именно и что именно болит");

  card(s, { x: M, y: 1.45, w: 6.5, h: 3.75, tint: true });
  s.addText("Формулировка проблемы", {
    x: M + 0.28, y: 1.68, w: 6, h: 0.3, fontFace: FONT, fontSize: 14, bold: true, color: MAX_BLUE, isTextBox: true, margin: 0,
  });
  s.addText(
    [
      { text: "Владелец микросервиса в сфере услуг", options: { bold: true, color: INK } },
      { text: " в ситуации, когда клиенты пишут в личные сообщения в любое время, ", options: { color: INK_2 } },
      { text: "хочет", options: { bold: true, color: INK } },
      { text: " принимать записи без ручного согласования каждой, ", options: { color: INK_2 } },
      { text: "но сталкивается с тем", options: { bold: true, color: INK } },
      { text: ", что онлайн-запись требует либо платной CRM с настройкой, либо разработки сайта или бота, ", options: { color: INK_2 } },
      { text: "из-за чего", options: { bold: true, color: INK } },
      { text: " продолжает вести запись вручную — теряет ночные заявки, допускает двойные брони и тратит рабочее время на переписку.", options: { color: INK_2 } },
    ],
    { x: M + 0.28, y: 2.1, w: 5.95, h: 3.0, fontFace: FONT, fontSize: 14.5, lineSpacingMultiple: 1.2, isTextBox: true, margin: 0 }
  );
  s.addText(
    "Сегмент выбран узко намеренно: одна отрасль, один сценарий, один участок процесса, который цифровое решение закрывает от начала до результата.",
    { x: M, y: 5.4, w: 6.5, h: 0.6, fontFace: FONT, fontSize: 11.5, color: INK_3, lineSpacingMultiple: 1.1, isTextBox: true, margin: 0 }
  );

  const gx = 7.45;
  const gw = (W - gx - M - 0.28) / 2;
  const facts = [
    ["6,6", "млн", "субъектов МСП в едином реестре", "ФНС России, июль 2026"],
    ["81,8", "%", "всех действующих юрлиц и ИП — это МСП", "ФНС России, 2026"],
    ["+3,5", "%", "рост числа субъектов МСП год к году", "ФНС России, 2026"],
    ["1,8", "млн", "работников — заявленная кадровая потребность", "Росстат / Роструд, май 2026"],
  ];
  facts.forEach(([v, u, l, src], i) => {
    stat(s, {
      x: gx + (i % 2) * (gw + 0.28),
      y: 1.45 + Math.floor(i / 2) * 2.0,
      w: gw, h: 1.82, value: v, unit: u, label: l, src,
    });
  });
  s.addText(
    "Данные описывают размер и динамику аудитории. Оценку доли микробизнеса без онлайн-записи мы выносим в допущения — см. слайд 14.",
    { x: gx, y: 5.5, w: W - gx - M, h: 0.6, fontFace: FONT, fontSize: 11, color: INK_3, lineSpacingMultiple: 1.1, isTextBox: true, margin: 0 }
  );
  chrome(s, 4, false);
}

// ====================================================================================
// 5. As Is / To Be
// ====================================================================================
{
  const s = lightSlide();
  head(s, "Участок процесса", "Что меняется в пользовательском пути",
    "Мы не автоматизируем весь бизнес-процесс — только тот участок, где эффект заметен сразу.");

  const cw = (CW - 0.35) / 2;
  card(s, { x: M, y: 1.85, w: cw, h: 2.95 });
  s.addText("AS IS — СЕГОДНЯ", {
    x: M + 0.28, y: 2.08, w: cw - 0.56, h: 0.26, fontFace: FONT, fontSize: 11, bold: true, color: "D31169", charSpacing: 1.4, isTextBox: true, margin: 0,
  });
  bullets(s, {
    x: M + 0.28, y: 2.45, w: cw - 0.56, h: 2.2,
    items: [
      "Клиент пишет в личные сообщения или звонит",
      "Владелец отвечает вручную, сверяется с блокнотом",
      "Согласование времени занимает несколько сообщений",
      "Ночные заявки остаются без ответа",
      "Прайс приходится пересказывать каждому заново",
      "Подтверждение и напоминание — снова вручную",
    ],
  });

  const x2 = M + cw + 0.35;
  card(s, { x: x2, y: 1.85, w: cw, h: 2.95, tint: true });
  s.addText("TO BE — С ВИТРИНОЙ", {
    x: x2 + 0.28, y: 2.08, w: cw - 0.56, h: 0.26, fontFace: FONT, fontSize: 11, bold: true, color: "1F8A55", charSpacing: 1.4, isTextBox: true, margin: 0,
  });
  bullets(s, {
    x: x2 + 0.28, y: 2.45, w: cw - 0.56, h: 2.2,
    items: [
      "Исчезает пересказ прайса: услуги и цены видны в витрине",
      "Упрощается выбор времени: клиент берёт слот сам",
      "Автоматически собирается заявка и падает в чат владельца",
      "Быстрее приходит ответ: подтверждение — одна кнопка",
      "Проще результат: запись принимается круглосуточно",
      "Владелец по-прежнему решает сам",
    ],
  });

  card(s, { x: M, y: 5.0, w: CW, h: 1.1 });
  s.addText(
    [
      { text: "Гипотеза. ", options: { bold: true, color: INK } },
      { text: "Если мы поможем владельцу микросервиса принимать записи витриной в MAX, собранной из одного сообщения, доля заявок, дошедших до подтверждения, вырастет, а время на переписку сократится — потому что клиент проходит путь сам, а владельцу остаётся одно решение.", options: { color: INK_2 } },
    ],
    { x: M + 0.28, y: 5.22, w: CW - 0.56, h: 0.7, fontFace: FONT, fontSize: 13, lineSpacingMultiple: 1.15, isTextBox: true, margin: 0 }
  );
  chrome(s, 5, false);
}

// ====================================================================================
// 6. Owner scenario
// ====================================================================================
{
  const s = lightSlide();
  head(s, "Основной сценарий · часть 1", "Владелец: одно сообщение");

  const cw = (CW - 0.3 * 3) / 4;
  const steps = [
    ["Открывает бота", "Находит @t403_hakaton_max_bot и нажимает «Начать» — в ответ одна кнопка «Открыть Витрину». Регистрации нет."],
    ["Описывает бизнес", "Обычными словами, одним сообщением прямо в мини-приложении: название, услуги, цены, часы работы."],
    ["Получает витрину", "Через несколько секунд витрина опубликована: ссылка для клиентов, «Поделиться» в чаты MAX и просмотр глазами клиента."],
    ["Правит текстом", "«Добавь развал-схождение 3000», «убери слоты на завтра» — правка тем же способом, что и создание. Ссылка не меняется."],
  ];
  steps.forEach(([t, b], i) => {
    const x = M + i * (cw + 0.3);
    card(s, { x, y: 1.45, w: cw, h: 2.15 });
    disc(s, x + 0.24, y0(), String(i + 1));
    s.addText(t, { x: x + 0.24, y: 2.1, w: cw - 0.48, h: 0.3, fontFace: FONT, fontSize: 14, bold: true, color: INK, isTextBox: true, margin: 0 });
    s.addText(b, { x: x + 0.24, y: 2.45, w: cw - 0.48, h: 1.0, fontFace: FONT, fontSize: 11.5, color: INK_2, lineSpacingMultiple: 1.1, isTextBox: true, margin: 0 });
  });
  function y0() { return 1.66; }

  card(s, { x: M, y: 3.85, w: CW, h: 2.25 });
  s.addText("Что приходит владельцу в чат", {
    x: M + 0.3, y: 4.05, w: 5.6, h: 0.3, fontFace: FONT, fontSize: 14, bold: true, color: INK, isTextBox: true, margin: 0,
  });
  s.addShape(pres.ShapeType.roundRect, {
    x: M + 0.3, y: 4.42, w: 5.6, h: 1.45, rectRadius: 0.06,
    fill: { color: WHITE }, line: { color: LINE, width: 1 },
  });
  s.addText(
    "Новая заявка · Автосервис на Лесной\n\nДиагностика подвески · Сегодня 14:00\nПётр, +7 999 000-11-22\n«Mazda 6, стучит подвеска»\n[ Открыть заявки ]",
    { x: M + 0.45, y: 4.55, w: 5.3, h: 1.2, fontFace: "Courier New", fontSize: 10, color: INK, lineSpacingMultiple: 1.15, isTextBox: true, margin: 0 }
  );

  const rx = M + 6.2;
  s.addText("Ссылку можно раздать как угодно", {
    x: rx, y: 4.05, w: W - rx - M, h: 0.3, fontFace: FONT, fontSize: 14, bold: true, color: INK, isTextBox: true, margin: 0,
  });
  bullets(s, {
    x: rx, y: 4.45, w: W - rx - M, h: 1.0,
    items: [
      "Отправить в переписке существующим клиентам",
      "Повесить QR-кодом на стойке, в витрине, на визитке",
      "Поставить в описание канала или профиля",
    ],
  });
  s.addText(
    "Ссылка открывает мини-приложение внутри MAX — клиент не уходит в браузер и ничего не устанавливает.",
    { x: rx, y: 5.5, w: W - rx - M, h: 0.45, fontFace: FONT, fontSize: 10.5, color: INK_3, lineSpacingMultiple: 1.1, isTextBox: true, margin: 0 }
  );
  chrome(s, 6, false);
}

// ====================================================================================
// 7. Customer scenario - real screenshots
// ====================================================================================
{
  const s = lightSlide();
  head(s, "Основной сценарий · часть 2", "Клиент: два касания до записи");

  const shots = [
    ["storefront", "Выбор", "Услуги с ценами и длительностью, ближайшие слоты. Имя подставляется из профиля MAX."],
    ["booking", "Отправка", "Телефон берётся из MAX по кнопке — вводить ничего не нужно. Кнопка действия закреплена внизу."],
    ["owner", "Ответ", "Заявка приходит владельцу в чат и в кабинет. Подтверждение — одна кнопка, клиент узнаёт в MAX."],
  ];
  // Sized by height: frame + caption have to fit between the title (ends at 1.24in) and
  // the footer (6.98in). A 2.16in frame is 4.21in tall, which leaves both gaps visible.
  const fw = 2.16;
  const top = 1.5;
  const colw = (CW - 0.5 * 2) / 3;
  shots.forEach(([name, title, note], i) => {
    const x = M + i * (colw + 0.5);
    const fh = phone(s, { x: x + (colw - fw) / 2, y: top, w: fw, name });
    s.addText(title, {
      x, y: top + fh + 0.18, w: colw, h: 0.3, align: "center",
      fontFace: FONT, fontSize: 14, bold: true, color: INK, isTextBox: true, margin: 0,
    });
    s.addText(note, {
      x, y: top + fh + 0.5, w: colw, h: 0.5, align: "center", valign: "top",
      fontFace: FONT, fontSize: 11, color: INK_2, lineSpacingMultiple: 1.1, isTextBox: true, margin: 0,
    });
  });
  chrome(s, 7, false);
}

// ====================================================================================
// 8. Expected effect
// ====================================================================================
{
  const s = lightSlide();
  head(s, "Ожидаемый эффект", "Что должно измениться и как это проверить",
    "На этапе хакатона это гипотезы. Важно не то, какие цифры мы заявим, а то, что каждую можно измерить после пилота.");

  const cw = (CW - 0.35) / 2;
  card(s, { x: M, y: 1.9, w: cw, h: 4.55 });
  s.addText("Метрики, которые снимает сам продукт", {
    x: M + 0.28, y: 2.12, w: cw - 0.56, h: 0.3, fontFace: FONT, fontSize: 14, bold: true, color: INK, isTextBox: true, margin: 0,
  });
  bullets(s, {
    x: M + 0.28, y: 2.6, w: cw - 0.56, h: 3.0, size: 13.5,
    items: [
      "Доля доведённых записей — открыл витрину → отправил заявку",
      "Время до подтверждения — от заявки до нажатия кнопки",
      "Доля заявок вне рабочих часов — замер того, что терялось",
      "Ручных сообщений на одну запись — целевое значение 0",
      "Время от «описал» до первой заявки",
    ],
  });
  s.addText("Все события уже проходят через наш бэкенд — отдельная аналитика не нужна.", {
    x: M + 0.28, y: 5.75, w: cw - 0.56, h: 0.45, fontFace: FONT, fontSize: 11, color: INK_3, isTextBox: true, margin: 0,
  });

  const x2 = M + cw + 0.35;
  card(s, { x: x2, y: 1.9, w: cw, h: 4.55, tint: true });
  s.addText("Как измеряем", {
    x: x2 + 0.28, y: 2.12, w: cw - 0.56, h: 0.3, fontFace: FONT, fontSize: 14, bold: true, color: INK, isTextBox: true, margin: 0,
  });
  bullets(s, {
    x: x2 + 0.28, y: 2.6, w: cw - 0.56, h: 1.6, size: 13.5,
    items: [
      "Базовая линия снимается до запуска: неделя ручного подсчёта",
      "Пилот — та же неделя через витрину, сравнение по тем же величинам",
      "Сравниваем на одном и том же бизнесе, а не между разными",
    ],
  });
  s.addShape(pres.ShapeType.roundRect, {
    x: x2 + 0.28, y: 4.5, w: cw - 0.56, h: 1.6, rectRadius: 0.08,
    fill: { color: WHITE }, line: { color: "C7DBFB", width: 1 },
  });
  s.addText(
    [
      { text: "Критерий успеха пилота: ", options: { bold: true, color: INK } },
      { text: "владелец после недели отказывается возвращаться к ручной записи, и хотя бы одна заявка пришла вне рабочих часов и была подтверждена.", options: { color: INK_2 } },
    ],
    { x: x2 + 0.48, y: 4.72, w: cw - 0.96, h: 1.2, fontFace: FONT, fontSize: 13, lineSpacingMultiple: 1.15, isTextBox: true, margin: 0 }
  );
  chrome(s, 8, false);
}

// ====================================================================================
// 9. Architecture (dark)
// ====================================================================================
{
  const s = darkSlide();
  head(s, "Архитектура", "Состав решения", null, true);

  const colTitles = ["МЕССЕНДЖЕР MAX", "БЭКЕНД AIRUNTIME", "ХРАНЕНИЕ И ИНФРАСТРУКТУРА"];
  const colX = [M, 5.0, 9.4];
  const colW = [3.9, 3.9, 3.38];
  colTitles.forEach((t, i) => {
    s.addText(t, {
      x: colX[i], y: 1.5, w: colW[i], h: 0.25,
      fontFace: FONT, fontSize: 10, bold: true, color: ACCENT_ON_DARK, charSpacing: 1.8, isTextBox: true, margin: 0,
    });
  });

  const boxes = [
    [0, 0, "Чат-бот", "приветствие и уведомления", true],
    [0, 1, "Мини-приложение", "создание, витрина, заявки", true],
    [1, 0, "Вебхук", "секрет в пути, всегда 200", false],
    [1, 1, "API мини-аппа", "вход — подпись initData", false],
    [1, 2, "Генератор витрины", "LLM → валидируемый конфиг", false],
    [2, 0, "PostgreSQL", "владельцы, витрины, заявки", false],
    [2, 1, "Docker + Traefik", "HTTPS, сертификат Минцифры", false],
    [2, 2, "LLM-провайдер", "внешний, с фоллбэком", false],
  ];
  const rowY = [1.85, 2.9, 3.95];
  boxes.forEach(([c, r, t, sub, accent]) => {
    s.addShape(pres.ShapeType.roundRect, {
      x: colX[c], y: rowY[r], w: colW[c], h: 0.82, rectRadius: 0.09,
      fill: { color: accent ? "10284F" : DARK_CARD },
      line: { color: accent ? "3E6DA8" : "2A3550", width: 1 },
    });
    s.addText(t, {
      x: colX[c] + 0.22, y: rowY[r] + 0.13, w: colW[c] - 0.44, h: 0.28,
      fontFace: FONT, fontSize: 13.5, bold: true, color: WHITE, isTextBox: true, margin: 0,
    });
    s.addText(sub, {
      x: colX[c] + 0.22, y: rowY[r] + 0.43, w: colW[c] - 0.44, h: 0.28,
      fontFace: FONT, fontSize: 10.5, color: ON_DARK_2, isTextBox: true, margin: 0,
    });
  });

  [[0, 0], [0, 1], [1, 0], [1, 1], [1, 2]].forEach(([c, r]) => {
    s.addShape(pres.ShapeType.line, {
      x: colX[c] + colW[c] + 0.06, y: rowY[r] + 0.41, w: colX[c + 1] - colX[c] - colW[c] - 0.12, h: 0,
      line: { color: "7FB6FF", width: 1.5, endArrowType: "triangle" },
    });
  });

  const cw3 = (CW - 0.3 * 2) / 3;
  const notes = [
    ["Витрина — это данные, а не код", "Один мультитенантный мини-апп рендерит все витрины из валидированного конфига. «Описал → клиент может записаться» занимает секунды и не ломается от неудачного ответа модели."],
    ["Две разные модели доверия", "Вебхук аутентифицируется секретом в пути — MAX не подписывает доставки. Мини-апп — подписью initData. Ни один эндпоинт не принимает id пользователя из тела запроса."],
    ["Отказоустойчивость по умолчанию", "Вебхук всегда отвечает 200: ошибка обработчика стала бы штормом повторов. Если LLM недоступна, витрина собирается черновиком."],
  ];
  notes.forEach(([t, b], i) => {
    const x = M + i * (cw3 + 0.3);
    card(s, { x, y: 5.05, w: cw3, h: 1.6, dark: true });
    cardText(s, { x, y: 5.05, w: cw3, h: 1.6, title: t, body: b, dark: true, size: 11 });
  });
  chrome(s, 9, true);
}

// ====================================================================================
// 10. MAX capabilities
// ====================================================================================
{
  const s = lightSlide();
  head(s, "Использование платформы", "Что мы берём у MAX и зачем",
    "Каждая возможность закрывает шаг сценария, а не добавлена ради галочки.");

  const cw = (CW - 0.3 * 2) / 3;
  const items = [
    ["open_app", "Витрина открывается внутри чат-бота. Клиент не уходит в браузер и ничего не устанавливает."],
    ["startapp deep link", "Одна ссылка на витрину, пригодная для QR-кода. Она же приводит клиента в бота."],
    ["requestContact()", "Телефон берётся из аккаунта MAX по кнопке и приходит подписанным."],
    ["shareMaxContent()", "«Поделиться» открывает родной экран MAX «Отправить в чат» — ссылка уходит клиентам, не выходя из мессенджера."],
    ["getViewportSize / getLaunchContext", "Интерфейс подстраивается под область просмотра и под источник запуска."],
    ["Обратная связь замыкается в MAX", "Клиент записался в MAX — и ответ получает там же, а не в письме."],
  ];
  items.forEach(([t, b], i) => {
    const x = M + (i % 3) * (cw + 0.3);
    const y = 1.95 + Math.floor(i / 3) * 1.72;
    card(s, { x, y, w: cw, h: 1.55, tint: i === 5 });
    cardText(s, { x, y, w: cw, h: 1.55, title: t, body: b, size: 11.5 });
  });

  card(s, { x: M, y: 5.45, w: CW, h: 0.95 });
  s.addText(
    [
      { text: "Мобильная и веб-версия. ", options: { bold: true, color: INK } },
      { text: "Мини-приложение — обычные HTML, CSS и JavaScript на HTTPS, вёрстка проверена от 320 px. Функциональность одинакова в обеих версиях; MAX Bridge деградирует мягко, если метод в конкретной сборке недоступен.", options: { color: INK_2 } },
    ],
    { x: M + 0.28, y: 5.62, w: CW - 0.56, h: 0.6, fontFace: FONT, fontSize: 12, lineSpacingMultiple: 1.12, isTextBox: true, margin: 0 }
  );
  chrome(s, 10, false);
}

// ====================================================================================
// 11. Data & integrations
// ====================================================================================
{
  const s = lightSlide();
  head(s, "Данные и интеграции", "Откуда берутся данные и что мы с ними делаем");

  const cw = (CW - 0.35) / 2;
  card(s, { x: M, y: 1.5, w: cw, h: 2.05 });
  s.addText("Данные в решении", { x: M + 0.28, y: 1.7, w: cw - 0.56, h: 0.3, fontFace: FONT, fontSize: 14, bold: true, color: INK, isTextBox: true, margin: 0 });
  bullets(s, {
    x: M + 0.28, y: 2.08, w: cw - 0.56, h: 1.3,
    items: [
      "Описание бизнеса — вводит сам владелец в мини-приложении",
      "Профиль и идентификатор MAX — из подписанных параметров",
      "Телефон клиента — только если он сам им поделился",
      "Заявки — то, что клиент выбрал в витрине",
    ],
  });

  card(s, { x: M, y: 3.75, w: cw, h: 2.15 });
  s.addText("Что мы НЕ делаем", { x: M + 0.28, y: 3.95, w: cw - 0.56, h: 0.3, fontFace: FONT, fontSize: 14, bold: true, color: INK, isTextBox: true, margin: 0 });
  bullets(s, {
    x: M + 0.28, y: 4.33, w: cw - 0.56, h: 1.4,
    items: [
      "Не собираем данные, которые пользователь не ввёл сам",
      "Не имитируем интеграции с государственными системами",
      "Не передаём токены и секреты в модель и не храним в репозитории",
      "Не включаем продуктовую аналитику на поверхности мини-аппа",
    ],
  });

  const x2 = M + cw + 0.35;
  card(s, { x: x2, y: 1.5, w: cw, h: 2.05, tint: true });
  s.addText("Интеграции", { x: x2 + 0.28, y: 1.7, w: cw - 0.56, h: 0.3, fontFace: FONT, fontSize: 14, bold: true, color: INK, isTextBox: true, margin: 0 });
  bullets(s, {
    x: x2 + 0.28, y: 2.08, w: cw - 0.56, h: 1.3,
    items: [
      "MAX Bot API — platform-api2.max.ru: вебхук, сообщения, кнопки. Реальная",
      "MAX Bridge — стартовые параметры, запрос контакта. Реальная",
      "LLM-провайдер — описание → конфигурация витрины, с фоллбэком",
    ],
  });

  card(s, { x: x2, y: 3.75, w: cw, h: 2.15 });
  cardText(s, {
    x: x2, y: 3.75, w: cw, h: 2.15,
    title: "Смоделированные данные",
    body: "В демонстрации используются витрины, созданные нами при проверке сценария: «Автосервис на Лесной» и подобные. Это не реальные организации, а примеры, введённые вручную через того же бота, которым пользуется предприниматель. Данные не подставлялись в обход продуктового сценария.",
  });
  chrome(s, 11, false);
}

// ====================================================================================
// 12. Scaling (dark)
// ====================================================================================
{
  const s = darkSlide();
  head(s, "Потенциал масштабирования", "Что остаётся неизменным, а что придётся менять",
    "Сильное решение тиражируется не потому, что перечислено много регионов, а потому, что понятно, как именно.", true);

  const cw = (CW - 0.35) / 2;
  card(s, { x: M, y: 1.95, w: cw, h: 2.5, dark: true });
  s.addText("Ядро продукта — переносится без изменений", {
    x: M + 0.28, y: 2.15, w: cw - 0.56, h: 0.3, fontFace: FONT, fontSize: 14, bold: true, color: ACCENT_ON_DARK, isTextBox: true, margin: 0,
  });
  bullets(s, {
    x: M + 0.28, y: 2.53, w: cw - 0.56, h: 1.75, dark: true, size: 11.5,
    items: [
      "Механика «одно сообщение → работающий сервис в MAX»",
      "Схема витрины: позиции, цена, длительность, слоты, поля заявки",
      "Диалог владельца: создание, правка текстом, публикация",
      "Маршрут заявки: клиент → чат владельца → ответ клиенту",
      "Модель доверия и проверка подписи стартовых параметров",
      "Мультитенантный рендер: новый арендатор не требует деплоя",
    ],
  });

  const x2 = M + cw + 0.35;
  card(s, { x: x2, y: 1.95, w: cw, h: 2.5, dark: true });
  s.addText("Переменная часть — адаптируется под контекст", {
    x: x2 + 0.28, y: 2.15, w: cw - 0.56, h: 0.3, fontFace: FONT, fontSize: 14, bold: true, color: PINK, isTextBox: true, margin: 0,
  });
  bullets(s, {
    x: x2 + 0.28, y: 2.53, w: cw - 0.56, h: 1.75, dark: true, size: 11.5,
    items: [
      "Тип витрины: запись → меню и заказ → заявка. Заложены три типа",
      "Словарь отрасли: «услуга» / «позиция» / «объект» в подсказках модели",
      "Правила слотов: длительность, рабочие часы, праздники региона",
      "Роли участников: один мастер → сотрудники → филиалы",
      "Интеграции: календарь, складские остатки, онлайн-оплата",
    ],
  });

  const cw3 = (CW - 0.3 * 2) / 3;
  const next = [
    ["Куда тиражируем первым", "Общепит: то же «выбрать позицию → оставить заявку». Тип menu уже поддержан."],
    ["Следующий контекст", "Локальная аренда: инвентарь, сутки вместо часов, залог. Понадобится календарь занятости."],
    ["Что понадобится", "Модерация витрин при росте, лимиты на владельца (заложены), партнёрский профиль MAX."],
  ];
  next.forEach(([t, b], i) => {
    const x = M + i * (cw3 + 0.3);
    card(s, { x, y: 4.7, w: cw3, h: 1.55, dark: true });
    cardText(s, { x, y: 4.7, w: cw3, h: 1.55, title: t, body: b, dark: true, size: 11 });
  });
  chrome(s, 12, true);
}

// ====================================================================================
// 13. Pilot
// ====================================================================================
{
  const s = lightSlide();
  head(s, "Сценарий пилота", "Первый ограниченный запуск");

  const cw = (CW - 0.3 * 2) / 3;
  const cells = [
    ["Для кого и где", "5–10 микросервисов услуг в одном районе одного города. Критерий: ведут запись в личных сообщениях и не имеют сайта."],
    ["Как встроится в процесс", "Витрина заменяет пересказ прайса и согласование времени. Приём, оплата, сама услуга — как было."],
    ["Кто участвует", "Владелец (создаёт и подтверждает), его клиенты, мы (смотрим метрики). Внешние владельцы процесса не нужны."],
    ["Как клиенты получат доступ", "Владелец рассылает ссылку существующим клиентам и вешает QR-код на точке. Аудитория у бизнеса уже есть."],
    ["Что понадобится", "Верифицированный профиль на «MAX для партнёров», модерация бота, домен с HTTPS, ключ LLM-провайдера."],
    ["Следующий шаг после пилота", "Если критерий успеха выполнен — открываем тип menu для общепита в том же районе, сохраняя ядро."],
  ];
  cells.forEach(([t, b], i) => {
    const x = M + (i % 3) * (cw + 0.3);
    const y = 1.5 + Math.floor(i / 3) * 1.85;
    card(s, { x, y, w: cw, h: 1.68, tint: i === 5 });
    cardText(s, { x, y, w: cw, h: 1.68, title: t, body: b, size: 11.5 });
  });

  card(s, { x: M, y: 5.35, w: CW, h: 1.0 });
  s.addText(
    [
      { text: "Метрики пилота: ", options: { bold: true, color: INK } },
      { text: "доля доведённых записей, время до подтверждения, доля заявок вне рабочих часов, число ручных сообщений на запись — все снимаются самим продуктом и сравниваются с базовой линией, собранной до запуска.", options: { color: INK_2 } },
    ],
    { x: M + 0.28, y: 5.55, w: CW - 0.56, h: 0.65, fontFace: FONT, fontSize: 12, lineSpacingMultiple: 1.12, isTextBox: true, margin: 0 }
  );
  chrome(s, 13, false);
}

// ====================================================================================
// 14. Limits, assumptions, risks
// ====================================================================================
{
  const s = lightSlide();
  head(s, "Ограничения, риски, допущения", "Что мы знаем и чего пока не знаем",
    "Разделяем подтверждённое источником и то, что остаётся нашей гипотезой.");

  const cw = (CW - 0.3 * 2) / 3;
  const cols = [
    ["ОГРАНИЧЕНИЯ MVP", MAX_BLUE, [
      "Слоты — текстовые варианты, а не календарь занятости",
      "Нет онлайн-оплаты: витрина доводит до заявки",
      "Один владелец на витрину, без сотрудников и ролей",
      "До 10 витрин на владельца",
      "Напоминания клиенту пока не отправляются",
    ]],
    ["ДОПУЩЕНИЯ — ТРЕБУЮТ ПРОВЕРКИ", "D31169", [
      "Что заметная доля микросервисов ведёт запись вручную и считает это проблемой",
      "Что владелец опишет бизнес одним сообщением, а не бросит на полпути",
      "Что клиенту привычнее записаться в MAX, чем написать в личные сообщения",
      "Оценки стоимости альтернатив мы не подтверждали исследованием",
    ]],
    ["РИСКИ", "D31169", [
      "Качество генерации: модель может неверно разобрать описание. Митигация — правка текстом и фоллбэк",
      "Доступность LLM: витрина собирается черновиком, сценарий не блокируется",
      "Модерация и доверие: при росте числа арендаторов нужна проверка содержимого",
    ]],
  ];
  cols.forEach(([t, colour, items], i) => {
    const x = M + i * (cw + 0.3);
    card(s, { x, y: 1.95, w: cw, h: 3.2 });
    s.addText(t, {
      x: x + 0.28, y: 2.15, w: cw - 0.56, h: 0.26,
      fontFace: FONT, fontSize: 10.5, bold: true, color: colour, charSpacing: 1.2, isTextBox: true, margin: 0,
    });
    bullets(s, { x: x + 0.28, y: 2.53, w: cw - 0.56, h: 2.4, size: 11.5, items });
  });

  card(s, { x: M, y: 5.4, w: CW, h: 1.0, tint: true });
  s.addText(
    [
      { text: "Что уже проверено на практике: ", options: { bold: true, color: INK } },
      { text: "сквозной путь «одно сообщение → заявка в чате владельца» проходит целиком и покрыт 54 автотестами, включая попытки подделать подпись стартовых параметров, подставить чужой токен, переиспользовать просроченные параметры и записаться на услугу, которой в витрине нет.", options: { color: INK_2 } },
    ],
    { x: M + 0.28, y: 5.58, w: CW - 0.56, h: 0.68, fontFace: FONT, fontSize: 12, lineSpacingMultiple: 1.12, isTextBox: true, margin: 0 }
  );
  chrome(s, 14, false);
}

// ====================================================================================
// 15. Sources (dark)
// ====================================================================================
{
  const s = darkSlide();
  head(s, "Источники", "На что мы опирались", null, true);

  const cw = (CW - 0.4) / 2;
  card(s, { x: M, y: 1.7, w: cw, h: 3.0, dark: true });
  s.addText("Данные об аудитории", {
    x: M + 0.28, y: 1.92, w: cw - 0.56, h: 0.3, fontFace: FONT, fontSize: 14, bold: true, color: WHITE, isTextBox: true, margin: 0,
  });
  bullets(s, {
    x: M + 0.28, y: 2.3, w: cw - 0.56, h: 1.85, dark: true, size: 11.5,
    items: [
      "ФНС России — Единый реестр субъектов МСП, июль 2026: 6,6 млн субъектов, 81,8% всех действующих юрлиц и ИП, рост 3,5% год к году",
      "Росстат по данным Роструда — заявленная работодателями потребность в работниках, конец мая 2026",
    ],
  });
  s.addText("Показатели приведены по материалам задания трека со ссылкой на первоисточники.", {
    x: M + 0.28, y: 4.22, w: cw - 0.56, h: 0.4, fontFace: FONT, fontSize: 10.5, color: "7C8AA6", isTextBox: true, margin: 0,
  });

  const x2 = M + cw + 0.4;
  card(s, { x: x2, y: 1.7, w: cw, h: 3.0, dark: true });
  s.addText("Техническая документация", {
    x: x2 + 0.28, y: 1.92, w: cw - 0.56, h: 0.3, fontFace: FONT, fontSize: 14, bold: true, color: WHITE, isTextBox: true, margin: 0,
  });
  bullets(s, {
    x: x2 + 0.28, y: 2.3, w: cw - 0.56, h: 2.25, dark: true, size: 11.5,
    items: [
      "MAX для разработчиков — API ботов: методы, вебхуки, типы кнопок",
      "MAX Bridge — стартовые параметры, запрос контакта, контекст запуска",
      "Валидация данных MAX — алгоритм проверки подписи",
      "Правила размещения чат-ботов и мини-приложений на платформе MAX",
      "Минцифры России — корневой сертификат для доступа к API",
    ],
  });

  card(s, { x: M, y: 4.95, w: CW, h: 0.95, dark: true });
  s.addText(
    "Документация MAX развивается: перед сдачей состав API и методов сверялся с актуальной версией разделов «API ботов», «MAX Bridge» и «Валидация данных», а не с примерами из сторонних источников.",
    { x: M + 0.28, y: 5.15, w: CW - 0.56, h: 0.6, fontFace: FONT, fontSize: 11.5, color: ON_DARK_2, lineSpacingMultiple: 1.12, isTextBox: true, margin: 0 }
  );
  chrome(s, 15, true);
}

// ====================================================================================
// 16. Closing - bookends the cover on the same background
// ====================================================================================
// Its one job is to hand the jury a way to try the product in the next ten seconds, hence
// the QR code rather than a list of URLs to retype. Boxes are deck.html's.
{
  const s = coverSlide();
  const small = { fontFace: FONT, fontSize: 8.6, bold: true, charSpacing: 2, isTextBox: true, margin: 0 };

  lockup(s, px(130));
  s.addText("СПАСИБО ЗА ВНИМАНИЕ", { ...small, x: px(72), y: px(194), w: px(520), h: px(20), color: ACCENT_ON_DARK });
  s.addText("Одно сообщение —\nи запись уже в MAX", {
    x: px(70), y: px(222), w: px(740), h: px(140), valign: "top",
    fontFace: FONT, fontSize: 46, bold: true, color: WHITE, lineSpacingMultiple: 0.98, isTextBox: true, margin: 0,
  });
  s.addText(
    "Бот и мини-приложение работают прямо сейчас. Опишите бизнес одним сообщением — секунд через десять у клиентов будет витрина с записью, а у вас заявки в чате.",
    {
      x: px(72), y: px(376), w: px(580), h: px(86), valign: "top",
      fontFace: FONT, fontSize: 14.5, color: ON_COVER_LEAD, lineSpacingMultiple: 1.15, isTextBox: true, margin: 0,
    }
  );

  [
    ["БОТ В MAX", "max.ru/t403_hakaton_max_bot"],
    ["МИНИ-ПРИЛОЖЕНИЕ", "airuntime.ru/max"],
    ["ИСХОДНЫЙ КОД", "github.com/airuntime-ru/airuntime"],
  ].forEach(([label, value], i) => {
    const y = px(499 + i * 34);
    s.addText(label, { ...small, x: px(72), y, w: px(180), h: px(24), valign: "middle", color: ON_COVER_MUTED });
    s.addText(value, {
      x: px(258), y, w: px(420), h: px(24), valign: "middle",
      fontFace: FONT, fontSize: 13, bold: true, color: WHITE, isTextBox: true, margin: 0,
    });
  });

  // The QR card: dark modules on white, the only way a code scans reliably.
  s.addShape(pres.ShapeType.roundRect, {
    x: px(862), y: px(160), w: px(324), h: px(384), rectRadius: px(28),
    fill: { color: WHITE }, line: { color: WHITE, width: 0 },
    shadow: { type: "outer", color: "000000", blur: 40, offset: 14, angle: 90, opacity: 0.55 },
  });
  s.addImage({ path: "qr-bot.png", x: px(906), y: px(190), w: px(236), h: px(236) });
  s.addText("Наведите камеру", {
    x: px(892), y: px(444), w: px(264), h: px(28), align: "center", valign: "middle",
    fontFace: FONT, fontSize: 15, bold: true, color: INK, isTextBox: true, margin: 0,
  });
  s.addText("Откроется бот в MAX — опишите свой бизнес и получите витрину", {
    x: px(892), y: px(476), w: px(264), h: px(44), align: "center", valign: "top",
    fontFace: FONT, fontSize: 11, color: INK_2, lineSpacingMultiple: 1.1, isTextBox: true, margin: 0,
  });

  chrome(s, 16, true);
}

pres.writeFile({ fileName: "presentation.pptx" }).then(() => console.log("wrote presentation.pptx"));
