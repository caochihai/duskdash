import { useMemo, useState } from 'react';
import { Button, Dropdown, Input, Modal, Popconfirm, Skeleton, Tooltip } from 'antd';
import type { MenuProps } from 'antd';
import {
  CustomerServiceOutlined,
  DeleteOutlined,
  EditOutlined,
  MessageOutlined,
  MoreOutlined,
  PlusOutlined,
  PushpinFilled,
  PushpinOutlined,
  QuestionCircleOutlined,
  SafetyOutlined,
  SearchOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { SHBLogo } from '@/components/common/SHBLogo';
import { UserAvatar } from '@/components/common/UserAvatar';
import { EmptyState } from '@/components/common/EmptyState';
import { PageError } from '@/components/common/PageError';
import { filterConversations, groupConversations } from '@/features/chat/utils/groupConversations';
import type { Conversation } from '@/types/conversation';
import type { UserProfile } from '@/types/user';
import { STAFF_ROLE_LABEL } from '@/types/user';
import styles from './ConversationSidebar.module.css';

export interface ConversationSidebarProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  collapsed?: boolean;
  user: UserProfile;
  onSelectConversation: (id: string) => void;
  onCreateConversation: () => void;
  onRenameConversation: (id: string, title: string) => void;
  onTogglePin: (id: string, pinned: boolean) => void;
  onDeleteConversation: (id: string) => void;
}

