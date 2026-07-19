import type { ChatSuggestion } from '@/types/chat';
import styles from './SuggestedQuestions.module.css';

export interface SuggestedQuestionsProps {
  suggestions: ChatSuggestion[];
  onSelect: (prompt: string) => void;
  label?: string;
  disabled?: boolean;
  /** Gợi ý mở phiên khách hàng -> chuyển phiên thay vì gửi câu hỏi. */
  onOpenCustomer?: (customerId: string) => void;
}

/** Chip gợi ý câu hỏi tiếp theo, hiển thị sau câu trả lời AI. */
export function SuggestedQuestions({
  suggestions,
  onSelect,
  label = 'Bạn có thể hỏi tiếp',
  disabled = false,
  onOpenCustomer,
}: SuggestedQuestionsProps) {
  if (!suggestions.length) return null;

  return (
    <div className={styles.wrapper}>
      <span className={styles.label}>{label}</span>
      <div className={styles.chips}>
        {suggestions.map((suggestion) => (
          <button
            key={suggestion.id}
            type="button"
            className={styles.chip}
            onClick={() => {
              if (suggestion.opensCustomerId && onOpenCustomer) {
                onOpenCustomer(suggestion.opensCustomerId);
                return;
              }
              onSelect(suggestion.prompt);
            }}
            disabled={disabled}
          >
            {suggestion.label}
          </button>
        ))}
      </div>
    </div>
  );
}
