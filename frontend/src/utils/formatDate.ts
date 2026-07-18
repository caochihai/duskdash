import type { Conversation, ConversationGroupKey } from '@/types/conversation';

const timeFormatter = new Intl.DateTimeFormat('vi-VN', {
  hour: '2-digit',
  minute: '2-digit',
});

const dateFormatter = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
});

const dateTimeFormatter = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

/** "14:35" */
export function formatTime(iso: string): string {
  return timeFormatter.format(new Date(iso));
}

/** "17/07/2026" */
export function formatDate(iso: string): string {
  return dateFormatter.format(new Date(iso));
}

/** "17/07/2026 14:35" */
export function formatDateTime(iso: string): string {
  return dateTimeFormatter.format(new Date(iso));
}

function startOfDay(date: Date): Date {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

/** Số ngày lịch giữa `iso` và hôm nay (0 = hôm nay, 1 = hôm qua). */
export function daysAgo(iso: string, now: Date = new Date()): number {
  const then = startOfDay(new Date(iso));
  const today = startOfDay(now);
  const msPerDay = 24 * 60 * 60 * 1000;
  return Math.round((today.getTime() - then.getTime()) / msPerDay);
}

/** Nhãn tương đối ngắn cho sidebar: "14:35" / "Hôm qua" / "17/07/2026". */
export function formatRelativeShort(iso: string, now: Date = new Date()): string {
  const diff = daysAgo(iso, now);
  if (diff <= 0) return formatTime(iso);
  if (diff === 1) return 'Hôm qua';
  if (diff < 7) return `${diff} ngày trước`;
  return formatDate(iso);
}

/** Xác định hội thoại thuộc nhóm nào trong sidebar. */
export function getConversationGroup(
  conversation: Conversation,
  now: Date = new Date(),
): ConversationGroupKey {
  if (conversation.pinned) return 'pinned';

  const diff = daysAgo(conversation.updatedAt, now);
  if (diff <= 0) return 'today';
  if (diff === 1) return 'yesterday';
  if (diff <= 7) return 'last7Days';
  return 'older';
}
