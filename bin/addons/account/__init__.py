# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

# list of tuples ('code', 'type') of the journals imported by default at new instance creation
DEFAULT_JOURNALS = [
    ('ACC', 'accrual'),
    ('HQ', 'hq'),
    ('HR', 'hr'),
    ('FXA', 'cur_adj'),
    ('OD', 'correction'),
    ('PUR', 'purchase'),
    ('PUF', 'purchase_refund'),
    ('SAL', 'sale'),
    ('SAR', 'sale_refund'),
    ('STO', 'stock'),
    ('IKD', 'inkind'),
    ('INT', 'intermission'),
    ('ODX', 'extra'),
    ('REV', 'revaluation'),
    ('MIG', 'migration'),
    ('ODM', 'correction_manual'),
    ('ODHQ', 'correction_hq'),
    ('ISI', 'purchase'),
    ('EOY', 'system'),
    ('IB', 'system')
]

from . import account
from . import installer
from . import project
from . import partner
from . import invoice
from . import account_bank_statement
from . import account_cash_statement
from . import account_move_line
from . import account_analytic_line
from . import wizard
from . import report
from . import product
from . import sequence
from . import company
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
