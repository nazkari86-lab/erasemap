const path = require("node:path");
const PptxGenJS = require("pptxgenjs");
const {
  imageSizingContain,
  warnIfSlideHasOverlaps,
  warnIfSlideElementsOutOfBounds,
} = require("./pptxgenjs_helpers");

const REPO = path.resolve(__dirname, "..");
const OUT = path.join(REPO, "competition", "EraSeMap_RKNP_ISEF_RU.pptx");
const ASSETS = path.join(REPO, "docs", "assets");
const PRESENTATION_ASSETS = path.join(REPO, "competition", "assets");

const pptx = new PptxGenJS();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "EraSeMap";
pptx.subject = "Evidence-led deletion verification";
pptx.title = "EraSeMap — проверяемый путь удаления данных";
pptx.company = "EraSeMap Research";
pptx.lang = "ru-RU";
pptx.theme = {
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  lang: "ru-RU",
};
pptx.defineLayout({ name: "ERA_WIDE", width: 13.333, height: 7.5 });
pptx.layout = "ERA_WIDE";

const W = 13.333;
const H = 7.5;
const F_HEAD = "Arial";
const F_BODY = "Arial";
const C = {
  bg: "F3F0E8",
  paper: "FBFAF6",
  ink: "173F38",
  ink2: "2D5B50",
  muted: "4F6960",
  line: "C8D6CE",
  sage: "CBE4D6",
  sage2: "E2F0E8",
  teal: "079E94",
  teal2: "14B8A6",
  coral: "E8795E",
  coral2: "F5D2C8",
  ochre: "D49B43",
  lilac: "7077D7",
  blue: "2E9BD5",
  white: "FFFFFF",
  black: "111C1A",
};

function addText(slide, text, x, y, w, h, size, color = C.ink, opts = {}) {
  slide.addText(text, {
    x, y, w, h,
    fontFace: opts.fontFace || F_BODY,
    fontSize: size,
    color,
    bold: opts.bold || false,
    italic: opts.italic || false,
    align: opts.align || "left",
    valign: opts.valign || "mid",
    margin: opts.margin === undefined ? 0 : opts.margin,
    breakLine: false,
    paraSpaceAfterPt: opts.paraSpaceAfterPt || 0,
    charSpacing: opts.charSpacing || 0,
    isTextBox: true,
  });
}

function shape(slide, type, x, y, w, h, fill = null, line = null, extra = {}) {
  const options = { x, y, w, h, ...extra };
  if (fill) options.fill = typeof fill === "string" ? { color: fill } : fill;
  if (line) options.line = typeof line === "string" ? { color: line, width: 1 } : line;
  slide.addShape(type, options);
}

function line(slide, x, y, w, h, color = C.line, width = 1.2, transparency = 0) {
  shape(slide, pptx.ShapeType.line, x, y, w, h, null, { color, width, transparency });
}

function circle(slide, x, y, d, fill, border = null, transparency = 0) {
  shape(slide, pptx.ShapeType.ellipse, x, y, d, d, { color: fill, transparency }, border ? { color: border, width: 1 } : null);
}

function rounded(slide, x, y, w, h, fill = C.paper, border = C.line, radius = 0.14, transparency = 0) {
  shape(slide, pptx.ShapeType.roundRect, x, y, w, h, { color: fill, transparency }, border ? { color: border, width: 1 } : null, { radius });
}

function organicBlob(slide, x, y, w, h, fill, transparency = 30, rotate = 0) {
  shape(slide, pptx.ShapeType.ellipse, x, y, w, h, { color: fill, transparency }, null, { rotate });
}

function addDecor(slide, variant = 0) {
  // Organic motif is strongest on the opening/closing slides and deliberately faint inside the deck.
  const hero = variant === 1 || variant === 13;
  if (hero) {
    organicBlob(slide, 10.84, 0.0, 2.40, 1.35, variant % 2 ? C.sage : C.coral2, 40, 14);
    organicBlob(slide, 11.75, 0.18, 1.3, 0.88, variant % 2 ? C.coral2 : C.sage, 32, -18);
  } else {
    organicBlob(slide, 11.15, 0.04, 1.92, 0.96, variant % 2 ? C.sage : C.coral2, 70, 14);
  }
  if (hero || variant === 6 || variant === 10) {
    organicBlob(slide, 0.0, 6.82, 2.1, 0.58, C.sage, 62, -9);
  }
  line(slide, 11.15, 1.05, 1.45, 0.38, C.line, 1.0, 22);
  line(slide, 0.28, 0.88, 0.76, -0.42, C.line, 1.0, 16);
  circle(slide, 0.64, 0.25, 0.16, C.teal);
  circle(slide, 0.86, 0.43, 0.09, C.coral);
}

