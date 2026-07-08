import { Accordion } from "@/components/ui/accordion";
import Link from "next/link";

const faqs = [
  {
    question: "Нужен ли опыт разработки?",
    answer: "Нет. Опишите результат обычными словами.",
  },
  {
    question: "Что можно собрать?",
    answer: "Лендинг, Telegram-бота или небольшой MVP.",
  },
  {
    question: "Сколько времени занимает запуск?",
    answer: "Обычно первые рабочие версии готовы в тот же день.",
  },
  {
    question: "Можно ли доработать проект после запуска?",
    answer: "Да. Продолжаете в том же чате: правки, новые функции, деплой.",
  },
  {
    question: "Нужно ли разбираться в серверах и доменах?",
    answer: "Нет. Сервис сам подготавливает инфраструктуру и выкладывает проект.",
  },
  {
    question: "Подходит ли для теста идеи на рынок?",
    answer: "Да. Это как раз формат быстрых MVP для проверки гипотезы.",
  },
];

export function FaqSection() {
  return (
    <section className="flex min-h-[100svh] flex-col items-center justify-center py-16 text-center">
      <p className="mb-3 text-xs font-medium uppercase tracking-[0.28em] text-[var(--ar-stone)] sm:text-sm">
        FAQ
      </p>
      <h2 className="text-4xl font-semibold tracking-[-0.03em] text-[var(--ar-black)] sm:text-6xl">
        Вопросы
      </h2>
      <p className="mx-auto mt-4 max-w-xl text-base text-[var(--ar-mist)] sm:text-lg">
        Коротко о том, как работает запуск проектов в AIRuntime.
      </p>

      <div className="mx-auto mt-10 w-full max-w-3xl rounded-2xl border border-black/10 bg-white/85 p-4 text-left shadow-[0_20px_60px_rgba(7,20,38,0.07)] sm:p-6">
        <Accordion items={faqs} />
      </div>

      <Link
        href="/auth/login"
        className="mt-8 inline-flex h-12 items-center justify-center rounded-full bg-[var(--ar-black)] px-7 text-sm font-medium text-white transition-transform hover:scale-[1.02] active:scale-[0.98]"
      >
        Запустить проект
      </Link>
    </section>
  );
}
