# Data dictionary

This dictionary covers every required `bank_ai` table and column. `N` means
nullable and `D` shows the database default (`—` means none). Index notation:
`PK` primary key, `UQ` unique, `IDX` lookup/filter participation, `GIN`, `BRIN`,
`HNSW`; the authoritative created secondary-index name and expression are in the
exact catalogue at the end of this file. Entries written `FK →` are physical
constraints. Entries written `logical reference →` deliberately have no physical
FK in V001–V017 (typically to avoid circular/polymorphic coupling) and must be
validated by the owning service.

Retention/sensitivity classes:

| Code | Retention class |
| --- | --- |
| `R1` | Reference/authorization configuration; retain while effective plus approved archive period |
| `R2` | Business/financial record; retain under applicable resource rule and legal hold |
| `R3` | Direct or linkable PII; encrypted/masked where specified and retained under R2 rules |
| `R4` | Document/object metadata or extracted content; follow document/object retention and legal hold |
| `R5` | Operational/replay/idempotency data; bounded cleanup after configured operational window |
| `R6` | Audit evidence; append-only and archived under audit retention/legal hold |
| `R7` | AI analysis/finding/report data; retained with its analysis/loan case and legal hold |

“Sensitive” includes direct PII, linkable identifiers, financial/confidential
content and security-relevant payloads. UUIDs that link to a person/resource are
marked sensitive even when they are not meaningful outside the system.

## `identity`

### `identity.branch` — branch reference

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Opaque branch ID | No / R1 |
| `branch_code` | CITEXT | No / — | UQ | Stable branch code | No / R1 |
| `branch_name` | TEXT | No / — | — | Display name | No / R1 |
| `parent_branch_id` | UUID | Yes / — | FK → `identity.branch.id`, IDX | Parent branch; cannot equal `id` | No / R1 |
| `status` | VARCHAR(20) | No / — | IDX | `ACTIVE` or `INACTIVE` | No / R1 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time UTC | No / R1 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update UTC | No / R1 |

### `identity.department` — organizational department

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Department ID | No / R1 |
| `department_code` | CITEXT | No / — | UQ | Stable department code | No / R1 |
| `department_name` | TEXT | No / — | — | Department name | No / R1 |
| `branch_id` | UUID | Yes / — | FK → `identity.branch.id`, IDX | Owning branch when branch-specific | No / R1 |
| `status` | VARCHAR(20) | No / — | IDX | Lifecycle status | No / R1 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | No / R1 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update time | No / R1 |

### `identity.employee` — employee business profile; no password

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Employee ID | Yes / R3 |
| `identity_subject` | CITEXT | No / — | UQ | Keycloak JWT `sub` link | Yes / R3 |
| `employee_code` | CITEXT | No / — | UQ | Internal employee code | Yes / R3 |
| `full_name` | TEXT | No / — | — | Employee name | Yes / R3 |
| `email` | CITEXT | No / — | UQ | Work email | Yes / R3 |
| `branch_id` | UUID | No / — | FK → `identity.branch.id`, IDX | Home branch | Yes / R3 |
| `department_id` | UUID | No / — | FK → `identity.department.id`, IDX | Department | Yes / R3 |
| `job_title` | TEXT | Yes / — | — | Job title | Yes / R3 |
| `manager_id` | UUID | Yes / — | FK → `identity.employee.id`, IDX | Manager; cannot self-reference | Yes / R3 |
| `employment_status` | VARCHAR(20) | No / — | IDX | Employment lifecycle status | Yes / R3 |
| `last_synced_at` | TIMESTAMPTZ | Yes / — | — | Last identity sync | Yes / R3 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R3 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R3 |
| `version` | INTEGER | No / `1` | — | Optimistic lock; positive | No / R3 |

### `identity.role` — workbench role catalogue

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Role ID | No / R1 |
| `role_code` | CITEXT | No / — | UQ | Stable role code | No / R1 |
| `role_name` | TEXT | No / — | — | Display name | No / R1 |
| `description` | TEXT | Yes / — | — | Role purpose | No / R1 |
| `is_system_role` | BOOLEAN | No / `TRUE` | — | Protected seeded role flag | No / R1 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | No / R1 |

### `identity.permission` — action catalogue

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Permission ID | No / R1 |
| `permission_code` | CITEXT | No / — | UQ | Stable `resource:action` code | No / R1 |
| `resource_type` | VARCHAR(50) | No / — | IDX | Protected resource type | No / R1 |
| `action` | VARCHAR(30) | No / — | IDX | Allowed action | No / R1 |
| `description` | TEXT | Yes / — | — | Permission purpose | No / R1 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | No / R1 |

### `identity.role_permission` — role/permission mapping

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `role_id` | UUID | No / — | PK part, FK → `identity.role.id` | Granted role | No / R1 |
| `permission_id` | UUID | No / — | PK part, FK → `identity.permission.id` | Granted permission | No / R1 |
| `created_at` | TIMESTAMPTZ | No / — | — | Grant creation time | No / R1 |

### `identity.employee_role` — time-bounded employee role

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Assignment ID | Yes / R3 |
| `employee_id` | UUID | No / — | FK → `identity.employee.id`, IDX | Assigned employee | Yes / R3 |
| `role_id` | UUID | No / — | FK → `identity.role.id`, IDX | Assigned role | Yes / R3 |
| `valid_from` | TIMESTAMPTZ | No / — | IDX | Authorization start | Yes / R3 |
| `valid_until` | TIMESTAMPTZ | Yes / — | IDX | Authorization end; after start | Yes / R3 |
| `assigned_by` | UUID | Yes / — | FK → `identity.employee.id`, IDX | Assigning employee | Yes / R3 |
| `created_at` | TIMESTAMPTZ | No / — | — | Assignment creation | Yes / R3 |

### `identity.employee_scope` — scoped authorization grant

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Scope grant ID | Yes / R3 |
| `employee_id` | UUID | No / — | FK → `identity.employee.id`, IDX | Grantee | Yes / R3 |
| `scope_type` | VARCHAR(30) | No / — | composite IDX | `BRANCH`, `CUSTOMER`, `LOAN_APPLICATION`, or `ANALYSIS_CASE` | Yes / R3 |
| `scope_id` | UUID | No / — | composite IDX | Opaque scoped resource | Yes / R3 |
| `permission_code` | CITEXT | No / — | IDX | Permission granted in scope | Yes / R3 |
| `valid_from` | TIMESTAMPTZ | No / — | IDX | Grant start | Yes / R3 |
| `valid_until` | TIMESTAMPTZ | Yes / — | IDX | Grant end; after start | Yes / R3 |
| `assigned_by` | UUID | Yes / — | FK → `identity.employee.id` | Assigning employee | Yes / R3 |
| `reason` | TEXT | Yes / — | — | Grant justification | Yes / R3 |
| `created_at` | TIMESTAMPTZ | No / — | — | Grant creation | Yes / R3 |

Composite access index: `(employee_id, scope_type, scope_id, permission_code)`.

## `customer`

### `customer.party` — person/organization supertype

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Party ID | Yes / R3 |
| `party_type` | VARCHAR(20) | No / — | IDX | `PERSON` or `ORGANIZATION` | Yes / R3 |
| `display_name` | TEXT | No / — | IDX | Display/search name | Yes / R3 |
| `status` | VARCHAR(20) | No / — | IDX | Party lifecycle status | Yes / R3 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R3 |
| `created_by` | UUID | Yes / — | logical employee link | Creator | Yes / R3 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R3 |
| `updated_by` | UUID | Yes / — | logical employee link | Last editor | Yes / R3 |
| `version` | INTEGER | No / `1` | — | Optimistic lock; positive | No / R3 |

### `customer.person_profile`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `party_id` | UUID | No / — | PK, FK → `customer.party.id` | Person party | Yes / R3 |
| `full_name` | TEXT | No / — | — | Legal/full name | Yes / R3 |
| `date_of_birth` | DATE | Yes / — | — | Birth date; age is derived | Yes / R3 |
| `gender` | VARCHAR(20) | Yes / — | — | Declared gender | Yes / R3 |
| `nationality` | CHAR(2) | Yes / — | — | ISO country code | Yes / R3 |
| `marital_status` | VARCHAR(30) | Yes / — | — | Marital status | Yes / R3 |
| `occupation` | TEXT | Yes / — | — | Occupation | Yes / R3 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R3 |

### `customer.organization_profile`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `party_id` | UUID | No / — | PK, FK → `customer.party.id` | Organization party | Yes / R3 |
| `legal_name` | TEXT | No / — | — | Registered name | Yes / R3 |
| `trading_name` | TEXT | Yes / — | — | Trading name | Yes / R3 |
| `business_type` | VARCHAR(50) | Yes / — | IDX | Legal/business form | Yes / R3 |
| `registration_number_hash` | CHAR(64) | Yes / — | IDX | Hashed registration number | Yes / R3 |
| `tax_code_hash` | CHAR(64) | Yes / — | IDX | Hashed tax code | Yes / R3 |
| `incorporation_date` | DATE | Yes / — | — | Incorporation date | Yes / R3 |
| `industry_code` | VARCHAR(30) | Yes / — | IDX | Industry classification | Yes / R3 |
| `legal_representative_party_id` | UUID | Yes / — | FK → `customer.party.id`, IDX | Legal representative | Yes / R3 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R3 |

### `customer.customer` — bank/customer relationship

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Customer ID | Yes / R3 |
| `party_id` | UUID | No / — | UQ, FK → `customer.party.id` | One party per customer | Yes / R3 |
| `customer_number` | CITEXT | No / — | UQ | Internal customer number | Yes / R3 |
| `customer_segment` | VARCHAR(30) | Yes / — | IDX | Customer segment | Yes / R3 |
| `home_branch_id` | UUID | No / — | FK → `identity.branch.id`, IDX | Owning/home branch | Yes / R3 |
| `relationship_manager_id` | UUID | Yes / — | FK → `identity.employee.id`, IDX | Relationship manager | Yes / R3 |
| `onboarding_date` | DATE | Yes / — | — | Relationship start | Yes / R3 |
| `kyc_status` | VARCHAR(30) | No / — | IDX | Current KYC status | Yes / R3 |
| `risk_rating` | VARCHAR(20) | Yes / — | IDX | Current risk rating | Yes / R3 |
| `risk_rating_as_of` | DATE | Yes / — | — | Rating effective date | Yes / R3 |
| `status` | VARCHAR(20) | No / — | IDX | Customer lifecycle status | Yes / R3 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R3 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R3 |
| `version` | INTEGER | No / `1` | — | Optimistic lock; positive | No / R3 |

### `customer.party_identifier` — encrypted official identifier

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Identifier record ID | Yes / R3 |
| `party_id` | UUID | No / — | FK → `customer.party.id`, IDX | Owning party | Yes / R3 |
| `identifier_type` | VARCHAR(30) | No / — | UQ part, IDX | Identifier class | Yes / R3 |
| `encrypted_value` | BYTEA | No / — | no readonly exposure | Encrypted full value | Yes / R3 |
| `value_hash` | CHAR(64) | No / — | UQ part, IDX | Lookup/dedup hash | Yes / R3 |
| `last4` | VARCHAR(4) | Yes / — | — | Masked display suffix | Yes / R3 |
| `issued_date` | DATE | Yes / — | — | Issue date | Yes / R3 |
| `expiry_date` | DATE | Yes / — | IDX | Expiry, not before issue | Yes / R3 |
| `issuing_authority` | TEXT | Yes / — | — | Issuer | Yes / R3 |
| `country_code` | CHAR(2) | Yes / — | — | Issuing country | Yes / R3 |
| `verification_status` | VARCHAR(30) | No / — | IDX | Verification status | Yes / R3 |
| `source_document_id` | UUID | Yes / — | logical reference → `document.document.id` | Evidence document | Yes / R4 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R3 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R3 |

Unique constraint: `(identifier_type, value_hash)`.