function footer(slide, section, n) {
  addText(slide, `ERASEMAP  /  ${section.toUpperCase()}`, 0.82, 0.25, 3.3, 0.18, 8.5, C.teal, { bold: true, charSpacing: 0.4 });
  addText(slide, String(n).padStart(2, "0"), 12.2, 0.25, 0.45, 0.18, 8.5, C.muted, { bold: true, align: "right" });
  addText(slide, "проверка удаления по доказательствам", 0.82, 7.22, 3.0, 0.14, 7.2, C.muted, { charSpacing: 0.1 });
  addText(slide, "РКНП · ISEF 2026", 11.35, 7.22, 1.08, 0.14, 7.2, C.muted, { bold: true, align: "right" });
}

function title(slide, section, heading, n, sub = "") {
  addDecor(slide, n);
  footer(slide, section, n);
  addText(slide, heading, 0.82, 0.92, 11.6, 0.56, 27, C.ink, { fontFace: F_HEAD, bold: true });
  if (sub) addText(slide, sub, 0.84, 1.54, 11.2, 0.32, 13.3, C.muted, { bold: false });
}

function sectionLabel(slide, text, x = 0.84, y = 0.64, w = 1.42) {
  rounded(slide, x, y, w, 0.25, C.sage2, null, 0.12, 0);
  addText(slide, text.toUpperCase(), x + 0.1, y + 0.03, w - 0.2, 0.17, 7.5, C.teal, { bold: true, align: "center", charSpacing: 0.5 });
}

function node(slide, x, y, w, h, label, sub, color, fill = C.paper) {
  rounded(slide, x, y, w, h, fill, color, 0.2, 0);
  circle(slide, x + 0.16, y + 0.16, 0.16, color);
  addText(slide, label, x + 0.42, y + 0.1, w - 0.55, 0.24, 13, C.ink, { bold: true });
  if (sub) addText(slide, sub, x + 0.42, y + 0.37, w - 0.55, 0.17, 9.5, C.muted);
}

function kpi(slide, x, y, value, label, color = C.teal) {
  addText(slide, value, x, y, 1.6, 0.38, 24, color, { fontFace: F_HEAD, bold: true });
  addText(slide, label, x, y + 0.38, 1.8, 0.24, 9.5, C.muted);
}

function chartFrame(slide, x, y, w, h, label) {
  rounded(slide, x, y, w, h, C.paper, C.line, 0.18, 0);
  rounded(slide, x + 0.16, y + 0.14, Math.min(2.65, w - 0.32), 0.27, C.ink, null, 0.12, 0);
  addText(slide, label, x + 0.26, y + 0.18, Math.min(2.45, w - 0.52), 0.15, 8.2, C.white, { bold: true, align: "center", charSpacing: 0.25 });
}

function addChart(slide, file, x, y, w, h, alt) {
  slide.addImage({ path: file, ...imageSizingContain(file, x, y, w, h), altText: alt });
}

function comparisonLane(slide, x, y, w, label, ours, baseline, direction, baselineName, color = C.teal) {
  rounded(slide, x, y, w, 0.72, C.paper, C.line, 0.18, 0);
  circle(slide, x + 0.18, y + 0.2, 0.28, color);
  addText(slide, label, x + 0.62, y + 0.12, 2.55, 0.2, 11.2, C.ink, { bold: true });
  addText(slide, direction, x + 0.62, y + 0.38, 1.55, 0.14, 8.5, C.muted);
  addText(slide, "EraSeMap", x + 2.95, y + 0.12, 1.15, 0.16, 8.7, C.teal, { bold: true, align: "right" });
  addText(slide, ours, x + 4.16, y + 0.08, 0.95, 0.25, 15, C.teal, { fontFace: F_HEAD, bold: true, align: "right" });
  line(slide, x + 5.25, y + 0.36, 0.35, 0, C.line, 1.4, 0);
  addText(slide, baselineName, x + 5.62, y + 0.12, 1.0, 0.16, 8.7, C.muted, { bold: true, align: "right" });
  addText(slide, baseline, x + 6.68, y + 0.08, 0.98, 0.25, 15, color === C.coral ? C.coral : C.ink2, { fontFace: F_HEAD, bold: true, align: "right" });
}

function notes(slide, text) {
  slide.addNotes(text);
}

