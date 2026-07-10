const STATUS_LABELS: Record<string, string> = {
  created: "Создан",
  ready: "Готов к запуску",
  deploying: "Запускается",
  live: "Запущен",
  stopped: "Остановлен",
  needs_configuration: "Нужна настройка",
  telegram_ready: "Бот настроен",
  blocked: "Заблокирован модерацией",
};

export function projectStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

const DEPLOYMENT_STATUS_LABELS: Record<string, string> = {
  completed: "Развёрнут",
  failed: "Ошибка",
  cancelled: "Отменён",
  running: "Запускается",
  queued: "В очереди",
};

export function deploymentStatusLabel(status: string): string {
  return DEPLOYMENT_STATUS_LABELS[status] ?? status;
}

export function isProjectRunning(status: string): boolean {
  return status === "live" || status === "deploying";
}

export function canStopProject(status: string): boolean {
  return isProjectRunning(status);
}

export function canStartProject(status: string): boolean {
  return (
    status === "created" ||
    status === "stopped" ||
    status === "ready" ||
    status === "needs_configuration" ||
    status === "telegram_ready"
  );
}
