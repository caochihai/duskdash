import { Avatar } from 'antd';
import { UserOutlined } from '@ant-design/icons';
import type { UserProfile } from '@/types/user';
import { shbColors } from '@/theme/tokens';

export interface UserAvatarProps {
  user?: UserProfile;
  size?: number | 'small' | 'default' | 'large';
}

/** Lấy chữ cái đầu của tên để hiển thị khi không có ảnh đại diện. */
function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return '';
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  // Tên tiếng Việt: lấy chữ cái của tên riêng (từ cuối) cho tự nhiên.
  return parts[parts.length - 1].charAt(0).toUpperCase();
}

export function UserAvatar({ user, size = 'default' }: UserAvatarProps) {
  if (!user) {
    return <Avatar size={size} icon={<UserOutlined />} />;
  }

  if (user.avatarUrl) {
    return <Avatar size={size} src={user.avatarUrl} alt={`Ảnh đại diện của ${user.displayName}`} />;
  }

  return (
    <Avatar
      size={size}
      style={{
        backgroundColor: shbColors.navy[100],
        color: shbColors.navy[700],
        fontWeight: 600,
      }}
    >
      {getInitials(user.displayName)}
    </Avatar>
  );
}