// 01 — cover
{
  const s = pptx.addSlide();
  s.background = { color: C.bg };
  addDecor(s, 1);
  addText(s, "ERASEMAP  /  RESEARCH PROTOTYPE", 0.82, 0.44, 3.9, 0.22, 9, C.teal, { bold: true, charSpacing: 0.8 });
  addText(s, "Удаление —\nэто не кнопка.", 0.82, 1.55, 6.1, 1.4, 42, C.ink, { fontFace: F_HEAD, bold: true });
  addText(s, "Это проверяемый путь.", 0.86, 3.16, 5.4, 0.38, 23, C.coral, { fontFace: F_HEAD, bold: true });
  addText(s, "EraSeMap проверяет, исчезли ли данные из копий, производных\nи будущих каналов восстановления.", 0.86, 3.76, 5.55, 0.62, 16.5, C.muted);
  rounded(s, 0.86, 5.02, 4.95, 0.52, C.sage2, C.teal, 0.18, 0);
  addText(s, "DELETE 200 OK  →  карта  →  проверка  →  сертификат", 1.04, 5.17, 4.58, 0.2, 10.5, C.ink, { bold: true, align: "center" });
  // Flow visual: edges first, then organic nodes.
  line(s, 8.0, 2.0, 1.2, 0.7, C.line, 2.2, 12);
  line(s, 9.2, 2.7, 1.18, -0.15, C.line, 2.2, 12);
  line(s, 8.0, 2.0, 0.78, 1.72, C.line, 2.2, 12);
  line(s, 8.78, 3.72, 1.48, -1.02, C.line, 2.2, 12);
  node(s, 7.25, 1.55, 1.68, 0.72, "источник", "исходная запись", C.blue, C.sage2);
  node(s, 9.18, 2.34, 1.75, 0.72, "производная", "шаблон / индекс", C.teal, C.sage2);
  node(s, 8.72, 3.66, 1.72, 0.72, "возврат", "резерв / восстановление", C.coral, C.coral2);
  node(s, 6.9, 3.76, 1.6, 0.72, "доказательство", "квитанция + повтор", C.lilac, C.sage2);
  rounded(s, 9.75, 4.85, 2.18, 0.76, C.ink, C.ink, 0.26, 0);
  addText(s, "VERIFY", 9.75, 5.08, 2.18, 0.25, 15, C.white, { fontFace: F_HEAD, bold: true, align: "center" });
  addText(s, "Проверяем путь, а не обещание «удалено»." , 0.86, 6.58, 5.0, 0.24, 12.3, C.teal, { bold: true });
  addText(s, "проверка удаления по доказательствам", 0.82, 7.22, 3.0, 0.14, 7.2, C.muted);
  addText(s, "РКНП · ISEF 2026", 11.35, 7.22, 1.08, 0.14, 7.2, C.muted, { bold: true, align: "right" });
  addText(s, "01", 12.2, 0.25, 0.45, 0.18, 8.5, C.muted, { bold: true, align: "right" });
  notes(s, "Начните с простой мысли: ответ DELETE 200 OK подтверждает только команду, но не исчезновение копий и производных. EraSeMap превращает обещание удаления в проверяемый путь.");
}

// 02 — problem
{
  const s = pptx.addSlide(); s.background = { color: C.bg };
  title(s, "Проблема", "Проблема: запись не живёт в одном месте", 2, "Копии, производные и отложенные задачи создают скрытый путь назад.");
  sectionLabel(s, "одна персона", 0.84, 2.22, 1.5);
  const layers = [
    ["Исходная запись", "пользователь / аккаунт", C.blue],
    ["Биометрический шаблон", "биометрический вектор", C.teal],
    ["Кэш и реплика", "быстрый путь чтения", C.ochre],
    ["Резерв / восстановление", "отложенная копия", C.coral],
    ["Влияние на модель", "сигнал в модели", C.lilac],
  ];
  layers.forEach(([label, sub, color], i) => {
    const y = 2.68 + i * 0.56;
    circle(s, 0.94, y + 0.1, 0.27, color);
    addText(s, label, 1.38, y, 2.65, 0.24, 13.2, C.ink, { bold: true });
    addText(s, sub, 1.38, y + 0.27, 2.35, 0.18, 9.3, C.muted);
    if (i < layers.length - 1) line(s, 1.07, y + 0.38, 0, 0.48, C.line, 1.5, 4);
  });
  addText(s, "Один человек → несколько представлений данных", 0.84, 5.84, 3.35, 0.36, 15, C.ink2, { fontFace: F_HEAD, bold: true });
  addText(s, "Удаление одной строки не закрывает весь граф.", 0.84, 6.29, 3.4, 0.22, 11.5, C.muted);
  // Right-side recovery path.
  rounded(s, 4.8, 2.22, 7.65, 4.15, C.paper, C.line, 0.24, 0);
  addText(s, "Скрытый путь назад", 5.2, 2.53, 4.6, 0.3, 20, C.ink, { fontFace: F_HEAD, bold: true });
  addText(s, "Если производное осталось, запись можно восстановить снова.", 5.2, 2.92, 5.7, 0.22, 11.5, C.muted);
  line(s, 6.2, 4.22, 1.68, -0.7, C.line, 2.2, 5);
  line(s, 7.88, 3.52, 1.62, 0.72, C.line, 2.2, 5);
  line(s, 6.2, 4.22, 1.38, 1.02, C.line, 2.2, 5);
  line(s, 7.58, 5.16, 1.92, -0.96, C.line, 2.2, 5);
  node(s, 5.65, 3.86, 1.7, 0.72, "источник", "строка аккаунта", C.blue, C.sage2);
  node(s, 7.52, 3.2, 1.9, 0.72, "шаблон", "лицо / признаки", C.teal, C.sage2);
  node(s, 9.45, 3.86, 1.65, 0.72, "кэш", "реплика", C.ochre, C.sage2);
  node(s, 7.25, 4.92, 1.92, 0.72, "резерв", "восстановление", C.coral, C.coral2);
  rounded(s, 5.28, 5.74, 6.67, 0.38, C.coral2, C.coral, 0.18, 0);
  addText(s, "«DELETE 200 OK»  ≠  данные исчезли", 5.5, 5.84, 6.25, 0.16, 11.2, C.coral, { bold: true, align: "center" });
  notes(s, "Покажите, что один пользователь представлен не одной строкой: есть шаблон, кэш, backup и влияние на модель. Любая из ветвей может стать путём восстановления.");
}

