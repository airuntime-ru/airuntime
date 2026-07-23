import { Bot, ExternalLink, Globe2 } from "lucide-react";

import { LandingSection, SectionHeading } from "@/components/landing/section";
import { resultCopy } from "@/lib/landing/content";

const trustStrip = [
  "Docker build ✓",
  "HTTPS ✓",
  "Git version ✓",
  "Runtime live ✓",
] as const;

export function ResultSection() {
  return (
    <LandingSection id="capabilities" ariaLabelledBy="result-title" tone="muted">
      <SectionHeading title={resultCopy.title} description={resultCopy.subtitle} id="result-title" />

      <div className="mt-10 overflow-hidden rounded-[1rem] border border-black/[0.08] bg-white">
        <div className="grid lg:grid-cols-2">
          <article className="border-b border-black/[0.06] p-5 sm:p-6 lg:border-b-0 lg:border-r">
            <div className="flex items-center gap-2">
              <Globe2 size={16} className="text-[var(--ar-sky)]" aria-hidden />
              <h3 className="text-sm font-semibold text-[var(--ar-black)]">Публичный сайт</h3>
            </div>
            <div className="mt-4 rounded-[0.75rem] bg-[#f4f7fb] p-4 sm:p-5">
              <p className="font-mono text-xs text-[var(--ar-stone)]">autoservice.airuntime.ru</p>
              <p className="mt-3 text-xl font-semibold tracking-[-0.02em] text-[var(--ar-black)]">
                Запись в автосервис
              </p>
              <p className="mt-2 text-sm leading-relaxed text-[var(--ar-mist)]">
                Услуга, дата и контакты — заявка сразу попадает в работу.
              </p>
              <p className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-[var(--ar-sky)]">
                Открыть сайт
                <ExternalLink size={14} aria-hidden />
              </p>
            </div>
          </article>

          <article className="p-5 sm:p-6">
            <div className="flex items-center gap-2">
              <Bot size={16} className="text-[var(--ar-sky)]" aria-hidden />
              <h3 className="text-sm font-semibold text-[var(--ar-black)]">Telegram-бот</h3>
            </div>
            <div className="mt-4 space-y-2 rounded-[0.75rem] bg-[#f4f7fb] p-4">
              <p className="max-w-[92%] rounded-lg rounded-bl-md bg-white px-3 py-2 text-sm text-[var(--ar-black)]">
                Запишите меня на завтра, 11:00
              </p>
              <p className="ml-auto max-w-[90%] rounded-lg rounded-br-md bg-[var(--ar-black)] px-3 py-2 text-sm text-white">
                Готово. Заявка принята, пришлю напоминание.
              </p>
            </div>
          </article>
        </div>

        <div className="flex flex-wrap gap-x-5 gap-y-2 border-t border-black/[0.06] bg-[#fafbfc] px-5 py-3.5 sm:px-6">
          {trustStrip.map((item) => (
            <span key={item} className="font-mono text-xs text-[var(--ar-graphite)] sm:text-[13px]">
              {item}
            </span>
          ))}
        </div>
      </div>
    </LandingSection>
  );
}
