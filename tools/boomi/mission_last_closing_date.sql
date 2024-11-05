drop view mission_last_closing_date;

-- create user boomi login password 'XXXX';
-- grant select on mission_last_closing_date to boomi;
create or replace view mission_last_closing_date as (
  select
      distinct on (i.code) i.code as mission,
      i.state as mission_state,
      to_char(date_start, 'YYYY-MM') as last_period_closed,
      st.write_date::timestamp(0) as last_modification_date
  from
    msf_instance i
    left join account_period_state st on st.instance_id = i.id
    left join account_period p on p.id = st.period_id
  where
    i.level='coordo' and
    st.state in ('mission-closed', 'done') and
    p.number not in (0, 16)
 order by
    i.code, date_start desc, p.number, i.id
);

