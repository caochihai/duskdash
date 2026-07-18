import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';
import { API_ERROR_CODES, type ApiError } from '@/types/api';
import { getValidAccessToken } from '@/auth/keycloak';

/**
 * Axios instance DUY NHẤT của ứng dụng.
 *
 * Quy tắc:
 * - Component không bao giờ import file này trực tiếp.
 *   Luồng đúng: component -> query hook -> service -> apiClient.
 * - Không log token, OTP, mật khẩu hay nội dung file.
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/* ---------------- Request interceptor ---------------- */

apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const token = await getValidAccessToken();
    if (token) {
      config.headers.set('Authorization', `Bearer ${token}`);
    }

    // Chỉ log method + đường dẫn ở môi trường dev.
    // KHÔNG log headers (chứa token) và KHÔNG log body (có thể chứa dữ liệu nhạy cảm).
    if (import.meta.env.DEV) {
      console.info(`[api] ${config.method?.toUpperCase()} ${config.url}`);
    }

    return config;
  },
  (error: unknown) => Promise.reject(normalizeError(error)),
);

/* ---------------- Response interceptor ---------------- */

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => Promise.reject(normalizeError(error)),
);

/* ---------------- Error normalization ---------------- */

interface ServerErrorBody {
  code?: string;
  message?: string;
  errors?: unknown;
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
    trace_id?: string;
  };
}

/** Thông điệp tiếng Việt an toàn cho người dùng cuối — không lộ stack trace. */
const USER_MESSAGE: Record<string, string> = {
  [API_ERROR_CODES.timeout]: 'Yêu cầu mất quá nhiều thời gian. Vui lòng thử lại.',
  [API_ERROR_CODES.network]: 'Không thể kết nối tới máy chủ. Vui lòng kiểm tra kết nối mạng.',
  [API_ERROR_CODES.notFound]: 'Không tìm thấy dữ liệu yêu cầu.',
  [API_ERROR_CODES.unauthorized]: 'Phiên đăng nhập đã hết hạn. Vui lòng thử lại.',
  [API_ERROR_CODES.server]: 'Hệ thống đang bận. Vui lòng thử lại sau ít phút.',
  [API_ERROR_CODES.validation]: 'Dữ liệu gửi lên không hợp lệ.',
  [API_ERROR_CODES.unknown]: 'Đã có lỗi xảy ra. Vui lòng thử lại.',
};

/**
 * Chuẩn hoá mọi lỗi (Axios / network / lỗi lạ) về `ApiError`.
 * Nhờ vậy UI chỉ cần xử lý một hình dạng lỗi duy nhất.
 */
export function normalizeError(error: unknown): ApiError {
  if (isApiError(error)) return error;

  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ServerErrorBody>;

    if (axiosError.code === 'ECONNABORTED' || axiosError.code === 'ETIMEDOUT') {
      return {
        code: API_ERROR_CODES.timeout,
        message: USER_MESSAGE[API_ERROR_CODES.timeout],
      };
    }

    if (!axiosError.response) {
      return {
        code: API_ERROR_CODES.network,
        message: USER_MESSAGE[API_ERROR_CODES.network],
      };
    }

    const status = axiosError.response.status;
    const body = axiosError.response.data;
    const code = resolveCodeFromStatus(status);

    const backendError = body?.error;
    return {
      code: backendError?.code ?? body?.code ?? code,
      // Ưu tiên message từ backend nếu có, nhưng luôn có fallback an toàn.
      message:
        backendError?.message ??
        body?.message ??
        USER_MESSAGE[code] ??
        USER_MESSAGE[API_ERROR_CODES.unknown],
      status,
      details: backendError?.details ?? body?.errors,
    };
  }

  // Error thường trong codebase mang thông điệp tiếng Việt viết cho người
  // dùng (vd: "Vui lòng chọn khách hàng trước khi tải tài liệu.") — giữ nguyên
  // thay vì ép về câu chung chung.
  if (error instanceof Error && error.message) {
    return { code: API_ERROR_CODES.unknown, message: error.message };
  }

  return {
    code: API_ERROR_CODES.unknown,
    message: USER_MESSAGE[API_ERROR_CODES.unknown],
  };
}

function resolveCodeFromStatus(status: number): string {
  if (status === 401 || status === 403) return API_ERROR_CODES.unauthorized;
  if (status === 404) return API_ERROR_CODES.notFound;
  if (status === 422 || status === 400) return API_ERROR_CODES.validation;
  if (status >= 500) return API_ERROR_CODES.server;
  return API_ERROR_CODES.unknown;
}

/** Type guard — dùng ở UI để đọc `error.message` an toàn. */
export function isApiError(value: unknown): value is ApiError {
  return (
    typeof value === 'object' &&
    value !== null &&
    'code' in value &&
    'message' in value &&
    typeof (value as ApiError).message === 'string'
  );
}

/** Lấy thông điệp hiển thị cho người dùng từ bất kỳ lỗi nào. */
export function getErrorMessage(error: unknown): string {
  return normalizeError(error).message;
}

/** Cờ bật mock API — đọc từ biến môi trường, mặc định bật cho demo. */
export const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API !== 'false';

export default apiClient;
