import { Drawer } from 'antd';
import { ConversationSidebar, type ConversationSidebarProps } from './ConversationSidebar';

export interface MobileNavigationDrawerProps extends Omit<ConversationSidebarProps, 'collapsed'> {
  open: boolean;
  onClose: () => void;
}

/**
 * Sidebar dạng Drawer cho mobile.
 *
 * Dùng lại đúng `ConversationSidebar` để tránh trùng lặp logic;
 * Drawer của Ant Design lo phần focus trap và khoá scroll nền.
 */
export function MobileNavigationDrawer({ open, onClose, ...sidebarProps }: MobileNavigationDrawerProps) {
  return (
    <Drawer
      open={open}
      onClose={onClose}
      placement="left"
      width={302}
      closable={false}
      styles={{ body: { padding: 0 } }}
      rootClassName="shb-mobile-nav-drawer"
    >
      <ConversationSidebar
        {...sidebarProps}
        // Chọn hội thoại xong thì đóng drawer luôn.
        onSelectConversation={(id) => {
          sidebarProps.onSelectConversation(id);
          onClose();
        }}
        onCreateConversation={() => {
          sidebarProps.onCreateConversation();
          onClose();
        }}
      />
    </Drawer>
  );
}
