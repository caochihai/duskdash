export interface Conversation {
  id: string;
  title: string;
  preview?: string;
  /** ISO 8601 */
  updatedAt: string;
  /** ISO 8601 */
  createdAt: string;
  pinned?: boolean;
  unread?: boolean;
  /**
   * Khách hàng mà phiên chat này gắn với.
   * Chuyên viên chat theo TỪNG khách hàng — mỗi khách hàng một phiên riêng.
   */
  customerId?: string;
  customerName?: string;
}

/** Nhóm hiển thị trong sidebar, theo thời gian cập nhật. */
export type ConversationGroupKey = 'pinned' | 'today' | 'yesterday' | 'last7Days' | 'older';

export const CONVERSATION_GROUP_LABEL: Record<ConversationGroupKey, string> = {
  pinned: 'Đã ghim',
  today: 'Hôm nay',
  yesterday: 'Hôm qua',
  last7Days: '7 ngày qua',
  older: 'Trước đó',
};

export interface ConversationGroup {
  key: ConversationGroupKey;
  label: string;
  items: Conversation[];
}
