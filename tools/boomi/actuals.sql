-- SET client_encoding TO 'UTF8';
-- select * from actuals where period >= '2024-08-01' and mission_code='HT_COOR';
-- grant select on actuals to boomi;

-- create index country_export_mapping_instance_id_index on country_export_mapping(instance_id);
-- drop view actuals_full;
drop view actuals;
create or replace view actuals as ( select
    al.id as analytic_line_id,
    i.code as instance_code,
    p.date_start as period,
    al.entry_sequence,
    al.document_date,
    al.date as posting_date,
    j.code as journal_code,
    round(al.amount_currency, 2) as book_amount,
    c.name as book_currency,
    round(al.amount, 2) as func_amount,
    cur_table.currency_table_name as currency_table,
    cur_table.rate as wefin_rate,
    round(al.amount_currency / cur_table.rate, 2) as wefin_amount,
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
        select cur.name as currency_name, cur_table.name as currency_table_name, rate.rate from
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
  where
    p.number not in (0, 16)
    and j.type not in ('cur_adj')
    and i.level in ('coordo', 'project')
    order by
    al.id
);
grant select on actuals to boomi;
