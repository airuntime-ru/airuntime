import { Accordion } from "@/components/ui/accordion";

const faqs = [
  {
    question: "Нужен ли опыт разработки?",
    answer: "Нет. Опишите результат обычными словами.",
  },
  {
    question: "Что можно собрать?",
    answer: "Лендинг, Telegram-бота или небольшой MVP.",
  },
];

export function FaqSection() {
  return (
    <section className="py-12 sm:py-16">
      <h2 className="mb-6 text-center text-xl font-semibold tracking-[-0.02em] text-[var(--ar-black)] sm:text-2xl">
        Вопросы
      </h2>
      <div className="mx-auto max-w-xl">
        <Accordion items={faqs} />
      </div>
    </section>
  );
}