// 03 — one algorithm
{
  const s = pptx.addSlide(); s.background = { color: C.bg };
  title(s, "Метод", "Один алгоритм. Пять вопросов.", 3, "Модули помогают аудиту, но публичный объект — один понятный вердикт EraSeMap.");
  const steps = [
    ["01", "Что существует?", "карта копий", C.blue],
    ["02", "Где путь назад?", "активные пробы", C.teal],
    ["03", "Что удалить?", "минимальный план", C.ochre],
    ["04", "Что будет завтра?", "проверка во времени", C.coral],
    ["05", "Что доказано?", "сертификат", C.lilac],
  ];
  steps.forEach(([n, q, sub, color], i) => {
    const x = 0.86 + i * 2.43;
    if (i < steps.length - 1) line(s, x + 1.65, 4.05, 0.76, 0, C.line, 2.4, 8);
    rounded(s, x, 3.18, 1.72, 1.02, C.paper, color, 0.28, 0);
    circle(s, x + 0.17, 3.38, 0.28, color);
    addText(s, n, x + 0.19, 3.42, 0.25, 0.13, 7.3, C.white, { bold: true, align: "center" });
    addText(s, q, x + 0.53, 3.36, 1.02, 0.35, 12.1, C.ink, { bold: true });
    addText(s, sub, x + 0.17, 4.42, 1.4, 0.18, 9.6, C.muted, { align: "center" });
  });
  rounded(s, 1.36, 5.35, 10.62, 0.58, C.sage2, C.teal, 0.24, 0);
  addText(s, "карта  →  поиск  →  минимум действий  →  проверка во времени  →  сертификат", 1.62, 5.53, 10.1, 0.18, 13, C.ink, { bold: true, align: "center" });
  addText(s, "Это одна процедура с пятью проверяемыми выходами — не набор несвязанных алгоритмов.", 1.2, 6.32, 10.95, 0.24, 12.5, C.muted, { align: "center" });
  notes(s, "Проговорите пять вопросов вместо названий внутренних модулей. Так алгоритм понятен комиссии: карта, поиск пути, минимальный план, временная проверка и сертификат.");
}

// 04 — verdict
{
  const s = pptx.addSlide(); s.background = { color: C.bg };
  title(s, "Вердикт", "Сильная система умеет сказать: INCOMPLETE", 4, "Если путь ещё активен, EraSeMap не выдаёт ложную уверенность.");
  rounded(s, 0.86, 2.25, 4.15, 3.8, C.coral2, C.coral, 0.28, 0);
  addText(s, "INCOMPLETE", 1.16, 2.7, 3.55, 0.55, 31, C.coral, { fontFace: F_HEAD, bold: true, align: "center" });
  addText(s, "Найден путь восстановления", 1.25, 3.42, 3.4, 0.25, 13.5, C.ink, { bold: true, align: "center" });
  line(s, 1.7, 4.42, 1.0, 0, C.coral, 3, 3);
  line(s, 2.7, 4.42, 0.88, 0, C.coral, 3, 3);
  circle(s, 1.42, 4.28, 0.28, C.blue);
  circle(s, 3.58, 4.28, 0.28, C.teal);
  addText(s, "источник", 1.16, 4.75, 0.85, 0.2, 10.5, C.muted, { align: "center" });
  addText(s, "шаблон", 3.36, 4.75, 1.15, 0.2, 10.5, C.muted, { align: "center" });
  addText(s, "План удаления ещё не закрыл\nпроизводный шаблон.", 1.26, 5.3, 3.35, 0.46, 13.2, C.ink2, { bold: true, align: "center" });
  rounded(s, 5.55, 2.25, 6.92, 3.8, C.paper, C.line, 0.28, 0);
  addText(s, "COMPLETE только если", 5.95, 2.7, 6.1, 0.3, 21, C.ink, { fontFace: F_HEAD, bold: true, align: "center" });
  addText(s, "P  ∧  D  ∧  T", 6.08, 3.34, 5.85, 0.68, 37, C.teal, { fontFace: F_HEAD, bold: true, align: "center" });
  const gates = [["P", "физическое", "все пути закрыты", C.blue], ["D", "производное", "шаблоны + индексы", C.teal], ["T", "временное", "повтор не вернёт данные", C.coral]];
  gates.forEach(([letter, name, sub, color], i) => {
    const x = 5.98 + i * 2.12;
    circle(s, x + 0.54, 4.35, 0.34, color);
    addText(s, letter, x + 0.54, 4.45, 0.34, 0.12, 10, C.white, { bold: true, align: "center" });
    addText(s, name, x, 4.82, 1.55, 0.28, 10.3, C.ink, { bold: true, align: "center" });
    addText(s, sub, x, 5.13, 1.55, 0.18, 8.8, C.muted, { align: "center" });
  });
  notes(s, "Ключевая сила — безопасный отказ. COMPLETE выдаётся только при одновременном физическом, производном и временном закрытии.");
}