### `customer.party_contact` — encrypted contact method

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Contact ID | Yes / R3 |
| `party_id` | UUID | No / — | FK → `customer.party.id`, IDX | Owning party | Yes / R3 |
| `contact_type` | VARCHAR(20) | No / — | composite IDX | Email/phone/contact type | Yes / R3 |
| `encrypted_value` | BYTEA | No / — | no readonly exposure | Encrypted full contact | Yes / R3 |
| `value_hash` | CHAR(64) | No / — | IDX | Lookup/dedup hash | Yes / R3 |
| `masked_value` | TEXT | Yes / — | — | Safe display value | Yes / R3 |
| `is_primary` | BOOLEAN | No / `FALSE` | composite IDX | Primary contact flag | Yes / R3 |
| `verification_status` | VARCHAR(30) | No / — | IDX | Verification status | Yes / R3 |
| `verified_at` | TIMESTAMPTZ | Yes / — | — | Verification time | Yes / R3 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R3 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R3 |

### `customer.party_address`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Address ID | Yes / R3 |
| `party_id` | UUID | No / — | FK → `customer.party.id`, IDX | Owning party | Yes / R3 |
| `address_type` | VARCHAR(30) | No / — | IDX | Registered/residential/etc. | Yes / R3 |
| `address_line` | TEXT | No / — | — | Street/address text | Yes / R3 |
| `ward` | TEXT | Yes / — | — | Ward | Yes / R3 |
| `district` | TEXT | Yes / — | — | District | Yes / R3 |
| `province` | TEXT | Yes / — | IDX | Province | Yes / R3 |
| `country_code` | CHAR(2) | No / — | — | Country | Yes / R3 |
| `valid_from` | DATE | Yes / — | — | Validity start | Yes / R3 |
| `valid_until` | DATE | Yes / — | — | Validity end, not before start | Yes / R3 |
| `verification_status` | VARCHAR(30) | No / — | IDX | Verification status | Yes / R3 |
| `source_document_id` | UUID | Yes / — | logical reference → `document.document.id` | Evidence document | Yes / R4 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R3 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R3 |

### `customer.employment`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Employment ID | Yes / R3 |
| `party_id` | UUID | No / — | FK → `customer.party.id`, IDX | Employed party | Yes / R3 |
| `employer_name` | TEXT | No / — | — | Employer | Yes / R3 |
| `position` | TEXT | Yes / — | — | Position | Yes / R3 |
| `employment_type` | VARCHAR(30) | Yes / — | IDX | Employment type | Yes / R3 |
| `start_date` | DATE | Yes / — | — | Start date | Yes / R3 |
| `end_date` | DATE | Yes / — | — | End date, not before start | Yes / R3 |
| `declared_monthly_income` | NUMERIC(24,4) | Yes / — | — | Declared monthly income | Yes / R2 |
| `currency` | CHAR(3) | No / `'VND'` | — | Currency | No / R2 |
| `verification_status` | VARCHAR(30) | No / — | IDX | Verification status | Yes / R3 |
| `source_document_id` | UUID | Yes / — | logical reference → `document.document.id` | Evidence document | Yes / R4 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R3 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R3 |
| `version` | INTEGER | No / `1` | — | Optimistic lock | No / R3 |

### `customer.income_source` — declared, verified and accepted income

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Income record ID | Yes / R2 |
| `party_id` | UUID | No / — | FK → `customer.party.id`, IDX | Income owner | Yes / R3 |
| `income_type` | VARCHAR(30) | No / — | IDX | Salary/business/etc. | Yes / R2 |
| `declared_amount` | NUMERIC(24,4) | Yes / — | — | Customer-declared amount | Yes / R2 |
| `verified_amount` | NUMERIC(24,4) | Yes / — | — | Evidence-verified amount | Yes / R2 |
| `accepted_amount` | NUMERIC(24,4) | Yes / — | — | Underwriting accepted amount; may exceed verified only with approval | Yes / R2 |
| `frequency` | VARCHAR(20) | No / — | — | Payment frequency | Yes / R2 |
| `currency` | CHAR(3) | No / — | — | Currency | No / R2 |
| `as_of_date` | DATE | No / — | IDX | Observation date | Yes / R2 |
| `verification_method` | VARCHAR(30) | Yes / — | — | Method | Yes / R2 |
| `verification_status` | VARCHAR(30) | No / — | IDX | Status | Yes / R2 |
| `source_document_id` | UUID | Yes / — | logical reference → `document.document.id` | Document evidence | Yes / R4 |
| `source_calculation_id` | UUID | Yes / — | logical reference → `credit.calculation_record.id` | Calculation evidence | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R2 |
| `version` | INTEGER | No / `1` | — | Optimistic lock | No / R2 |

### `customer.party_relationship`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Relationship ID | Yes / R3 |
| `from_party_id` | UUID | No / — | FK → `customer.party.id`, IDX | Source party | Yes / R3 |
| `to_party_id` | UUID | No / — | FK → `customer.party.id`, IDX | Related party; cannot equal source | Yes / R3 |
| `relationship_type` | VARCHAR(40) | No / — | IDX | Spouse/co-borrower/guarantor/legal representative/director/shareholder/related company | Yes / R3 |
| `valid_from` | DATE | Yes / — | — | Validity start | Yes / R3 |
| `valid_until` | DATE | Yes / — | — | Validity end | Yes / R3 |
| `source_document_id` | UUID | Yes / — | logical reference → `document.document.id` | Evidence document | Yes / R4 |
| `verification_status` | VARCHAR(30) | No / — | IDX | Verification status | Yes / R3 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R3 |

### `customer.kyc_assessment`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Assessment ID | Yes / R3 |
| `customer_id` | UUID | No / — | FK → `customer.customer.id`, IDX | Assessed customer | Yes / R3 |
| `assessment_date` | TIMESTAMPTZ | No / — | IDX | Assessment time | Yes / R3 |
| `kyc_status` | VARCHAR(30) | No / — | IDX | KYC result | Yes / R3 |
| `aml_risk_level` | VARCHAR(20) | Yes / — | IDX | AML risk | Yes / R3 |
| `pep_status` | VARCHAR(20) | Yes / — | IDX | PEP result | Yes / R3 |
| `sanction_status` | VARCHAR(20) | Yes / — | IDX | Sanctions result | Yes / R3 |
| `beneficial_owner_verified` | BOOLEAN | Yes / — | — | Beneficial-owner verification | Yes / R3 |
| `source_system` | TEXT | Yes / — | — | Assessment source | Yes / R3 |
| `assessment_payload` | JSONB | No / `{}` | GIN where queried | Structured details; minimize PII | Yes / R3 |
| `assessed_by` | UUID | Yes / — | FK → `identity.employee.id` | Assessor | Yes / R3 |
| `created_at` | TIMESTAMPTZ | No / — | — | Record creation | Yes / R3 |

## `banking`

### `banking.account`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Account ID | Yes / R2 |
| `account_number_masked` | TEXT | No / — | — | Masked number for display | Yes / R3 |
| `account_number_hash` | CHAR(64) | No / — | UQ | Search/dedup hash; never full number | Yes / R3 |
| `account_type` | VARCHAR(30) | No / — | IDX | Account product/type | Yes / R2 |
| `currency` | CHAR(3) | No / — | — | Account currency | No / R2 |
| `branch_id` | UUID | Yes / — | FK → `identity.branch.id`, IDX | Servicing branch | Yes / R2 |
| `status` | VARCHAR(20) | No / — | IDX | Account lifecycle status | Yes / R2 |
| `opened_at` | TIMESTAMPTZ | Yes / — | — | Open time | Yes / R2 |
| `closed_at` | TIMESTAMPTZ | Yes / — | — | Close time, not before open | Yes / R2 |
| `current_balance` | NUMERIC(24,4) | Yes / — | — | Latest known balance | Yes / R2 |
| `balance_as_of` | TIMESTAMPTZ | Yes / — | — | Balance observation time | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R2 |
| `version` | INTEGER | No / `1` | — | Optimistic lock | No / R2 |

### `banking.account_holder`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Holder relationship ID | Yes / R2 |
| `account_id` | UUID | No / — | FK → `banking.account.id`, IDX | Account | Yes / R2 |
| `party_id` | UUID | No / — | FK → `customer.party.id`, IDX | Holder party | Yes / R3 |
| `holder_role` | VARCHAR(30) | No / — | IDX | Owner/joint/authorized role | Yes / R2 |
| `valid_from` | DATE | Yes / — | — | Relationship start | Yes / R2 |
| `valid_until` | DATE | Yes / — | — | Relationship end | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |

### `banking.transaction` — monthly range-partitioned on `booking_time`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK part | Transaction ID | Yes / R2 |
| `account_id` | UUID | No / — | FK → `banking.account.id`, composite IDX | Account | Yes / R2 |
| `booking_time` | TIMESTAMPTZ | No / — | PK/partition key; B-tree/BRIN | Booking time UTC | Yes / R2 |
| `value_date` | DATE | Yes / — | — | Value date | Yes / R2 |
| `direction` | VARCHAR(10) | No / — | IDX | `CREDIT` or `DEBIT` | Yes / R2 |
| `amount` | NUMERIC(24,4) | No / — | — | Positive amount | Yes / R2 |
| `currency` | CHAR(3) | No / — | — | Currency | No / R2 |
| `transaction_type` | VARCHAR(50) | Yes / — | composite IDX | Classified transaction type | Yes / R2 |
| `channel` | VARCHAR(30) | Yes / — | IDX | Origination channel | Yes / R2 |
| `description` | TEXT | Yes / — | — | Transaction narrative; may contain PII | Yes / R2 |
| `balance_after` | NUMERIC(24,4) | Yes / — | — | Post-transaction balance | Yes / R2 |
| `counterparty_name_masked` | TEXT | Yes / — | — | Masked counterparty | Yes / R3 |
| `counterparty_account_hash` | CHAR(64) | Yes / — | IDX | Counterparty account hash | Yes / R3 |
| `reference_number` | TEXT | Yes / — | IDX | Bank reference | Yes / R2 |
| `status` | VARCHAR(20) | No / — | IDX | Transaction status | Yes / R2 |
| `raw_payload` | JSONB | No / `{}` | no readonly exposure | Source payload; minimize and protect | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Ingestion time | Yes / R2 |

Primary key: `(id, booking_time)`. Every monthly/default partition has
`(account_id, booking_time DESC)`, `(transaction_type, booking_time DESC)`,
`counterparty_account_hash`, and BRIN `(booking_time)` indexes. Partitions cover
the previous/current years and a default; the maintenance script creates future
months.

### `banking.account_monthly_summary`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `account_id` | UUID | No / — | PK part, FK → `banking.account.id` | Account | Yes / R2 |
| `year_month` | DATE | No / — | PK part | First day of summary month | Yes / R2 |
| `total_inflow` | NUMERIC(24,4) | No / — | — | Monthly credits | Yes / R2 |
| `total_outflow` | NUMERIC(24,4) | No / — | — | Monthly debits | Yes / R2 |
| `salary_inflow` | NUMERIC(24,4) | No / — | — | Classified salary credits | Yes / R2 |
| `loan_payment` | NUMERIC(24,4) | No / — | — | Classified debt payments | Yes / R2 |
| `cash_deposit` | NUMERIC(24,4) | No / — | — | Cash deposits | Yes / R2 |
| `average_balance` | NUMERIC(24,4) | Yes / — | — | Average balance | Yes / R2 |
| `minimum_balance` | NUMERIC(24,4) | Yes / — | — | Minimum balance | Yes / R2 |
| `maximum_balance` | NUMERIC(24,4) | Yes / — | — | Maximum balance | Yes / R2 |
| `transaction_count` | INTEGER | No / — | — | Non-negative transaction count | Yes / R2 |
| `computed_at` | TIMESTAMPTZ | No / — | — | Computation time | Yes / R2 |

### `banking.credit_report`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Credit report ID | Yes / R2 |
| `customer_id` | UUID | No / — | FK → `customer.customer.id`, IDX | Customer | Yes / R3 |
| `provider` | VARCHAR(50) | No / — | IDX | External provider | Yes / R2 |
| `report_reference` | TEXT | Yes / — | IDX | Provider reference | Yes / R2 |
| `requested_at` | TIMESTAMPTZ | No / — | IDX | Request time | Yes / R2 |
| `report_as_of_date` | DATE | No / — | IDX | Report observation date | Yes / R2 |
| `risk_summary` | JSONB | No / `{}` | GIN where queried | Structured risk summary | Yes / R2 |
| `storage_object_id` | UUID | Yes / — | logical reference → `storage.object_metadata.id` | Stored report object | Yes / R4 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |

