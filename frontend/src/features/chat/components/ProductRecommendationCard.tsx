import { Button, Tag } from 'antd';
import { CheckCircleFilled } from '@ant-design/icons';
import styles from './ProductRecommendationCard.module.css';

export interface ProductRecommendationCardProps {
  title: string;
  description: string;
  benefits: string[];
  badge?: string;
  primaryActionLabel: string;
  secondaryActionLabel?: string;
  onPrimaryAction: () => void;
  onSecondaryAction?: () => void;
}

/** Thẻ giới thiệu sản phẩm trong câu trả lời AI. */
export function ProductRecommendationCard({
  title,
  description,
  benefits,
  badge,
  primaryActionLabel,
  secondaryActionLabel,
  onPrimaryAction,
  onSecondaryAction,
}: ProductRecommendationCardProps) {
  return (
    <section className={styles.card}>
      <span className={styles.accent} aria-hidden="true" />

      <div className={styles.header}>
        <h3 className={styles.title}>{title}</h3>
        {badge && <Tag>{badge}</Tag>}
      </div>

      <p className={styles.description}>{description}</p>

      <ul className={styles.benefits}>
        {benefits.map((benefit) => (
          <li key={benefit} className={styles.benefit}>
            <CheckCircleFilled className={styles.benefitIcon} aria-hidden="true" />
            <span>{benefit}</span>
          </li>
        ))}
      </ul>

      <div className={styles.actions}>
        <Button type="primary" onClick={onPrimaryAction}>
          {primaryActionLabel}
        </Button>
        {secondaryActionLabel && onSecondaryAction && (
          <Button onClick={onSecondaryAction}>{secondaryActionLabel}</Button>
        )}
      </div>
    </section>
  );
}
