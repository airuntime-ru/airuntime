import type { FaqItem, HowStep, NavItem, TrustPoint, UseCase } from "./types";

export const LOGIN_HREF = "/auth/login";
export const PROCESS_ANCHOR = "#how-it-works";

export const navItems: NavItem[] = [
  { href: "#capabilities", label: "Результат" },
  { href: "#how-it-works", label: "Как работает" },
  { href: "#trust", label: "Платформа" },
  { href: "#faq", label: "FAQ" },
];

export const heroCopy = {
  titleLine1: "Опишите идею.",
  titleLine2: "Получите работающий проект.",
  subtitle:
    "AIRuntime создаст сайт или Telegram-бота, проверит сборку и запустит готовую версию.",
  primaryCta: "Создать проект",
  secondaryCta: "Посмотреть, как это работает",
} as const;

export const resultCopy = {
  title: "Что вы получаете",
  subtitle: "Публичный сайт или активный Telegram-бот — без ручной сборки и деплоя.",
} as const;

export const howCopy = {
  title: "Как это работает",
  subtitle: "Один чат — от описания задачи до рабочей ссылки.",
} as const;

export const howSteps: HowStep[] = [
  {
    id: "describe",
    title: "Опишите",
    detail: "Расскажите обычными словами, какой результат нужен.",
  },
  {
    id: "build",
    title: "AIRuntime соберёт",
    detail: "Агент создаст проект, проверит сборку и исправит ошибки.",
  },
  {
    id: "run",
    title: "Получите ссылку",
    detail: "Сайт откроется по HTTPS, а Telegram-бот начнёт работать.",
  },
];

export const useCasesCopy = {
  title: "Что можно создать",
  subtitle: "Типовые задачи, с которых удобно начать.",
} as const;

export const useCases: UseCase[] = [
  {
    id: "company",
    title: "Сайт компании",
    detail: "Услуги, контакты и форма заявки.",
    prompt: "«Сделай сайт автосервиса с записью»",
  },
  {
    id: "landing",
    title: "Лендинг или промо",
    detail: "Короткая страница с понятным призывом к действию.",
    prompt: "«Нужен лендинг для запуска курса»",
  },
  {
    id: "booking",
    title: "Сервис записи",
    detail: "Слоты, заявки и подтверждения клиентам.",
    prompt: "«Сайт записи к мастеру с уведомлениями»",
  },
  {
    id: "telegram",
    title: "Telegram-бот или сайт + бот",
    detail: "Диалоги, заявки или общая логика с сайтом.",
    prompt: "«Бот принимает заявки и шлёт напоминания»",
  },
];

export const trustCopy = {
  title: "AIRuntime отвечает не только за код",
  subtitle: "Платформа собирает, запускает и сохраняет проект.",
  audienceLine:
    "Для предпринимателей, маркетологов и продуктовых команд, которым нужно быстро проверить идею.",
} as const;

export const trustPoints: TrustPoint[] = [
  {
    title: "Реальная Docker-сборка",
    detail: "Проект собирается в контейнере, а не остаётся набором файлов.",
  },
  {
    title: "Автоматический deploy",
    detail: "После успешной сборки платформа запускает версию сама.",
  },
  {
    title: "Базы и сервисы",
    detail: "Postgres, Redis и другие подключаются по запросу агента.",
  },
  {
    title: "Секреты вне модели",
    detail: "Токены и ключи вводятся в настройках и не уходят в LLM.",
  },
  {
    title: "Версии и rollback",
    detail: "История изменений сохраняется, к прошлой версии можно вернуться.",
  },
];

export const faqs: FaqItem[] = [
  {
    question: "Нужен ли опыт разработки?",
    answer:
      "Нет. Опишите нужный результат обычными словами — агент спроектирует структуру, напишет код и запустит проект.",
  },
  {
    question: "Что можно создать?",
    answer:
      "Сайт компании, лендинг, сервис записи, Telegram-бота или смешанный вариант — сайт и бот вместе. Стек выбирает агент под задачу.",
  },
  {
    question: "Сколько занимает запуск?",
    answer:
      "Первая версия обычно появляется в одной сессии чата. Сложность задачи влияет на число итераций сборки.",
  },
  {
    question: "Кому принадлежит код?",
    answer:
      "Вы можете просматривать файлы, скачивать архивы версий и продолжать работу в кабинете. Условия сервиса фиксируются при регистрации.",
  },
  {
    question: "Что происходит при ошибке сборки?",
    answer:
      "Агент читает логи сборки, исправляет проект и повторяет build. Ошибка не остаётся ручной DevOps-задачей.",
  },
];

export const finalCtaCopy = {
  title: "Опишите задачу — получите работающий сайт или Telegram-бота.",
  subtitle: "Создайте первый проект в чате. AIRuntime соберёт и запустит его за вас.",
  primaryCta: "Создать проект",
  secondaryCta: "Уже есть аккаунт? Войти",
} as const;

export const seoCopy = {
  title: "AIRuntime — от идеи до работающего сайта или Telegram-бота",
  description:
    "Опишите задачу в чате. AIRuntime создаст сайт или Telegram-бота, проверит сборку и запустит готовую версию.",
} as const;

export const demoScript = {
  userMessage: "Сделай сайт для записи в автосервис",
  steps: [
    "Структура готова",
    "Docker build прошёл",
    "Проект запущен",
  ] as const,
  url: "autoservice.airuntime.ru",
} as const;