### `banking.credit_facility`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Facility ID | Yes / R2 |
| `credit_report_id` | UUID | No / — | FK → `banking.credit_report.id`, IDX | Source report | Yes / R2 |
| `lender_name` | TEXT | Yes / — | — | Lender | Yes / R2 |
| `facility_type` | VARCHAR(30) | No / — | IDX | Facility type | Yes / R2 |
| `credit_limit` | NUMERIC(24,4) | Yes / — | — | Limit | Yes / R2 |
| `outstanding_balance` | NUMERIC(24,4) | Yes / — | — | Outstanding amount | Yes / R2 |
| `monthly_obligation` | NUMERIC(24,4) | Yes / — | — | Monthly obligation | Yes / R2 |
| `overdue_days` | INTEGER | Yes / — | IDX | Days overdue | Yes / R2 |
| `debt_group` | VARCHAR(20) | Yes / — | IDX | Debt classification | Yes / R2 |
| `currency` | CHAR(3) | No / — | — | Currency | No / R2 |
| `as_of_date` | DATE | No / — | IDX | Observation date | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |

## `storage`

### `storage.object_metadata`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Object metadata ID | Yes / R4 |
| `bucket_name` | TEXT | No / — | UQ part, IDX | Exact private bucket | Yes / R4 |
| `object_key` | TEXT | No / — | UQ part, IDX | PII-free opaque key | Yes / R4 |
| `object_version_id` | TEXT | Yes / — | UQ part | MinIO version ID | Yes / R4 |
| `etag` | TEXT | Yes / — | — | Object ETag | Yes / R4 |
| `sha256` | CHAR(64) | No / — | IDX | Integrity checksum | Yes / R4 |
| `size_bytes` | BIGINT | No / — | — | Non-negative size | No / R4 |
| `mime_type` | TEXT | No / — | IDX | Media type | Yes / R4 |
| `storage_class` | VARCHAR(30) | Yes / — | — | Storage class | No / R4 |
| `encryption_type` | VARCHAR(30) | Yes / — | — | At-rest encryption indicator | Yes / R4 |
| `retention_until` | TIMESTAMPTZ | Yes / — | IDX | Earliest allowed deletion | Yes / R4 |
| `legal_hold` | BOOLEAN | No / `FALSE` | IDX | Deletion hold | Yes / R4 |
| `created_by` | UUID | Yes / — | logical employee/service link | Creator | Yes / R4 |
| `created_at` | TIMESTAMPTZ | No / — | IDX | Creation time | Yes / R4 |
| `deleted_at` | TIMESTAMPTZ | Yes / — | IDX | Soft deletion time | Yes / R4 |

Unique location constraint is `(bucket_name, object_key, object_version_id)` with
`NULLS NOT DISTINCT`.

### `storage.upload_session`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Upload session ID | Yes / R5 |
| `customer_id` | UUID | No / — | FK → `customer.customer.id`, IDX | Customer scope | Yes / R3 |
| `loan_application_id` | UUID | Yes / — | logical reference → `credit.loan_application.id` | Optional loan scope | Yes / R2 |
| `expected_document_type` | VARCHAR(50) | Yes / — | IDX | Declared type | Yes / R4 |
| `original_filename` | TEXT | No / — | no object-key use | Client filename metadata | Yes / R4 |
| `expected_mime_type` | TEXT | No / — | — | Required media type | Yes / R4 |
| `expected_size_bytes` | BIGINT | No / — | — | Required non-negative size | No / R4 |
| `expected_sha256` | CHAR(64) | No / — | — | Required checksum | Yes / R4 |
| `quarantine_object_key` | TEXT | No / — | — | PII-free staging key | Yes / R4 |
| `status` | VARCHAR(30) | No / — | IDX | Created/uploading/uploaded/verifying/completed/expired/failed | Yes / R5 |
| `expires_at` | TIMESTAMPTZ | No / — | IDX | Session expiry | Yes / R5 |
| `completed_at` | TIMESTAMPTZ | Yes / — | — | Completion time | Yes / R5 |
| `created_by` | UUID | No / — | FK → `identity.employee.id`, IDX | Initiating employee | Yes / R3 |
| `idempotency_key` | UUID | No / — | `idx_upload_session_idempotency` | Duplicate-request guard | Yes / R5 |
| `created_at` | TIMESTAMPTZ | No / — | IDX | Creation time | Yes / R5 |

### `storage.retention_rule`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Rule ID | No / R1 |
| `rule_code` | CITEXT | No / — | UQ | Stable rule code | No / R1 |
| `resource_type` | VARCHAR(50) | No / — | IDX | Governed resource type | No / R1 |
| `retention_years` | INTEGER | Yes / — | — | Positive years when year-based | No / R1 |
| `retention_days` | INTEGER | Yes / — | — | Positive days when day-based | No / R1 |
| `start_event` | VARCHAR(50) | No / — | — | Event starting retention clock | No / R1 |
| `description` | TEXT | Yes / — | — | Rule explanation | No / R1 |
| `is_active` | BOOLEAN | No / `TRUE` | IDX | Active flag | No / R1 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | No / R1 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | No / R1 |

At least one positive duration is required.

### `storage.resource_retention`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Applied retention ID | Yes / R2 |
| `resource_type` | VARCHAR(50) | No / — | composite IDX | Resource discriminator | Yes / R2 |
| `resource_id` | UUID | No / — | composite IDX | Opaque resource | Yes / R2 |
| `retention_rule_id` | UUID | No / — | FK → `storage.retention_rule.id`, IDX | Applied rule | No / R1 |
| `retention_start_date` | DATE | Yes / — | — | Clock start | Yes / R2 |
| `retention_until` | DATE | Yes / — | IDX | Earliest deletion date | Yes / R2 |
| `legal_hold` | BOOLEAN | No / `FALSE` | IDX | Legal hold flag | Yes / R2 |
| `legal_hold_reason` | TEXT | Yes / — | — | Required when held | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R2 |

## `document`

### `document.document`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Logical document ID | Yes / R4 |
| `document_type` | VARCHAR(50) | No / — | IDX | Document class | Yes / R4 |
| `document_subtype` | VARCHAR(50) | Yes / — | IDX | More specific class | Yes / R4 |
| `title` | TEXT | Yes / — | — | Safe business title; may be PII | Yes / R4 |
| `owner_party_id` | UUID | Yes / — | FK → `customer.party.id`, IDX | Owner party | Yes / R3 |
| `classification` | VARCHAR(30) | No / — | IDX | Information classification | Yes / R4 |
| `document_date` | DATE | Yes / — | IDX | Document date | Yes / R4 |
| `valid_from` | DATE | Yes / — | — | Validity start | Yes / R4 |
| `valid_until` | DATE | Yes / — | IDX | Validity end | Yes / R4 |
| `verification_status` | VARCHAR(30) | No / — | IDX | Verification status | Yes / R4 |
| `processing_status` | VARCHAR(30) | No / — | IDX | Pipeline status | Yes / R4 |
| `created_by` | UUID | No / — | FK → `identity.employee.id`, IDX | Creator | Yes / R3 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R4 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R4 |
| `version` | INTEGER | No / `1` | — | Optimistic lock | No / R4 |

### `document.document_version`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Version ID | Yes / R4 |
| `document_id` | UUID | No / — | FK → `document.document.id`, UQ/IDX | Logical document | Yes / R4 |
| `version_number` | INTEGER | No / — | UQ part | Positive sequence | No / R4 |
| `original_object_id` | UUID | No / — | FK → `storage.object_metadata.id` | Original MinIO metadata | Yes / R4 |
| `original_filename` | TEXT | No / — | — | Client filename metadata, never key | Yes / R4 |
| `mime_type` | TEXT | No / — | IDX | Media type | Yes / R4 |
| `file_size` | BIGINT | No / — | — | Non-negative bytes | No / R4 |
| `sha256` | CHAR(64) | No / — | IDX | File integrity checksum | Yes / R4 |
| `uploaded_by` | UUID | No / — | FK → `identity.employee.id`, IDX | Uploader | Yes / R3 |
| `uploaded_at` | TIMESTAMPTZ | No / — | IDX | Upload time | Yes / R4 |
| `scan_status` | VARCHAR(30) | No / — | IDX | Security scan status | Yes / R4 |
| `is_current` | BOOLEAN | No / `TRUE` | partial UQ | Current logical version | No / R4 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R4 |

Unique `(document_id, version_number)` and partial unique `document_id WHERE
is_current` enforce version rules.

### `document.document_link`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Link ID | Yes / R4 |
| `document_id` | UUID | No / — | FK → `document.document.id`, IDX | Document | Yes / R4 |
| `entity_type` | VARCHAR(40) | No / — | composite IDX | Customer/loan/collateral type | Yes / R4 |
| `entity_id` | UUID | No / — | composite IDX | Opaque linked entity | Yes / R4 |
| `relationship_type` | VARCHAR(40) | No / — | IDX | Evidence/ownership relation | Yes / R4 |
| `created_at` | TIMESTAMPTZ | No / — | — | Link creation | Yes / R4 |

### `document.processing_job`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Document processing job ID | Yes / R5 |
| `document_version_id` | UUID | No / — | FK → `document.document_version.id`, IDX | Input version | Yes / R4 |
| `job_type` | VARCHAR(40) | No / — | composite IDX | Scan/OCR/classify/extract/embed | Yes / R5 |
| `status` | VARCHAR(30) | No / — | composite IDX | Job status | Yes / R5 |
| `model_name` | TEXT | Yes / — | — | Processing model | No / R5 |
| `model_version` | TEXT | Yes / — | — | Model version | No / R5 |
| `attempt_count` | INTEGER | No / `0` | — | Non-negative attempts | No / R5 |
| `started_at` | TIMESTAMPTZ | Yes / — | — | Start time | Yes / R5 |
| `completed_at` | TIMESTAMPTZ | Yes / — | — | Completion time | Yes / R5 |
| `error_code` | VARCHAR(50) | Yes / — | IDX | Safe machine error | Yes / R5 |
| `error_message_safe` | TEXT | Yes / — | — | Redacted operator message | Yes / R5 |
| `correlation_id` | UUID | No / — | IDX | Cross-service correlation | Yes / R5 |
| `created_at` | TIMESTAMPTZ | No / — | IDX | Creation time | Yes / R5 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R5 |

### `document.document_page`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Page ID | Yes / R4 |
| `document_version_id` | UUID | No / — | FK → `document.document_version.id`, UQ/IDX | Document version | Yes / R4 |
| `page_number` | INTEGER | No / — | UQ part | Positive one-based page | No / R4 |
| `text_content` | TEXT | Yes / — | full-text/IDX only if approved | Normalized OCR text, not Kafka payload | Yes / R4 |
| `ocr_confidence` | NUMERIC(6,5) | Yes / — | — | 0–1 OCR confidence | No / R4 |
| `page_image_object_id` | UUID | Yes / — | FK → `storage.object_metadata.id` | Derived page image | Yes / R4 |
| `width` | INTEGER | Yes / — | — | Pixel width | No / R4 |
| `height` | INTEGER | Yes / — | — | Pixel height | No / R4 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R4 |

Unique `(document_version_id, page_number)`.

