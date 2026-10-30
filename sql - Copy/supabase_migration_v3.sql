-- CareCompass migration v3 (run ONCE in the Supabase SQL Editor, after v2; safe to re-run)
-- Adds the reviewed function that lets the "My wellbeing plan" screen read ONLY the latest assessment's
-- bands + personalisation answers + an urgent flag. Raw responses and scores are never returned.

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

create or replace function public.log_event(p_type text, p_model_version text default null)
returns void language plpgsql security definer set search_path = public as $$
begin
  if p_type not in ('login','assessment_saved','assessment_deleted','followup_saved','groq_fallback',
                    'safety_pathway_shown','model_disabled','deletion_requested','profile_saved','chat_crisis_shown','plan_generated') then
    raise exception 'unknown event type';
  end if;
  insert into public.audit_events(user_id, event_type, model_version) values (auth.uid(), p_type, p_model_version);
end $$;
