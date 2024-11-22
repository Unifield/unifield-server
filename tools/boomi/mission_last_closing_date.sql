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
grant select on mission_last_closing_date to boomi;

drop view country_last_closing_date;
create or replace view country_last_closing_date as (
  select
      distinct on (acc.code)
      acc.code as country_code,
      p.date_start as last_period_closed,
      max(st.write_date::timestamp(0)) as last_modification_date,
      array_to_string(array_agg(i.code order by i.id), ',') as missions,
      array_to_string(array_agg(i.state order by i.id), ',') as mission_status
  from
    account_analytic_account acc
    inner join account_target_costcenter target on target.cost_center_id = acc.id
    inner join msf_instance i on i.id = target.instance_id
    left join account_period_state st on st.instance_id = i.id
    left join account_period p on p.id = st.period_id
  where
    acc.category = 'OC' and
    acc.type = 'view' and
    length(acc.code) = 3 and
    i.level='coordo' and
    st.state in ('mission-closed', 'done') and
    p.number not in (0, 16)
 group by
    acc.code, p.id
 having
    count(i.id) = count(st.id)
 order by
    acc.code, p.date_start desc, p.number desc
);
grant select on country_last_closing_date to boomi;