### `document.extracted_field`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Field ID | Yes / R4 |
| `document_version_id` | UUID | No / — | FK → `document.document_version.id`, IDX | Source version | Yes / R4 |
| `field_name` | CITEXT | No / — | composite IDX | Canonical field name | Yes / R4 |
| `value_type` | VARCHAR(20) | No / — | — | Text/number/date/etc. | No / R4 |
| `ocr_value_text` | TEXT | Yes / — | — | Immutable OCR observation | Yes / R4 |
| `normalized_value_text` | TEXT | Yes / — | — | Machine-normalized value | Yes / R4 |
| `corrected_value_text` | TEXT | Yes / — | — | Human correction; does not overwrite OCR | Yes / R4 |
| `value_number` | NUMERIC(24,4) | Yes / — | — | Typed numeric value | Yes / R4 |
| `value_date` | DATE | Yes / — | — | Typed date value | Yes / R4 |
| `page_number` | INTEGER | Yes / — | composite IDX | Positive source page | No / R4 |
| `bounding_box` | JSONB | Yes / — | — | Page coordinates | No / R4 |
| `source_text` | TEXT | Yes / — | — | Evidence excerpt | Yes / R4 |
| `confidence` | NUMERIC(6,5) | Yes / — | — | 0–1 confidence | No / R4 |
| `verification_status` | VARCHAR(30) | No / — | IDX | Review status | Yes / R4 |
| `verified_by` | UUID | Yes / — | FK → `identity.employee.id`, IDX | Reviewer | Yes / R3 |
| `verified_at` | TIMESTAMPTZ | Yes / — | — | Review time | Yes / R4 |
| `verification_reason` | TEXT | Yes / — | — | Review rationale | Yes / R4 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R4 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R4 |

### `document.document_chunk`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Chunk ID | Yes / R4 |
| `document_version_id` | UUID | No / — | FK → `document.document_version.id`, UQ/IDX | Source version and scope filter | Yes / R4 |
| `page_from` | INTEGER | Yes / — | — | First source page | No / R4 |
| `page_to` | INTEGER | Yes / — | — | Last source page | No / R4 |
| `chunk_index` | INTEGER | No / — | UQ part | Zero-based chunk order | No / R4 |
| `text_content` | TEXT | No / — | — | Chunk text; access-filtered | Yes / R4 |
| `token_count` | INTEGER | Yes / — | — | Token count | No / R4 |
| `embedding` | VECTOR(1024) | Yes / — | HNSW cosine | Semantic embedding | Yes / R4 |
| `metadata` | JSONB | No / `{}` | GIN | Minimal retrieval metadata | Yes / R4 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R4 |

Unique `(document_version_id, chunk_index)`. Vector search must also apply
customer/document authorization scope.

### `document.document_issue`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Issue ID | Yes / R4 |
| `document_version_id` | UUID | No / — | FK → `document.document_version.id`, IDX | Affected version | Yes / R4 |
| `issue_type` | VARCHAR(40) | No / — | IDX | Issue category | Yes / R4 |
| `severity` | VARCHAR(20) | No / — | IDX | Severity | Yes / R4 |
| `title` | TEXT | No / — | — | Short title | Yes / R4 |
| `description` | TEXT | No / — | — | Issue details | Yes / R4 |
| `field_id` | UUID | Yes / — | FK → `document.extracted_field.id`, IDX | Related extracted field | Yes / R4 |
| `status` | VARCHAR(30) | No / — | IDX | Resolution status | Yes / R4 |
| `detected_by` | VARCHAR(30) | No / — | — | Detector class | Yes / R4 |
| `resolved_by` | UUID | Yes / — | FK → `identity.employee.id` | Resolver | Yes / R3 |
| `resolved_at` | TIMESTAMPTZ | Yes / — | — | Resolution time | Yes / R4 |
| `resolution_note` | TEXT | Yes / — | — | Resolution rationale | Yes / R4 |
| `created_at` | TIMESTAMPTZ | No / — | IDX | Detection time | Yes / R4 |

## `credit`

### `credit.loan_product`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Product ID | No / R1 |
| `product_code` | CITEXT | No / — | UQ | Stable product code | No / R1 |
| `product_name` | TEXT | No / — | — | Product name | No / R1 |
| `customer_type` | VARCHAR(20) | No / — | IDX | Eligible customer type | No / R1 |
| `loan_purpose` | VARCHAR(40) | Yes / — | IDX | Eligible purpose | No / R1 |
| `min_amount` | NUMERIC(24,4) | Yes / — | — | Minimum amount | No / R1 |
| `max_amount` | NUMERIC(24,4) | Yes / — | — | Maximum, not below minimum | No / R1 |
| `min_term_months` | INTEGER | Yes / — | — | Minimum term | No / R1 |
| `max_term_months` | INTEGER | Yes / — | — | Maximum, not below minimum | No / R1 |
| `status` | VARCHAR(20) | No / — | IDX | Product status | No / R1 |
| `effective_from` | DATE | No / — | IDX | Effective start | No / R1 |
| `effective_until` | DATE | Yes / — | IDX | Effective end | No / R1 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | No / R1 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | No / R1 |

### `credit.loan_application`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Loan application ID | Yes / R2 |
| `application_number` | CITEXT | No / — | UQ | Internal application number | Yes / R2 |
| `primary_customer_id` | UUID | No / — | FK → `customer.customer.id`, IDX | Primary customer | Yes / R3 |
| `product_id` | UUID | No / — | FK → `credit.loan_product.id`, IDX | Requested product | No / R2 |
| `requested_amount` | NUMERIC(24,4) | No / — | — | Positive requested amount | Yes / R2 |
| `currency` | CHAR(3) | No / — | — | Currency | No / R2 |
| `requested_term_months` | INTEGER | No / — | — | Positive requested term | Yes / R2 |
| `loan_purpose` | VARCHAR(40) | No / — | IDX | Loan purpose | Yes / R2 |
| `interest_rate_assumption` | NUMERIC(12,8) | Yes / — | — | Analysis rate assumption | Yes / R2 |
| `repayment_method` | VARCHAR(40) | Yes / — | — | Proposed repayment method | Yes / R2 |
| `status` | VARCHAR(30) | No / — | IDX | Contractual application workflow status | Yes / R2 |
| `assigned_employee_id` | UUID | Yes / — | FK → `identity.employee.id`, IDX | Assigned officer | Yes / R3 |
| `submitted_at` | TIMESTAMPTZ | Yes / — | IDX | Submission time | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | IDX | Creation time | Yes / R2 |
| `created_by` | UUID | No / — | logical employee FK/IDX | Creator | Yes / R3 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R2 |
| `updated_by` | UUID | Yes / — | logical employee FK | Last editor | Yes / R3 |
| `version` | INTEGER | No / `1` | — | Optimistic lock | No / R2 |

Allowed statuses: `DRAFT`, `DOCUMENT_COLLECTION`, `UNDER_ANALYSIS`,
`NEEDS_INFORMATION`, `READY_FOR_REVIEW`, `SUBMITTED_FOR_APPROVAL`, `APPROVED`,
`APPROVED_WITH_CONDITIONS`, `REJECTED`, `WITHDRAWN`.

### `credit.loan_party`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Loan-party link ID | Yes / R2 |
| `loan_application_id` | UUID | No / — | FK → `credit.loan_application.id`, IDX | Application | Yes / R2 |
| `party_id` | UUID | No / — | FK → `customer.party.id`, IDX | Related party | Yes / R3 |
| `party_role` | VARCHAR(40) | No / — | composite IDX | Primary/co-borrower, guarantor, spouse, collateral owner or legal representative | Yes / R3 |
| `created_at` | TIMESTAMPTZ | No / — | — | Link creation | Yes / R2 |

### `credit.existing_obligation`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Obligation ID | Yes / R2 |
| `loan_application_id` | UUID | No / — | FK → `credit.loan_application.id`, IDX | Application | Yes / R2 |
| `party_id` | UUID | No / — | FK → `customer.party.id`, IDX | Liable party | Yes / R3 |
| `lender_name` | TEXT | Yes / — | — | Lender | Yes / R2 |
| `obligation_type` | VARCHAR(30) | No / — | IDX | Obligation type | Yes / R2 |
| `outstanding_balance` | NUMERIC(24,4) | Yes / — | — | Outstanding amount | Yes / R2 |
| `monthly_payment` | NUMERIC(24,4) | Yes / — | — | Monthly payment | Yes / R2 |
| `credit_limit` | NUMERIC(24,4) | Yes / — | — | Credit limit | Yes / R2 |
| `currency` | CHAR(3) | No / — | — | Currency | No / R2 |
| `verified_status` | VARCHAR(30) | No / — | IDX | Verification status | Yes / R2 |
| `source_type` | VARCHAR(30) | No / — | composite IDX | Evidence resource type | Yes / R2 |
| `source_id` | UUID | Yes / — | composite IDX | Evidence resource ID | Yes / R2 |
| `as_of_date` | DATE | No / — | IDX | Observation date | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |

### `credit.collateral`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Collateral ID | Yes / R2 |
| `loan_application_id` | UUID | No / — | FK → `credit.loan_application.id`, IDX | Secured application | Yes / R2 |
| `owner_party_id` | UUID | No / — | FK → `customer.party.id`, IDX | Owner | Yes / R3 |
| `collateral_type` | VARCHAR(40) | No / — | IDX | Collateral class | Yes / R2 |
| `description` | TEXT | Yes / — | — | Description, may contain sensitive location/details | Yes / R2 |
| `declared_value` | NUMERIC(24,4) | Yes / — | — | Declared value | Yes / R2 |
| `appraised_value` | NUMERIC(24,4) | Yes / — | — | Appraised value | Yes / R2 |
| `eligible_value` | NUMERIC(24,4) | Yes / — | — | Policy-eligible value | Yes / R2 |
| `currency` | CHAR(3) | No / — | — | Currency | No / R2 |
| `valuation_date` | DATE | Yes / — | IDX | Latest valuation date | Yes / R2 |
| `valuation_status` | VARCHAR(30) | Yes / — | IDX | Valuation status | Yes / R2 |
| `ownership_verification_status` | VARCHAR(30) | Yes / — | IDX | Ownership verification | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R2 |
| `version` | INTEGER | No / `1` | — | Optimistic lock | No / R2 |

### `credit.collateral_valuation`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Valuation ID | Yes / R2 |
| `collateral_id` | UUID | No / — | FK → `credit.collateral.id`, IDX | Collateral | Yes / R2 |
| `valuation_date` | DATE | No / — | composite IDX | Valuation date | Yes / R2 |
| `market_value` | NUMERIC(24,4) | No / — | — | Market value | Yes / R2 |
| `eligible_value` | NUMERIC(24,4) | Yes / — | — | Eligible value | Yes / R2 |
| `currency` | CHAR(3) | No / — | — | Currency | No / R2 |
| `valuation_method` | VARCHAR(50) | Yes / — | — | Method | Yes / R2 |
| `valuer_name` | TEXT | Yes / — | — | Valuer | Yes / R3 |
| `source_document_id` | UUID | Yes / — | FK → `document.document.id` | Valuation document | Yes / R4 |
| `status` | VARCHAR(30) | No / — | IDX | Status | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |

### `credit.loan_checklist_item`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Checklist item ID | Yes / R2 |
| `loan_application_id` | UUID | No / — | FK → `credit.loan_application.id`, composite IDX | Application | Yes / R2 |
| `requirement_code` | CITEXT | No / — | — | Requirement | Yes / R2 |
| `document_type` | VARCHAR(50) | Yes / — | IDX | Required document class | Yes / R4 |
| `requirement_status` | VARCHAR(30) | No / — | IDX | Required/received/valid/expired/incomplete/inconsistent/waived/not applicable | Yes / R2 |
| `mandatory_level` | VARCHAR(30) | No / — | — | Requirement strength | Yes / R2 |
| `source_policy_clause_id` | UUID | Yes / — | logical reference → `policy.policy_clause.id` | Governing clause | Yes / R1 |
| `linked_document_id` | UUID | Yes / — | FK → `document.document.id`, IDX | Submitted document | Yes / R4 |
| `waived_by` | UUID | Yes / — | FK → `identity.employee.id` | Authorized waiver actor | Yes / R3 |
| `waiver_reason` | TEXT | Yes / — | — | Required for waived status | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R2 |

