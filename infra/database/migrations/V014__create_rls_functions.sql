CREATE FUNCTION identity.current_employee_id()
RETURNS UUID
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
DECLARE
    setting_value TEXT;
    parsed_value UUID;
BEGIN
    setting_value := current_setting('app.employee_id', TRUE);
    IF setting_value IS NULL OR btrim(setting_value) = '' THEN
        RETURN NULL;
    END IF;

    BEGIN
        parsed_value := setting_value::UUID;
    EXCEPTION
        WHEN invalid_text_representation THEN
            RETURN NULL;
    END;

    IF EXISTS (
        SELECT 1
        FROM identity.employee AS employee
        WHERE employee.id = parsed_value
          AND employee.employment_status = 'ACTIVE'
    ) THEN
        RETURN parsed_value;
    END IF;

    RETURN NULL;
END
$function$;

CREATE FUNCTION identity.current_branch_id()
RETURNS UUID
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
DECLARE
    setting_value TEXT;
    parsed_value UUID;
    employee_value UUID;
BEGIN
    setting_value := current_setting('app.branch_id', TRUE);
    employee_value := identity.current_employee_id();
    IF setting_value IS NULL OR btrim(setting_value) = '' OR employee_value IS NULL THEN
        RETURN NULL;
    END IF;

    BEGIN
        parsed_value := setting_value::UUID;
    EXCEPTION
        WHEN invalid_text_representation THEN
            RETURN NULL;
    END;

    IF EXISTS (
        SELECT 1
        FROM identity.employee AS employee
        WHERE employee.id = employee_value
          AND employee.branch_id = parsed_value
    ) THEN
        RETURN parsed_value;
    END IF;

    RETURN NULL;
END
$function$;

CREATE FUNCTION identity.current_has_role(required_role_code public.citext)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
    SELECT identity.current_employee_id() IS NOT NULL
       AND EXISTS (
            SELECT 1
            FROM identity.employee_role AS employee_role
            JOIN identity.role AS role
              ON role.id = employee_role.role_id
            WHERE employee_role.employee_id = identity.current_employee_id()
              AND role.role_code = required_role_code
              AND employee_role.valid_from <= CURRENT_TIMESTAMP
              AND (employee_role.valid_until IS NULL OR employee_role.valid_until > CURRENT_TIMESTAMP)
       );
$function$;

CREATE FUNCTION identity.current_is_admin()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
    SELECT COALESCE(current_setting('app.is_admin', TRUE), 'false') = 'true'
       AND identity.current_has_role('admin'::public.citext);
$function$;

CREATE FUNCTION identity.can_access_customer(employee_id UUID, customer_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
    SELECT employee_id IS NOT NULL
       AND customer_id IS NOT NULL
       AND employee_id = identity.current_employee_id()
       AND (
            identity.current_is_admin()
            OR EXISTS (
                SELECT 1
                FROM customer.customer AS customer_record
                JOIN identity.employee AS employee
                  ON employee.id = employee_id
                WHERE customer_record.id = customer_id
                  AND (
                       customer_record.relationship_manager_id = employee_id
                       OR customer_record.home_branch_id = identity.current_branch_id()
                       OR EXISTS (
                           SELECT 1
                           FROM identity.employee_scope AS employee_scope
                           WHERE employee_scope.employee_id = employee_id
                             AND employee_scope.valid_from <= CURRENT_TIMESTAMP
                             AND (
                                 employee_scope.valid_until IS NULL
                                 OR employee_scope.valid_until > CURRENT_TIMESTAMP
                             )
                             AND employee_scope.permission_code IN (
                                 'customer:read'::public.citext,
                                 'customer:search'::public.citext
                             )
                             AND (
                                 (
                                     employee_scope.scope_type = 'CUSTOMER'
                                     AND employee_scope.scope_id = customer_id
                                 )
                                 OR (
                                     employee_scope.scope_type = 'BRANCH'
                                     AND employee_scope.scope_id = customer_record.home_branch_id
                                 )
                             )
                       )
                  )
            )
       );
$function$;

CREATE FUNCTION identity.can_access_loan(employee_id UUID, loan_application_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
    SELECT employee_id IS NOT NULL
       AND loan_application_id IS NOT NULL
       AND employee_id = identity.current_employee_id()
       AND (
            identity.current_is_admin()
            OR EXISTS (
                SELECT 1
                FROM credit.loan_application AS loan
                WHERE loan.id = loan_application_id
                  AND (
                      loan.assigned_employee_id = employee_id
                      OR identity.can_access_customer(employee_id, loan.primary_customer_id)
                      OR EXISTS (
                          SELECT 1
                          FROM identity.employee_scope AS employee_scope
                          WHERE employee_scope.employee_id = employee_id
                            AND employee_scope.scope_type = 'LOAN_APPLICATION'
                            AND employee_scope.scope_id = loan_application_id
                            AND employee_scope.valid_from <= CURRENT_TIMESTAMP
                            AND (
                                employee_scope.valid_until IS NULL
                                OR employee_scope.valid_until > CURRENT_TIMESTAMP
                            )
                            AND employee_scope.permission_code IN (
                                'loan:read'::public.citext,
                                'loan:update'::public.citext,
                                'loan:analyze'::public.citext,
                                'loan:submit'::public.citext,
                                'loan:approve'::public.citext
                            )
                      )
                  )
            )
       );
$function$;

REVOKE ALL ON FUNCTION identity.current_employee_id() FROM PUBLIC;
REVOKE ALL ON FUNCTION identity.current_branch_id() FROM PUBLIC;
REVOKE ALL ON FUNCTION identity.current_has_role(public.citext) FROM PUBLIC;
REVOKE ALL ON FUNCTION identity.current_is_admin() FROM PUBLIC;
REVOKE ALL ON FUNCTION identity.can_access_customer(UUID, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION identity.can_access_loan(UUID, UUID) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION identity.current_employee_id() TO bank_app, bank_worker;
GRANT EXECUTE ON FUNCTION identity.current_branch_id() TO bank_app, bank_worker;
GRANT EXECUTE ON FUNCTION identity.current_has_role(public.citext) TO bank_app, bank_worker;
GRANT EXECUTE ON FUNCTION identity.current_is_admin() TO bank_app, bank_worker;
GRANT EXECUTE ON FUNCTION identity.can_access_customer(UUID, UUID) TO bank_app, bank_worker;
GRANT EXECUTE ON FUNCTION identity.can_access_loan(UUID, UUID) TO bank_app, bank_worker;
