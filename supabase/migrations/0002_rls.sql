-- =============================================================================
-- Row Level Security (migration 0002)
--
-- Model: the backend talks to Supabase with the SERVICE ROLE key (bypasses RLS)
-- and enforces RBAC in app/auth/rbac.py. RLS below protects DIRECT client
-- access (anon/authenticated JWT) so a browser can never read another tenant's
-- rows or mutate audit history.
--
-- JWT claims used:  sub (user id), app_metadata.tenant_id, app_metadata.roles[]
-- =============================================================================

create or replace function auth_tenant() returns text language sql stable as $$
  select coalesce(
    nullif(current_setting('request.jwt.claims', true)::jsonb -> 'app_metadata' ->> 'tenant_id', ''),
    (select tenant_id from users where id = auth.uid()::text limit 1)
  )
$$;

create or replace function auth_has_role(r text) returns boolean language sql stable as $$
  select exists (
    select 1 from user_roles ur where ur.user_id = auth.uid()::text and ur.role_id = r
  ) or coalesce((current_setting('request.jwt.claims', true)::jsonb -> 'app_metadata' -> 'roles') ? r, false)
$$;

-- enable RLS everywhere
do $$
declare t text;
begin
  for t in select unnest(array['tenants','teams','users','user_roles','party_contacts','email_messages','attachments','cases','case_documents',
                               'extracted_fields','comparisons','comparison_fields','case_summaries','action_recommendations','drafts',
                               'assignments','shares','notifications','policies','policy_versions','audit_events','processing_errors','ai_runs'])
  loop
    execute format('alter table %I enable row level security', t);
    execute format('alter table %I force row level security', t);
  end loop;
end $$;

-- ---- tenant-scoped READ for every authenticated user of that tenant
do $$
declare t text;
begin
  for t in select unnest(array['teams','users','party_contacts','email_messages','attachments','cases','case_documents','extracted_fields',
                               'comparisons','comparison_fields','case_summaries','action_recommendations','drafts','assignments','shares',
                               'notifications','policies','policy_versions','audit_events','processing_errors'])
  loop
    execute format('drop policy if exists %I on %I', t || '_tenant_read', t);
    execute format('create policy %I on %I for select to authenticated using (tenant_id = auth_tenant())', t || '_tenant_read', t);
  end loop;
end $$;

drop policy if exists tenants_self_read on tenants;
create policy tenants_self_read on tenants for select to authenticated using (id = auth_tenant());

drop policy if exists user_roles_read on user_roles;
create policy user_roles_read on user_roles for select to authenticated
  using (exists (select 1 from users u where u.id = user_roles.user_id and u.tenant_id = auth_tenant()));

-- ---- WRITE rules (client-side writes are limited; the API does the rest with service role)
-- operations/supervisor/admin may update case assignment + status
drop policy if exists cases_ops_update on cases;
create policy cases_ops_update on cases for update to authenticated
  using (tenant_id = auth_tenant() and (auth_has_role('OPERATIONS_STAFF') or auth_has_role('SUPERVISOR') or auth_has_role('ADMIN')))
  with check (tenant_id = auth_tenant());

-- drafts: staff may edit; only supervisor/admin may set APPROVED/SENT
drop policy if exists drafts_edit on drafts;
create policy drafts_edit on drafts for update to authenticated
  using (tenant_id = auth_tenant() and (auth_has_role('OPERATIONS_STAFF') or auth_has_role('SUPERVISOR') or auth_has_role('ADMIN')))
  with check (tenant_id = auth_tenant() and (status not in ('APPROVED','SENT') or auth_has_role('SUPERVISOR') or auth_has_role('ADMIN')));

-- shares: internal share by staff; external (is_external) only by supervisor/admin
drop policy if exists shares_insert on shares;
create policy shares_insert on shares for insert to authenticated
  with check (tenant_id = auth_tenant() and shared_by = auth.uid()::text
              and ((not is_external and (auth_has_role('OPERATIONS_STAFF') or auth_has_role('SUPERVISOR') or auth_has_role('ADMIN')))
                   or (is_external and (auth_has_role('SUPERVISOR') or auth_has_role('ADMIN')))));

-- recipients may acknowledge shares addressed to them
drop policy if exists shares_ack on shares;
create policy shares_ack on shares for update to authenticated
  using (tenant_id = auth_tenant() and recipient_user_id = auth.uid()::text)
  with check (tenant_id = auth_tenant() and recipient_user_id = auth.uid()::text);

-- policies: admin only
drop policy if exists policy_versions_admin on policy_versions;
create policy policy_versions_admin on policy_versions for insert to authenticated
  with check (tenant_id = auth_tenant() and auth_has_role('ADMIN'));
drop policy if exists policies_admin on policies;
create policy policies_admin on policies for all to authenticated
  using (tenant_id = auth_tenant() and auth_has_role('ADMIN')) with check (tenant_id = auth_tenant() and auth_has_role('ADMIN'));

-- audit: insert-only for authenticated (trigger blocks update/delete for everyone incl. service role)
drop policy if exists audit_insert on audit_events;
create policy audit_insert on audit_events for insert to authenticated with check (tenant_id = auth_tenant());

-- audit read restricted to SUPERVISOR / ADMIN / AUDITOR (overrides generic tenant read)
drop policy if exists audit_events_tenant_read on audit_events;
create policy audit_events_tenant_read on audit_events for select to authenticated
  using (tenant_id = auth_tenant() and (auth_has_role('SUPERVISOR') or auth_has_role('ADMIN') or auth_has_role('AUDITOR')));

-- ---- storage: documents bucket, tenant-prefixed paths <tenant>/... ; signed URLs expire (default 300 s in API)
drop policy if exists documents_read on storage.objects;
create policy documents_read on storage.objects for select to authenticated
  using (bucket_id = 'documents' and (storage.foldername(name))[1] in (auth_tenant(), 'bundle', 'webhook', 'upload', 'test'));
drop policy if exists documents_write on storage.objects;
create policy documents_write on storage.objects for insert to authenticated
  with check (bucket_id = 'documents' and (auth_has_role('OPERATIONS_STAFF') or auth_has_role('SUPERVISOR') or auth_has_role('ADMIN')));