### `credit.calculation_record`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Reproducible calculation ID | Yes / R2 |
| `loan_application_id` | UUID | No / — | FK → `credit.loan_application.id`, IDX | Application | Yes / R2 |
| `analysis_case_id` | UUID | Yes / — | logical reference → `ai.analysis_case.id`; indexed | Analysis context | Yes / R7 |
| `calculation_type` | VARCHAR(40) | No / — | composite IDX | DTI/DSCR/LTV/etc. | Yes / R2 |
| `calculation_version` | VARCHAR(20) | No / — | composite IDX | Deterministic implementation version | No / R2 |
| `inputs` | JSONB | No / — | no broad exposure | Exact typed inputs | Yes / R2 |
| `formula` | TEXT | No / — | — | Auditable formula | Yes / R2 |
| `result_value` | NUMERIC(30,10) | Yes / — | — | Scalar result | Yes / R2 |
| `result_payload` | JSONB | No / `{}` | — | Structured result | Yes / R2 |
| `unit` | VARCHAR(30) | Yes / — | — | Result unit | No / R2 |
| `calculated_at` | TIMESTAMPTZ | No / — | IDX | Calculation time | Yes / R2 |
| `created_by_type` | VARCHAR(20) | No / — | — | Employee/service/agent class | Yes / R2 |
| `created_by_id` | UUID | Yes / — | IDX | Creator ID | Yes / R2 |

### `credit.affordability_assessment`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Assessment ID | Yes / R2 |
| `loan_application_id` | UUID | No / — | FK → `credit.loan_application.id`, IDX | Application | Yes / R2 |
| `calculation_version` | VARCHAR(20) | No / — | IDX | Calculation version | No / R2 |
| `monthly_declared_income` | NUMERIC(24,4) | Yes / — | — | Declared monthly income | Yes / R2 |
| `monthly_verified_income` | NUMERIC(24,4) | Yes / — | — | Verified monthly income | Yes / R2 |
| `monthly_accepted_income` | NUMERIC(24,4) | Yes / — | — | Accepted monthly income | Yes / R2 |
| `monthly_existing_obligations` | NUMERIC(24,4) | Yes / — | — | Existing monthly debt | Yes / R2 |
| `projected_monthly_payment` | NUMERIC(24,4) | Yes / — | — | Proposed payment | Yes / R2 |
| `dti` | NUMERIC(12,8) | Yes / — | — | Debt-to-income ratio | Yes / R2 |
| `dscr` | NUMERIC(12,8) | Yes / — | — | Debt-service coverage | Yes / R2 |
| `ltv` | NUMERIC(12,8) | Yes / — | — | Loan-to-value | Yes / R2 |
| `net_disposable_income` | NUMERIC(24,4) | Yes / — | — | Disposable income | Yes / R2 |
| `stress_interest_rate` | NUMERIC(12,8) | Yes / — | — | Stress rate | Yes / R2 |
| `stress_dti` | NUMERIC(12,8) | Yes / — | — | Stressed DTI | Yes / R2 |
| `result` | VARCHAR(30) | No / — | IDX | Assessment result | Yes / R2 |
| `calculation_payload` | JSONB | No / — | — | Reproducible details | Yes / R2 |
| `calculated_at` | TIMESTAMPTZ | No / — | IDX | Assessment time | Yes / R2 |

### `credit.policy_check`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Check ID | Yes / R2 |
| `loan_application_id` | UUID | No / — | FK → `credit.loan_application.id`, IDX | Application | Yes / R2 |
| `analysis_case_id` | UUID | Yes / — | logical reference → `ai.analysis_case.id`; indexed | Analysis case | Yes / R7 |
| `policy_version_id` | UUID | No / — | logical reference → `policy.policy_version.id` | Policy version | Yes / R1 |
| `clause_id` | UUID | Yes / — | logical reference → `policy.policy_clause.id` | Clause | Yes / R1 |
| `rule_code` | CITEXT | Yes / — | IDX | Evaluated rule | Yes / R1 |
| `status` | VARCHAR(30) | No / — | IDX | Pass/fail/conditional/insufficient/not applicable | Yes / R2 |
| `actual_value` | TEXT | Yes / — | — | Observed value | Yes / R2 |
| `required_value` | TEXT | Yes / — | — | Policy threshold | Yes / R2 |
| `explanation` | TEXT | No / — | — | Auditable explanation | Yes / R2 |
| `checked_at` | TIMESTAMPTZ | No / — | IDX | Check time | Yes / R2 |

### `credit.approval_request`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Approval request ID | Yes / R2 |
| `loan_application_id` | UUID | No / — | FK → `credit.loan_application.id`, IDX | Application | Yes / R2 |
| `requested_by` | UUID | No / — | FK → `identity.employee.id`, IDX | Requesting employee | Yes / R3 |
| `requested_at` | TIMESTAMPTZ | No / — | IDX | Request time | Yes / R2 |
| `requested_authority_level` | VARCHAR(30) | Yes / — | — | Required decision authority | Yes / R2 |
| `status` | VARCHAR(30) | No / — | IDX | Request status | Yes / R2 |
| `request_note` | TEXT | Yes / — | — | Human note | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |

### `credit.loan_decision` — human authority only

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Official decision ID | Yes / R2 |
| `loan_application_id` | UUID | No / — | FK → `credit.loan_application.id`, IDX | Application | Yes / R2 |
| `approval_request_id` | UUID | Yes / — | FK → `credit.approval_request.id`, IDX | Approval workflow request | Yes / R2 |
| `decision_type` | VARCHAR(40) | No / — | IDX | Official decision | Yes / R2 |
| `approved_amount` | NUMERIC(24,4) | Yes / — | — | Approved amount | Yes / R2 |
| `approved_term_months` | INTEGER | Yes / — | — | Approved term | Yes / R2 |
| `conditions` | JSONB | No / `[]` | GIN where queried | Approval conditions | Yes / R2 |
| `rationale` | TEXT | No / — | — | Human rationale | Yes / R2 |
| `decision_maker_id` | UUID | No / — | FK → `identity.employee.id`, IDX | Authorized human decision maker | Yes / R3 |
| `decision_at` | TIMESTAMPTZ | No / — | IDX | Decision time | Yes / R2 |
| `is_override` | BOOLEAN | No / `FALSE` | IDX | Policy/normal-process override | Yes / R2 |
| `override_reason` | TEXT | Yes / — | — | Required for override | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Record creation | Yes / R2 |

Worker roles have no insert/update grant on this table.

### `credit.disbursement`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Disbursement ID | Yes / R2 |
| `loan_application_id` | UUID | No / — | FK → `credit.loan_application.id`, composite IDX | Application | Yes / R2 |
| `drawdown_number` | INTEGER | No / — | — | Positive drawdown sequence | Yes / R2 |
| `amount` | NUMERIC(24,4) | No / — | — | Positive amount | Yes / R2 |
| `currency` | CHAR(3) | No / — | — | Currency | No / R2 |
| `beneficiary_name_masked` | TEXT | Yes / — | — | Masked beneficiary | Yes / R3 |
| `beneficiary_account_hash` | CHAR(64) | Yes / — | IDX | Beneficiary account hash | Yes / R3 |
| `purpose_reference` | TEXT | Yes / — | — | Payment purpose/reference | Yes / R2 |
| `payment_transaction_id` | UUID | Yes / — | logical transaction link, IDX | Payment transaction | Yes / R2 |
| `status` | VARCHAR(30) | No / — | IDX | Disbursement status | Yes / R2 |
| `approved_by` | UUID | Yes / — | FK → `identity.employee.id`, IDX | Approver | Yes / R3 |
| `disbursed_at` | TIMESTAMPTZ | Yes / — | IDX | Execution time | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |

### `credit.loan_account`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Loan account ID | Yes / R2 |
| `loan_application_id` | UUID | No / — | UQ, FK → `credit.loan_application.id` | Originating application | Yes / R2 |
| `account_number_masked` | TEXT | No / — | — | Masked loan account number | Yes / R3 |
| `account_number_hash` | CHAR(64) | No / — | UQ | Account lookup hash | Yes / R3 |
| `principal_amount` | NUMERIC(24,4) | No / — | — | Original principal | Yes / R2 |
| `outstanding_principal` | NUMERIC(24,4) | No / — | — | Outstanding principal | Yes / R2 |
| `interest_rate` | NUMERIC(12,8) | No / — | — | Contract rate | Yes / R2 |
| `disbursement_date` | DATE | No / — | IDX | Start date | Yes / R2 |
| `maturity_date` | DATE | No / — | IDX | Maturity, on/after disbursement | Yes / R2 |
| `status` | VARCHAR(30) | No / — | IDX | Loan account status | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R2 |

### `credit.repayment_schedule`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Installment ID | Yes / R2 |
| `loan_account_id` | UUID | No / — | FK → `credit.loan_account.id`, UQ/IDX | Loan account | Yes / R2 |
| `installment_number` | INTEGER | No / — | UQ part | Positive sequence | Yes / R2 |
| `due_date` | DATE | No / — | IDX | Due date | Yes / R2 |
| `principal_due` | NUMERIC(24,4) | No / — | — | Principal due | Yes / R2 |
| `interest_due` | NUMERIC(24,4) | No / — | — | Interest due | Yes / R2 |
| `fee_due` | NUMERIC(24,4) | No / `0` | — | Fee due | Yes / R2 |
| `total_due` | NUMERIC(24,4) | No / — | — | Total due | Yes / R2 |
| `payment_status` | VARCHAR(30) | No / — | IDX | Payment status | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |

Unique `(loan_account_id, installment_number)`.

### `credit.loan_payment`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Payment allocation ID | Yes / R2 |
| `loan_account_id` | UUID | No / — | FK → `credit.loan_account.id`, IDX | Loan account | Yes / R2 |
| `transaction_id` | UUID | Yes / — | logical banking transaction link, IDX | Source payment transaction | Yes / R2 |
| `payment_date` | TIMESTAMPTZ | No / — | IDX | Payment time | Yes / R2 |
| `principal_paid` | NUMERIC(24,4) | No / — | — | Principal paid | Yes / R2 |
| `interest_paid` | NUMERIC(24,4) | No / — | — | Interest paid | Yes / R2 |
| `fee_paid` | NUMERIC(24,4) | No / `0` | — | Fees paid | Yes / R2 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R2 |

## `policy`

### `policy.policy`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Policy ID | No / R1 |
| `policy_code` | CITEXT | No / — | UQ | Stable policy code | No / R1 |
| `policy_name` | TEXT | No / — | — | Policy name | No / R1 |
| `policy_type` | VARCHAR(40) | No / — | IDX | Policy category | No / R1 |
| `owner_department_id` | UUID | Yes / — | FK → `identity.department.id`, IDX | Policy owner | Yes / R1 |
| `status` | VARCHAR(20) | No / — | IDX | Policy lifecycle status | No / R1 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | No / R1 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | No / R1 |

### `policy.policy_version`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Policy version ID | No / R1 |
| `policy_id` | UUID | No / — | FK → `policy.policy.id`, UQ/IDX | Parent policy | No / R1 |
| `version_number` | VARCHAR(30) | No / — | UQ part | Business version label | No / R1 |
| `effective_from` | DATE | No / — | IDX | Effective start | No / R1 |
| `effective_until` | DATE | Yes / — | IDX | Effective end | No / R1 |
| `approved_by` | UUID | Yes / — | FK → `identity.employee.id`, IDX | Human approver | Yes / R3 |
| `approved_at` | TIMESTAMPTZ | Yes / — | — | Approval time | Yes / R1 |
| `source_document_id` | UUID | No / — | FK → `document.document.id` | Authoritative policy document | Yes / R4 |
| `status` | VARCHAR(20) | No / — | IDX | Version status | No / R1 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | No / R1 |

Unique `(policy_id, version_number)`.

### `policy.policy_clause`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Clause ID | No / R1 |
| `policy_version_id` | UUID | No / — | FK → `policy.policy_version.id`, UQ/IDX | Policy version and retrieval scope | No / R1 |
| `clause_number` | TEXT | No / — | UQ part | Human clause number | No / R1 |
| `title` | TEXT | Yes / — | — | Clause title | No / R1 |
| `content` | TEXT | No / — | — | Authoritative clause text | Yes / R1 |
| `page_number` | INTEGER | Yes / — | IDX | Positive source page | No / R1 |
| `embedding` | VECTOR(1024) | Yes / — | HNSW cosine | Semantic embedding | Yes / R1 |
| `metadata` | JSONB | No / `{}` | GIN | Minimal retrieval metadata | Yes / R1 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | No / R1 |

Unique `(policy_version_id, clause_number)`; vector search also filters policy
version/effective status and caller authorization.

