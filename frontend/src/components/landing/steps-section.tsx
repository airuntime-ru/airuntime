import { MessageSquareText, Rocket, WandSparkles } from "lucide-react";

const steps = [
  {
    title: "Опишите идею",
    hint: "Сайт, бот или внутренний инструмент. Достаточно обычного сообщения.",
    icon: MessageSquareText,
  },
  {
    title: "AIRuntime собирает",
    hint: "Планирует, пишет код, готовит окружение, хранит секреты и проверяет результат.",
    icon: WandSparkles,
  },
  {
    title: "Запускайте",
    hint: "Получаете рабочую ссылку, историю изменений и понятный путь к доработкам.",
    icon: Rocket,
  },
];

export function StepsSection() {
  return (
    <section className="py-8 sm:py-12 md:py-20">
      <div className="mb-8 max-w-2xl">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--ar-sky)]">Как это работает</p>
        <h2 className="mt-3 text-3xl font-semibold tracking-tight text-[var(--ar-black)] sm:text-4xl">
          От сообщения до работающего проекта
        </h2>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {steps.map((step, index) => (
          <div
            key={step.title}
            className="glass rounded-[var(--ar-radius-sm)] p-5 transition-transform duration-300 hover:-translate-y-1"
          >
            <div className="flex h-11 w-11 items-center justify-center rounded-[var(--ar-radius-sm)] bg-white text-[var(--ar-sky)] shadow-sm shadow-sky-950/5">
              <step.icon size={20} />
            </div>
            <p className="mt-5 text-sm font-semibold text-[var(--ar-stone)]">0{index + 1}</p>
            <h3 className="mt-1 text-xl font-semibold text-[var(--ar-black)]">{step.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--ar-mist)]">{step.hint}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
