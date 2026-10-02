import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const [year, month, day] = value.slice(0, 10).split("-");
  if (!year || !month || !day) return value;
  return `${day}/${month}/${year}`;
}

export function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" }).format(date);
}

export function placeLabel(article: string | null, clause: string | null, point: string | null): string {
  return [article ? `Điều ${article}` : "", clause ? `Khoản ${clause}` : "", point ? `Điểm ${point}` : ""]
    .filter(Boolean)
    .join(" · ");
}

export function clip(value: string, max = 280): string {
  const text = value.trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max).trimEnd()}…`;
}
