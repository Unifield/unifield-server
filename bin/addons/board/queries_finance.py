# -*- coding: utf-8 -*-

# this is only used to export translations
def _(a):
    return a


queries = [
    {
        'ref': 'ji_unbalanced_booking',
        'title': _('Journal Items that are not balanced in booking currency'),
        'headers': [_('Period'), _('Entry Sequence'), _('Difference')],
        'query': """select p.name period, m.name, sum(l.credit_currency-l.debit_currency) difference
from account_move_line l,
account_period p,
account_move m,
account_journal j
where
m.period_id = p.id and
l.move_id = m.id and
m.state='posted' and
m.journal_id = j.id and
j.type != 'system'
%s
group by p.name, m.name, l.move_id, p.date_start
having abs(sum(l.credit_currency-l.debit_currency)) > 0.00001
order by p.date_start, m.name;
"""
    },
    {
        'ref': 'ji_unbalanced_fctal',
        'title': _('Journal Items that are not balanced in functional currency'),
        'headers': [_('Period'), _('Entry Sequence'), _('Difference')],
        'query': """select p.name period, m.name, sum(l.credit-l.debit) difference
from account_move_line l,
account_period p,
account_move m,
account_journal j
where
m.period_id = p.id and
l.move_id = m.id and
m.state='posted' and
m.journal_id = j.id and
j.type != 'system'
%s
group by p.name, m.name, l.move_id, p.date_start
having abs(sum(l.credit-l.debit)) > 0.00001
order by p.date_start, m.name;"""
    },
    {
        'ref': 'mismatch_ji_aji_booking',
        'title': _('P&L Journal Items vs Analytic Journal Items mismatch in booking currency (except FXA and REV)'),
        'headers': [_('Period'), _('Entry Sequence'), _('Account Code'), _('JI Book. Amount'), _('AJI Book. Amount'), _('Difference')],
        'query': """SELECT
account_period.name,
m.name,
account_account.code,
avg(l.credit_currency - l.debit_currency) JI,
sum(COALESCE(account_analytic_line.amount_currency, 0)) AJI,
abs(abs(avg(l.debit_currency - l.credit_currency)) - abs(sum(COALESCE(account_analytic_line.amount_currency, 0)))) difference
FROM
account_move_line l
JOIN account_move m ON m.id = l.move_id
JOIN account_account ON account_account.id = l.account_id
JOIN account_journal ON account_journal.id = m.journal_id
JOIN account_period ON m.period_id = account_period.id
LEFT JOIN account_analytic_line on account_analytic_line.move_id = l.id
LEFT JOIN account_analytic_account ON account_analytic_line.account_id = account_analytic_account.id
WHERE
account_journal.type not in ('system', 'revaluation', 'cur_adj') AND
account_account.is_analytic_addicted = 't' AND
COALESCE(account_analytic_account.category, '') not in ('FREE1', 'FREE2')
%s
GROUP BY account_period.name, m.name, l.id, account_period.date_start, account_account.code
HAVING abs(abs(avg(l.debit_currency - l.credit_currency)) - abs(sum(COALESCE(account_analytic_line.amount_currency, 0)))) > 0.00001
ORDER BY account_period.date_start, m.name;"""
    },
    {
        'ref': 'mismatch_ji_aji_fctal',
        'title': _('P&L Journal Items vs Analytic Journal Items mismatch in functional currency (FXA and REV only)'),
        'headers': [_('Period'), _('Entry Sequence'), _('Account Code'), _('JI Func. Amount'), _('AJI Func. Amount'), _('Difference')],
        'query': """SELECT
account_period.name,
m.name,
account_account.code,
avg(l.credit - l.debit) JI,
sum(COALESCE(account_analytic_line.amount, 0)) AJI,
abs(avg(l.credit - l.debit) - sum(COALESCE(account_analytic_line.amount, 0))) difference
FROM
account_move_line l
JOIN account_move m ON m.id = l.move_id
JOIN account_account ON account_account.id = l.account_id
JOIN account_journal ON m.journal_id = account_journal.id
JOIN account_period ON account_period.id = m.period_id
LEFT JOIN account_analytic_line ON account_analytic_line.move_id = l.id
LEFT JOIN account_analytic_account ON account_analytic_line.account_id = account_analytic_account.id
WHERE
account_journal.type in ('revaluation', 'cur_adj') AND
account_account.is_analytic_addicted = 't' AND
COALESCE(account_analytic_account.category, '') not in ('FREE1', 'FREE2')
%s
GROUP BY account_period.name, m.name, l.id, account_period.date_start, account_account.code
HAVING abs(avg(l.credit - l.debit) - sum(COALESCE(account_analytic_line.amount, 0))) > 0.00001
order by account_period.date_start, m.name;"""
    },
    {
        'ref': 'unbalanced_rec_fctal',
        'title': _('Unbalanced reconciliations in functional currency'),
        'headers': [_('Reconcile number'), _('Reconcile date'), _('Difference')],
        'query': """SELECT rec.name, 'rec_date', sum(l.credit-l.debit)
from account_move_line l, account_move_reconcile rec, msf_instance inst, res_company c
where l.reconcile_id=rec.id and c.instance_id = inst.id and (rec.is_multi_instance= 'f' or inst.level!='project')
%s
group by rec.id, rec.name
having(abs(sum(l.credit-l.debit)) > 0.0001)
order by rec.name;
"""
    },
    {
        'ref': 'unbalanced_rec_booking',
        'title': _('Unbalanced reconciliations in booking currency'),
        'headers': [_('Reconcile number'), _('Reconcile date'), _('Difference')],
        'query': """SELECT rec.name, 'rec_date', sum(l.credit_currency-l.debit_currency)
from account_move_line l, account_move_reconcile rec, msf_instance inst, res_company c
where l.reconcile_id=rec.id and c.instance_id = inst.id and (rec.is_multi_instance= 'f' or inst.level!='project')
%s
group by rec.id, rec.name
having(abs(sum(l.credit_currency-l.debit_currency)) > 0.0001 and count(distinct(l.currency_id))=1)
order by rec.name;
"""
    },
    {
        'ref': 'not_runs_entries',
        'title': _('Not runs entries'),
        'headers': [_('Object/model'), _('Source instance'), _('xml.id'), _('Sync date'), _('Execution date')],
        'query': """SELECT s.model, s.source, s.sdref, s.create_date, s.execution_date
from sync_client_update_received s
where s.run=FALSE AND
s.model in ('account.bank.statement.line', 'account.move','account.move.line','account.analytic.line')
%s
order by s.model;"""
    },
    {
        'ref': 'aji_duplicated',
        'title': _('Analytic Journal Items possibly duplicated'),
        'headers': [_('Analytic Journal Item Name'), _('Instance Name'), _('Period'), _('Ref')],
        'query': """SELECT
    sub.name,
    STRING_AGG(DISTINCT sub.instance_name, ', ' ORDER BY sub.instance_name) AS instance_details,
    STRING_AGG(DISTINCT sub.period_name, ', ' ORDER BY sub.period_name) AS periods,
    STRING_AGG(DISTINCT sub.ref, ', ' ORDER BY sub.ref) AS refs
FROM (
    SELECT
        aal.name,
        mi.name AS instance_name,
        ap.name AS period_name,
        aal.ref
    FROM account_analytic_line aal
    JOIN msf_instance mi
        ON aal.instance_id = mi.id
    LEFT JOIN account_period ap
        ON aal.real_period_id = ap.id
    %s
    WHERE aal.name ~ '^(COR[0-9]|REV)'
      AND (
            aal.last_corrected_id IN (
                SELECT last_corrected_id
                FROM account_analytic_line
                WHERE last_corrected_id IS NOT NULL
                GROUP BY last_corrected_id
                HAVING COUNT(*) > 1
            )
         OR
            aal.reversal_origin IN (
                SELECT reversal_origin
                FROM account_analytic_line
                WHERE reversal_origin IS NOT NULL
                GROUP BY reversal_origin
                HAVING COUNT(*) > 1
            )
      )
) sub
GROUP BY sub.name
HAVING COUNT(DISTINCT sub.instance_name) > 1
ORDER BY sub.name;"""
    },
]
