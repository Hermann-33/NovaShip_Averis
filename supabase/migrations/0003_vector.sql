-- =============================================================================
-- Migration 0003 - pgvector store for Ask-AI retrieval (RAG)
-- Requires: Database > Extensions > "vector" enabled (Supabase has it built in).
-- Embedding dims: Gemini text-embedding-004 = 768, OpenAI text-embedding-3-small = 1536,
-- local fallback = 256. Change EMBED_DIMS below to match EMBEDDING_PROVIDER, then re-run
-- `python -m app.agents.create_index` (a dimension change requires TRUNCATE case_embeddings).
-- =============================================================================
create extension if not exists vector;

do $$ begin
  if not exists (select 1 from information_schema.tables where table_name = 'case_embeddings') then
    execute 'create table case_embeddings (
      id         text primary key,
      tenant_id  text not null references tenants(id),
      case_id    text references cases(id) on delete cascade,
      source     text not null,
      content    text not null,
      metadata   jsonb not null default ''{}'',
      embedding  vector(768),            -- EMBED_DIMS
      created_at timestamptz not null default now()
    )';
  end if;
end $$;
create index if not exists ix_emb_case   on case_embeddings(case_id);
create index if not exists ix_emb_source on case_embeddings(tenant_id, source);
-- ANN index (cosine). Build after the first bulk load for best results.
create index if not exists ix_emb_vec on case_embeddings using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- Similarity search scoped to tenant + (optionally) one case + source prefixes.
create or replace function match_case_chunks(query_embedding vector, match_count int, p_tenant text, p_case_id text default null, p_sources text[] default '{}')
returns table (id text, case_id text, source text, content text, metadata jsonb, similarity float)
language sql stable as $$
  select e.id, e.case_id, e.source, e.content, e.metadata, 1 - (e.embedding <=> query_embedding) as similarity
  from case_embeddings e
  where e.tenant_id = p_tenant
    and (p_case_id is null or e.case_id is null or e.case_id = p_case_id)         -- never leak other cases
    and (coalesce(array_length(p_sources, 1), 0) = 0 or exists (select 1 from unnest(p_sources) s where e.source like s || '%'))
  order by e.embedding <=> query_embedding
  limit match_count
$$;

-- RLS: same tenant-scoped read as everything else
alter table case_embeddings enable row level security;
drop policy if exists case_embeddings_tenant_read on case_embeddings;
create policy case_embeddings_tenant_read on case_embeddings for select to authenticated using (tenant_id = auth_tenant());

-- LangGraph Postgres checkpointer (optional): tables are created automatically by
-- `PostgresSaver.setup()` when LANGGRAPH_CHECKPOINT=postgres and LANGGRAPH_PG_URL is set.
