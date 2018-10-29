# -*- coding: utf-8 -*-

# this is only used to export translations
def _(a):
    return a


queries = [
    {
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
order by p.date_start, m.name
"""
    },
    {
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
order by p.date_start, m.name"""
    },
    {
        'title': _('P&L Journal Items vs Analytic Journal Items mismatch in booking currency (except FXA and REV)'),
        'headers': [_('Period'), _('Entry Sequence'), _('Account Code'), _('JI Book. Amount'), _('AJI Book. Amount'), _('Difference')],
        'query': """SELECT
account_period.name,
account_move.name,
account_account.code,
avg(l.credit_currency - l.debit_currency) JI,
sum(COALESCE(account_analytic_line.amount_currency, 0)) AJI,
abs(abs(avg(l.debit_currency - l.credit_currency)) - abs(sum(COALESCE(account_analytic_line.amount_currency, 0)))) difference
FROM
account_move_line l
JOIN account_move ON account_move.id = l.move_id
JOIN account_account ON account_account.id = l.account_id
JOIN account_journal ON account_journal.id = account_move.journal_id
JOIN account_period ON account_move.period_id = account_period.id
LEFT JOIN account_analytic_line on account_analytic_line.move_id = l.id
LEFT JOIN account_analytic_account ON account_analytic_line.account_id = account_analytic_account.id
WHERE
account_journal.type not in ('system', 'revaluation', 'cur_adj') AND
account_account.is_analytic_addicted = 't' AND
account_analytic_account.category not in ('FREE1', 'FREE2')
%s
GROUP BY account_period.name, account_move.name, l.id, account_period.date_start, account_account.code
HAVING abs(abs(avg(l.debit_currency - l.credit_currency)) - abs(sum(COALESCE(account_analytic_line.amount_currency, 0)))) > 0.00001
ORDER BY account_period.date_start, account_move.name"""
    },
    {
        'title': _('P&L Journal Items vs Analytic Journal Items mismatch in functional currency (FXA and REV only)'),
        'headers': [_('Period'), _('Entry Sequence'), _('Account Code'), _('JI Func. Amount'), _('AJI Func. Amount'), _('Difference')],
        'query': """SELECT
account_period.name,
account_move.name,
account_account.code,
avg(l.credit - l.debit) JI,
sum(COALESCE(account_analytic_line.amount, 0)) AJI,
abs(avg(l.credit - l.debit) - sum(COALESCE(account_analytic_line.amount, 0))) difference
FROM
account_move_line l
JOIN account_move ON account_move.id = l.move_id
JOIN account_account ON account_account.id = l.account_id
JOIN account_journal ON account_move.journal_id = account_journal.id
JOIN account_period ON account_period.id = account_move.period_id
LEFT JOIN account_analytic_line ON account_analytic_line.move_id = l.id
LEFT JOIN account_analytic_account ON account_analytic_line.account_id = account_analytic_account.id
WHERE
account_journal.type in ('revaluation', 'cur_adj') AND
account_account.is_analytic_addicted = 't' AND
account_analytic_account.category not in ('FREE1', 'FREE2')
%s
GROUP BY account_period.name, account_move.name, l.id, account_period.date_start, account_account.code
HAVING abs(avg(l.credit - l.debit) - sum(COALESCE(account_analytic_line.amount, 0))) > 0.00001
order by account_period.date_start, account_move.name"""
    },
    {
        'title': _('Unbalanced reconciliations in functional currency'),
        'headers': [_('Reconcile number'), _('Reconcile date'), _('Difference')],
        'query': """SELECT rec.name, l.reconcile_date, sum(l.credit-l.debit)
from account_move_line l, account_move_reconcile rec
where l.reconcile_id=rec.id
%s
group by rec.id, rec.name, l.reconcile_date
having(abs(sum(l.credit-l.debit)) > 0.0001)
order by rec.name
"""
    },
    {
        'title': _('Unbalanced reconciliations in booking currency'),
        'headers': [_('Reconcile number'), _('Reconcile date'), _('Difference')],
        'query': """SELECT rec.name, l.reconcile_date, sum(l.credit_currency-l.debit_currency)
from account_move_line l, account_move_reconcile rec
where l.reconcile_id=rec.id
%s
group by rec.id, rec.name, l.reconcile_date
having(abs(sum(l.credit_currency-l.debit_currency)) > 0.0001 and count(distinct(l.currency_id))=1)
order by rec.name
"""
    },
]