// 05 — one-request walkthrough
{
  const s = pptx.addSlide(); s.background = { color: C.bg };
  title(s, "Пример", "Один запрос: как EraSeMap проверяет удаление", 5, "Клиент просит удалить биометрический шаблон. Система проходит пять шагов, прежде чем сказать «готово».");
  const items = [
    ["Запрос", "клиент просит удалить", C.blue], ["Карта", "где лежат копии", C.teal], ["Закрытие", "закрываем нужные артефакты", C.ochre], ["Проверка", "проба + время", C.coral], ["Вердикт", "COMPLETE / INCOMPLETE", C.lilac],
  ];
  items.forEach(([label, sub, color], i) => {
    const x = 0.92 + i * 2.43;
    if (i < items.length - 1) line(s, x + 1.54, 3.77, 0.88, 0, C.line, 2.3, 9);
    circle(s, x + 0.44, 3.1, 0.82, color, color, 0);
    addText(s, label, x, 4.07, 1.7, 0.28, 14, C.ink, { fontFace: F_HEAD, bold: true, align: "center" });
    addText(s, sub, x, 4.42, 1.7, 0.2, 10, C.muted, { align: "center" });
  });
  rounded(s, 1.3, 5.34, 4.78, 0.65, C.paper, C.line, 0.2, 0);
  addText(s, "COMPLETE ⇔ все известные пути закрыты", 1.55, 5.55, 4.3, 0.2, 16, C.teal, { fontFace: F_HEAD, bold: true, align: "center" });
  rounded(s, 6.63, 5.34, 5.35, 0.65, C.sage2, C.teal, 0.2, 0);
  addText(s, "INCOMPLETE = риск найден", 6.9, 5.55, 4.8, 0.2, 12.7, C.ink, { bold: true, align: "center" });
  addText(s, "Если путь неизвестен или риск найден — EraSeMap не говорит «готово».", 1.1, 6.44, 11.2, 0.25, 12, C.muted, { align: "center" });
  notes(s, "Расскажите это как одну историю: запрос идёт от карты данных к закрытию копий, затем к активной проверке и только после этого к вердикту. Если найден риск или путь не подтверждён, EraSeMap не говорит COMPLETE.");
}

// 06 — safety evidence
{
  const s = pptx.addSlide(); s.background = { color: C.bg };
  title(s, "Доказательства", "Сравнение 1 / ложное «ГОТОВО»", 6, "Безопасность: false-COMPLETE — система сказала «готово», хотя данные ещё можно восстановить. Ниже — лучше.");
  chartFrame(s, 0.84, 2.18, 9.18, 4.02, "БЕЗОПАСНОСТЬ  ·  НИЖЕ ЛУЧШЕ");
  addChart(s, path.join(PRESENTATION_ASSETS, "readable_pcug.png"), 1.02, 2.72, 8.82, 3.17, "Крупное сравнение false COMPLETE");
  kpi(s, 10.38, 2.42, "0 / 60", "открытый перенос", C.teal);
  kpi(s, 10.38, 3.55, "0 / 75", "исходный протокол", C.teal2);
  kpi(s, 10.38, 4.68, "20 / 20", "повторная проверка", C.blue);
  addText(s, "Ограниченный протокол;\nне заявление о внедрении.", 10.38, 5.65, 2.2, 0.38, 10, C.muted, { align: "left" });
  notes(s, "Чётко назовите метрику: false COMPLETE, а не общая точность. Ноль — безопасный результат на ограниченном протоколе, не обещание промышленного внедрения.");
}

// 07 — efficiency evidence
{
  const s = pptx.addSlide(); s.background = { color: C.bg };
  title(s, "Доказательства", "Сравнение 2 / эффективность", 7, "Одна задача удаления: стоимость действий, время, байты и успешное завершение. Ниже — лучше.");
  chartFrame(s, 0.84, 2.18, 9.46, 4.0, "СТОИМОСТЬ  ·  ВРЕМЯ  ·  БАЙТЫ  ·  НИЖЕ ЛУЧШЕ");
  addChart(s, path.join(PRESENTATION_ASSETS, "readable_cdc.png"), 1.01, 2.7, 9.1, 3.03, "Крупное сравнение стоимости, времени и байтов");
  kpi(s, 10.58, 2.42, "17.64×", "быстрее полной пересборки", C.teal);
  kpi(s, 10.58, 3.55, "−94.62%", "перезаписанные байты", C.teal2);
  kpi(s, 10.58, 4.68, "17", "средняя стоимость", C.blue);
  rounded(s, 10.49, 5.66, 2.25, 0.5, C.sage2, C.teal, 0.18, 0);
  addText(s, "Сначала safety,\nпотом оптимизация.", 10.62, 5.78, 2.0, 0.25, 10.2, C.ink, { bold: true, align: "center" });
  notes(s, "Сравнение показывает эффективность после прохождения safety gates. Это нормализованная bounded задача, поэтому не переносите цифры автоматически на production.");
}

