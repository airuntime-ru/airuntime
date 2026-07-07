import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const tiers = [
  { name: "Starter", price: "Free", detail: "1B credits to explore and ship your first product." },
  { name: "Pro", price: "$49", detail: "For founders shipping multiple products every month." },
  { name: "Team", price: "$199", detail: "Shared workspaces, roles, and priority runtime capacity." },
];

export function PricingSection() {
  return (
    <section>
      <h2 className="mb-6 text-3xl font-semibold text-[var(--ar-cloud)]">Pricing</h2>
      <div className="grid gap-4 md:grid-cols-3">
        {tiers.map((tier) => (
          <Card key={tier.name} className="flex flex-col">
            <p className="text-sm text-[var(--ar-stone)]">{tier.name}</p>
            <p className="mt-2 text-3xl font-semibold text-[var(--ar-cloud)]">{tier.price}</p>
            <p className="mt-3 flex-1 text-sm text-[var(--ar-mist)]">{tier.detail}</p>
            <Button variant="outline" className="mt-6 w-full">
              Choose {tier.name}
            </Button>
          </Card>
        ))}
      </div>
    </section>
  );
}
