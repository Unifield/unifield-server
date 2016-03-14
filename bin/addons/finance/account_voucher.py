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

class account_voucher(osv.osv):
    _name = 'account.voucher'
    _inherit = 'account.voucher'

    def __hook_move_line_values_before_creation(self, cr, uid, move_line):
        """
        Add document date if date in vals
        """
        if 'date' in move_line and not 'document_date' in move_line:
            move_line.update({'document_date': move_line.get('date')})
        return move_line

account_voucher()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
