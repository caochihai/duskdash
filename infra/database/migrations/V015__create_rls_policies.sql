-- RLS is deliberately not forced for the migration owner so repeatable seed
-- scripts can run as bank_migrator. Runtime roles are non-owners and cannot
-- bypass RLS.
ALTER TABLE customer.customer ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer.party_identifier ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer.party_contact ENABLE ROW LEVEL SECURITY;
ALTER TABLE banking.account ENABLE ROW LEVEL SECURITY;
ALTER TABLE banking."transaction" ENABLE ROW LEVEL SECURITY;
ALTER TABLE document.document ENABLE ROW LEVEL SECURITY;
ALTER TABLE document.document_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE document.extracted_field ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit.loan_application ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit.loan_decision ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai.conversation ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai.analysis_case ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai.finding ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai.report ENABLE ROW LEVEL SECURITY;

CREATE POLICY customer_select_policy
ON customer.customer
FOR SELECT
TO bank_app, bank_worker
USING (identity.can_access_customer(identity.current_employee_id(), id));

CREATE POLICY customer_insert_policy
ON customer.customer
FOR INSERT
TO bank_app
WITH CHECK (
    identity.current_is_admin()
    OR (
        identity.current_employee_id() IS NOT NULL
        AND identity.current_branch_id() = home_branch_id
    )
);

CREATE POLICY customer_update_policy
ON customer.customer
FOR UPDATE
TO bank_app
USING (identity.can_access_customer(identity.current_employee_id(), id))
WITH CHECK (identity.can_access_customer(identity.current_employee_id(), id));

CREATE POLICY party_identifier_access_policy
ON customer.party_identifier
FOR ALL
TO bank_app, bank_worker
USING (
    EXISTS (
        SELECT 1
        FROM customer.customer AS customer_record
        WHERE customer_record.party_id = party_identifier.party_id
          AND identity.can_access_customer(
              identity.current_employee_id(),
              customer_record.id
          )
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM customer.customer AS customer_record
        WHERE customer_record.party_id = party_identifier.party_id
          AND identity.can_access_customer(
              identity.current_employee_id(),
              customer_record.id
          )
    )
);

CREATE POLICY party_contact_access_policy
ON customer.party_contact
FOR ALL
TO bank_app, bank_worker
USING (
    EXISTS (
        SELECT 1
        FROM customer.customer AS customer_record
        WHERE customer_record.party_id = party_contact.party_id
          AND identity.can_access_customer(
              identity.current_employee_id(),
              customer_record.id
          )
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM customer.customer AS customer_record
        WHERE customer_record.party_id = party_contact.party_id
          AND identity.can_access_customer(
              identity.current_employee_id(),
              customer_record.id
          )
    )
);

CREATE POLICY account_access_policy
ON banking.account
FOR ALL
TO bank_app, bank_worker
USING (
    identity.current_is_admin()
    OR (
        identity.current_employee_id() IS NOT NULL
        AND branch_id = identity.current_branch_id()
    )
    OR EXISTS (
        SELECT 1
        FROM banking.account_holder AS holder
        JOIN customer.customer AS customer_record
          ON customer_record.party_id = holder.party_id
        WHERE holder.account_id = account.id
          AND identity.can_access_customer(
              identity.current_employee_id(),
              customer_record.id
          )
    )
)
WITH CHECK (
    identity.current_is_admin()
    OR (
        identity.current_employee_id() IS NOT NULL
        AND branch_id = identity.current_branch_id()
    )
    OR EXISTS (
        SELECT 1
        FROM banking.account_holder AS holder
        JOIN customer.customer AS customer_record
          ON customer_record.party_id = holder.party_id
        WHERE holder.account_id = account.id
          AND identity.can_access_customer(
              identity.current_employee_id(),
              customer_record.id
          )
    )
);

CREATE POLICY transaction_access_policy
ON banking."transaction"
FOR ALL
TO bank_app, bank_worker
USING (
    EXISTS (
        SELECT 1
        FROM banking.account
        WHERE account.id = "transaction".account_id
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM banking.account
        WHERE account.id = "transaction".account_id
    )
);

CREATE POLICY document_access_policy
ON document.document
FOR ALL
TO bank_app, bank_worker
USING (
    identity.current_is_admin()
    OR created_by = identity.current_employee_id()
    OR EXISTS (
        SELECT 1
        FROM customer.customer AS customer_record
        WHERE customer_record.party_id = document.owner_party_id
          AND identity.can_access_customer(
              identity.current_employee_id(),
              customer_record.id
          )
    )
    OR EXISTS (
        SELECT 1
        FROM document.document_link AS document_link
        WHERE document_link.document_id = document.id
          AND (
              (
                  document_link.entity_type = 'CUSTOMER'
                  AND identity.can_access_customer(
                      identity.current_employee_id(),
                      document_link.entity_id
                  )
              )
              OR (
                  document_link.entity_type = 'LOAN_APPLICATION'
                  AND identity.can_access_loan(
                      identity.current_employee_id(),
                      document_link.entity_id
                  )
              )
          )
    )
)
WITH CHECK (
    identity.current_is_admin()
    OR created_by = identity.current_employee_id()
    OR EXISTS (
        SELECT 1
        FROM customer.customer AS customer_record
        WHERE customer_record.party_id = document.owner_party_id
          AND identity.can_access_customer(
              identity.current_employee_id(),
              customer_record.id
          )
    )
);

