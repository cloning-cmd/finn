-- FINN schema of record (Postgres / Supabase). Mirrored by SQLAlchemy models in api/db.py.
-- pgvector is optional: embeddings are stored as bytea and searched in Python (see DECISIONS 2026-11-11).

create table if not exists companies (
  ticker text primary key,
  name text not null,
  nse_symbol text,
  bse_code text,
  sector text,
  industry text,
  is_lender boolean default false,
  in_portfolio boolean default false,
  weight double precision default 0
);

create table if not exists prices_eod (
  ticker text not null,
  date text not null,
  open double precision, high double precision, low double precision, close double precision,
  volume bigint,
  ret double precision, vol60 double precision, vol_avg20 double precision, z double precision,
  primary key (ticker, date)
);

create table if not exists filings (
  id text primary key,
  ticker text not null,
  exchange text default 'NSE',
  ts timestamptz not null,
  subject text,
  raw_category text,
  body_text text,
  attachment_url text,
  content_hash text unique,
  category text,
  category_conf double precision,
  classifier text,
  priority double precision,
  tier text,
  headline text,
  one_liner text,
  payload jsonb,
  card_type text,
  created_at timestamptz default now()
);
create index if not exists ix_filings_ticker_ts on filings (ticker, ts);
create index if not exists ix_filings_ts on filings (ts);
create index if not exists ix_filings_category on filings (category);

create table if not exists anomalies (
  id text primary key,
  ticker text, date text, kind text,
  value double precision, z double precision, vol_multiple double precision,
  explained_by jsonb, unexplained boolean default false,
  priority double precision, tier text, payload jsonb,
  created_at timestamptz default now()
);
create index if not exists ix_anomalies_ticker on anomalies (ticker);
create index if not exists ix_anomalies_date on anomalies (date);

create table if not exists rules (
  id text primary key,
  json jsonb not null,
  enabled boolean default true,
  updated_at timestamptz default now()
);

create table if not exists alerts (
  id text primary key,
  rule_id text, card_id text,
  fired_at timestamptz default now(),
  delivered boolean default false,
  card jsonb
);
create index if not exists ix_alerts_fired_at on alerts (fired_at);

create table if not exists push_subscriptions (
  endpoint text primary key,
  json jsonb not null,
  created_at timestamptz default now()
);

create table if not exists documents (
  id text primary key,
  ticker text, kind text, period text, url text, sha256 text, text_path text, pages integer,
  scanned boolean default false,
  created_at timestamptz default now()
);
create index if not exists ix_documents_ticker on documents (ticker);

create table if not exists chunks (
  id text primary key,
  document_id text, ticker text, period text, speaker text, page integer,
  text text,
  embedding bytea
);
create index if not exists ix_chunks_ticker on chunks (ticker);
create index if not exists ix_chunks_document on chunks (document_id);

create table if not exists promises (
  id text primary key,
  ticker text, json jsonb not null, status text,
  created_at timestamptz default now()
);
create index if not exists ix_promises_ticker on promises (ticker);

create table if not exists dossiers (
  ticker text primary key,
  as_of text, doc_sha text, prompt_version text,
  json jsonb not null,
  created_at timestamptz default now()
);

create table if not exists llm_cache (
  key text primary key,
  task text, model text, prompt_version text, input_hash text,
  output jsonb,
  tokens_in integer default 0, tokens_out integer default 0, cost_inr double precision default 0,
  hits integer default 0,
  created_at timestamptz default now()
);
create index if not exists ix_llm_cache_task on llm_cache (task);

create table if not exists feedback (
  id serial primary key,
  card_id text, ticker text, category text, action text,
  ts timestamptz default now()
);
create index if not exists ix_feedback_ticker_cat on feedback (ticker, category);
