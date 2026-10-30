-- CareCompass migration v2 (run ONCE in Supabase SQL Editor on your existing project; safe to re-run)
-- Adds: profile name/age/gender, "how I feel right now" check-ins, extra audit event types.

alter table public.profiles add column if not exists age smallint check (age between 10 and 100);
alter table public.profiles add column if not exists gender text check (char_length(gender) <= 40);

-- Check-ins no longer have to belong to an assessment
alter table public.carecompass_followups alter column assessment_id drop not null;
alter table public.carecompass_followups add column if not exists stress smallint check (stress between 1 and 5);
alter table public.carecompass_followups add column if not exists anxiety smallint check (anxiety between 1 and 5);
alter table public.carecompass_followups add column if not exists feelings text[]
  check (feelings is null or cardinality(feelings) <= 12);

drop policy if exists fu_ins on public.carecompass_followups;
create policy fu_ins on public.carecompass_followups for insert to authenticated
  with check (user_id = auth.uid()
    and (assessment_id is null
         or exists (select 1 from public.carecompass_assessments a where a.id = assessment_id and a.user_id = auth.uid()))
    and public.has_consent('followup'));

create or replace function public.log_event(p_type text, p_model_version text default null)
returns void language plpgsql security definer set search_path = public as $$
begin
  if p_type not in ('login','assessment_saved','assessment_deleted','followup_saved','groq_fallback',
                    'safety_pathway_shown','model_disabled','deletion_requested','profile_saved','chat_crisis_shown') then
    raise exception 'unknown event type';
  end if;
  insert into public.audit_events(user_id, event_type, model_version) values (auth.uid(), p_type, p_model_version);
end $$;
