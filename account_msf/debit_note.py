#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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

from osv import osv
from osv import fields

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    _columns = {
        'is_debit_note': fields.boolean(string="Is a Debit Note?"),
    }

    _defaults = {
        'is_debit_note': lambda *a: False,
    }

account_invoice()

class debit_note(osv.osv):
    _name = 'debit.note'
    _inherit = 'account.invoice'

    _defaults = {
        'is_debit_note': lambda *a: True,
    }

debit_note()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
