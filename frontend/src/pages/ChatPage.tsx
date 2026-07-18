import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { App, Drawer, Grid } from 'antd';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { AppHeader } from '@/components/layout/AppHeader';
import { ConversationSidebar } from '@/features/chat/components/ConversationSidebar';
import { MobileNavigationDrawer } from '@/components/layout/MobileNavigationDrawer';
import { ChatWorkspace } from '@/features/chat/components/ChatWorkspace';
import { SourceDrawer } from '@/features/chat/components/SourceDrawer';
import { CustomerWorkspacePanel } from '@/features/customer/components/CustomerWorkspacePanel';
import {
  DEMO_APPROVAL_LIMIT,
  findLoansByCustomer,
} from '@/features/chat/constants/mockCustomers';
import styles from './ChatPage.module.css';
import type { Customer, LoanApplication, LoanApplicationStatus } from '@/types/customer';
import { LOAN_STATUS_LABEL } from '@/types/customer';
import { LoadingScreen } from '@/components/common/LoadingScreen';
import { useConversations } from '@/hooks/useConversations';
import { useConversationMessages } from '@/hooks/useConversationMessages';
import { useCreateConversation } from '@/hooks/useCreateConversation';
import { useRenameConversation } from '@/hooks/useRenameConversation';
import { useDeleteConversation } from '@/hooks/useDeleteConversation';
import { useTogglePinnedConversation } from '@/hooks/useTogglePinnedConversation';
import { useSendMessage } from '@/hooks/useSendMessage';
import { getErrorMessage } from '@/services/apiClient';
import { USE_MOCK_API } from '@/services/apiClient';
import { useCustomers } from '@/hooks/useCustomers';
import { claimCustomerAssignment } from '@/services/customerAssignmentService';
import { getAssignedLoanApplicationId } from '@/services/customerService';
import { setConversationCustomer } from '@/services/conversationService';
import type { ChatMessage, ChatMode } from '@/types/chat';
import type { ChatAttachment } from '@/types/attachment';
import type { ChatSource } from '@/types/source';
import type { UserProfile } from '@/types/user';

const FoundationPage = lazy(() => import('./FoundationPage'));

/**
 * Người dùng demo — CHUYÊN VIÊN NGÂN HÀNG, không phải khách hàng.
 * Theo đề bài, hệ chuyên gia số phục vụ vận hành nội bộ của SHB.
 * Khi có auth thật sẽ lấy từ phiên đăng nhập.
 */
const DEMO_USER: UserProfile = {
  id: 'staff-demo',
  displayName: 'Nguyễn Minh Anh',
  role: 'credit-officer',
  department: 'Khối Tín dụng',
  branch: 'CN Hà Nội',
  approvalLimit: DEMO_APPROVAL_LIMIT,
};

