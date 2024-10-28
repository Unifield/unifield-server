# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
from tools.translate import _

GENERIC_MESSAGE = _("""
        IMPORTANT : The file should be in xlsx format.
        The columns should be in this values: """)
ACCRUAL_LINES_COLUMNS_FOR_IMPORT = [
    _('Description'),
    _('Reference'),
    _('Expense Account'),
    _('Accrual Amount Booking'),
    _('Percentage'),
    _('Cost Center'),
    _('Destination'),
    _('Funding Pool'),
]

from . import account
from . import account_move_line
from . import msf_accrual_line
from . import msf_accrual_line_expense
from . import wizard

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
