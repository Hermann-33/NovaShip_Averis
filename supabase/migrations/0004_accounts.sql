-- 0004: local password accounts + session revocation (login / register / logout).
-- Supabase Auth JWTs keep working; this table only backs the built-in email+password login.
create table if not exists user_credentials (
  user_id       text primary key references users(id) on delete cascade,
  password_hash text not null,                      -- pbkdf2_sha256$rounds$salt$digest (never plaintext)
  updated_at    timestamptz not null default now()
);

create table if not exists revoked_sessions (
  session_id text primary key,
  revoked_at timestamptz not null default now()
);

-- Service-role only: the API layer reads these, browsers never do.
alter table user_credentials enable row level security;
alter table revoked_sessions enable row level security;
