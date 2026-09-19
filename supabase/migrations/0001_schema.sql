-- =============================================================================
-- NovaShip Averis — Supabase / PostgreSQL schema (migration 0001)
-- Run in Supabase SQL editor or: supabase db push
-- All tables are tenant-scoped (tenant_id) and RLS-enabled in 0002_rls.sql.
-- Rich objects are kept in JSONB `payload` columns for replay; normalized
-- columns/tables exist for reporting, filtering, RLS and the dashboard.
-- =============================================================================

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------- tenants / users / roles
create table if not exists tenants (
  id          text primary key,
  name        text not null,
  created_at  timestamptz not null default now()
);

create table if not exists teams (
  id          text primary key,
  tenant_id   text not null references tenants(id),
  name        text not null
);

create table if not exists users (
  id           text primary key,                 -- = auth.users.id (uuid as text) or seed id
  tenant_id    text not null references tenants(id),
  email        text not null unique,
  display_name text not null,
  team_id      text references teams(id),
  is_external  boolean not null default false,
  created_at   timestamptz not null default now()
);

create table if not exists roles (
  id          text primary key,                  -- OPERATIONS_STAFF | SUPERVISOR | ADMIN | AUDITOR
  description text
);

create table if not exists user_roles (
  user_id   text not null references users(id) on delete cascade,
  role_id   text not null references roles(id),
  primary key (user_id, role_id)
);

create table if not exists party_contacts (              -- approved external Notify Party / collaborator contacts
  id          text primary key,
  tenant_id   text not null references tenants(id),
  name        text not null,
  email       text not null,
  party_name  text not null,
  approved    boolean not null default true
);

-- ---------------------------------------------------------------- email + attachments
create table if not exists email_messages (
  id                  text primary key,          -- immutable source message id
  tenant_id           text not null references tenants(id),
  provider            text not null default 'bundle',
  provider_message_id text,
  conversation_id     text,
  sender              text not null,
  sender_name         text,
  recipients          jsonb not null default '[]',
  cc                  jsonb not null default '[]',
  subject             text not null default '',
  body                text not null default '',
  received_at         timestamptz not null default now(),
  language            text not null default 'en',
  checksum            text not null,
  is_duplicate_of     text,
  payload             jsonb not null,
  created_at          timestamptz not null default now()
);
create index if not exists ix_email_checksum on email_messages(checksum);
create index if not exists ix_email_sender   on email_messages(tenant_id, sender);

create table if not exists attachments (
  id                    text primary key,
  tenant_id             text not null references tenants(id),
  source_email_id       text not null references email_messages(id) on delete cascade,
  file_name             text not null,
  file_type             text not null,
  size_bytes            integer not null default 0,
  checksum              text not null,
  storage_pointer       text,                    -- object path inside the `documents` bucket
  detected_type         text not null default 'UNKNOWN_DOCUMENT',
  detection_confidence  numeric(4,3) not null default 0,
  extraction_status     text not null default 'PENDING',
  extraction_confidence numeric(4,3) not null default 0,
  raw_text              text,
  page_count            integer,
  is_duplicate_of       text
);
create index if not exists ix_att_email    on attachments(source_email_id);
create index if not exists ix_att_checksum on attachments(checksum);

-- ---------------------------------------------------------------- cases
create table if not exists cases (
  id                 text primary key,
  tenant_id          text not null references tenants(id),
  source_email_id    text not null references email_messages(id),
  intent             text not null,
  hackathon_category text not null,
  action_required    boolean not null default false,
  priority           text not null default 'LOW',
  status             text not null default 'RECEIVED',
  security_outcome   text not null default 'SAFE',
  mismatch_count     integer not null default 0,
  comparison_status  text,
  review_reason      text,
  confidence         numeric(4,3) not null default 0,
  si_available       boolean not null default false,
  bl_available       boolean not null default false,
  si_document_id     text,
  bl_document_id     text,
  assigned_user_id   text references users(id),
  assigned_team_id   text references teams(id),
  shared_with        jsonb not null default '[]',
  processing_ms      integer not null default 0,
  payload            jsonb not null,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);