// 08 — hidden path
{
  const s = pptx.addSlide(); s.background = { color: C.bg };
  title(s, "Доказательства", "Сравнение 3 / поиск скрытого пути", 8, "Активная проба сокращает пространство гипотез после каждого ответа системы восстановления.");
  chartFrame(s, 0.84, 2.18, 8.28, 4.02, "ПОИСК ПУТИ  ·  НИЖЕ ЛУЧШЕ");
  addChart(s, path.join(PRESENTATION_ASSETS, "readable_ghostgraph.png"), 1.02, 2.58, 7.9, 3.54, "Крупное сравнение активных проб");
  rounded(s, 9.38, 2.18, 3.1, 4.02, C.paper, C.line, 0.25, 0);
  addText(s, "Почему это важно", 9.68, 2.55, 2.5, 0.3, 20, C.ink, { fontFace: F_HEAD, bold: true, align: "center" });
  [["7", "EraSeMap", C.teal], ["13", "случайный", C.muted], ["49", "полный перебор", C.muted]].forEach(([v, l, c], i) => {
    const y = 3.24 + i * 0.62;
    addText(s, v, 9.72, y, 0.55, 0.36, 24, c, { fontFace: F_HEAD, bold: true });
    addText(s, l, 10.45, y + 0.08, 1.6, 0.18, 11, C.ink, { bold: true });
  });
  rounded(s, 9.68, 5.76, 2.5, 0.4, C.sage2, C.teal, 0.18, 0);
  addText(s, "50 / 50 новых семейств вне разработки", 9.8, 5.86, 2.26, 0.2, 8.4, C.ink, { bold: true, align: "center" });
  notes(s, "Активная проба выбирает следующий тест так, чтобы разделить оставшиеся гипотезы. Результат family-held-out показывает переносимость на новые семейства топологий, но не production deployment.");
}

// 09 — system comparison
{
  const s = pptx.addSlide(); s.background = { color: C.bg };
  title(s, "Доказательства", "Сравнение 4 / итог по критериям", 9, "Четыре независимых критерия — не единый сводный балл.");
  rounded(s, 0.84, 2.18, 8.46, 4.02, C.paper, C.line, 0.25, 0);
  addText(s, "Где EraSeMap лучше", 1.2, 2.5, 4.3, 0.3, 20, C.ink, { fontFace: F_HEAD, bold: true });
  comparisonLane(s, 1.2, 2.92, 7.75, "Безопасность", "0 / 100", "100 / 100", "ложное «ГОТОВО» ↓", "чек-лист", C.teal);
  comparisonLane(s, 1.2, 3.70, 7.75, "Будущая регенерация", "30 / 30", "0 / 30", "найденные риски ↑", "снимок", C.teal2);
  comparisonLane(s, 1.2, 4.48, 7.75, "Стоимость действий", "17", "48.67", "средняя стоимость ↓", "удалить всё", C.ochre);
  comparisonLane(s, 1.2, 5.26, 7.75, "Время задачи", "5.67%", "100%", "норм. время ↓", "пересобрать всё", C.blue);
  rounded(s, 9.56, 2.18, 2.92, 4.02, C.paper, C.line, 0.25, 0);
  addText(s, "Где не заявляем", 9.8, 2.55, 2.44, 0.3, 19, C.coral, { fontFace: F_HEAD, bold: true, align: "center" });
  addText(s, "Кандидат MUFAC не прошёл\nпорог полезности для\nоставшихся пользователей.", 9.82, 3.28, 2.38, 0.56, 10.3, C.ink, { bold: true, align: "center" });
  rounded(s, 9.82, 4.05, 2.38, 0.42, C.coral2, C.coral, 0.16, 0);
  addText(s, "FAIL · полезность", 9.98, 4.18, 2.06, 0.14, 9, C.coral, { bold: true, align: "center" });
  addText(s, "Точная пересборка сохраняет\nбезопасность, но не ускоряет работу.", 9.7, 4.8, 2.6, 0.42, 10.2, C.muted, { align: "center" });
  addText(s, "Метрики взяты из отдельных\nэкспериментов с одним протоколом.", 9.78, 5.64, 2.46, 0.34, 9, C.muted, { align: "center" });
  notes(s, "Не скрывайте отрицательный model-unlearning результат. Сильная область проекта — evidence-led storage deletion; модельный канал доказывается отдельно. Подчеркните, что четыре строки не складываются в один рейтинг.");
}

