import { Accordion } from "@/components/ui/accordion";

const faqs = [
  {
    question: "Do I need infrastructure experience?",
    answer: "No. AIRuntime owns runtime, secrets, deployment, and monitoring boundaries.",
  },
  {
    question: "What can I build?",
    answer: "Telegram bots, websites, SaaS backends, landing pages, and internal tools.",
  },
  {
    question: "How are secrets handled?",
    answer: "Encrypted at rest and never injected into model prompts.",
  },
  {
    question: "Can I use my own domain?",
    answer: "Yes. Configure APP_DOMAIN and reverse proxy settings for production.",
  },
];

export function FaqSection() {
  return (
    <section>
      <h2 className="mb-6 text-3xl font-semibold text-[var(--ar-cloud)]">FAQ</h2>
      <Accordion items={faqs} />
    </section>
  );
}
