import { useState, type ReactNode } from 'react';
import { ThoughtChain } from '@ant-design/x';
import type { ThoughtChainItemType } from '@ant-design/x';
import { Tag } from 'antd';
import {
  ApartmentOutlined,
  AuditOutlined,
  CheckCircleFilled,
  DeploymentUnitOutlined,
  DownOutlined,
  FileProtectOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { AGENT_LABEL, AGENT_SHORT_LABEL, type AgentRole, type AgentTrace as AgentTraceData } from '@/types/agent';
import styles from './AgentTrace.module.css';

export interface AgentTraceProps {
  trace: AgentTraceData;
  /** Hệ agent vẫn đang chạy -> mở sẵn để chuyên viên theo dõi tiến trình. */
  running?: boolean;
}

/** Icon đại diện cho từng agent chuyên môn. */
const AGENT_ICON: Record<AgentRole, ReactNode> = {
  planner: <ApartmentOutlined />,
  credit: <AuditOutlined />,
  legal: <SafetyCertificateOutlined />,
  operations: <SettingOutlined />,
  product: <FileProtectOutlined />,
};

const AGENT_COLOR: Record<AgentRole, string> = {
  planner: 'purple',
  credit: 'orange',
  legal: 'blue',
  operations: 'cyan',
  product: 'gold',
};

/** Map trạng thái nội bộ -> trạng thái của ThoughtChain. */
function toChainStatus(status: string): ThoughtChainItemType['status'] {
  if (status === 'running') return 'loading';
  if (status === 'error') return 'error';
  if (status === 'success') return 'success';
  return undefined;
}

/**
 * Agent trace — hiển thị hệ multi-agent đã lập kế hoạch, gọi công cụ và
 * phối hợp ra sao để xử lý yêu cầu.
 *
 * Đây là dấu vết vận hành phục vụ giám sát (đề bài yêu cầu "agent traces,
 * task status, decisions, collaboration flows"), KHÔNG phải chain-of-thought
 * nội bộ của mô hình: mỗi bước chỉ nêu hành động, công cụ và kết quả.
 */
export function AgentTrace({ trace, running = false }: AgentTraceProps) {
  const [open, setOpen] = useState(running);
  const prefersReducedMotion = useReducedMotion();

  const doneCount = trace.steps.filter((step) => step.status === 'success').length;
  const totalMs = trace.steps.reduce((sum, step) => sum + (step.durationMs ?? 0), 0);

  const items: ThoughtChainItemType[] = trace.steps.map((step) => ({
    key: step.id,
    status: toChainStatus(step.status),
    icon: AGENT_ICON[step.agent],
    title: (
      <span className={styles.stepTitle}>
        <Tag className={styles.agentTag} color={AGENT_COLOR[step.agent]} bordered={false}>
          {AGENT_SHORT_LABEL[step.agent]}
        </Tag>
        {step.title}
      </span>
    ),
    content: (
      <>
        {step.description && <p className={styles.stepDesc}>{step.description}</p>}

        {step.tool && (
          <div className={styles.toolCall}>
            <ToolOutlined className={styles.toolIcon} aria-hidden="true" />
            <span className={styles.toolName}>{step.tool.label}</span>
            {step.tool.result && <span className={styles.toolResult}>— {step.tool.result}</span>}
          </div>
        )}
      </>
    ),
  }));

  return (
    <section className={styles.wrapper} aria-label="Tiến trình xử lý của hệ chuyên gia số">
      <button
        type="button"
        className={styles.header}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <DeploymentUnitOutlined className={styles.headerIcon} aria-hidden="true" />
        <span className={styles.headerTitle}>{trace.summary}</span>

        <span className={styles.headerMeta}>
          {running ? 'Đang xử lý…' : `${doneCount} bước`}
          {!running && totalMs > 0 && ` • ${(totalMs / 1000).toFixed(1)}s`}
        </span>

        <DownOutlined
          className={[styles.chevron, open ? styles.chevronOpen : ''].filter(Boolean).join(' ')}
          aria-hidden="true"
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={prefersReducedMotion ? false : { height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={prefersReducedMotion ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
            style={{ overflow: 'hidden' }}
          >
            <div className={styles.body}>
              <ThoughtChain items={items} line="dashed" />

              {!running && (
                <div className={styles.doneRow}>
                  <CheckCircleFilled aria-hidden="true" />
                  Hoàn tất — các chuyên gia số đã thống nhất kết quả
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

export { AGENT_LABEL };
