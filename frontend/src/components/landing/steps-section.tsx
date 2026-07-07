const steps = ["Опишите", "Соберём", "Запустим"];

export function StepsSection() {
  return (
    <section className="border-y border-black/[0.06] py-12 sm:py-16">
      <div className="flex flex-col items-center justify-center gap-8 sm:flex-row sm:gap-0">
        {steps.map((step, index) => (
          <div key={step} className="flex items-center">
            <p className="min-w-[7rem] text-center text-lg font-medium tracking-[-0.02em] text-[var(--ar-black)] sm:text-xl">
              {step}
            </p>
            {index < steps.length - 1 ? (
              <span className="mx-6 hidden h-px w-10 bg-black/10 sm:block md:mx-10 md:w-16" aria-hidden />
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}
