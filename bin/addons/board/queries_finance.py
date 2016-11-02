# -*- coding: utf-8 -*-

# this is only used to export translations
def _(a):
    return a


queries = [
    {
        'title': _('Journal Items that are not balanced in booking currency'),
        'headers': [_('Period'), _('Entry Sequence'), _('Difference')],
        'query': """select p.name period, m.name, sum(l.credit_currency-l.debit_currency) difference from account_move_line l,
account_period p,
account_move m,
account_journal j
where
m.period_id = p.id and
l.move_id = m.id and
l.state='valid' and
m.journal_id = j.id and
j.type != 'system'
group by p.name, m.name, l.move_id, p.date_start
having abs(sum(l.credit_currency-l.debit_currency)) > 0.00001
order by p.date_start, m.name
"""
    },
    {
        'title': _('Journal Items that are not balanced in functional currency'),
        'headers': [_('Period'), _('Entry Sequence'), _('Difference')],
        'query': """select p.name period, m.name, sum(l.credit-l.debit) difference from account_move_line l,
account_period p,
account_move m,
account_journal j
where
m.period_id = p.id and
l.move_id = m.id and
l.state='valid' and
m.journal_id = j.id and
j.type != 'system'
group by p.name, m.name, l.move_id, p.date_start
having abs(sum(l.credit-l.debit)) > 0.00001
order by p.date_start, m.name"""
    },
    {
        'title': _('P&L Journal Items vs Analytic Journal Items mismatch in booking currency (except FXA and REV)'),
        'headers': [_('Period'), _('Entry Sequence'), _('JI Book. Amount'), _('AJI Book. Amount'), _('Difference')],
        'query': """SELECT
account_period.name,
account_move.name,
avg(account_move_line.debit_currency-account_move_line.credit_currency) JI,
sum(account_analytic_line.amount_currency) AJI,
abs(abs(avg(account_move_line.debit_currency-account_move_line.credit_currency)) - abs(sum(account_analytic_line.amount_currency))) difference
FROM
account_move,
account_move_line,
account_account,
account_analytic_line,
account_journal,
account_period
WHERE
account_analytic_line.move_id = account_move_line.id and
account_move_line.move_id = account_move.id AND
account_move_line.account_id = account_account.id AND
account_journal.id = account_move.journal_id AND
account_move.period_id = account_period.id AND
account_journal.type not in ('system', 'revaluation', 'cur_adj') AND
account_account.code in (
SELECT
account_account.code
FROM
account_account,
account_account_type
WHERE
account_account.user_type = account_account_type.id and
account_account_type.code in ('income', 'expense')
)
GROUP BY account_period.name, account_move.name, account_move_line.id, account_period.date_start
HAVING abs(abs(avg(account_move_line.debit_currency-account_move_line.credit_currency)) - abs(sum(account_analytic_line.amount_currency))) > 0.00001
ORDER BY account_period.date_start, account_move.name"""
    },
    {
        'title': _('P&L Journal Items vs Analytic Journal Items mismatch in functional currency (FXA and REV only)'),
        'headers': [_('Period'), _('Entry Sequence'), _('JI Func. Amount'), _('AJI Func. Amount'), _('Difference')],
        'query': """SELECT
account_period.name,
account_move.name,
avg(account_move_line.credit-account_move_line.debit) JI,
sum(account_analytic_line.amount) AJI,
abs(avg(account_move_line.credit-account_move_line.debit) - sum(account_analytic_line.amount)) difference
FROM
account_move,
account_move_line,
account_account,
account_analytic_line,
account_journal,
account_period
WHERE
account_analytic_line.move_id = account_move_line.id and
account_move_line.move_id = account_move.id AND
account_move_line.account_id = account_account.id AND
account_journal.id = account_move.journal_id AND
account_move.period_id = account_period.id AND
account_journal.type in ('revaluation', 'cur_adj') AND
account_account.code in (
SELECT
account_account.code
FROM
account_account,
account_account_type
WHERE
account_account.user_type = account_account_type.id and
account_account_type.code in ('income', 'expense')
)
GROUP BY account_period.name, account_move.name, account_move_line.id, account_period.date_start
HAVING abs(avg(account_move_line.credit-account_move_line.debit) - sum(account_analytic_line.amount)) > 0.00001
order by account_period.date_start, account_move.name"""
    },
    {
        'title': _('Unbalanced reconciliations in functional currency'),
        'headers': [_('Reconcile number'), _('Difference')],
        'query': """SELECT rec.name, sum(l.credit-l.debit)
from account_move_line l, account_move_reconcile rec
where l.reconcile_id=rec.id
group by rec.id, rec.name
having(abs(sum(l.credit-l.debit)) > 0.0001)
order by rec.name
"""
    },
    {
        'title': _('Unbalanced reconciliations in booking currency'),
        'headers': [_('Reconcile number'), _('Difference')],
        'query': """SELECT rec.name, sum(l.credit_currency-l.debit_currency)
from account_move_line l, account_move_reconcile rec
where l.reconcile_id=rec.id
group by rec.id, rec.name
having(abs(sum(l.credit_currency-l.debit_currency)) > 0.0001 and count(l.currency_id)=1)
order by rec.name
"""
    },
]
