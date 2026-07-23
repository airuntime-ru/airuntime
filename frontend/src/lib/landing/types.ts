export type NavItem = {
  href: string;
  label: string;
};

export type FaqItem = {
  question: string;
  answer: string;
};

export type ComparisonRow = {
  generator: string;
  airuntime: string;
};

export type UseCase = {
  id: string;
  title: string;
  detail: string;
};

export type AudienceItem = {
  id: string;
  title: string;
  task: string;
  outcome: string;
  artifact: string;
};

export type SecurityPoint = {
  title: string;
  detail: string;
};

export type VersionEvent = {
  version: string;
  label: string;
  detail: string;
  current?: boolean;
};

export type HowStep = {
  id: string;
  title: string;
  detail: string;
  status: string;
};

export type DemoPhase =
  | "user"
  | "analyze"
  | "structure"
  | "build"
  | "fix"
  | "deploy"
  | "live";
