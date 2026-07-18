CREATE VIEW customer.v_customer_summary
WITH (security_barrier = TRUE)
AS
SELECT
    customer_record.id AS customer_id,
    customer_record.customer_number,
    party.id AS party_id,
    party.party_type,
    party.display_name,
    person.full_name,
    customer_record.customer_segment,
    customer_record.home_branch_id,
    customer_record.relationship_manager_id,
    customer_record.onboarding_date,
    customer_record.kyc_status,
    customer_record.risk_rating,
    customer_record.risk_rating_as_of,
    customer_record.status,
    customer_record.updated_at
FROM customer.customer AS customer_record
JOIN customer.party AS party
  ON party.id = customer_record.party_id
LEFT JOIN customer.person_profile AS person
  ON person.party_id = party.id;

CREATE VIEW banking.v_account_masked
WITH (security_barrier = TRUE)
AS
SELECT
    account.id AS account_id,
    holder.party_id,
    account.account_number_masked,
    account.account_type,
    account.currency,
    account.branch_id,
    account.status,
    account.opened_at,
    account.closed_at,
    account.current_balance,
    account.balance_as_of,
    account.updated_at
FROM banking.account
LEFT JOIN banking.account_holder AS holder
  ON holder.account_id = account.id
 AND (holder.valid_until IS NULL OR holder.valid_until >= CURRENT_DATE);

CREATE VIEW banking.v_transaction_summary
WITH (security_barrier = TRUE)
AS
SELECT
    transaction_record.id AS transaction_id,
    transaction_record.account_id,
    transaction_record.booking_time,
    transaction_record.value_date,
    transaction_record.direction,
    transaction_record.amount,
    transaction_record.currency,
    transaction_record.transaction_type,
    transaction_record.channel,
    transaction_record.description,
    transaction_record.balance_after,
    transaction_record.counterparty_name_masked,
    transaction_record.reference_number,
    transaction_record.status
FROM banking."transaction" AS transaction_record;

CREATE VIEW document.v_document_summary
WITH (security_barrier = TRUE)
AS
SELECT
    document.id AS document_id,
    document.document_type,
    document.document_subtype,
    document.title,
    document.owner_party_id,
    document.classification,
    document.document_date,
    document.valid_from,
    document.valid_until,
    document.verification_status,
    document.processing_status,
    current_version.id AS current_version_id,
    current_version.version_number,
    current_version.mime_type,
    current_version.file_size,
    current_version.scan_status,
    document.created_at,
    document.updated_at
FROM document.document
LEFT JOIN document.document_version AS current_version
  ON current_version.document_id = document.id
 AND current_version.is_current;

CREATE VIEW credit.v_loan_application_summary
WITH (security_barrier = TRUE)
AS
SELECT
    loan.id AS loan_application_id,
    loan.application_number,
    loan.primary_customer_id,
    loan.product_id,
    product.product_code,
    product.product_name,
    loan.requested_amount,
    loan.currency,
    loan.requested_term_months,
    loan.loan_purpose,
    loan.status,
    loan.assigned_employee_id,
    loan.submitted_at,
    loan.created_at,
    loan.updated_at
FROM credit.loan_application AS loan
JOIN credit.loan_product AS product
  ON product.id = loan.product_id;

CREATE VIEW ai.v_report_summary
WITH (security_barrier = TRUE)
AS
SELECT
    report.id AS report_id,
    report.analysis_case_id,
    analysis_case.customer_id,
    analysis_case.loan_application_id,
    report.report_type,
    report.status,
    report.reviewed_by,
    report.approved_by,
    report.version_number,
    report.pdf_object_id,
    report.created_at
FROM ai.report
JOIN ai.analysis_case
  ON analysis_case.id = report.analysis_case_id;