// 10 — theory
{
  const s = pptx.addSlide(); s.background = { color: C.bg };
  title(s, "Теория", "Формула вердикта и три проверяемых условия", 10, "Короткая запись облегчает объяснение; мы проверяем совместную корректность условий.");
  rounded(s, 1.1, 2.17, 11.15, 1.05, C.paper, C.teal, 0.26, 0);
  addText(s, "COMPLETE  ⇔  P  ∧  D  ∧  T", 1.35, 2.48, 10.65, 0.4, 32, C.teal, { fontFace: F_HEAD, bold: true, align: "center" });
  const gates = [["P", "физическое", "все пути закрыты", C.blue], ["D", "производное", "шаблоны + индексы", C.teal], ["T", "временное", "повтор не вернёт данные", C.coral]];
  gates.forEach(([l, name, sub, color], i) => {
    const x = 1.1 + i * 3.78;
    rounded(s, x, 3.75, 3.34, 1.35, C.paper, color, 0.2, 0);
    circle(s, x + 0.24, 4.1, 0.44, color);
    addText(s, l, x + 0.24, 4.22, 0.44, 0.13, 13, C.white, { fontFace: F_HEAD, bold: true, align: "center" });
    addText(s, name, x + 0.82, 4.0, 2.2, 0.24, 12.2, C.ink, { bold: true });
    addText(s, sub, x + 0.82, 4.33, 2.22, 0.2, 9.4, C.muted);
  });
  addText(s, "3 072 / 3 072 формальных проверок прошли в proof harness проекта.", 1.12, 5.67, 11.1, 0.26, 12.5, C.ink2, { bold: true, align: "center" });
  addText(s, "Это проверка соответствия протоколу, а не доказательство внедрения в production.", 1.2, 6.18, 10.95, 0.22, 11.2, C.muted, { align: "center" });
  notes(s, "Формула — удобная рамка для комиссии. Важно уточнить: formal checks подтверждают conformance протокола и composition property, но не заменяют внешний production pilot.");
}

// 11 — model channel
{
  const s = pptx.addSlide(); s.background = { color: C.bg };
  title(s, "Ограничение", "Влияние на модель — отдельный канал", 11, "Model unlearning проверяется отдельно и не заменяет физическое удаление.");
  rounded(s, 0.84, 2.18, 5.55, 3.85, C.paper, C.line, 0.24, 0);
  addText(s, "Что проверяем", 1.22, 2.55, 4.75, 0.28, 20, C.ink, { fontFace: F_HEAD, bold: true });
  [["01", "влияние / полезность для оставшихся", C.blue], ["02", "сравнение с точным переобучением", C.teal], ["03", "атака на приватность + порог качества", C.coral]].forEach(([n, t, c], i) => {
    const y = 3.28 + i * 0.72;
    circle(s, 1.25, y, 0.3, c);
    addText(s, n, 1.25, y + 0.09, 0.3, 0.1, 7.5, C.white, { bold: true, align: "center" });
    addText(s, t, 1.78, y + 0.02, 3.95, 0.22, 12.2, C.ink, { bold: true });
  });
  rounded(s, 6.86, 2.18, 5.62, 3.85, C.coral2, C.coral, 0.24, 0);
  addText(s, "Реальный результат", 7.25, 2.55, 4.84, 0.28, 20, C.coral, { fontFace: F_HEAD, bold: true });
  addText(s, "Кандидат MUFAC", 7.25, 3.28, 3.9, 0.26, 16, C.ink, { bold: true });
  rounded(s, 7.25, 3.68, 2.62, 0.31, C.paper, C.coral, 0.16, 0);
  addText(s, "FAIL · порог полезности", 7.38, 3.77, 2.36, 0.12, 8.1, C.coral, { bold: true, align: "center" });
  addText(s, "Точное переобучение", 7.25, 4.53, 3.9, 0.26, 16, C.teal, { bold: true });
  rounded(s, 7.25, 4.93, 2.52, 0.31, C.sage2, C.teal, 0.16, 0);
  addText(s, "PASS · безопасно / без ускорения", 7.38, 5.02, 2.26, 0.12, 8.1, C.teal, { bold: true, align: "center" });
  addText(s, "Честная граница: приближённое переобучение не считается успешным без проверки полезности.", 1.25, 6.45, 10.9, 0.25, 11.6, C.muted, { align: "center" });
  notes(s, "Поясните термины: retained utility — полезность для оставшихся пользователей; exact fallback — безопасное переобучение. Отрицательный результат здесь усиливает научную честность.");
}

