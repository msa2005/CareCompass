-- CareCompass: Supabase schema (run in Supabase SQL editor, then TEST the policies; see bottom)
-- Principles: every row owned by auth.uid(); RLS on everything; private data only via reviewed functions.

create extension if not exists pgcrypto;

-- 1. profiles ---------------------------------------------------------------
create table if not exists public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  display_name text check (char_length(display_name) <= 60),
  age smallint check (age between 10 and 100),
  gender text check (char_length(gender) <= 40)
);

-- 2. consent_records (append-only history; withdrawal = new row with granted=false) ----
create table if not exists public.consent_records (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  consent_type text not null check (consent_type in ('assessment','followup')),
  notice_version text not null,
  granted boolean not null,
  recorded_at timestamptz not null default now()
);
create index if not exists consent_user_idx on public.consent_records(user_id, consent_type, recorded_at desc);

-- 3. carecompass_assessments (user-facing history: NO raw scores / responses) ----------
create table if not exists public.carecompass_assessments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  screening_mode text not null default 'full21' check (screening_mode in ('full21','adaptive_experimental')),
  severity_bands jsonb not null,
  summary text,
  scoring_version text not null,
  model_version text
);
create index if not exists assess_user_idx on public.carecompass_assessments(user_id, created_at desc);

-- 4. carecompass_assessment_private (restricted; no direct client policies at all) -------
create table if not exists public.carecompass_assessment_private (
  assessment_id uuid primary key references public.carecompass_assessments(id) on delete cascade,
  raw_scores jsonb not null,
  responses jsonb not null,
  context jsonb,
  model_estimates jsonb
);

-- 5. carecompass_followups ------------------------------------------------------------
create table if not exists public.carecompass_followups (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  assessment_id uuid references public.carecompass_assessments(id) on delete cascade,
  created_at timestamptz not null default now(),
  mood smallint check (mood between 1 and 5),
  sleep smallint check (sleep between 1 and 5),
  energy smallint check (energy between 1 and 5),
  stress smallint check (stress between 1 and 5),
  anxiety smallint check (anxiety between 1 and 5),
  feelings text[] check (feelings is null or cardinality(feelings) <= 12),
  helpfulness text check (helpfulness in ('helpful','somewhat','not_helpful')),
  note text check (char_length(note) <= 500)
);

-- 6. recommendation_catalog -----------------------------------------------------------
create table if not exists public.recommendation_catalog (
  recommendation_id text not null,
  version int not null default 1,
  approved_text text not null,
  applicable_conditions jsonb not null default '{}',
  review_status text not null default 'draft' check (review_status in ('draft','approved','retired')),
  primary key (recommendation_id, version)
);

-- 7. model_registry --------------------------------------------------------------------
create table if not exists public.model_registry (
  model_version text primary key,
  artifact_identifier text not null,
  feature_schema jsonb not null,
  validation_status text not null default 'unvalidated' check (validation_status in ('unvalidated','validated','retired'))
);

-- 8. audit_events (written only through log_event) --------------------------------------
create table if not exists public.audit_events (
  id bigint generated always as identity primary key,
  user_id uuid,
  event_type text not null,
  model_version text,
  meta jsonb,
  created_at timestamptz not null default now()
);

-- 9. account deletion requests ------------------------------------------------------------
create table if not exists public.account_deletion_requests (
  user_id uuid primary key references auth.users(id) on delete cascade,
  requested_at timestamptz not null default now(),
  status text not null default 'pending'
);

-- has_consent must exist BEFORE the policies that use it
create or replace function public.has_consent(p_type text)
returns boolean language sql stable security definer set search_path = public as $$
  select coalesce((select granted from public.consent_records
                   where user_id = auth.uid() and consent_type = p_type
                   order by recorded_at desc limit 1), false);
$$;

-- ROW LEVEL SECURITY ----------------------------------------------------------------------
alter table public.profiles                       enable row level security;
alter table public.consent_records                enable row level security;
alter table public.carecompass_assessments        enable row level security;
alter table public.carecompass_assessment_private enable row level security;
alter table public.carecompass_followups          enable row level security;
alter table public.recommendation_catalog         enable row level security;
alter table public.model_registry                 enable row level security;
alter table public.audit_events                   enable row level security;
alter table public.account_deletion_requests      enable row level security;

