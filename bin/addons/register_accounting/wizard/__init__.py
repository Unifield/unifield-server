#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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

from . import cashbox_closing
from . import register_reopen
from . import temp_posting
from . import hard_posting
from . import wizard_cash_return
from . import direct_invoice
from . import import_invoice_on_registers
from . import import_cheque_on_bank_registers
from . import register_creation
from . import wizard_confirm_bank
from . import invoice_date
from . import down_payment
from . import wizard_register_import
from . import wizard_liquidity_position
from . import register_opening
from . import modify_responsible



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
