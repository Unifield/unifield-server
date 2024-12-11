-- SET client_encoding TO 'UTF8';
-- select * from actuals where period >= '2024-08-01' and mission_code='HT_COOR';
-- create index account_target_costcenter_is_target_index on account_target_costcenter(is_target);
-- select * from actuals_eng where period>='2024-01-01';
-- grant select on actuals_eng to boomi;
-- create index account_analytic_journal_type_index on account_analytic_journal(type);
drop view actuals_eng;
create or replace view actuals_eng as ( select
    al.id as analytic_line_id,
    i.code as instance_code,
    to_char(al.date, 'YYYY-MM-01') as period,
    al.entry_sequence,
    al.document_date,
    al.date as posting_date,
    j.code as journal_code,
    round(al.amount_currency, 2) as book_amount,
    c.name as book_currency,
    round(al.amount, 2) as func_amount,
    cur_table.currency_table_name as currency_table,
    cur_table.rate as currency_table_rate,
    round(al.amount_currency / cur_table.rate, 2) as func_amount_table_rate,
    al.name as description,
    al.ref as reference,
    cost_center.code as cost_center_code,
    dest.code as destination_code,
    fp.code as funding_code,
    a.code as account_code,
    al.partner_txt as partner_txt,
    case when i.level = 'section' then coalesce(parent.code, target_instance.code) else coalesce(parent.code, i.code) end as mission_code,
    country.mapping_value as country_code
 from
    account_analytic_line al
    inner join account_analytic_journal j on j.id = al.journal_id and j.type = 'engagement'
    inner join account_account a on a.id = al.general_account_id
    inner join account_analytic_account dest on dest.id = al.destination_id
    inner join account_analytic_account cost_center on cost_center.id = al.cost_center_id
    inner join msf_instance i on i.id = al.instance_id


    inner join account_analytic_account fp on fp.id = al.account_id
    inner join res_currency c on c.id = al.currency_id
    left join lateral (
        select cur.name as currency_name, cur_table.name as currency_table_name, rate.rate from
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
    left join account_target_costcenter target_cc on target_cc.cost_center_id = al.cost_center_id and target_cc.is_target='t'
    left join msf_instance target_instance on target_instance.id = target_cc.instance_id
    left join msf_instance parent on i.level = 'project' and parent.id = i.parent_id or i.level = 'section' and target_instance.level = 'project' and parent.id = target_instance.parent_id
    left join country_export_mapping country on country.instance_id = case when i.level = 'section' then coalesce(parent.id, target_instance.id) else coalesce(parent.id, i.id) end
 order by
     al.id
);
