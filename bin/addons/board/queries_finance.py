# -*- coding: utf-8 -*-

queries = [
    {
        'title': "JI entries in booking currency that do not add up",
        'headers': ['Period', 'JI', 'Difference'],
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
group by p.name, m.name, l.move_id
having abs(sum(l.credit_currency-l.debit_currency)) > 0.00001
order by m.name
"""
    },

    {
        'title': "JI entries in functional currency that do not add up",
        'headers': ['Period', 'JI', 'Difference'],
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
group by p.name, m.name, l.move_id
having abs(sum(l.credit-l.debit)) > 0.00001
order by m.name"""
    },
    {
        'title': "AJI/JI mismatch in functional currency",
        'headers': ['Period', 'JI', 'JI Fct. Amount', 'AJI Fct. Amount', 'Difference'],
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
GROUP BY account_period.name, account_move.name, account_move_line.id
HAVING abs(avg(account_move_line.credit-account_move_line.debit) - sum(account_analytic_line.amount)) > 0.00001
order by difference desc, account_move.name"""},

    {
        'title': "AJI/JI mismatch in booking currency",
        'headers': ['Period', 'JI', 'JI Book. Amount', 'AJI Book. Amount', 'Difference'],
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
GROUP BY account_period.name, account_move.name, account_move_line.id
HAVING abs(abs(avg(account_move_line.debit_currency-account_move_line.credit_currency)) - abs(sum(account_analytic_line.amount_currency))) > 0.00001
ORDER BY difference desc, account_move.name"""
    }
]
