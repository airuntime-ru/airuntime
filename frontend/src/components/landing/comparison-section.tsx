import { Card } from "@/components/ui/card";

export function ComparisonSection() {
  return (
    <section>
      <h2 className="mb-6 text-3xl font-semibold text-[var(--ar-cloud)]">A new category of software</h2>
      <div className="grid gap-4 md:grid-cols-2">
        <Card hover={false}>
          <p className="text-sm uppercase tracking-wide text-[var(--ar-stone)]">Traditional development</p>
          <p className="mt-3 text-[var(--ar-mist)]">idea → code → server → deployment → problems</p>
        </Card>
        <Card>
          <p className="text-sm uppercase tracking-wide text-[var(--ar-sky)]">AIRuntime</p>
          <p className="mt-3 text-xl text-[var(--ar-cloud)]">idea → AI → live application</p>
        </Card>
      </div>
    </section>
  );
}