CREATE POLICY document_version_access_policy
ON document.document_version
FOR ALL
TO bank_app, bank_worker
USING (
    EXISTS (
        SELECT 1
        FROM document.document
        WHERE document.id = document_version.document_id
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM document.document
        WHERE document.id = document_version.document_id
    )
);

CREATE POLICY extracted_field_access_policy
ON document.extracted_field
FOR ALL
TO bank_app, bank_worker
USING (
    EXISTS (
        SELECT 1
        FROM document.document_version
        WHERE document_version.id = extracted_field.document_version_id
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM document.document_version
        WHERE document_version.id = extracted_field.document_version_id
    )
);

CREATE POLICY loan_application_select_policy
ON credit.loan_application
FOR SELECT
TO bank_app, bank_worker
USING (identity.can_access_loan(identity.current_employee_id(), id));

CREATE POLICY loan_application_insert_policy
ON credit.loan_application
FOR INSERT
TO bank_app
WITH CHECK (
    created_by = identity.current_employee_id()
    AND identity.can_access_customer(
        identity.current_employee_id(),
        primary_customer_id
    )
);

CREATE POLICY loan_application_update_policy
ON credit.loan_application
FOR UPDATE
TO bank_app
USING (identity.can_access_loan(identity.current_employee_id(), id))
WITH CHECK (identity.can_access_loan(identity.current_employee_id(), id));

CREATE POLICY loan_decision_select_policy
ON credit.loan_decision
FOR SELECT
TO bank_app
USING (
    identity.can_access_loan(
        identity.current_employee_id(),
        loan_application_id
    )
);

CREATE POLICY loan_decision_insert_policy
ON credit.loan_decision
FOR INSERT
TO bank_app
WITH CHECK (
    decision_maker_id = identity.current_employee_id()
    AND identity.can_access_loan(
        identity.current_employee_id(),
        loan_application_id
    )
    AND (
        identity.current_is_admin()
        OR identity.current_has_role('loan_approver'::public.citext)
    )
);

CREATE POLICY loan_decision_update_policy
ON credit.loan_decision
FOR UPDATE
TO bank_app
USING (
    decision_maker_id = identity.current_employee_id()
    AND identity.can_access_loan(
        identity.current_employee_id(),
        loan_application_id
    )
    AND (
        identity.current_is_admin()
        OR identity.current_has_role('loan_approver'::public.citext)
    )
)
WITH CHECK (
    decision_maker_id = identity.current_employee_id()
    AND identity.can_access_loan(
        identity.current_employee_id(),
        loan_application_id
    )
    AND (
        identity.current_is_admin()
        OR identity.current_has_role('loan_approver'::public.citext)
    )
);

CREATE POLICY conversation_select_policy
ON ai.conversation
FOR SELECT
TO bank_app, bank_worker
USING (
    identity.current_is_admin()
    OR employee_id = identity.current_employee_id()
);

CREATE POLICY conversation_insert_policy
ON ai.conversation
FOR INSERT
TO bank_app
WITH CHECK (
    employee_id = identity.current_employee_id()
    AND (
        active_customer_id IS NULL
        OR identity.can_access_customer(
            identity.current_employee_id(),
            active_customer_id
        )
    )
    AND (
        active_loan_application_id IS NULL
        OR identity.can_access_loan(
            identity.current_employee_id(),
            active_loan_application_id
        )
    )
);

CREATE POLICY conversation_update_policy
ON ai.conversation
FOR UPDATE
TO bank_app
USING (
    identity.current_is_admin()
    OR employee_id = identity.current_employee_id()
)
WITH CHECK (
    identity.current_is_admin()
    OR employee_id = identity.current_employee_id()
);

CREATE POLICY analysis_case_access_policy
ON ai.analysis_case
FOR ALL
TO bank_app, bank_worker
USING (
    identity.can_access_customer(identity.current_employee_id(), customer_id)
    AND (
        loan_application_id IS NULL
        OR identity.can_access_loan(
            identity.current_employee_id(),
            loan_application_id
        )
    )
)
WITH CHECK (
    created_by = identity.current_employee_id()
    AND identity.can_access_customer(identity.current_employee_id(), customer_id)
    AND (
        loan_application_id IS NULL
        OR identity.can_access_loan(
            identity.current_employee_id(),
            loan_application_id
        )
    )
);

CREATE POLICY finding_access_policy
ON ai.finding
FOR ALL
TO bank_app, bank_worker
USING (
    EXISTS (
        SELECT 1
        FROM ai.analysis_case
        WHERE analysis_case.id = finding.analysis_case_id
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM ai.analysis_case
        WHERE analysis_case.id = finding.analysis_case_id
    )
);

CREATE POLICY report_access_policy
ON ai.report
FOR ALL
TO bank_app, bank_worker
USING (
    EXISTS (
        SELECT 1
        FROM ai.analysis_case
        WHERE analysis_case.id = report.analysis_case_id
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM ai.analysis_case
        WHERE analysis_case.id = report.analysis_case_id
    )
);
