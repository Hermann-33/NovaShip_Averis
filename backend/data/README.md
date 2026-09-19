# Knowledge folder (RAG corpus)

Drop Markdown files here. The file-name prefix before the first underscore becomes the chunk `source`
(`policy_verification.md` -> source `policy`, `glossary_shipping.md` -> `glossary`, `ports_aliases.md` -> `ports`).
Then rebuild the index:

    cd backend
    python -m app.agents.create_index            # knowledge + all seeded cases
    python -m app.agents.create_index --knowledge-only

`index.json` (local store) is generated; it is git-ignored. With `VECTOR_STORE=supabase` chunks go to the
`case_embeddings` table (migration 0003_vector.sql) instead.