create index if not exists ix_cases_status   on cases(tenant_id, status);
create index if not exists ix_cases_priority on cases(tenant_id, priority);
create index if not exists ix_cases_intent   on cases(tenant_id, intent);
create index if not exists ix_cases_assigned on cases(assigned_user_id);
create index if not exists ix_cases_updated  on cases(updated_at desc);

create table if not exists case_documents (              -- which attachment plays which role in a case
  id           text primary key,
  case_id      text not null references cases(id) on delete cascade,
  attachment_id text not null references attachments(id),
  role         text not null check (role in ('SI','BL','OTHER'))
);

create table if not exists extracted_fields (
  id               text primary key,
  tenant_id        text not null references tenants(id),
  case_id          text not null references cases(id) on delete cascade,
  document_kind    text not null check (document_kind in ('SI','BL')),
  field_name       text not null check (field_name in ('shipper','consignee','notify_party','port_of_loading','port_of_discharge','container_count','gross_weight_kg')),
  original_value   text,
  normalized_value text,
  confidence       numeric(4,3) not null default 0,
  needs_review     boolean not null default false,
  evidence         jsonb not null default '{}'
);
create index if not exists ix_xf_case on extracted_fields(case_id);

create table if not exists comparisons (
  id                   text primary key,
  tenant_id            text not null references tenants(id),
  case_id              text not null references cases(id) on delete cascade,
  comparison_status    text not null,
  mismatch_count       integer not null default 0,
  required_field_count integer not null default 7,
  message              text not null,
  mismatch_fields      jsonb not null default '[]',
  review_fields        jsonb not null default '[]',
  review_reason        text,
  compared_at          timestamptz not null default now(),
  si_document_id       text,
  bl_document_id       text,
  policy_version       text not null default 'v1'
);

create table if not exists comparison_fields (
  id             text primary key,
  comparison_id  text not null references comparisons(id) on delete cascade,
  case_id        text not null references cases(id) on delete cascade,
  tenant_id      text not null references tenants(id),
  field_name     text not null check (field_name in ('shipper','consignee','notify_party','port_of_loading','port_of_discharge','container_count','gross_weight_kg')),
  si_original    text,
  bl_original    text,
  si_normalized  text,
  bl_normalized  text,
  result         text not null check (result in ('MATCH','MISMATCH','MISSING_IN_SI','MISSING_IN_BL','LOW_CONFIDENCE_REVIEW')),
  confidence     numeric(4,3) not null default 0,
  reason         text not null default '',
  attention      text not null default '',
  si_evidence    jsonb not null default '{}',
  bl_evidence    jsonb not null default '{}',
  unique (comparison_id, field_name)
);
create index if not exists ix_cf_case on comparison_fields(case_id);

create table if not exists case_summaries (
  id            text primary key,
  tenant_id     text not null references tenants(id),
  case_id       text not null references cases(id) on delete cascade,
  text          text not null,
  generated_by  text not null default 'rule',
  evidence_refs jsonb not null default '[]',
  confidence    numeric(4,3) not null default 1
);

create table if not exists action_recommendations (
  id                 text primary key,
  tenant_id          text not null references tenants(id),
  case_id            text not null references cases(id) on delete cascade,
  action_required    boolean not null,
  action_type        text not null,
  priority           text not null,
  reason             text not null,
  recommended_action text not null,
  responsible_role   text not null,
  confidence         numeric(4,3) not null default 0
);