### `policy.checklist_rule`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Rule ID | No / R1 |
| `policy_version_id` | UUID | No / — | FK → `policy.policy_version.id`, UQ/IDX | Policy version | No / R1 |
| `rule_code` | CITEXT | No / — | UQ part | Stable rule code within version | No / R1 |
| `rule_name` | TEXT | No / — | — | Rule name | No / R1 |
| `conditions` | JSONB | No / — | GIN where queried | Declarative conditions | Yes / R1 |
| `status` | VARCHAR(20) | No / — | IDX | Rule status | No / R1 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | No / R1 |

Unique `(policy_version_id, rule_code)`.

### `policy.checklist_rule_requirement`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Requirement ID | No / R1 |
| `checklist_rule_id` | UUID | No / — | FK → `policy.checklist_rule.id`, IDX | Parent rule | No / R1 |
| `requirement_code` | CITEXT | No / — | composite IDX | Requirement code | No / R1 |
| `document_type` | VARCHAR(50) | Yes / — | IDX | Required document type | No / R1 |
| `mandatory_level` | VARCHAR(30) | No / — | — | Mandatory strength | No / R1 |
| `requirement_description` | TEXT | No / — | — | Requirement wording | No / R1 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | No / R1 |

## `ai`

### `ai.conversation`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Conversation ID | Yes / R7 |
| `employee_id` | UUID | No / — | FK → `identity.employee.id`, IDX | Owning employee | Yes / R3 |
| `active_customer_id` | UUID | Yes / — | FK → `customer.customer.id`, IDX | Current authorized customer context | Yes / R3 |
| `active_loan_application_id` | UUID | Yes / — | FK → `credit.loan_application.id`, IDX | Current loan context | Yes / R2 |
| `title` | TEXT | Yes / — | — | Conversation label; avoid direct PII | Yes / R7 |
| `status` | VARCHAR(20) | No / — | IDX | Conversation status | Yes / R7 |
| `started_at` | TIMESTAMPTZ | No / — | IDX | Start time | Yes / R7 |
| `ended_at` | TIMESTAMPTZ | Yes / — | — | End time | Yes / R7 |

### `ai.message` — no private chain-of-thought

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Message ID | Yes / R7 |
| `conversation_id` | UUID | No / — | FK → `ai.conversation.id`, IDX | Conversation | Yes / R7 |
| `sender_type` | VARCHAR(20) | No / — | IDX | Employee/service/agent sender type | Yes / R7 |
| `sender_id` | UUID | Yes / — | IDX | Sender ID | Yes / R7 |
| `content` | TEXT | No / — | — | User-visible message only, never private reasoning | Yes / R7 |
| `created_at` | TIMESTAMPTZ | No / — | composite IDX | Message time | Yes / R7 |
| `parent_message_id` | UUID | Yes / — | FK → `ai.message.id`, IDX | Reply/branch parent | Yes / R7 |
| `route_type` | VARCHAR(30) | Yes / — | IDX | Routing classification | Yes / R7 |
| `complexity_level` | SMALLINT | Yes / — | — | Non-negative routing complexity | No / R7 |
| `analysis_case_id` | UUID | Yes / — | logical reference → `ai.analysis_case.id` | Related analysis | Yes / R7 |

### `ai.analysis_case`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Analysis case ID | Yes / R7 |
| `case_type` | VARCHAR(40) | No / — | IDX | Analysis type | Yes / R7 |
| `customer_id` | UUID | No / — | FK → `customer.customer.id`, IDX | Customer scope | Yes / R3 |
| `loan_application_id` | UUID | Yes / — | FK → `credit.loan_application.id`, IDX | Loan scope | Yes / R2 |
| `conversation_id` | UUID | Yes / — | FK → `ai.conversation.id`, IDX | Origin conversation | Yes / R7 |
| `created_by` | UUID | No / — | FK → `identity.employee.id`, IDX | Requesting employee | Yes / R3 |
| `status` | VARCHAR(30) | No / — | IDX | Case workflow status | Yes / R7 |
| `objective` | TEXT | No / — | — | Authorized analysis objective | Yes / R7 |
| `correlation_id` | UUID | No / — | `idx_analysis_case_correlation` | Cross-service correlation | Yes / R7 |
| `created_at` | TIMESTAMPTZ | No / — | IDX | Creation time | Yes / R7 |
| `completed_at` | TIMESTAMPTZ | Yes / — | — | Completion time | Yes / R7 |

### `ai.analysis_task`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Task ID | Yes / R7 |
| `analysis_case_id` | UUID | No / — | FK → `ai.analysis_case.id`, composite IDX | Case | Yes / R7 |
| `task_code` | CITEXT | No / — | — | Task code within case | Yes / R7 |
| `agent_type` | VARCHAR(30) | No / — | IDX | Assigned agent class | No / R7 |
| `objective` | TEXT | No / — | — | Bounded task objective | Yes / R7 |
| `status` | VARCHAR(30) | No / — | composite IDX | Task status | Yes / R7 |
| `depends_on` | JSONB | No / `[]` | — | Dependency task IDs | Yes / R7 |
| `attempt_count` | INTEGER | No / `0` | — | Non-negative attempts | No / R7 |
| `started_at` | TIMESTAMPTZ | Yes / — | — | Start time | Yes / R7 |
| `completed_at` | TIMESTAMPTZ | Yes / — | — | Completion time | Yes / R7 |
| `error_code` | VARCHAR(50) | Yes / — | IDX | Safe error code | Yes / R7 |
| `created_at` | TIMESTAMPTZ | No / — | IDX | Creation time | Yes / R7 |

### `ai.agent_run` — metadata only, no chain-of-thought

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Agent execution ID | Yes / R7 |
| `analysis_case_id` | UUID | No / — | FK → `ai.analysis_case.id`, IDX | Case | Yes / R7 |
| `analysis_task_id` | UUID | No / — | FK → `ai.analysis_task.id`, IDX | Task | Yes / R7 |
| `agent_type` | VARCHAR(30) | No / — | IDX | Agent class | No / R7 |
| `status` | VARCHAR(30) | No / — | IDX | Run status | Yes / R7 |
| `model_provider` | TEXT | Yes / — | — | Provider name | No / R7 |
| `model_name` | TEXT | Yes / — | — | Model name | No / R7 |
| `model_version` | TEXT | Yes / — | — | Model version | No / R7 |
| `prompt_version` | TEXT | Yes / — | — | Prompt/template version only | No / R7 |
| `input_hash` | CHAR(64) | Yes / — | IDX | Input integrity hash, not input | Yes / R7 |
| `output_hash` | CHAR(64) | Yes / — | IDX | Output integrity hash | Yes / R7 |
| `started_at` | TIMESTAMPTZ | Yes / — | — | Start time | Yes / R7 |
| `completed_at` | TIMESTAMPTZ | Yes / — | — | Completion time | Yes / R7 |
| `created_at` | TIMESTAMPTZ | No / — | IDX | Creation time | Yes / R7 |

### `ai.finding`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Finding ID | Yes / R7 |
| `analysis_case_id` | UUID | No / — | FK → `ai.analysis_case.id`, composite IDX | Case | Yes / R7 |
| `agent_run_id` | UUID | No / — | FK → `ai.agent_run.id`, IDX | Producing run | Yes / R7 |
| `finding_type` | VARCHAR(40) | No / — | IDX | Finding class | Yes / R7 |
| `title` | TEXT | No / — | — | Finding title | Yes / R7 |
| `description` | TEXT | No / — | — | Evidence-backed description | Yes / R7 |
| `severity` | VARCHAR(20) | No / — | composite IDX | Severity | Yes / R7 |
| `status` | VARCHAR(30) | No / — | composite IDX | Review/resolution status | Yes / R7 |
| `confidence` | NUMERIC(6,5) | Yes / — | — | 0–1 confidence | No / R7 |
| `recommended_action` | TEXT | Yes / — | — | Recommendation, never automatic decision | Yes / R7 |
| `created_at` | TIMESTAMPTZ | No / — | IDX | Creation time | Yes / R7 |

### `ai.evidence_link`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Evidence link ID | Yes / R7 |
| `finding_id` | UUID | No / — | FK → `ai.finding.id`, IDX | Supported finding | Yes / R7 |
| `source_type` | VARCHAR(40) | No / — | composite IDX | Customer/transaction/document/calculation/policy/loan source type | Yes / R7 |
| `source_id` | UUID | No / — | composite IDX | Source record ID | Yes / R7 |
| `source_locator` | JSONB | No / — | GIN where queried | Page/field/query locator, minimal PII | Yes / R7 |
| `quoted_text` | TEXT | Yes / — | — | Minimal evidence quote | Yes / R7 |
| `evidence_role` | VARCHAR(20) | No / — | IDX | Primary/supporting/contradicting | Yes / R7 |
| `created_at` | TIMESTAMPTZ | No / — | — | Link creation | Yes / R7 |

### `ai.validation_result`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Validation ID | Yes / R7 |
| `analysis_case_id` | UUID | No / — | FK → `ai.analysis_case.id`, IDX | Case | Yes / R7 |
| `validation_status` | VARCHAR(30) | No / — | IDX | Overall status | Yes / R7 |
| `citation_coverage` | NUMERIC(6,5) | Yes / — | — | 0–1 supported-claim coverage | No / R7 |
| `unsupported_claims` | JSONB | No / `[]` | — | Unsupported claim references | Yes / R7 |
| `calculation_errors` | JSONB | No / `[]` | — | Calculation issues | Yes / R7 |
| `policy_conflicts` | JSONB | No / `[]` | — | Policy conflicts | Yes / R7 |
| `agent_contradictions` | JSONB | No / `[]` | — | Cross-agent contradictions | Yes / R7 |
| `approved_for_synthesis` | BOOLEAN | No / — | IDX | Validator gate, not credit approval | Yes / R7 |
| `created_at` | TIMESTAMPTZ | No / — | IDX | Validation time | Yes / R7 |

### `ai.report`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Report ID | Yes / R7 |
| `analysis_case_id` | UUID | No / — | FK → `ai.analysis_case.id`, UQ/IDX | Case | Yes / R7 |
| `report_type` | VARCHAR(30) | No / — | IDX | Report class | Yes / R7 |
| `status` | VARCHAR(30) | No / — | IDX | Generation/review status | Yes / R7 |
| `generated_by_agent_run_id` | UUID | Yes / — | FK → `ai.agent_run.id` | Generating run | Yes / R7 |
| `reviewed_by` | UUID | Yes / — | FK → `identity.employee.id`, IDX | Human reviewer | Yes / R3 |
| `approved_by` | UUID | Yes / — | FK → `identity.employee.id`, IDX | Report approver, not loan decision | Yes / R3 |
| `version_number` | INTEGER | No / — | UQ part | Positive report version | No / R7 |
| `json_payload` | JSONB | No / — | no broad exposure | Structured report | Yes / R7 |
| `pdf_object_id` | UUID | Yes / — | FK → `storage.object_metadata.id` | Generated PDF object | Yes / R4 |
| `created_at` | TIMESTAMPTZ | No / — | IDX | Creation time | Yes / R7 |

Unique `(analysis_case_id, version_number)`.

### `ai.report_claim`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Claim ID | Yes / R7 |
| `report_id` | UUID | No / — | FK → `ai.report.id`, IDX | Report | Yes / R7 |
| `section` | VARCHAR(50) | No / — | composite IDX | Report section | Yes / R7 |
| `claim_text` | TEXT | No / — | — | Verifiable claim | Yes / R7 |
| `claim_type` | VARCHAR(30) | No / — | IDX | Claim category | Yes / R7 |
| `confidence` | NUMERIC(6,5) | Yes / — | — | 0–1 confidence | No / R7 |
| `validation_status` | VARCHAR(30) | No / — | IDX | Evidence validation status | Yes / R7 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R7 |

### `ai.report_claim_evidence`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `claim_id` | UUID | No / — | PK part, FK → `ai.report_claim.id` | Report claim | Yes / R7 |
| `evidence_link_id` | UUID | No / — | PK part, FK → `ai.evidence_link.id` | Supporting/contradicting evidence | Yes / R7 |
| `support_type` | VARCHAR(20) | No / — | IDX | Support relation | Yes / R7 |

## `integration`

