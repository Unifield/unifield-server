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

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    def _get_fake(self, cr, uid, ids, field_name=None, arg=None, context={}):
        """
        Fake method for 'ready_for_import_in_register' field
        """
        res = {}
        for id in ids:
            res[id] = False
        return res

    def _search_ready_for_import_in_register(self, cr, uid, obj, name, args, context={}):
        """
        Add debit note default account filter for search (if this account have been selected)
        """
        if not args:
            return []
        res = super(account_move_line, self)._search_ready_for_import_in_register(cr, uid, obj, name, args, context)
        # verify debit note default account configuration
        default_account = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.import_invoice_default_account
        if default_account:
            res.append(('account_id', '!=', default_account.id))
        return res

    _columns = {
        'invoice_partner_link': fields.many2one('account.invoice', string="Invoice partner link", readonly=True, 
            help="This link implies this line come from the total of an invoice, directly from partner account."),
        'invoice_line_id': fields.many2one('account.invoice.line', string="Invoice line origin", readonly=True, 
            help="Invoice line which have produced this line."),
        'ready_for_import_in_register': fields.function(_get_fake, fnct_search=_search_ready_for_import_in_register, type="boolean", 
            method=True, string="Can be imported as invoice in register?",),
    }

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
