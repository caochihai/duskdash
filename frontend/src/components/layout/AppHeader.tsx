import { Button, Dropdown, Grid, Tag, Tooltip } from 'antd';
import type { MenuProps } from 'antd';
import { Link } from 'react-router-dom';
import {
  BookOutlined,
  DeploymentUnitOutlined,
  DownOutlined,
  EnvironmentOutlined,
  ExportOutlined,
  MenuOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MoreOutlined,
  PlusOutlined,
  ShareAltOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { SHBLogo } from '@/components/common/SHBLogo';
import { StatusBadge } from '@/components/common/StatusBadge';
import { UserAvatar } from '@/components/common/UserAvatar';
import { CHAT_MODE_LABEL, type ChatMode } from '@/types/chat';
import type { UserProfile } from '@/types/user';
import styles from './AppHeader.module.css';

export interface AppHeaderProps {
  title: string;
  mode: ChatMode;
  onModeChange: (mode: ChatMode) => void;
  user: UserProfile;
  scrolled?: boolean;
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  onOpenMobileNav: () => void;
  onCreateConversation: () => void;
  onViewSources: () => void;
  onShare: () => void;
  onExport: () => void;
  onFindBranch: () => void;
  hasSources: boolean;
  /**
   * Khách hàng mà phiên chat đang gắn vào. Hiển thị rõ để chuyên viên luôn biết
   * mình đang làm việc trên hồ sơ của ai — phiên chỉ trả lời về khách hàng này.
   */
  sessionCustomerName?: string;
  /**
   * Khi Welcome State hiển thị, h1 của màn hình là lời chào ở giữa trang.
   * Ngược lại, tiêu đề hội thoại chính là h1. Cờ này đảm bảo trên màn hình
   * luôn có ĐÚNG một h1 (accessibility).
   */
  titleAsHeading: boolean;
}

/** Header của vùng chat — sticky trong main content. */
export function AppHeader({
  title,
  mode,
  onModeChange,
  user,
  scrolled = false,
  sidebarCollapsed,
  onToggleSidebar,
  onOpenMobileNav,
  onCreateConversation,
  onViewSources,
  onShare,
  onExport,
  onFindBranch,
  hasSources,
  titleAsHeading,
  sessionCustomerName,
}: AppHeaderProps) {
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;

  const modeItems: MenuProps['items'] = (Object.keys(CHAT_MODE_LABEL) as ChatMode[]).map((key) => ({
    key,
    label: CHAT_MODE_LABEL[key],
    onClick: () => onModeChange(key),
  }));

  // Trên mobile, các action phụ gom vào menu "thêm".
  const overflowItems: MenuProps['items'] = [
    ...(isMobile
      ? [
          {
            key: 'sources',
            icon: <BookOutlined />,
            label: 'Xem nguồn',
            disabled: !hasSources,
            onClick: onViewSources,
          },
        ]
      : []),
    {
      key: 'dashboard',
      icon: <DeploymentUnitOutlined />,
      label: <Link to="/dashboard">Giám sát hệ chuyên gia số</Link>,
    },
    { type: 'divider' },
    { key: 'share', icon: <ShareAltOutlined />, label: 'Chia sẻ hội thoại', onClick: onShare },
    { key: 'export', icon: <ExportOutlined />, label: 'Xuất nội dung', onClick: onExport },
    {
      key: 'branch',
      icon: <EnvironmentOutlined />,
      label: 'Tìm ATM và chi nhánh',
      onClick: onFindBranch,
    },
  ];

  return (
    <header className={[styles.header, scrolled ? styles.headerScrolled : ''].filter(Boolean).join(' ')}>
      <div className={styles.left}>
        {isMobile ? (
          <>
            <Button
              type="text"
              icon={<MenuOutlined />}
              onClick={onOpenMobileNav}
              aria-label="Mở danh sách cuộc trò chuyện"
            />
            <span className={styles.mobileLogo}>
              <SHBLogo size="small" />
            </span>
          </>
        ) : (
          <Tooltip title={sidebarCollapsed ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'}>
            <Button
              type="text"
              icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={onToggleSidebar}
              aria-label={sidebarCollapsed ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'}
              aria-expanded={!sidebarCollapsed}
            />
          </Tooltip>
        )}

        <div className={styles.titleGroup}>
          {titleAsHeading ? (
            <h1 className={styles.title}>{title}</h1>
          ) : (
            <span className={styles.title}>{title}</span>
          )}
          {!isMobile &&
            (sessionCustomerName ? (
              <Tooltip title={`Phiên này chỉ trả lời về hồ sơ của ${sessionCustomerName}`}>
                <Tag icon={<UserOutlined />} color="processing" style={{ marginInlineEnd: 0 }}>
                  {sessionCustomerName}
                </Tag>
              </Tooltip>
            ) : (
              <StatusBadge tone="online" label="Đang hoạt động" />
            ))}
        </div>

        {!isMobile && (
          <>
            <span className={styles.divider} aria-hidden="true" />
            <Dropdown menu={{ items: modeItems, selectedKeys: [mode] }} trigger={['click']}>
              <Button type="text" className={styles.modeButton}>
                {CHAT_MODE_LABEL[mode]} <DownOutlined style={{ fontSize: 10 }} />
              </Button>
            </Dropdown>
          </>
        )}
      </div>

      <div className={styles.right}>
        <Tooltip title="Cuộc trò chuyện mới">
          <Button
            type="text"
            icon={<PlusOutlined />}
            onClick={onCreateConversation}
            aria-label="Tạo cuộc trò chuyện mới"
          />
        </Tooltip>

        {!isMobile && (
          <Tooltip title={hasSources ? 'Xem nguồn tham khảo' : 'Chưa có nguồn tham khảo'}>
            <Button
              type="text"
              icon={<BookOutlined />}
              onClick={onViewSources}
              disabled={!hasSources}
              aria-label="Xem nguồn tham khảo"
            />
          </Tooltip>
        )}

        <Dropdown menu={{ items: overflowItems }} trigger={['click']} placement="bottomRight">
          <Button type="text" icon={<MoreOutlined />} aria-label="Thêm tuỳ chọn" />
        </Dropdown>

        <Dropdown
          menu={{
            items: [
              { key: 'profile', label: 'Hồ sơ của tôi' },
              { key: 'settings', label: 'Cài đặt tài khoản' },
              { type: 'divider' },
              { key: 'logout', label: 'Đăng xuất' },
            ],
          }}
          trigger={['click']}
          placement="bottomRight"
        >
          <button
            type="button"
            style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: 2 }}
            aria-label="Tài khoản của tôi"
          >
            <UserAvatar user={user} size="small" />
          </button>
        </Dropdown>
      </div>
    </header>
  );
}
