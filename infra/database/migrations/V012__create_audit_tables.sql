CREATE TABLE audit.audit_event (
    id UUID PRIMARY KEY,
    event_time TIMESTAMPTZ NOT NULL,
    actor_type VARCHAR(20) NOT NULL,
    actor_id UUID NULL,
    action VARCHAR(60) NOT NULL,
    resource_type VARCHAR(40) NOT NULL,
    resource_id UUID NULL,
    customer_id UUID NULL,
    loan_application_id UUID NULL,
    result VARCHAR(20) NOT NULL,
    ip_address INET NULL,
    user_agent TEXT NULL,
    session_id TEXT NULL,
    request_id UUID NULL,
    correlation_id UUID NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    previous_hash CHAR(64) NULL,
    event_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE FUNCTION audit.reject_audit_event_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
BEGIN
    RAISE EXCEPTION 'audit.audit_event is append-only; % is not permitted', TG_OP
        USING ERRCODE = '42501';
END
$function$;

REVOKE ALL ON FUNCTION audit.reject_audit_event_mutation() FROM PUBLIC;

CREATE TRIGGER trg_audit_event_append_only
BEFORE UPDATE OR DELETE ON audit.audit_event
FOR EACH ROW
EXECUTE FUNCTION audit.reject_audit_event_mutation();
