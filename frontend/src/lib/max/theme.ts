import type { ServiceConfig } from "@/lib/max/api";

export type StorefrontMood = ServiceConfig["mood"];

function blobOf(config: ServiceConfig): string {
  return [config.title, config.tagline, config.about, ...config.items.map((item) => item.title)]
    .join(" ")
    .toLowerCase();
}

/**
 * Existing storefronts were generated before mood/comment_hint existed. Infer from the
 * copy so a tutor page stops looking (and asking) like the auto-shop demo without a regen.
 */
export function storefrontMood(config: ServiceConfig): StorefrontMood {
  if (config.mood && config.mood !== "bold") return config.mood;
  const blob = blobOf(config);
  if (/репетитор|урок|егэ|огэ|занят|математик|английск|физик|школ|подготовк/.test(blob)) {
    return "calm";
  }
  if (/кафе|кофе|пекарн|ресторан|пицц|суши|десерт|кондитер/.test(blob)) return "warm";
  if (/консульт|юрист|бухгалтер|агентств|презентац/.test(blob)) return "minimal";
  if (/авто|машин|барбер|стрижк|ремонт|шиномонт/.test(blob)) return "bold";
  return config.mood || "bold";
}

export function commentHint(config: ServiceConfig): string {
  const written = (config.comment_hint || "").trim();
  if (written && !/марка авто/i.test(written)) return written;
  const blob = blobOf(config);
  if (/репетитор|урок|егэ|огэ|занят|математик|английск|физик|школ/.test(blob)) {
    return "Класс, тема занятия, онлайн или очно";
  }
  if (/авто|машин|шиномонт|двигател|подвеск/.test(blob)) {
    return "Марка, год, что случилось";
  }
  if (/кафе|кофе|пекарн|ресторан|пицц|суши/.test(blob)) {
    return "Аллергии, пожелания к заказу";
  }
  if (config.kind === "menu") return "Аллергии, пожелания к заказу";
  if (config.kind === "landing") return "Что нужно обсудить";
  return written || "Пожелания к записи";
}

export function kindKicker(kind: ServiceConfig["kind"]): string {
  if (kind === "menu") return "Меню";
  if (kind === "landing") return "Заявка";
  return "Запись";
}

export function readableAccentText(hex: string): "#ffffff" | "#10141c" {
  const raw = hex.replace("#", "");
  const normalized = raw.length === 3 ? raw.split("").map((part) => part + part).join("") : raw;
  if (!/^[0-9a-f]{6}$/i.test(normalized)) return "#ffffff";
  const channels = [0, 2, 4].map(
    (offset) => parseInt(normalized.slice(offset, offset + 2), 16) / 255
  );
  const linear = channels.map((channel) =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  );
  const luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
  // 0.179 is the WCAG crossover where black starts having the higher contrast ratio.
  return luminance > 0.179 ? "#10141c" : "#ffffff";
}
