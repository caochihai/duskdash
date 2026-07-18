/**
 * Máy tính khoản vay — CHỈ DÙNG CHO DEMO.
 *
 * Đây là công thức niên kim (annuity) tiêu chuẩn dùng để minh hoạ giao diện.
 * Nó KHÔNG phản ánh chính sách tín dụng, biểu lãi suất hay kết quả thẩm định
 * thực tế của SHB. Khi có backend, toàn bộ phép tính phải chuyển về phía máy chủ.
 */

export interface LoanEstimateInput {
  /** Số tiền vay (VNĐ). */
  amount: number;
  /** Thời hạn (năm). */
  termYears: number;
  /** Lãi suất giả định (%/năm). */
  annualRatePercent: number;
}

export interface LoanEstimateResult {
  monthlyPayment: number;
  totalPayment: number;
  totalInterest: number;
  months: number;
}

/**
 * Trả đều hàng tháng (annuity): M = P * r / (1 - (1 + r)^-n)
 */
export function calculateAnnuityLoan(input: LoanEstimateInput): LoanEstimateResult {
  const { amount, termYears, annualRatePercent } = input;
  const months = Math.round(termYears * 12);

  if (amount <= 0 || months <= 0) {
    return { monthlyPayment: 0, totalPayment: 0, totalInterest: 0, months: 0 };
  }

  const monthlyRate = annualRatePercent / 100 / 12;

  // Lãi suất 0% -> chia đều gốc.
  if (monthlyRate === 0) {
    const monthlyPayment = amount / months;
    return {
      monthlyPayment,
      totalPayment: amount,
      totalInterest: 0,
      months,
    };
  }

  const monthlyPayment = (amount * monthlyRate) / (1 - Math.pow(1 + monthlyRate, -months));
  const totalPayment = monthlyPayment * months;

  return {
    monthlyPayment,
    totalPayment,
    totalInterest: totalPayment - amount,
    months,
  };
}