### `integration.background_job` — durable job source of truth

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Job ID | Yes / R5 |
| `job_type` | VARCHAR(50) | No / — | composite IDX | Job type | Yes / R5 |
| `resource_type` | VARCHAR(40) | No / — | composite IDX | Target resource type | Yes / R5 |
| `resource_id` | UUID | No / — | composite IDX | Target resource | Yes / R5 |
| `status` | VARCHAR(30) | No / — | composite IDX | Queued/published/running/waiting/retrying/completed/failed/cancelled | Yes / R5 |
| `progress_percent` | SMALLINT | No / `0` | — | 0–100 progress | No / R5 |
| `current_step` | VARCHAR(50) | Yes / — | — | Current safe step code | Yes / R5 |
| `correlation_id` | UUID | No / — | `idx_background_job_correlation` | End-to-end correlation | Yes / R5 |
| `requested_by` | UUID | Yes / — | FK → `identity.employee.id`, IDX | Requesting employee | Yes / R3 |
| `priority` | SMALLINT | No / `5` | composite IDX | Non-negative scheduling priority | No / R5 |
| `attempt_count` | INTEGER | No / `0` | — | Attempts so far | No / R5 |
| `max_attempts` | INTEGER | No / `5` | — | Positive finite limit | No / R5 |
| `scheduled_at` | TIMESTAMPTZ | Yes / — | IDX | Earliest run time | Yes / R5 |
| `started_at` | TIMESTAMPTZ | Yes / — | — | Start time | Yes / R5 |
| `completed_at` | TIMESTAMPTZ | Yes / — | IDX | Completion time | Yes / R5 |
| `error_code` | VARCHAR(50) | Yes / — | IDX | Safe machine error | Yes / R5 |
| `error_message_safe` | TEXT | Yes / — | — | Redacted diagnostic | Yes / R5 |
| `result_reference_type` | VARCHAR(40) | Yes / — | composite IDX | Durable result type | Yes / R5 |
| `result_reference_id` | UUID | Yes / — | composite IDX | Durable result ID | Yes / R5 |
| `created_at` | TIMESTAMPTZ | No / — | IDX | Creation time | Yes / R5 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R5 |
| `version` | INTEGER | No / `1` | — | Optimistic lock | No / R5 |

### `integration.background_job_step`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Step ID | Yes / R5 |
| `job_id` | UUID | No / — | FK → `integration.background_job.id`, UQ/IDX | Parent job | Yes / R5 |
| `step_code` | CITEXT | No / — | UQ part | Stable step code | Yes / R5 |
| `step_order` | INTEGER | No / — | composite IDX | Non-negative execution order | No / R5 |
| `status` | VARCHAR(30) | No / — | composite IDX | Step status | Yes / R5 |
| `progress_percent` | SMALLINT | No / `0` | — | 0–100 progress | No / R5 |
| `attempt_count` | INTEGER | No / `0` | — | Non-negative attempts | No / R5 |
| `started_at` | TIMESTAMPTZ | Yes / — | — | Start time | Yes / R5 |
| `completed_at` | TIMESTAMPTZ | Yes / — | — | Completion time | Yes / R5 |
| `error_code` | VARCHAR(50) | Yes / — | IDX | Safe error code | Yes / R5 |
| `error_message_safe` | TEXT | Yes / — | — | Redacted error | Yes / R5 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R5 |
| `updated_at` | TIMESTAMPTZ | No / — | — | Last update | Yes / R5 |

Unique `(job_id, step_code)`.

### `integration.job_event` — ordered SSE replay history

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | BIGSERIAL | No / sequence | PK | Internal event row ID | No / R5 |
| `job_id` | UUID | No / — | FK → `integration.background_job.id`, UQ/IDX | Job | Yes / R5 |
| `event_type` | VARCHAR(50) | No / — | IDX | Progress event type | Yes / R5 |
| `sequence_number` | BIGINT | No / — | UQ part | Non-negative per-job sequence | No / R5 |
| `payload` | JSONB | No / — | — | Minimal reconnect payload; no secrets | Yes / R5 |
| `created_at` | TIMESTAMPTZ | No / — | composite IDX | Event time | Yes / R5 |

Unique `(job_id, sequence_number)`.

### `integration.event_outbox` — transactional outbox

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Outbox/event ID | Yes / R5 |
| `aggregate_type` | VARCHAR(50) | No / — | composite IDX | Aggregate type | Yes / R5 |
| `aggregate_id` | UUID | No / — | composite IDX | Aggregate ID | Yes / R5 |
| `event_type` | VARCHAR(100) | No / — | IDX | Contract event type | Yes / R5 |
| `event_version` | INTEGER | No / — | — | Positive schema version | No / R5 |
| `partition_key` | TEXT | No / — | IDX | Kafka ordering key; no direct PII | Yes / R5 |
| `payload` | JSONB | No / — | — | Validated minimal event payload | Yes / R5 |
| `headers` | JSONB | No / `{}` | — | Safe correlation/schema headers | Yes / R5 |
| `status` | VARCHAR(20) | No / `'PENDING'` | scheduling IDX | Pending/processing/published/failed | Yes / R5 |
| `attempt_count` | INTEGER | No / `0` | — | Non-negative publish attempts | No / R5 |
| `available_at` | TIMESTAMPTZ | No / — | scheduling IDX | Earliest publish time | Yes / R5 |
| `locked_at` | TIMESTAMPTZ | Yes / — | — | Publisher lease time | Yes / R5 |
| `locked_by` | TEXT | Yes / — | — | Publisher instance | Yes / R5 |
| `published_at` | TIMESTAMPTZ | Yes / — | IDX | Successful publish time | Yes / R5 |
| `last_error` | TEXT | Yes / — | — | Redacted last error | Yes / R5 |
| `created_at` | TIMESTAMPTZ | No / — | scheduling IDX | Creation time | Yes / R5 |

Critical leasing index: `(status, available_at, created_at)`; publisher uses
`FOR UPDATE SKIP LOCKED`.

### `integration.event_inbox` — consumer de-duplication

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Inbox row ID | Yes / R5 |
| `event_id` | UUID | No / — | UQ part | Incoming envelope ID | Yes / R5 |
| `consumer_name` | TEXT | No / — | UQ part | Stable consumer name | No / R5 |
| `event_type` | VARCHAR(100) | No / — | IDX | Event type | Yes / R5 |
| `received_at` | TIMESTAMPTZ | No / — | IDX | Receipt time | Yes / R5 |
| `processed_at` | TIMESTAMPTZ | Yes / — | IDX | Completion time | Yes / R5 |
| `status` | VARCHAR(20) | No / — | composite IDX | Processing status | Yes / R5 |
| `result_reference_id` | UUID | Yes / — | IDX | Durable result reference | Yes / R5 |
| `error_code` | VARCHAR(50) | Yes / — | IDX | Safe error | Yes / R5 |
| `created_at` | TIMESTAMPTZ | No / — | — | Record creation | Yes / R5 |

Unique `(event_id, consumer_name)` is the at-least-once idempotency boundary.

### `integration.idempotency_record`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Record ID | Yes / R5 |
| `idempotency_key` | UUID | No / — | UQ part | Client/request idempotency key | Yes / R5 |
| `actor_id` | UUID | No / — | UQ part, IDX | Request actor | Yes / R3 |
| `operation_name` | VARCHAR(100) | No / — | UQ part | Stable operation | Yes / R5 |
| `request_hash` | CHAR(64) | No / — | — | Request integrity hash | Yes / R5 |
| `response_status` | INTEGER | Yes / — | — | Stored HTTP/result status | Yes / R5 |
| `response_payload` | JSONB | Yes / — | no secrets/tokens | Safe replay response | Yes / R5 |
| `resource_type` | VARCHAR(40) | Yes / — | composite IDX | Created/affected resource type | Yes / R5 |
| `resource_id` | UUID | Yes / — | composite IDX | Created/affected resource ID | Yes / R5 |
| `expires_at` | TIMESTAMPTZ | No / — | IDX | Eligible cleanup time | Yes / R5 |
| `created_at` | TIMESTAMPTZ | No / — | — | Creation time | Yes / R5 |

Unique `(actor_id, operation_name, idempotency_key)`.

### `integration.notification`

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Notification ID | Yes / R5 |
| `employee_id` | UUID | No / — | FK → `identity.employee.id`, composite IDX | Recipient | Yes / R3 |
| `notification_type` | VARCHAR(50) | No / — | IDX | Notification type | Yes / R5 |
| `title` | TEXT | No / — | — | Safe title | Yes / R5 |
| `message` | TEXT | No / — | — | Safe user-visible message | Yes / R5 |
| `resource_type` | VARCHAR(40) | Yes / — | composite IDX | Related resource type | Yes / R5 |
| `resource_id` | UUID | Yes / — | composite IDX | Related resource | Yes / R5 |
| `status` | VARCHAR(20) | No / — | composite IDX | Unread/read/dismissed | Yes / R5 |
| `created_at` | TIMESTAMPTZ | No / — | composite IDX | Creation time | Yes / R5 |
| `read_at` | TIMESTAMPTZ | Yes / — | — | Read/dismiss time as required | Yes / R5 |

## `audit`

### `audit.audit_event` — append-only tamper-evident audit

| Column | Type | N / D | FK / index | Meaning | Sensitive / retention |
| --- | --- | --- | --- | --- | --- |
| `id` | UUID | No / — | PK | Audit event ID | Yes / R6 |
| `event_time` | TIMESTAMPTZ | No / — | composite IDX/BRIN | Event time UTC | Yes / R6 |
| `actor_type` | VARCHAR(20) | No / — | composite IDX | Employee/service/agent actor type | Yes / R6 |
| `actor_id` | UUID | Yes / — | composite IDX | Actor ID | Yes / R6 |
| `action` | VARCHAR(60) | No / — | composite IDX | Audited action | Yes / R6 |
| `resource_type` | VARCHAR(40) | No / — | composite IDX | Resource type | Yes / R6 |
| `resource_id` | UUID | Yes / — | composite IDX | Resource ID | Yes / R6 |
| `customer_id` | UUID | Yes / — | composite IDX | Customer scope | Yes / R6 |
| `loan_application_id` | UUID | Yes / — | composite IDX | Loan scope | Yes / R6 |
| `result` | VARCHAR(20) | No / — | IDX | Success/denied/failure result | Yes / R6 |
| `ip_address` | INET | Yes / — | IDX where justified | Request network address | Yes / R6 |
| `user_agent` | TEXT | Yes / — | — | User-agent string | Yes / R6 |
| `session_id` | TEXT | Yes / — | IDX | Opaque session reference, never token | Yes / R6 |
| `request_id` | UUID | Yes / — | IDX | Request correlation | Yes / R6 |
| `correlation_id` | UUID | Yes / — | IDX | Workflow correlation | Yes / R6 |
| `metadata` | JSONB | No / `{}` | GIN where queried | Minimal redacted audit metadata | Yes / R6 |
| `previous_hash` | CHAR(64) | Yes / — | — | Previous chain hash | Yes / R6 |
| `event_hash` | CHAR(64) | No / — | — | Current event hash | Yes / R6 |
| `created_at` | TIMESTAMPTZ | No / — | BRIN/IDX | Insert time | Yes / R6 |

Runtime roles cannot update, delete or truncate this table; a trigger rejects row
mutation. Tokens, passwords, API keys, complete identity/account numbers and
document bodies are forbidden in `metadata`.

## Readonly views

| View | Purpose and excluded data |
| --- | --- |
| `customer.v_customer_summary` | Customer/party summary without encrypted identifiers or contacts |
| `banking.v_account_masked` | Masked account view without a full account number or raw sensitive payload |
| `banking.v_transaction_summary` | Authorized transaction summary without sensitive `raw_payload` |
| `document.v_document_summary` | Document metadata/status without object credentials or full content |
| `credit.v_loan_application_summary` | Loan workflow/amount summary without calculation/report payloads |
| `ai.v_report_summary` | Report metadata/review state without full report payload |

For business data, `bank_readonly` receives view access only. Its separate
`pg_monitor` membership exposes PostgreSQL system statistics to the exporter,
not business-table writes. These `security_barrier` views are a column-masking
boundary and never expose `encrypted_value`, secrets, credentials, full account
numbers or sensitive raw payloads. They are not a substitute for assigning the
readonly credential only to an appropriately authorized reporting service;
deployments requiring per-employee row scope must use invoker-safe RLS or an
equivalent scoped query path.

