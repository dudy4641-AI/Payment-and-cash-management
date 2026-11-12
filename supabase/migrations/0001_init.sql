-- Initial schema for supplier payments and balances (SPEC.md).
-- Mirrors payments/models.py. USD only; amounts are numeric(14,2), never float.

create type doc_status as enum (
  'הועלתה',
  'ממתינה לאישור',
  'אושרה',
  'שולמה',
  'חסרה חשבונית',
  'דורשת בירור'
);

create type doc_type as enum ('דרישת תשלום', 'חשבונית מס');
create type entity as enum ('ישראל', 'ארה"ב');
create type bank_kind as enum ('bank', 'card_platform');
create type alert_type as enum ('כפל תשלום', 'בנק לא נכון', 'מקרה ספק');
create type alert_recipient as enum ('סמנכ"ל כספים', 'מנהלת חשבונות');

create table banks (
  code            text primary key,
  name            text not null,
  entity          entity not null,
  kind            bank_kind not null,
  opening_balance numeric(14,2) not null
);

create table suppliers (
  name            text primary key,
  entity          entity not null,
  budget_category text           -- null = new supplier, must be set before approval
);

create table documents (
  id                uuid primary key default gen_random_uuid(),
  doc_type          doc_type not null,
  supplier_name     text not null references suppliers(name),
  amount            numeric(14,2) not null check (amount > 0),
  doc_number        text not null,
  status            doc_status not null,
  linked_payment_id uuid,          -- tax invoice that closes a paid demand
  uploaded_at       timestamptz not null default now()
);
-- Not unique on purpose: a double upload is stored and flagged, not rejected.
create index documents_fingerprint on documents (supplier_name, doc_type, doc_number);

create table payments (
  id                uuid primary key default gen_random_uuid(),
  document_id       uuid not null unique references documents(id),
  bank_code         text not null references banks(code),
  supplier_name     text not null references suppliers(name),
  amount            numeric(14,2) not null check (amount > 0),
  approved_at       timestamptz not null default now(),
  statement_line_id uuid
);

alter table documents
  add constraint documents_linked_payment_fk
  foreign key (linked_payment_id) references payments(id);

create table statement_lines (
  id                 uuid primary key default gen_random_uuid(),
  bank_code          text not null references banks(code),
  payee_name         text not null,
  amount             numeric(14,2) not null check (amount > 0),
  value_date         date not null,
  status             doc_status,
  matched_payment_id uuid unique references payments(id),
  uploaded_at        timestamptz not null default now()
);

alter table payments
  add constraint payments_statement_line_fk
  foreign key (statement_line_id) references statement_lines(id);

create table alerts (
  id                uuid primary key default gen_random_uuid(),
  alert_type        alert_type not null,
  recipient         alert_recipient not null,
  document_id       uuid references documents(id),
  statement_line_id uuid references statement_lines(id),
  message           text not null default '',
  resolved          boolean not null default false,
  created_at        timestamptz not null default now(),
  check (document_id is not null or statement_line_id is not null)
);

-- Row level security on every table. With no policies, the public (anon) key
-- sees nothing; the server-side key used by the app and tests bypasses RLS.
alter table banks           enable row level security;
alter table suppliers       enable row level security;
alter table documents       enable row level security;
alter table payments        enable row level security;
alter table statement_lines enable row level security;
alter table alerts          enable row level security;