// 12 — novelty
{
  const s = pptx.addSlide(); s.background = { color: C.bg };
  title(s, "Позиционирование", "Новизна — в составе доказательств", 12, "Не четыре разрозненных алгоритма, а одна процедура, закрывающая три риска.");
  addText(s, "Три отличительных объекта", 0.84, 2.2, 4.1, 0.3, 20, C.ink, { fontFace: F_HEAD, bold: true });
  [["путь восстановления", "ищем, где запись может появиться снова", C.blue], ["временное закрытие", "проверяем будущую регенерацию", C.teal], ["сертификат удаления", "показываем границу неизвестности", C.lilac]].forEach(([name, sub, color], i) => {
    const y = 2.93 + i * 0.83;
    circle(s, 0.98, y, 0.38, color);
    addText(s, name, 1.58, y + 0.02, 2.25, 0.22, 13, C.ink, { bold: true });
    addText(s, sub, 1.58, y + 0.32, 3.45, 0.18, 9.7, C.muted);
  });
  rounded(s, 6.08, 2.2, 6.39, 3.92, C.paper, C.line, 0.24, 0);
  addText(s, "Лестница доказательств", 6.55, 2.56, 5.42, 0.3, 20, C.ink, { fontFace: F_HEAD, bold: true, align: "center" });
  [["пилот внедрения", false], ["скрытая проверка", false], ["семейства вне разработки", true], ["скрытая выборка", true], ["воспроизводимая лаборатория", true]].forEach(([label, pass], i) => {
    const y = 3.24 + i * 0.45;
    rounded(s, 6.58, y, pass ? 4.3 - i * 0.16 : 2.2, 0.26, pass ? C.sage2 : C.coral2, pass ? C.teal : C.coral, 0.13, 0);
    addText(s, pass ? "✓" : "→", 6.75, y + 0.055, 0.37, 0.11, 8, pass ? C.teal : C.coral, { bold: true, align: "center" });
    addText(s, label, 7.2, y + 0.055, 3.3, 0.11, 8.8, pass ? C.ink : C.coral, { bold: true });
  });
  addText(s, "Сейчас: сильная воспроизводимость и ограниченные внешние данные.\nСледующий честный шаг — независимая скрытая проверка.", 6.52, 5.62, 5.52, 0.4, 10.7, C.muted, { align: "center" });
  notes(s, "Новизна формулируется как композиция: recovery-path discovery, temporal closure и сертификат с границей неизвестности. Отдельно покажите, какие доказательства уже есть, а какие ещё нужны.");
}

// 13 — close
{
  const s = pptx.addSlide(); s.background = { color: C.bg };
  addDecor(s, 13);
  addText(s, "ERASEMAP  /  CONCLUSION", 0.82, 0.44, 3.6, 0.22, 9, C.teal, { bold: true, charSpacing: 0.8 });
  addText(s, "Проверять путь,\nа не обещание.", 0.82, 1.55, 5.85, 1.32, 42, C.ink, { fontFace: F_HEAD, bold: true });
  addText(s, "EraSeMap превращает удаление из одной команды\nв проверяемый, устойчивый во времени вердикт.", 0.86, 3.55, 5.65, 0.56, 16.5, C.muted);
  rounded(s, 0.86, 4.86, 4.95, 0.58, C.sage2, C.teal, 0.22, 0);
  addText(s, "Следующий эксперимент: независимая скрытая проверка", 1.04, 5.05, 4.58, 0.18, 10.5, C.ink, { bold: true, align: "center" });
  // Organic closing mark.
  line(s, 8.4, 2.2, 1.32, 0.88, C.line, 2.3, 8);
  line(s, 9.72, 3.08, -0.62, 1.18, C.line, 2.3, 8);
  line(s, 9.1, 4.26, 1.35, -0.7, C.line, 2.3, 8);
  circle(s, 7.62, 1.9, 1.62, C.sage, C.teal, 15);
  addText(s, "MAP", 7.62, 2.55, 1.62, 0.2, 15, C.teal, { fontFace: F_HEAD, bold: true, align: "center" });
  circle(s, 9.52, 3.0, 1.28, C.coral2, C.coral, 12);
  addText(s, "PROVE", 9.52, 3.54, 1.28, 0.2, 13, C.coral, { fontFace: F_HEAD, bold: true, align: "center" });
  circle(s, 7.25, 4.8, 1.05, C.sage2, C.lilac, 10);
  addText(s, "SAFE", 7.25, 5.23, 1.05, 0.18, 11, C.lilac, { fontFace: F_HEAD, bold: true, align: "center" });
  addText(s, "проверка удаления по доказательствам", 0.82, 7.22, 3.0, 0.14, 7.2, C.muted);
  addText(s, "РКНП · ISEF 2026", 11.35, 7.22, 1.08, 0.14, 7.2, C.muted, { bold: true, align: "right" });
  addText(s, "13", 12.2, 0.25, 0.45, 0.18, 8.5, C.muted, { bold: true, align: "right" });
  notes(s, "Закройте одной фразой: EraSeMap проверяет путь, а не обещание. Если спросят о следующем шаге, называйте independent hidden challenge и production pilot.");
}

for (const slide of pptx._slides) {
  warnIfSlideHasOverlaps(slide, pptx);
  warnIfSlideElementsOutOfBounds(slide, pptx);
}

pptx.writeFile({ fileName: OUT });
console.log(JSON.stringify({ output: OUT, slides: pptx._slides.length }, null, 2));