## Exact secondary-index catalogue

The list below mirrors `V013__create_indexes.sql`. PK/UQ indexes created by table
constraints remain documented in their column/table sections above.

| Schema | Index | Key / predicate |
| --- | --- | --- |
| identity | `idx_branch_parent_branch_id` | `branch(parent_branch_id)` |
| identity | `idx_branch_status` | `branch(status)` |
| identity | `idx_department_branch_id` | `department(branch_id)` |
| identity | `idx_department_status` | `department(status)` |
| identity | `idx_employee_branch_id` | `employee(branch_id)` |
| identity | `idx_employee_department_id` | `employee(department_id)` |
| identity | `idx_employee_manager_id` | `employee(manager_id)` |
| identity | `idx_employee_employment_status` | `employee(employment_status)` |
| identity | `idx_role_permission_permission_id` | `role_permission(permission_id)` |
| identity | `idx_employee_role_employee_validity` | `employee_role(employee_id, valid_from, valid_until)` |
| identity | `idx_employee_role_role_id` | `employee_role(role_id)` |
| identity | `idx_employee_scope_employee_validity` | `employee_scope(employee_id, valid_from, valid_until)` |
| identity | `idx_employee_scope_target` | `employee_scope(scope_type, scope_id, permission_code)` |
| customer | `idx_party_type_status` | `party(party_type, status)` |
| customer | `idx_organization_legal_representative` | `organization_profile(legal_representative_party_id)` |
| customer | `idx_customer_home_branch` | `customer(home_branch_id)` |
| customer | `idx_customer_relationship_manager` | `customer(relationship_manager_id)` |
| customer | `idx_customer_kyc_status` | `customer(kyc_status)` |
| customer | `idx_customer_status` | `customer(status)` |
| customer | `idx_party_identifier_party_id` | `party_identifier(party_id)` |
| customer | `idx_party_contact_party_type` | `party_contact(party_id, contact_type)` |
| customer | `uq_party_contact_primary_type` | unique `party_contact(party_id, contact_type) WHERE is_primary` |
| customer | `idx_party_address_party_type` | `party_address(party_id, address_type)` |
| customer | `idx_employment_party_id` | `employment(party_id)` |
| customer | `idx_income_source_party_date` | `income_source(party_id, as_of_date DESC)` |
| customer | `idx_party_relationship_from` | `party_relationship(from_party_id)` |
| customer | `idx_party_relationship_to` | `party_relationship(to_party_id)` |
| customer | `idx_kyc_assessment_customer_date` | `kyc_assessment(customer_id, assessment_date DESC)` |
| banking | `idx_account_branch_status` | `account(branch_id, status)` |
| banking | `idx_account_holder_account` | `account_holder(account_id)` |
| banking | `idx_account_holder_party` | `account_holder(party_id)` |
| banking | `idx_transaction_account_booking` | `transaction(account_id, booking_time DESC)`; partitioned |
| banking | `idx_transaction_type_booking` | `transaction(transaction_type, booking_time DESC)`; partitioned |
| banking | `idx_transaction_counterparty_hash` | `transaction(counterparty_account_hash)`; partitioned |
| banking | `idx_transaction_booking_brin` | BRIN `transaction(booking_time)`; partitioned |
| banking | `idx_monthly_summary_year_month` | `account_monthly_summary(year_month)` |
| banking | `idx_credit_report_customer_date` | `credit_report(customer_id, report_as_of_date DESC)` |
| banking | `idx_credit_facility_report` | `credit_facility(credit_report_id)` |
| storage | `idx_object_metadata_active_location` | `object_metadata(bucket_name, object_key) WHERE deleted_at IS NULL` |
| storage | `idx_object_metadata_sha256` | `object_metadata(sha256)` |
| storage | `idx_upload_session_customer_status` | `upload_session(customer_id, status, created_at DESC)` |
| storage | `idx_upload_session_loan_application` | `upload_session(loan_application_id)` |
| storage | `idx_upload_session_expiry` | `upload_session(expires_at) WHERE status IN (CREATED, UPLOADING, UPLOADED, VERIFYING)` |
| storage | `idx_upload_session_idempotency` | `upload_session(idempotency_key)` |
| storage | `idx_retention_rule_resource_active` | `retention_rule(resource_type, is_active)` |
| storage | `idx_resource_retention_resource` | `resource_retention(resource_type, resource_id)` |
| storage | `idx_resource_retention_until` | `resource_retention(retention_until) WHERE legal_hold = FALSE` |
| document | `idx_document_owner` | `document(owner_party_id)` |
| document | `idx_document_processing_status` | `document(processing_status, verification_status)` |
| document | `idx_document_version_document` | `document_version(document_id)` |
| document | `uq_document_current_version` | unique `document_version(document_id) WHERE is_current` |
| document | `idx_document_link_entity` | `document_link(entity_type, entity_id)` |
| document | `idx_document_link_document` | `document_link(document_id)` |
| document | `idx_processing_job_document_status` | `processing_job(document_version_id, status)` |
| document | `idx_processing_job_correlation` | `processing_job(correlation_id)` |
| document | `idx_document_page_object` | `document_page(page_image_object_id)` |
| document | `idx_extracted_field_document_name` | `extracted_field(document_version_id, field_name)` |
| document | `idx_extracted_field_verification` | `extracted_field(verification_status)` |
| document | `idx_document_chunk_version` | `document_chunk(document_version_id)` |
| document | `idx_document_chunk_metadata` | GIN `document_chunk(metadata)` |
| document | `idx_document_chunk_embedding_hnsw` | HNSW `document_chunk(embedding vector_cosine_ops)` |
| document | `idx_document_issue_version_status` | `document_issue(document_version_id, status)` |
| document | `idx_document_issue_field` | `document_issue(field_id)` |
| credit | `idx_loan_product_status_effective` | `loan_product(status, effective_from, effective_until)` |
| credit | `idx_loan_application_customer` | `loan_application(primary_customer_id, created_at DESC)` |
| credit | `idx_loan_application_assignee_status` | `loan_application(assigned_employee_id, status)` |
| credit | `idx_loan_application_product` | `loan_application(product_id)` |
| credit | `idx_loan_party_application` | `loan_party(loan_application_id)` |
| credit | `idx_loan_party_party` | `loan_party(party_id)` |
| credit | `idx_existing_obligation_application` | `existing_obligation(loan_application_id)` |
| credit | `idx_existing_obligation_party` | `existing_obligation(party_id)` |
| credit | `idx_collateral_application` | `collateral(loan_application_id)` |
| credit | `idx_collateral_owner` | `collateral(owner_party_id)` |
| credit | `idx_collateral_valuation_collateral` | `collateral_valuation(collateral_id, valuation_date DESC)` |
| credit | `idx_loan_checklist_application_status` | `loan_checklist_item(loan_application_id, requirement_status)` |
| credit | `idx_calculation_application_type` | `calculation_record(loan_application_id, calculation_type, calculated_at DESC)` |
| credit | `idx_calculation_analysis_case` | `calculation_record(analysis_case_id)` |
| credit | `idx_affordability_application` | `affordability_assessment(loan_application_id, calculated_at DESC)` |
| credit | `idx_policy_check_application_status` | `policy_check(loan_application_id, status)` |
| credit | `idx_policy_check_analysis_case` | `policy_check(analysis_case_id)` |
| credit | `idx_approval_request_application` | `approval_request(loan_application_id, requested_at DESC)` |
| credit | `idx_loan_decision_application` | `loan_decision(loan_application_id, decision_at DESC)` |
| credit | `idx_disbursement_application` | `disbursement(loan_application_id)` |
| credit | `idx_repayment_schedule_due` | `repayment_schedule(loan_account_id, due_date)` |
| credit | `idx_loan_payment_account_date` | `loan_payment(loan_account_id, payment_date DESC)` |
| policy | `idx_policy_owner_department` | `policy(owner_department_id)` |
| policy | `idx_policy_status` | `policy(status)` |
| policy | `idx_policy_version_effective` | `policy_version(policy_id, effective_from, effective_until)` |
| policy | `idx_policy_clause_embedding_hnsw` | HNSW `policy_clause(embedding vector_cosine_ops)` |
| policy | `idx_policy_clause_metadata` | GIN `policy_clause(metadata)` |
| policy | `idx_checklist_rule_policy` | `checklist_rule(policy_version_id)` |
| policy | `idx_checklist_requirement_rule` | `checklist_rule_requirement(checklist_rule_id)` |
| ai | `idx_conversation_employee_started` | `conversation(employee_id, started_at DESC)` |
| ai | `idx_conversation_customer` | `conversation(active_customer_id)` |
| ai | `idx_message_conversation_created` | `message(conversation_id, created_at)` |
| ai | `idx_message_parent` | `message(parent_message_id)` |
| ai | `idx_analysis_case_customer_status` | `analysis_case(customer_id, status, created_at DESC)` |
| ai | `idx_analysis_case_loan` | `analysis_case(loan_application_id)` |
| ai | `idx_analysis_case_correlation` | `analysis_case(correlation_id)` |
| ai | `idx_analysis_task_case_status` | `analysis_task(analysis_case_id, status)` |
| ai | `idx_agent_run_case_status` | `agent_run(analysis_case_id, status)` |
| ai | `idx_agent_run_task` | `agent_run(analysis_task_id)` |
| ai | `idx_finding_case_severity` | `finding(analysis_case_id, severity)` |
| ai | `idx_finding_agent_run` | `finding(agent_run_id)` |
| ai | `idx_evidence_finding` | `evidence_link(finding_id)` |
| ai | `idx_evidence_source` | `evidence_link(source_type, source_id)` |
| ai | `idx_validation_case` | `validation_result(analysis_case_id)` |
| ai | `idx_report_case_status` | `report(analysis_case_id, status)` |
| ai | `idx_report_claim_report` | `report_claim(report_id)` |
| ai | `idx_report_claim_evidence_link` | `report_claim_evidence(evidence_link_id)` |
| integration | `idx_background_job_status_schedule` | `background_job(status, scheduled_at, priority, created_at)` |
| integration | `idx_background_job_resource` | `background_job(resource_type, resource_id)` |
| integration | `idx_background_job_correlation` | `background_job(correlation_id)` |
| integration | `idx_background_job_requested_by` | `background_job(requested_by, created_at DESC)` |
| integration | `idx_background_job_step_job_order` | `background_job_step(job_id, step_order)` |
| integration | `idx_job_event_job_created` | `job_event(job_id, created_at)` |
| integration | `idx_event_outbox_pending` | `event_outbox(status, available_at, created_at)` |
| integration | `idx_event_outbox_aggregate` | `event_outbox(aggregate_type, aggregate_id)` |
| integration | `idx_event_inbox_status_received` | `event_inbox(consumer_name, status, received_at)` |
| integration | `idx_idempotency_expiry` | `idempotency_record(expires_at)` |
| integration | `idx_notification_employee_status` | `notification(employee_id, status, created_at DESC)` |
| audit | `idx_audit_event_time_brin` | BRIN `audit_event(event_time)` |
| audit | `idx_audit_event_actor` | `audit_event(actor_type, actor_id, event_time DESC)` |
| audit | `idx_audit_event_resource` | `audit_event(resource_type, resource_id, event_time DESC)` |
| audit | `idx_audit_event_customer` | `audit_event(customer_id, event_time DESC)` |
| audit | `idx_audit_event_loan` | `audit_event(loan_application_id, event_time DESC)` |
| audit | `idx_audit_event_correlation` | `audit_event(correlation_id)` |

## Completeness and maintenance

The dictionary covers 77 logical tables across all 10 required schemas. Monthly
`banking.transaction_*` partitions and `banking.transaction_default` inherit the
parent column contract and are physical partitions, not additional logical
entities. Flyway schema history is managed by Flyway in its configured metadata
schema and is not a business table.

Any migration that adds/changes a column, FK, index, sensitivity or retention
behavior must update this file in the same change. Database comments are the
machine-adjacent description; this dictionary adds operational sensitivity and
retention context.
