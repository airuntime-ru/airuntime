import { Accordion } from "@/components/ui/accordion";

const faqs = [
  {
    question: "Нужен ли опыт разработки?",
    answer: "Нет. Вы описываете результат, а AIRuntime помогает пройти путь от идеи до запуска.",
  },
  {
    question: "Что можно собрать?",
    answer: "Лендинг, Telegram-бота, MVP, внутренний инструмент, форму заявок, небольшой SaaS или backend-сервис.",
  },
  {
    question: "Где хранятся ключи и токены?",
    answer: "В разделе секретов проекта. Их не нужно вставлять в сообщения и пересылать в чат.",
  },
  {
    question: "Можно ли дорабатывать проект после запуска?",
    answer: "Да. Вы возвращаетесь в чат проекта, описываете изменение и запускаете новую версию.",
  },
];

export function FaqSection() {
  return (
    <section className="py-10 sm:py-16">
      <div className="mb-8 max-w-2xl">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--ar-sky)]">FAQ</p>
        <h2 className="mt-3 text-3xl font-semibold tracking-tight text-[var(--ar-black)] sm:text-4xl">
          Вопросы перед первым запуском
        </h2>
      </div>
      <Accordion items={faqs} />
    </section>
  );
}
