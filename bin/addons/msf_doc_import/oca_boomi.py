# encoding: utf-8
from osv import osv

class res_currency(osv.osv):
    _name = 'res.currency'
    _inherit = 'res.currency'

    def _auto_init(self, cr, context=None):
        super(res_currency, self)._auto_init(cr, context)
        # sql view are dropped in addons/base/res/res_currency.py before loading other objects
        # and created here at the end of modules init

        cr.execute('''
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
)
''')

        cr.execute('''
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
)
''')

        cr.execute('''
create or replace view actuals as ( select
    al.id as analytic_line_id,
    i.code as instance_code,
    p.date_start as period,
    al.entry_sequence,
    al.document_date,
    al.date as posting_date,
    j.code as journal_code,
    CASE WHEN left(dest.code, 1) = 'I' then -1  else 1 end * round(al.amount_currency, 2) as book_amount,
    c.name as book_currency,
    CASE WHEN left(dest.code, 1) = 'I' then -1  else 1 end * round(al.amount, 2) as func_amount,
    coalesce(cur_table.currency_table_name, 'UF rate') as currency_table,
    coalesce(cur_table.rate, real_fx_rate.rate) as wefin_rate,
    coalesce(cur_table.fx_date, real_fx_rate.fx_date) as fx_from_date,
    CASE WHEN left(dest.code, 1) = 'I' then -1  else 1 end * case when cur_table.rate is not null then round(al.amount_currency / cur_table.rate, 2) else round(al.amount, 2) end as wefin_amount,
    al.name as description,
    al.ref as reference,
    cost_center.code as cost_center_code,
    case dest.code  when 'OPS' then 'TEMP00-OPS' else dest.code END as destination_code,
    fp.code as funding_code,
    a.code as account_code,
    coalesce(tr.value, a.name) as account_name,
    hr.identification_id as emplid,
    case hr.employee_type when 'local' then 'LRS' when 'ex' then 'IMS' else NULL end as employee_type,
    al.partner_txt as partner_txt,
    aml.partner_id as partner_id,
    aml.id as account_move_line_id,
    coalesce(parent.code, i.code) as mission_code,
    left(cost_center.code, 3) as country_code,
    'f'::boolean as  isCommitment
 from
    account_analytic_line al
    inner join account_period p on p.id = al.real_period_id
    inner join account_analytic_journal j on j.id = al.journal_id
    inner join msf_instance i on i.id = al.instance_id
    left outer join msf_instance parent on parent.id = i.parent_id and i.level = 'project'
    left join country_export_mapping country on country.instance_id = coalesce(parent.id, i.id)
    inner join account_move_line aml on aml.id = al.move_id
    inner join account_move am on am.id = aml.move_id
    inner join account_account a on a.id = al.general_account_id
    left join ir_translation tr on tr.name='account.account,name' and tr.lang='en_MF' and tr.type='model' and tr.res_id=a.id
    inner join account_analytic_account dest on dest.id = al.destination_id
    inner join account_analytic_account cost_center on cost_center.id = al.cost_center_id
    inner join account_analytic_account fp on fp.id = al.account_id
    inner join res_currency c on c.id = al.currency_id
    left outer join hr_employee hr on hr.id = aml.employee_id
    left join lateral (
        select cur.name as currency_name, cur_table.name as currency_table_name, rate.rate, rate.name as fx_date from
            res_currency_table cur_table, res_currency cur, res_currency_rate rate
        where
            rate.name <= al.source_date and
            cur.reference_currency_id = al.currency_id and
            rate.currency_id = cur.id and
            cur.currency_table_id = cur_table.id and
            cur_table.state = 'valid' and
            cur_table.code like 'WEFIN%'
            order by rate.name desc, cur_table.id desc
        limit 1
    ) cur_table on true
    left join lateral (
        select rate.rate, rate.name as fx_date from
            res_currency_rate rate
        where
            rate.name <= al.source_date and
            rate.currency_id = al.currency_id
            order by rate.name desc, id desc
        limit 1
    ) real_fx_rate on true
  where
    p.number not in (0, 16)
    and j.type not in ('cur_adj', 'revaluation')
    and i.level in ('coordo', 'project')
    order by
    al.id
)
''')

        cr.execute('''
create or replace view actuals_eng as ( select
    al.id as analytic_line_id,
    i.code as instance_code,
    to_char(al.date, 'YYYY-MM-01')::date as period,
    al.entry_sequence,
    al.document_date,
    al.date as posting_date,
    j.code as journal_code,
    round(al.amount_currency, 2) as book_amount,
    c.name as book_currency,
    round(al.amount, 2) as func_amount,
    coalesce(cur_table.currency_table_name, 'UF rate') as currency_table,
    coalesce(cur_table.rate, real_fx_rate.rate) as wefin_rate,
    coalesce(cur_table.fx_date, real_fx_rate.fx_date) as fx_from_date,
    case when cur_table.rate is not null then round(al.amount_currency / cur_table.rate, 2) else round(al.amount, 2) end as wefin_amount,
    al.name as description,
    al.ref as reference,
    cost_center.code as cost_center_code,
    case dest.code when 'OPS' then 'TEMP00-OPS' else dest.code end as destination_code,
    fp.code as funding_code,
    a.code as account_code,
    coalesce(tr.value, a.name) as account_name,
    NULL::varchar as emplid,
    NULL::varchar as employee_type,
    al.partner_txt as partner_txt,
    NULL::integer as partner_id,
    NULL::integer as account_move_line_id,
    case when i.level = 'section' then coalesce(parent.code, target_instance.code) else coalesce(parent.code, i.code) end as mission_code,
    left(cost_center.code, 3) as country_code,
    't'::boolean as  isCommitment
 from
    account_analytic_line al
    inner join account_analytic_journal j on j.id = al.journal_id and j.type = 'engagement'
    inner join account_account a on a.id = al.general_account_id
    left join ir_translation tr on tr.name='account.account,name' and tr.lang='en_MF' and tr.type='model' and tr.res_id=a.id
    inner join account_analytic_account dest on dest.id = al.destination_id
    inner join account_analytic_account cost_center on cost_center.id = al.cost_center_id
    inner join msf_instance i on i.id = al.instance_id


    inner join account_analytic_account fp on fp.id = al.account_id
    inner join res_currency c on c.id = al.currency_id
    left join lateral (
        select cur.name as currency_name, cur_table.name as currency_table_name, rate.rate, rate.name as fx_date from
            res_currency_table cur_table, res_currency cur, res_currency_rate rate
        where
            rate.name <= coalesce(al.source_date, al.date) and
            cur.reference_currency_id = al.currency_id and
            rate.currency_id = cur.id and
            cur.currency_table_id = cur_table.id and
            cur_table.state = 'valid' and
            cur_table.code like 'WEFIN%'
            order by rate.name desc, cur_table.id desc
        limit 1
    ) cur_table on true
    left join lateral (
        select rate.rate, rate.name as fx_date from
            res_currency_rate rate
        where
            rate.name <= coalesce(al.source_date, al.date) and
            rate.currency_id = al.currency_id
            order by rate.name desc, id desc
        limit 1
    ) real_fx_rate on true
    left join account_target_costcenter target_cc on target_cc.cost_center_id = al.cost_center_id and target_cc.is_target='t'
    left join msf_instance target_instance on target_instance.id = target_cc.instance_id
    left join msf_instance parent on i.level = 'project' and parent.id = i.parent_id or i.level = 'section' and target_instance.level = 'project' and parent.id = target_instance.parent_id
    left join country_export_mapping country on country.instance_id = case when i.level = 'section' then coalesce(parent.id, target_instance.id) else coalesce(parent.id, i.id) end
 order by
     al.id
)
''')

        cr.execute('''
create or replace view actuals_full as (
    select * from actuals
    UNION
    select * from actuals_eng
)
''')

        boomi_user = 'boomi'
        if cr.sql_user_exists(boomi_user):
            for boomi_view in ['mission_last_closing_date', 'country_last_closing_date', 'actuals_full', 'actuals', 'actuals_eng']:
                cr.execute("grant select on "+boomi_view+" to "+boomi_user) # not_a_user_entry

res_currency()
