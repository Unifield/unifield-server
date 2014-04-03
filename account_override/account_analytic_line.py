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

from osv import osv
from osv import fields

class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _inherit = 'account.analytic.line'

    def join_without_redundancy(self, text='', string=''):
        return self.pool.get('account.move.line').join_without_redundancy(text, string)

    _columns = {
        'journal_id': fields.many2one('account.analytic.journal', 'Journal Code', required=True, ondelete='restrict', select=True, readonly=True),
        'journal_type': fields.related('journal_id', 'type', 'Journal type', readonly=True),
        'move_id': fields.many2one('account.move.line', 'Entry Sequence', ondelete='restrict', select=True, readonly=True, domain="[('account_id.user_type.code', 'in', ['expense', 'income'])]"), # UF-1719: Domain added for search view
    }

account_analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