export default function ChatPage() {
  const { message: messageApi, modal } = App.useApp();
  const screens = Grid.useBreakpoint();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();

  const isMobile = !screens.md;

  /* ---------------- Local UI state (không dùng TanStack Query) ---------------- */

  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [sourceDrawerOpen, setSourceDrawerOpen] = useState(false);
  const [activeSources, setActiveSources] = useState<ChatSource[]>([]);
  const [composerValue, setComposerValue] = useState('');
  const [mode, setMode] = useState<ChatMode>('general');
  const [activeCustomer, setActiveCustomer] = useState<Customer | null>(null);
  const [activeAssignmentLeaseToken, setActiveAssignmentLeaseToken] = useState<string>();
  const [panelOpen, setPanelOpen] = useState(false);
  /** Độ rộng panel hồ sơ (% của vùng nội dung), điều chỉnh bằng thanh kéo. */
  const [panelWidth, setPanelWidth] = useState(46);

  /* ---------------- Server state ---------------- */

  const conversationsQuery = useConversations();
  const customersQuery = useCustomers();
  const messagesQuery = useConversationMessages(activeConversationId);
  const createConversation = useCreateConversation();
  const renameConversation = useRenameConversation();
  const deleteConversation = useDeleteConversation();
  const togglePin = useTogglePinnedConversation();

  const { streamingMessage, isStreaming, send, stop, regenerate } =
    useSendMessage(activeConversationId);

  const conversations = useMemo(() => conversationsQuery.data ?? [], [conversationsQuery.data]);
  const customers = useMemo(() => customersQuery.data ?? [], [customersQuery.data]);
  const messages = useMemo(() => messagesQuery.data ?? [], [messagesQuery.data]);

  // Mở hội thoại đầu tiên khi vào ứng dụng.
  useEffect(() => {
    if (!activeConversationId && conversations.length > 0) {
      setActiveConversationId(conversations[0].id);
    }
  }, [activeConversationId, conversations]);

  const activeConversation = useMemo(
    () => conversations.find((item) => item.id === activeConversationId) ?? null,
    [conversations, activeConversationId],
  );

  /**
   * Welcome State được tính ở đây (thay vì trong ChatWorkspace) để header và
   * workspace thống nhất: đúng một h1 trên màn hình ở mọi trạng thái.
   */
  const showWelcome =
    !messagesQuery.isLoading &&
    !messagesQuery.error &&
    messages.length === 0 &&
    !streamingMessage;

  /** Nguồn của câu trả lời AI gần nhất — dùng cho nút "Xem nguồn" trên header. */
  const latestSources = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index];
      if (message.role === 'assistant' && message.sources?.length) return message.sources;
    }
    return [];
  }, [messages]);

  /* ---------------- Handlers ---------------- */

  const handleSend = useCallback(
    async (content: string, attachments: ChatAttachment[]) => {
      let conversationId = activeConversationId;

      // Chưa có hội thoại nào -> tạo mới trước khi gửi.
      if (!conversationId) {
        try {
          const created = await createConversation.mutateAsync({});
          conversationId = created.id;
          setActiveConversationId(created.id);
        } catch (error) {
          messageApi.error(getErrorMessage(error));
          return;
        }
      }

      setComposerValue('');
      await send({
        conversationId,
        content,
        attachments,
        mode,
        assignmentLeaseToken: activeAssignmentLeaseToken,
      });
    },
    [
      activeAssignmentLeaseToken,
      activeConversationId,
      createConversation,
      messageApi,
      mode,
      send,
    ],
  );

  /** Quick prompt / CTA / suggestion -> gửi ngay. */
  const handleQuickPrompt = useCallback(
    (prompt: string) => {
      if (isStreaming) {
        setComposerValue(prompt);
        return;
      }
      void handleSend(prompt, []);
    },
    [handleSend, isStreaming],
  );

  /**
   * Trang hồ sơ khách hàng điều hướng về đây kèm state `askCustomer`
   * -> tự động hỏi hệ chuyên gia số về khách hàng đó, rồi xoá state để
   * không lặp lại khi refresh/back.
   */
  useEffect(() => {
    const state = location.state as { askCustomer?: { id: string; name: string } } | null;
    if (state?.askCustomer) {
      handleQuickPrompt(`Cho tôi thông tin khách hàng ${state.askCustomer.name}.`);
      navigate('.', { replace: true, state: null });
    }
  }, [location.state, handleQuickPrompt, navigate]);

  const handleCreateConversation = useCallback(async () => {
    try {
      const created = await createConversation.mutateAsync({});
      setActiveConversationId(created.id);
      setComposerValue('');
    } catch (error) {
      messageApi.error(getErrorMessage(error));
    }
  }, [createConversation, messageApi]);

  const handleRename = useCallback(
    (id: string, title: string) => {
      renameConversation.mutate(
        { conversationId: id, title },
        {
          onError: (error) => messageApi.error(getErrorMessage(error)),
          onSuccess: () => messageApi.success('Đã đổi tên cuộc trò chuyện'),
        },
      );
    },
    [messageApi, renameConversation],
  );

  const handleTogglePin = useCallback(
    (id: string, pinned: boolean) => {
      togglePin.mutate(
        { conversationId: id, pinned },
        { onError: (error) => messageApi.error(getErrorMessage(error)) },
      );
    },
    [messageApi, togglePin],
  );

  const handleDelete = useCallback(
    (id: string) => {
      deleteConversation.mutate(id, {
        onSuccess: () => {
          messageApi.success('Đã xoá cuộc trò chuyện');
          if (id === activeConversationId) {
            const next = conversations.find((item) => item.id !== id);
            setActiveConversationId(next?.id ?? null);
          }
        },
        onError: (error) => messageApi.error(getErrorMessage(error)),
      });
    },
    [activeConversationId, conversations, deleteConversation, messageApi],
  );

  const handleViewSources = useCallback((message: ChatMessage) => {
    setActiveSources(message.sources ?? []);
    setSourceDrawerOpen(true);
  }, []);

  const handleViewLatestSources = useCallback(() => {
    setActiveSources(latestSources);
    setSourceDrawerOpen(true);
  }, [latestSources]);

  /* ---------------- Khách hàng & phê duyệt ---------------- */

  /**
   * Mở phiên chat GẮN VỚI một khách hàng: nếu đã có phiên của khách hàng đó thì
   * mở lại, chưa có thì tạo mới. Chuyên viên chat theo từng khách hàng.
   */
  const openCustomerConversation = useCallback(
    async (customer: Customer) => {
      try {
        const lease = await claimCustomerAssignment(
          customer.id,
          customer.assignmentVersion ?? 1,
        );
        setActiveAssignmentLeaseToken(lease?.lease_token);

        const existing = conversations.find((item) => item.customerId === customer.id);
        if (existing) {
          setActiveConversationId(existing.id);
          return;
        }

        let loanApplicationId: string | undefined;
        try {
          loanApplicationId = await getAssignedLoanApplicationId(customer.id);
        } catch {
          // A customer-only conversation remains useful for direct/document queries.
        }
        const created = await createConversation.mutateAsync({
          customerId: customer.id,
          customerName: customer.fullName,
          loanApplicationId,
        });
        setActiveConversationId(created.id);
        setComposerValue('');
      } catch (error) {
        messageApi.error(getErrorMessage(error));
      }
    },
    [conversations, createConversation, messageApi],
  );

  /** Chọn khách hàng (lệnh `/`) -> mở phiên chat của họ + panel hồ sơ nửa màn hình. */
  const handleSelectCustomer = useCallback(
    (customer: Customer) => {
      setActiveCustomer(customer);
      setPanelOpen(true);
      void openCustomerConversation(customer);
    },
    [openCustomerConversation],
  );

  /**
   * Upload hồ sơ khi chưa chọn khách hàng -> backend đã tự tạo khách nháp.
   * Gắn khách đó vào hội thoại hiện tại (server) + panel hồ sơ (client);
   * tên khách sẽ được vision cập nhật từ nội dung hồ sơ sau tin nhắn đầu.
   */
  const handleCustomerAutoCreated = useCallback(
    (customerId: string) => {
      if (activeConversationId) {
        void setConversationCustomer(activeConversationId, customerId);
      }
      void customersQuery.refetch().then((result) => {
        const created = result.data?.find((item) => item.id === customerId);
        if (created) {
          setActiveCustomer(created);
          setPanelOpen(true);
        }
      });
    },
    [activeConversationId, customersQuery],
  );

  /** Xem hồ sơ khách hàng (từ card trong chat) -> mở panel, không đổi phiên chat. */
  const handleViewCustomer = useCallback((customerId: string) => {
    const found = customers.find((item) => item.id === customerId);
    if (found) {
      setActiveCustomer(found);
      setPanelOpen(true);
    }
  }, [customers]);

  const handleSelectConversation = useCallback((conversationId: string) => {
    setActiveAssignmentLeaseToken(undefined);
    setActiveConversationId(conversationId);
  }, []);

  /** Đưa các hồ sơ đã chọn trong lưới vào chat để hệ chuyên gia số thẩm định. */
  const handleReviewInChat = useCallback(
    (records: LoanApplication[]) => {
      if (!records.length) return;
      const codes = records.map((r) => r.code).join(', ');
      const prompt =
        records.length === 1
          ? `Thẩm định hồ sơ vay ${codes}.`
          : `Thẩm định các hồ sơ vay sau: ${codes}.`;
      handleQuickPrompt(prompt);
    },
    [handleQuickPrompt],
  );

  const handleLoanDecision = useCallback(
    (application: LoanApplication, status: LoanApplicationStatus, note: string) => {
      // Bản demo chỉ ghi nhận cục bộ — không gửi tới hệ thống tín dụng thật.
      messageApi.success(
        `${LOAN_STATUS_LABEL[status]}: ${application.code}${note ? ` — ${note}` : ''}`,
      );
    },
    [messageApi],
  );

  const handleShare = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      messageApi.success('Đã sao chép liên kết cuộc trò chuyện');
    } catch {
      messageApi.error('Không sao chép được liên kết');
    }
  }, [messageApi]);

  const handleExport = useCallback(() => {
    if (!messages.length) {
      messageApi.info('Cuộc trò chuyện chưa có nội dung để xuất');
      return;
    }

    const content = messages
      .map((item) => `${item.role === 'user' ? 'Bạn' : 'SH-AI'}:\n${item.content}`)
      .join('\n\n---\n\n');

    // Xuất file phía client, không gửi nội dung hội thoại đi đâu.
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${activeConversation?.title ?? 'cuoc-tro-chuyen'}.txt`;
    link.click();
    URL.revokeObjectURL(url);

    messageApi.success('Đã xuất nội dung cuộc trò chuyện');
  }, [activeConversation, messageApi, messages]);

  const handleFindBranch = useCallback(() => {
    handleQuickPrompt('Hãy giúp tôi tìm ATM hoặc chi nhánh SHB.');
  }, [handleQuickPrompt]);

  const handleModeChange = useCallback(
    (next: ChatMode) => {
      setMode(next);
      messageApi.info(`Đã chuyển sang chế độ: ${next === 'general' ? 'Tư vấn chung' : next}`);
    },
    [messageApi],
  );

  const showAiPolicy = useCallback(() => {
    modal.info({
      title: 'Chính sách sử dụng SH-AI',
      content:
        'SH-AI là trợ lý thông tin. Nội dung mang tính tham khảo, không thay thế tư vấn chính thức và không thực hiện giao dịch trong phiên bản demo này.',
      okText: 'Đã hiểu',
    });
  }, [modal]);

  /* ---------------- Foundation mode ---------------- */

  // ?view=foundation -> trang kiểm chứng nền tảng.
  if (searchParams.get('view') === 'foundation') {
    return (
      <Suspense fallback={<LoadingScreen message="Đang tải Foundation Page" />}>
        <FoundationPage />
      </Suspense>
    );
  }

  /* ---------------- Panel resize ---------------- */

  const showPanel = panelOpen && activeCustomer !== null;
  const customerRecords = useMemo(
    () => (activeCustomer && USE_MOCK_API ? findLoansByCustomer(activeCustomer.id) : []),
    [activeCustomer],
  );

  /**
   * Kéo thanh giữa chat và panel để đổi tỉ lệ. Tính theo % của vùng nội dung,
   * kẹp trong khoảng 32–62% để không bên nào bị bóp quá hẹp.
   */
  const handleResizeStart = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    const container = event.currentTarget.parentElement;
    if (!container) return;
    const rect = container.getBoundingClientRect();

    const onMove = (moveEvent: PointerEvent) => {
      const fromRight = ((rect.right - moveEvent.clientX) / rect.width) * 100;
      setPanelWidth(Math.min(62, Math.max(32, fromRight)));
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };

    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, []);

  const closePanel = useCallback(() => {
    setPanelOpen(false);
  }, []);

  const openFullProfile = useCallback(
    (customer: Customer) => {
      setPanelOpen(false);
      navigate(`/customer/${customer.id}`);
    },
    [navigate],
  );

  /* ---------------- Render ---------------- */

  const sidebarProps = {
    conversations,
    activeConversationId,
    loading: conversationsQuery.isLoading,
    error: conversationsQuery.error,
    onRetry: () => void conversationsQuery.refetch(),
    user: DEMO_USER,
    onSelectConversation: handleSelectConversation,
    onCreateConversation: () => void handleCreateConversation(),
    onRenameConversation: handleRename,
    onTogglePin: handleTogglePin,
    onDeleteConversation: handleDelete,
  };

  return (
    <>
      {/* Skip link: người dùng bàn phím bỏ qua sidebar để tới nội dung chính. */}
      <a className="skip-link" href="#main-content">
        Bỏ qua để tới nội dung chính
      </a>

      <AppShell
        sidebarCollapsed={sidebarCollapsed}
        sidebar={<ConversationSidebar {...sidebarProps} collapsed={sidebarCollapsed} />}
        header={
          <AppHeader
            title={activeConversation?.title ?? 'Trợ lý SHB'}
            mode={mode}
            onModeChange={handleModeChange}
            user={DEMO_USER}
            sidebarCollapsed={sidebarCollapsed}
            onToggleSidebar={() => setSidebarCollapsed((value) => !value)}
            onOpenMobileNav={() => setMobileNavOpen(true)}
            onCreateConversation={() => void handleCreateConversation()}
            onViewSources={handleViewLatestSources}
            onShare={() => void handleShare()}
            onExport={handleExport}
            onFindBranch={handleFindBranch}
            hasSources={latestSources.length > 0}
            titleAsHeading={!showWelcome}
          />
        }
      >
        {/* Split-view: chat bên trái, panel hồ sơ khách hàng bên phải (desktop). */}
        <div className={styles.splitRow}>
          <div className={styles.chatCol}>
            <ChatWorkspace
              messages={messages}
              streamingMessage={streamingMessage}
              loading={messagesQuery.isLoading}
              error={messagesQuery.error}
              onRetryLoad={() => void messagesQuery.refetch()}
              composerValue={composerValue}
              onComposerChange={setComposerValue}
              onSend={(content, attachments) => void handleSend(content, attachments)}
              onStop={stop}
              onQuickPrompt={handleQuickPrompt}
              onRegenerate={() => void regenerate()}
              onViewSources={handleViewSources}
              isStreaming={isStreaming}
              showWelcome={showWelcome}
              staffName={DEMO_USER.displayName}
              customers={customers}
              onSelectCustomer={handleSelectCustomer}
              onCustomerAutoCreated={handleCustomerAutoCreated}
              onViewCustomer={handleViewCustomer}
              onLoanDecision={handleLoanDecision}
              uploadContext={{
                customerId: activeConversation?.customerId,
                loanApplicationId: activeConversation?.activeLoanApplicationId,
              }}
            />
          </div>

          {/* Panel inline chỉ trên desktop; mobile dùng Drawer bên dưới. */}
          {showPanel && !isMobile && activeCustomer && (
            <div className={styles.panelCol} style={{ width: `${panelWidth}%` }}>
              <div
                className={styles.resizer}
                role="separator"
                aria-orientation="vertical"
                aria-label="Kéo để đổi độ rộng panel"
                onPointerDown={handleResizeStart}
              />
              <CustomerWorkspacePanel
                customer={activeCustomer}
                records={customerRecords}
                onClose={closePanel}
                onOpenFullPage={openFullProfile}
                onReviewInChat={handleReviewInChat}
                onLoanDecision={handleLoanDecision}
              />
            </div>
          )}
        </div>
      </AppShell>

      {isMobile && (
        <MobileNavigationDrawer
          {...sidebarProps}
          open={mobileNavOpen}
          onClose={() => setMobileNavOpen(false)}
        />
      )}

      <SourceDrawer
        open={sourceDrawerOpen}
        onClose={() => setSourceDrawerOpen(false)}
        sources={activeSources}
      />

      {/* Mobile: panel hồ sơ hiển thị dạng Drawer gần full màn hình. */}
      {isMobile && activeCustomer && (
        <Drawer
          open={showPanel}
          onClose={closePanel}
          placement="right"
          width="100%"
          closable={false}
          styles={{ body: { padding: 0 } }}
        >
          <CustomerWorkspacePanel
            customer={activeCustomer}
            records={customerRecords}
            onClose={closePanel}
            onOpenFullPage={openFullProfile}
            onReviewInChat={handleReviewInChat}
            onLoanDecision={handleLoanDecision}
          />
        </Drawer>
      )}

      {/* Nút ẩn phục vụ liên kết chính sách AI từ sidebar. */}
      <button type="button" onClick={showAiPolicy} className="sr-only">
        Chính sách sử dụng AI
      </button>
    </>
  );
}
