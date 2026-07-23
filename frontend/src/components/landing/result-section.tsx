import { Bot, ExternalLink, GitCommitHorizontal, Globe2, Terminal } from "lucide-react";

import { LandingSection, SectionHeading, StatusChip } from "@/components/landing/section";
import { resultCopy } from "@/lib/landing/content";

export function ResultSection() {
  return (
    <LandingSection id="capabilities" ariaLabelledBy="result-title" tone="muted">
      <SectionHeading
        eyebrow={resultCopy.eyebrow}
        title={resultCopy.title}
        description={resultCopy.subtitle}
        id="result-title"
      />

      <div className="mt-10 grid gap-4 lg:grid-cols-12">
        <article className="overflow-hidden rounded-[1rem] border border-black/[0.09] bg-white lg:col-span-7">
          <div className="flex items-center justify-between gap-3 border-b border-black/[0.07] px-4 py-3 sm:px-5">
            <div className="flex items-center gap-2">
              <Globe2 size={16} className="text-[var(--ar-sky)]" aria-hidden />
              <p className="text-sm font-semibold text-[var(--ar-black)]">Публичный сайт</p>
            </div>
            <StatusChip tone="live">HTTPS</StatusChip>
          </div>
          <div className="bg-[linear-gradient(180deg,#f8fafc_0%,#eef3f9_100%)] px-4 py-5 sm:px-6 sm:py-6">
            <div className="rounded-[0.75rem] border border-black/[0.08] bg-white p-4 shadow-[0_12px_30px_rgba(7,20,38,0.06)] sm:p-5">
              <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--ar-stone)]">
                autoservice.airuntime.ru
              </p>
              <h3 className="mt-3 text-xl font-semibold tracking-[-0.02em] text-[var(--ar-black)]">
                Запись в автосервис
              </h3>
              <p className="mt-2 text-sm text-[var(--ar-mist)]">
                Выберите услугу, дату и оставьте контакты — заявка сразу попадает в работу.
              </p>
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                <div className="rounded-[0.55rem] border border-black/[0.08] bg-[#f7f8fa] px-3 py-2.5 text-sm text-[var(--ar-graphite)]">
                  Диагностика
                </div>
                <div className="rounded-[0.55rem] border border-black/[0.08] bg-[#f7f8fa] px-3 py-2.5 text-sm text-[var(--ar-graphite)]">
                  Замена масла
                </div>
              </div>
              <div className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-[var(--ar-sky)]">
                Открыть сайт
                <ExternalLink size={14} aria-hidden />
              </div>
            </div>
          </div>
        </article>

        <div className="grid gap-4 lg:col-span-5">
          <article className="rounded-[1rem] border border-black/[0.09] bg-white p-4 sm:p-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Bot size={16} className="text-[var(--ar-cyan)]" aria-hidden />
                <p className="text-sm font-semibold text-[var(--ar-black)]">Telegram-бот</p>
              </div>
              <StatusChip tone="mint">Online</StatusChip>
            </div>
            <div className="mt-4 space-y-2 rounded-[0.75rem] bg-[#eef2f7] p-3">
              <p className="rounded-lg rounded-bl-md bg-white px-3 py-2 text-sm text-[var(--ar-black)]">
                Запишите меня на завтра, 11:00
              </p>
              <p className="ml-auto max-w-[90%] rounded-lg rounded-br-md bg-[var(--ar-black)] px-3 py-2 text-sm text-white">
                Готово. Заявка принята, пришлю напоминание.
              </p>
            </div>
          </article>

          <article className="rounded-[1rem] border border-black/[0.09] bg-white p-4 sm:p-5">
            <div className="flex items-center gap-2">
              <Terminal size={16} className="text-[var(--ar-sky)]" aria-hidden />
              <p className="text-sm font-semibold text-[var(--ar-black)]">Docker build</p>
            </div>
            <p className="mt-3 font-mono text-xs leading-relaxed text-[var(--ar-graphite)]">
              Step 8/8 : CMD [&quot;node&quot;, &quot;server.js&quot;]
              <br />
              Successfully built · exit 0
            </p>
          </article>

          <article className="rounded-[1rem] border border-black/[0.09] bg-white p-4 sm:p-5">
            <div className="flex items-center gap-2">
              <GitCommitHorizontal size={16} className="text-[var(--ar-indigo)]" aria-hidden />
              <p className="text-sm font-semibold text-[var(--ar-black)]">Последнее изменение в git</p>
            </div>
            <p className="mt-3 font-mono text-xs text-[var(--ar-graphite)]">
              a3f91c2 · feat: booking form + schedule
            </p>
            <p className="mt-2 text-sm text-[var(--ar-mist)]">Публичный URL уже указывает на эту версию.</p>
          </article>
        </div>
      </div>
    </LandingSection>
  );
}
