-- CareCompass migration v4 (run ONCE in Supabase SQL Editor, after v2 & v3; safe to re-run)
-- Adds a read-only function for the login pattern-mining + voice notification feature.
-- Does NOT change any existing table, policy, or function from schema.sql / v2 / v3.

create or replace function public.get_my_wellbeing_summary()
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare
  v_assessments jsonb;
  v_checkins jsonb;
begin
  if auth.uid() is null then raise exception 'not authenticated'; end if;

  -- Last 3 assessments for this user (bands + context + urgent boolean only).
  -- Raw responses and raw scores stay in carecompass_assessment_private and never leave the DB.
  select coalesce(jsonb_agg(jsonb_build_object(
           'id', a.id,
           'created_at', a.created_at,
           'bands', a.severity_bands,
           'context', coalesce(p.context, '{}'::jsonb),
           'urgent', coalesce(((p.responses ->> 20)::int) >= 2, false)
         ) order by a.created_at desc), '[]'::jsonb)
    into v_assessments
    from (
      select * from public.carecompass_assessments
       where user_id = auth.uid()
       order by created_at desc
       limit 3
    ) a
    left join public.carecompass_assessment_private p on p.assessment_id = a.id;

  -- Last 14 check-ins for this user.
  select coalesce(jsonb_agg(jsonb_build_object(
           'created_at', f.created_at,
           'mood', f.mood, 'stress', f.stress, 'anxiety', f.anxiety,
           'energy', f.energy, 'sleep', f.sleep,
           'feelings', f.feelings, 'note', f.note
         ) order by f.created_at desc), '[]'::jsonb)
    into v_checkins
    from (
      select * from public.carecompass_followups
       where user_id = auth.uid()
       order by created_at desc
       limit 14
    ) f;

  return jsonb_build_object('assessments', v_assessments, 'checkins', v_checkins);
end $$;

revoke execute on function public.get_my_wellbeing_summary() from public, anon;
grant execute on function public.get_my_wellbeing_summary() to authenticated;