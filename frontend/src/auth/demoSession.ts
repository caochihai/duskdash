import { useSyncExternalStore } from 'react';
import { DEMO_ACCOUNTS, findDemoAccount, type DemoAccount } from './demoAccounts';
import type { UserProfile } from '@/types/user';

/**
 * Phiên đăng nhập của bản demo.
 *
 * Lưu ở `sessionStorage` (không phải `localStorage`): phiên mất khi đóng tab,
 * đúng nguyên tắc tối thiểu hoá dữ liệu của ứng dụng nội bộ. Chỉ lưu `username`
 * — hồ sơ nhân viên được tra lại từ `DEMO_ACCOUNTS`, không ghi mật khẩu.
 */

const STORAGE_KEY = 'shb-demo-session';

export interface DemoSession {
  username: string;
  profile: UserProfile;
  authorizedCustomerIds: string[];
  signedInAt: string;
}

let current: DemoSession | null = restore();
const listeners = new Set<() => void>();

function toSession(account: DemoAccount, signedInAt: string): DemoSession {
  return {
    username: account.username,
    profile: account.profile,
    authorizedCustomerIds: account.authorizedCustomerIds,
    signedInAt,
  };
}

function restore(): DemoSession | null {
  if (typeof window === 'undefined') return null;

  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw) as { username?: string; signedInAt?: string };
    const account = DEMO_ACCOUNTS.find((item) => item.username === parsed.username);
    if (!account) return null;

    return toSession(account, parsed.signedInAt ?? new Date().toISOString());
  } catch {
    // sessionStorage bị chặn hoặc dữ liệu hỏng -> coi như chưa đăng nhập.
    return null;
  }
}

function persist(session: DemoSession | null) {
  try {
    if (session) {
      window.sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ username: session.username, signedInAt: session.signedInAt }),
      );
    } else {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Không lưu được thì phiên chỉ tồn tại trong bộ nhớ — vẫn dùng được.
  }
}

function emit() {
  listeners.forEach((listener) => listener());
}

/** Đăng nhập bằng tài khoản demo. Trả về phiên, hoặc `null` nếu sai thông tin. */
export function signIn(username: string, password: string): DemoSession | null {
  const account = findDemoAccount(username, password);
  if (!account) return null;

  current = toSession(account, new Date().toISOString());
  persist(current);
  emit();
  return current;
}

export function signOut(): void {
  current = null;
  persist(null);
  emit();
}

export function getDemoSession(): DemoSession | null {
  return current;
}

export function hasDemoSession(): boolean {
  return current !== null;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Đọc phiên hiện tại trong React và tự render lại khi đăng nhập/đăng xuất. */
export function useDemoSession(): DemoSession | null {
  return useSyncExternalStore(subscribe, getDemoSession, () => null);
}