create table if not exists drafts (
  id                         text primary key,
  tenant_id                  text not null references tenants(id),
  case_id                    text not null references cases(id) on delete cascade,
  draft_type                 text not null,
  to_recipients              jsonb not null default '[]',
  cc_recipients              jsonb not null default '[]',
  subject                    text not null,
  body                       text not null,
  evidence_refs              jsonb not null default '[]',
  status                     text not null default 'PROPOSED',
  version                    integer not null default 1,
  requires_external_approval boolean not null default true,
  generated_by               text not null default 'rule',
  created_at                 timestamptz not null default now()
);

create table if not exists assignments (
  id               text primary key,
  tenant_id        text not null references tenants(id),
  case_id          text not null references cases(id) on delete cascade,
  assigned_user_id text references users(id),
  assigned_team_id text references teams(id),
  assigned_at      timestamptz not null default now()
);

create table if not exists shares (
  id                 text primary key,
  tenant_id          text not null references tenants(id),
  case_id            text not null references cases(id) on delete cascade,
  shared_by          text not null,
  recipient_type     text not null,
  recipient_user_id  text,
  recipient_party_id text,
  recipient_label    text not null default '',
  is_external        boolean not null default false,
  message            text not null,
  payload_preview    jsonb not null default '{}',
  due_date           text,
  sent_at            timestamptz,
  viewed_at          timestamptz,
  acknowledged_at    timestamptz,
  response           text,
  status             text not null default 'PENDING_CONFIRMATION'
);
create index if not exists ix_shares_case on shares(case_id);

create table if not exists notifications (
  id          text primary key,
  tenant_id   text not null references tenants(id),
  case_id     text references cases(id) on delete cascade,
  channel     text not null default 'email',
  recipient   text not null,
  subject     text,
  body        text,
  status      text not null default 'QUEUED',
  sent_at     timestamptz,
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------- policies (versioned)
create table if not exists policies (
  id             text primary key,
  tenant_id      text not null references tenants(id),
  name           text not null,
  active_version text not null
);

create table if not exists policy_versions (
  id          text primary key,
  tenant_id   text not null references tenants(id),
  policy_id   text not null references policies(id),
  version     text not null,
  name        text not null,
  values      jsonb not null,
  updated_by  text not null,
  change_note text not null default '',
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------- audit (append-only), errors, ai runs
create table if not exists audit_events (
  event_id       text primary key,
  tenant_id      text not null references tenants(id),
  case_id        text,
  timestamp      timestamptz not null default now(),
  actor_type     text not null check (actor_type in ('USER','AI','SYSTEM')),
  actor_id       text not null,
  action         text not null,
  before         jsonb,
  after          jsonb,
  evidence_ref   text,
  policy_version text not null default 'v1'
);
create index if not exists ix_audit_case on audit_events(case_id, timestamp);

create table if not exists processing_errors (
  id           text primary key,
  tenant_id    text not null references tenants(id),
  case_id      text not null references cases(id) on delete cascade,
  category     text not null,
  step         text not null,
  message      text not null,
  safe_details text,
  recovery     text not null,
  retryable    boolean not null default true,
  created_at   timestamptz not null default now(),
  resolved     boolean not null default false
);

create table if not exists ai_runs (                      -- idempotency + LLM run log
  id         text primary key,                            -- job key e.g. run:<email checksum>
  tenant_id  text not null references tenants(id),
  result     jsonb not null default '{}',
  provider   text,
  model      text,
  latency_ms integer,
  created_at timestamptz not null default now()
);

-- append-only guard for audit_events
create or replace function audit_events_no_update() returns trigger language plpgsql as $$
begin
  raise exception 'audit_events is append-only';
end $$;
drop trigger if exists trg_audit_no_update on audit_events;
create trigger trg_audit_no_update before update or delete on audit_events for each row execute function audit_events_no_update();

-- updated_at maintenance
create or replace function touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;
drop trigger if exists trg_cases_touch on cases;
create trigger trg_cases_touch before update on cases for each row execute function touch_updated_at();

-- storage bucket for original documents (private; use signed URLs)
insert into storage.buckets (id, name, public) values ('documents', 'documents', false) on conflict (id) do nothing;
