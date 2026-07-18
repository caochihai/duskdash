const vndFormatter = new Intl.NumberFormat('vi-VN', {
  maximumFractionDigits: 0,
});

/** 2000000000 -> "2.000.000.000 VNĐ" */
export function formatCurrency(value: number): string {
  return `${vndFormatter.format(Math.round(value))} VNĐ`;
}

/** 2000000000 -> "2.000.000.000" */
export function formatNumber(value: number): string {
  return vndFormatter.format(Math.round(value));
}

/** 2000000000 -> "2 tỷ", 15000000 -> "15 triệu" — dùng cho nhãn ngắn/chart. */
export function formatCompactVnd(value: number): string {
  if (Math.abs(value) >= 1_000_000_000) {
    const billions = value / 1_000_000_000;
    return `${Number(billions.toFixed(billions >= 10 ? 0 : 1))} tỷ`;
  }
  if (Math.abs(value) >= 1_000_000) {
    const millions = value / 1_000_000;
    return `${Number(millions.toFixed(millions >= 10 ? 0 : 1))} triệu`;
  }
  if (Math.abs(value) >= 1_000) {
    return `${Number((value / 1_000).toFixed(0))} nghìn`;
  }
  return formatNumber(value);
}

/** 9 -> "9%/năm" */
export function formatRate(value: number): string {
  return `${Number(value.toFixed(2))}%/năm`;
}
