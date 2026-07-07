import { Card } from "@/components/ui/card";

const features = [
  "AI development",
  "Automatic deployment",
  "Custom domains",
  "Isolated infrastructure",
  "Runtime monitoring",
  "Safe rollback",
];

export function FeaturesSection() {
  return (
    <section>
      <h2 className="mb-6 text-3xl font-semibold text-[var(--ar-cloud)]">Everything you need to ship</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {features.map((feature) => (
          <Card key={feature} hover={false}>
            <p className="text-lg font-medium text-[var(--ar-cloud)]">{feature}</p>
            <p className="mt-2 text-sm text-[var(--ar-mist)]">Built into the runtime, invisible until you need it.</p>
          </Card>
        ))}
      </div>
    </section>
  );
}