-- Start from zero privileges, then grant narrowly.
revoke all on all tables in schema public from anon, authenticated;

-- profiles: owner read/insert/update
grant select, insert, update on public.profiles to authenticated;
drop policy if exists profiles_sel on public.profiles;
create policy profiles_sel on public.profiles for select to authenticated using (user_id = auth.uid());
drop policy if exists profiles_ins on public.profiles;
create policy profiles_ins on public.profiles for insert to authenticated with check (user_id = auth.uid());
drop policy if exists profiles_upd on public.profiles;
create policy profiles_upd on public.profiles for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- consent: owner read + insert only (append-only)
grant select, insert on public.consent_records to authenticated;
drop policy if exists consent_sel on public.consent_records;
create policy consent_sel on public.consent_records for select to authenticated using (user_id = auth.uid());
drop policy if exists consent_ins on public.consent_records;
create policy consent_ins on public.consent_records for insert to authenticated with check (user_id = auth.uid());

-- assessments (history view): owner SELECT only. Writes/deletes go through functions below.
grant select on public.carecompass_assessments to authenticated;
drop policy if exists assess_sel on public.carecompass_assessments;
create policy assess_sel on public.carecompass_assessments for select to authenticated using (user_id = auth.uid());

-- private table: RLS enabled, NO policies, NO grants => unreachable from the API. Functions only.

-- followups: owner read/insert/delete; insert must reference the user's own assessment
grant select, insert, delete on public.carecompass_followups to authenticated;
drop policy if exists fu_sel on public.carecompass_followups;
create policy fu_sel on public.carecompass_followups for select to authenticated using (user_id = auth.uid());
drop policy if exists fu_del on public.carecompass_followups;
create policy fu_del on public.carecompass_followups for delete to authenticated using (user_id = auth.uid());
drop policy if exists fu_ins on public.carecompass_followups;
create policy fu_ins on public.carecompass_followups for insert to authenticated
  with check (user_id = auth.uid()
    and (assessment_id is null or exists (select 1 from public.carecompass_assessments a where a.id = assessment_id and a.user_id = auth.uid()))
    and public.has_consent('followup'));

-- catalog / registry: read-only for signed-in users, approved/validated rows only
grant select on public.recommendation_catalog to authenticated;
drop policy if exists cat_sel on public.recommendation_catalog;
create policy cat_sel on public.recommendation_catalog for select to authenticated using (review_status = 'approved');
grant select on public.model_registry to authenticated;
drop policy if exists reg_sel on public.model_registry;
create policy reg_sel on public.model_registry for select to authenticated using (validation_status = 'validated');

-- deletion requests: owner can see their own request; created via function
grant select on public.account_deletion_requests to authenticated;
drop policy if exists del_sel on public.account_deletion_requests;
create policy del_sel on public.account_deletion_requests for select to authenticated using (user_id = auth.uid());

-- audit_events: no policies, no grants.

-- FUNCTIONS (security definer, validate ownership + inputs) ----------------------------------

create or replace function public.save_assessment(
  p_bands jsonb, p_summary text, p_scoring_version text, p_model_version text,
  p_raw_scores jsonb, p_responses jsonb, p_context jsonb, p_model_estimates jsonb
) returns uuid language plpgsql security definer set search_path = public as $$
declare
  uid uuid := auth.uid();
  new_id uuid;
  band text;
  k text;
  v jsonb;