/** Sidebar quản lý hội thoại. */
export function ConversationSidebar({
  conversations,
  activeConversationId,
  loading = false,
  error,
  onRetry,
  collapsed = false,
  user,
  onSelectConversation,
  onCreateConversation,
  onRenameConversation,
  onTogglePin,
  onDeleteConversation,
}: ConversationSidebarProps) {
  // Trạng thái UI cục bộ -> React state, không đưa vào TanStack Query.
  const [searchTerm, setSearchTerm] = useState('');
  const [renameTarget, setRenameTarget] = useState<Conversation | null>(null);
  const [renameValue, setRenameValue] = useState('');

  const groups = useMemo(
    () => groupConversations(filterConversations(conversations, searchTerm)),
    [conversations, searchTerm],
  );

  const hasResults = groups.some((group) => group.items.length > 0);

  const openRename = (conversation: Conversation) => {
    setRenameTarget(conversation);
    setRenameValue(conversation.title);
  };

  const confirmRename = () => {
    if (renameTarget && renameValue.trim()) {
      onRenameConversation(renameTarget.id, renameValue.trim());
    }
    setRenameTarget(null);
  };

  const buildMenu = (conversation: Conversation): MenuProps['items'] => [
    {
      key: 'rename',
      icon: <EditOutlined />,
      label: 'Đổi tên',
      onClick: ({ domEvent }) => {
        domEvent.stopPropagation();
        openRename(conversation);
      },
    },
    {
      key: 'pin',
      icon: conversation.pinned ? <PushpinFilled /> : <PushpinOutlined />,
      label: conversation.pinned ? 'Bỏ ghim' : 'Ghim',
      onClick: ({ domEvent }) => {
        domEvent.stopPropagation();
        onTogglePin(conversation.id, !conversation.pinned);
      },
    },
    { type: 'divider' },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      danger: true,
      label: (
        <Popconfirm
          title="Xoá cuộc trò chuyện?"
          description="Nội dung sẽ không thể khôi phục."
          okText="Xoá"
          cancelText="Huỷ"
          okButtonProps={{ danger: true }}
          onConfirm={() => onDeleteConversation(conversation.id)}
        >
          <span onClick={(event) => event.stopPropagation()}>Xoá</span>
        </Popconfirm>
      ),
    },
  ];

  /* ---------------- Trạng thái thu gọn ---------------- */

  if (collapsed) {
    return (
      <div className={styles.sider}>
        <div className={[styles.brand, styles.brandCollapsed].join(' ')}>
          {/* Không có symbol chính thức -> thu nhỏ logo đầy đủ, không tự crop. */}
          <Tooltip title="SH-AI" placement="right">
            <span>
              <SHBLogo size="small" />
            </span>
          </Tooltip>
        </div>

        <div className={styles.section}>
          <Tooltip title="Cuộc trò chuyện mới" placement="right">
            <Button
              type="primary"
              shape="circle"
              icon={<PlusOutlined />}
              onClick={onCreateConversation}
              aria-label="Cuộc trò chuyện mới"
              style={{ margin: '0 auto', display: 'block' }}
            />
          </Tooltip>
        </div>

        <div className={styles.list}>
          {conversations.slice(0, 12).map((conversation) => (
            <Tooltip key={conversation.id} title={conversation.title} placement="right">
              <button
                type="button"
                className={[
                  styles.collapsedItem,
                  conversation.id === activeConversationId ? styles.collapsedItemActive : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                onClick={() => onSelectConversation(conversation.id)}
                aria-current={conversation.id === activeConversationId ? 'true' : undefined}
              >
                <MessageOutlined />
              </button>
            </Tooltip>
          ))}
        </div>

        <div className={styles.footer}>
          <Tooltip title={user.displayName} placement="right">
            <span style={{ display: 'block', textAlign: 'center' }}>
              <UserAvatar user={user} />
            </span>
          </Tooltip>
        </div>
      </div>
    );
  }

  /* ---------------- Trạng thái mở rộng ---------------- */

  return (
    <div className={styles.sider}>
      <div className={styles.brand}>
        <SHBLogo size="medium" showProductName />
      </div>

      <div className={styles.section}>
        <Button
          className={styles.newChatBtn}
          type="primary"
          icon={<PlusOutlined />}
          onClick={onCreateConversation}
          size="large"
        >
          Cuộc trò chuyện mới
        </Button>
      </div>

      <div className={styles.section}>
        <Input
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          placeholder="Tìm kiếm cuộc trò chuyện"
          prefix={<SearchOutlined style={{ color: 'var(--shb-text-muted)' }} />}
          allowClear
          aria-label="Tìm kiếm cuộc trò chuyện"
        />
      </div>

      <div className={styles.list}>
        {loading ? (
          <div style={{ padding: '8px 10px' }}>
            <Skeleton active paragraph={{ rows: 5 }} title={false} />
          </div>
        ) : error ? (
          <PageError
            compact
            title="Không tải được danh sách"
            error={error}
            onRetry={onRetry}
          />
        ) : conversations.length === 0 ? (
          <div className={styles.searchEmpty}>
            <EmptyState
              compact
              title="Chưa có cuộc trò chuyện nào"
              description="Hãy bắt đầu bằng một câu hỏi dành cho SH-AI."
            />
          </div>
        ) : !hasResults ? (
          <div className={styles.searchEmpty}>
            <EmptyState
              compact
              title="Không tìm thấy cuộc trò chuyện"
              description="Thử từ khoá khác hoặc tạo cuộc trò chuyện mới."
            />
          </div>
        ) : (
          groups.map((group) => (
            <div key={group.key}>
              <div className={styles.groupLabel}>{group.label}</div>

              {group.items.map((conversation) => {
                const isActive = conversation.id === activeConversationId;

                return (
                  <div
                    key={conversation.id}
                    className={[styles.item, isActive ? styles.itemActive : '']
                      .filter(Boolean)
                      .join(' ')}
                    role="button"
                    tabIndex={0}
                    aria-current={isActive ? 'true' : undefined}
                    onClick={() => onSelectConversation(conversation.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        onSelectConversation(conversation.id);
                      }
                    }}
                  >
                    {isActive && <span className={styles.activeBar} aria-hidden="true" />}

                    <span className={styles.itemBody}>
                      <span
                        className={[styles.itemTitle, isActive ? styles.itemTitleActive : '']
                          .filter(Boolean)
                          .join(' ')}
                      >
                        {conversation.pinned && (
                          <PushpinFilled className={styles.pinIcon} aria-label="Đã ghim" />
                        )}{' '}
                        {conversation.title}
                      </span>
                      {conversation.preview && (
                        <span className={styles.itemPreview}>{conversation.preview}</span>
                      )}
                    </span>

                    <Dropdown
                      menu={{ items: buildMenu(conversation) }}
                      trigger={['click']}
                      placement="bottomRight"
                    >
                      <Button
                        className={styles.itemMenu}
                        type="text"
                        size="small"
                        icon={<MoreOutlined />}
                        onClick={(event) => event.stopPropagation()}
                        aria-label={`Tuỳ chọn cho ${conversation.title}`}
                      />
                    </Dropdown>
                  </div>
                );
              })}
            </div>
          ))
        )}
      </div>

      <div className={styles.footer}>
        <div className={styles.supportCard}>
          <CustomerServiceOutlined className={styles.supportIcon} aria-hidden="true" />
          <span className={styles.supportBody}>
            <span className={styles.supportTitle}>Bạn cần hỗ trợ thêm?</span>
            <span className={styles.supportText}>
              Liên hệ chuyên viên SHB qua kênh chính thức để được tư vấn trực tiếp.
            </span>
          </span>
        </div>

        <div className={styles.footerLinks}>
          <button type="button" className={styles.footerLink}>
            <QuestionCircleOutlined aria-hidden="true" />
            Trợ giúp
          </button>
          <button type="button" className={styles.footerLink}>
            <SafetyOutlined aria-hidden="true" />
            Chính sách sử dụng AI
          </button>
          <button type="button" className={styles.footerLink}>
            <SettingOutlined aria-hidden="true" />
            Cài đặt
          </button>
        </div>

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
          placement="topRight"
        >
          <button type="button" className={styles.profile}>
            <UserAvatar user={user} />
            <span className={styles.profileBody}>
              <span className={styles.profileName}>{user.displayName}</span>
              <span className={styles.profileRole}>
                {STAFF_ROLE_LABEL[user.role]} • {user.branch}
              </span>
            </span>
          </button>
        </Dropdown>
      </div>

      <Modal
        open={renameTarget !== null}
        title="Đổi tên cuộc trò chuyện"
        okText="Lưu"
        cancelText="Huỷ"
        onOk={confirmRename}
        onCancel={() => setRenameTarget(null)}
        okButtonProps={{ disabled: !renameValue.trim() }}
        destroyOnHidden
      >
        <Input
          value={renameValue}
          onChange={(event) => setRenameValue(event.target.value)}
          onPressEnter={confirmRename}
          placeholder="Nhập tên mới"
          aria-label="Tên cuộc trò chuyện"
          autoFocus
          maxLength={80}
        />
      </Modal>
    </div>
  );
}
