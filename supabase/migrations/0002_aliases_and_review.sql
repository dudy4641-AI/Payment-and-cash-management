-- Stage 2a additions (SPEC section 5, matching rule (b) and wrong-bank hold).

-- Extra bank names of a supplier, saved when the bookkeeper confirms a match.
-- `alias` is the cleaned name, as produced by payments/names.py.
create table supplier_aliases (
  alias         text primary key,
  supplier_name text not null references suppliers(name),
  created_at    timestamptz not null default now()
);
alter table supplier_aliases enable row level security;

-- Bank the CFO picked when approval raised a wrong-bank alert.
alter table documents add column requested_bank_code text references banks(code);

-- Documents a doubtful statement line could belong to.
alter table statement_lines add column candidate_document_ids uuid[] not null default '{}';