begin
  if uid is null then raise exception 'not authenticated'; end if;
  if not public.has_consent('assessment') then raise exception 'assessment consent required'; end if;

  -- validate bands
  for k in select jsonb_object_keys(p_bands) loop
    if k not in ('Depression','Anxiety','Stress') then raise exception 'bad subscale'; end if;
    band := p_bands->>k;
    if band not in ('Normal','Mild','Moderate','Severe','Extremely Severe') then raise exception 'bad band'; end if;
  end loop;
  if (select count(*) from jsonb_object_keys(p_bands)) <> 3 then raise exception 'need 3 subscales'; end if;

  -- validate 21 responses in 0..3
  if jsonb_typeof(p_responses) <> 'array' or jsonb_array_length(p_responses) <> 21 then
    raise exception 'need 21 responses';
  end if;
  for v in select * from jsonb_array_elements(p_responses) loop
    if jsonb_typeof(v) <> 'number' or (v #>> '{}')::numeric not in (0,1,2,3) then
      raise exception 'invalid response value';
    end if;
  end loop;

  insert into public.carecompass_assessments(user_id, severity_bands, summary, scoring_version, model_version)
  values (uid, p_bands, left(p_summary, 2000), p_scoring_version, p_model_version)
  returning id into new_id;

  insert into public.carecompass_assessment_private(assessment_id, raw_scores, responses, context, model_estimates)
  values (new_id, p_raw_scores, p_responses, p_context, p_model_estimates);

  return new_id;
end $$;

create or replace function public.update_assessment_context(p_id uuid, p_context jsonb, p_summary text)
returns boolean language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null then raise exception 'not authenticated'; end if;
  update public.carecompass_assessments set summary = left(p_summary, 2000)
   where id = p_id and user_id = auth.uid();
  if not found then return false; end if;
  update public.carecompass_assessment_private set context = p_context where assessment_id = p_id;
  return true;
end $$;

create or replace function public.delete_my_assessment(p_id uuid)
returns boolean language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null then raise exception 'not authenticated'; end if;
  delete from public.carecompass_assessments where id = p_id and user_id = auth.uid();
  return found;  -- private + follow-ups cascade
end $$;

create or replace function public.delete_all_my_assessments()
returns integer language plpgsql security definer set search_path = public as $$
declare n integer;
begin
  if auth.uid() is null then raise exception 'not authenticated'; end if;
  delete from public.carecompass_assessments where user_id = auth.uid();
  get diagnostics n = row_count;
  return n;
end $$;

create or replace function public.request_account_deletion()
returns void language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is null then raise exception 'not authenticated'; end if;
  insert into public.account_deletion_requests(user_id) values (auth.uid()) on conflict do nothing;
end $$;

create or replace function public.log_event(p_type text, p_model_version text default null)
returns void language plpgsql security definer set search_path = public as $$
begin
  if p_type not in ('login','assessment_saved','assessment_deleted','followup_saved',
                    'groq_fallback','safety_pathway_shown','model_disabled','deletion_requested','profile_saved','chat_crisis_shown','plan_generated') then
    raise exception 'unknown event type';
  end if;
  insert into public.audit_events(user_id, event_type, model_version) values (auth.uid(), p_type, p_model_version);
end $$;

create or replace function public.get_my_latest_plan_inputs()
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare r jsonb;
begin
  if auth.uid() is null then raise exception 'not authenticated'; end if;
  select jsonb_build_object(
           'assessment_id', a.id,
           'created_at',    a.created_at,
           'bands',         a.severity_bands,
           'context',       coalesce(p.context, '{}'::jsonb),
           -- true when item 21 was answered 2 or 3 (the same rule the safety engine uses); only the boolean leaves the database
           'urgent',        coalesce(((p.responses ->> 20)::int) >= 2, false))
    into r
    from public.carecompass_assessments a
    join public.carecompass_assessment_private p on p.assessment_id = a.id
   where a.user_id = auth.uid()
   order by a.created_at desc
   limit 1;
  return r;  -- null when the user has no assessment yet
end $$;

revoke execute on function public.get_my_latest_plan_inputs() from public, anon;
grant execute on function public.get_my_latest_plan_inputs() to authenticated;

revoke execute on all functions in schema public from public, anon;
grant execute on function public.has_consent(text), public.save_assessment(jsonb,text,text,text,jsonb,jsonb,jsonb,jsonb),
  public.update_assessment_context(uuid,jsonb,text), public.delete_my_assessment(uuid),
  public.delete_all_my_assessments(), public.request_account_deletion(), public.log_event(text,text),
  public.get_my_latest_plan_inputs()
  to authenticated;

-- TESTING CHECKLIST (do this with two real test users A and B, using each one's access token):
--  1. B cannot select A's assessments, followups, consents (expect 0 rows).
--  2. Neither user can select/insert/update/delete carecompass_assessment_private directly (expect permission denied).
--  3. Neither user can insert into carecompass_assessments directly (expect permission denied).
--  4. save_assessment fails without assessment consent, and with 20 responses or a value of 4.
--  5. delete_my_assessment(A's id) as B returns false.
--  6. Anonymous (anon key, no login) can read nothing and call nothing.
--  7. Follow-up insert fails after followup consent is withdrawn.
