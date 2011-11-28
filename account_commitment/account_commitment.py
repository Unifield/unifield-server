#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
from tools.translate import _
from time import strftime
import decimal_precision as dp

class account_commitment(osv.osv):
    _name = 'account.commitment'
    _description = "Account Commitment"
    _order = "id desc"

    def _get_total(self, cr, uid, ids, name, args, context={}):
        """
        Give total of given commitments
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse commitments
        for co in self.browse(cr, uid, ids, context=context):
            res[co.id] = 0.0
            for line in co.line_ids:
                res[co.id] += line.amount
        return res

    _columns = {
        'journal_id': fields.many2one('account.journal', string="Journal", readonly=True),
        'name': fields.char(string="Number", size=64),
        'currency_id': fields.many2one('res.currency', string="Currency", readonly=True),
        'partner_id': fields.many2one('res.partner', string="Supplier", readonly=True),
        'period_id': fields.many2one('account.period', string="Period", readonly=True),
        'ref': fields.char(string='Reference', size=64),
        'state': fields.selection([('draft', 'Draft'), ('open', 'Open'), ('done', 'Closed'), ('cancel', 'Cancel')], readonly=True, string="State"),
        'date': fields.date(string="Commitment Date", readonly=True, required=True, states={'draft': [('readonly', False)], 'open': [('readonly', False)]}),
        'line_ids': fields.one2many('account.commitment.line', 'commit_id', string="Commitment Items"),
        'total': fields.function(_get_total, type='float', method=True, digits_compute=dp.get_precision('Account'), readonly=True, string="Total"),
        'purchase_id': fields.many2one('purchase.order', string="Source document", readonly=True),
    }

    _defaults = {
        'name': '/',
        'state': lambda *a: 'draft',
        'date': lambda *a: strftime('%Y-%m-%d'),
    }

account_commitment()

class account_commitment_line(osv.osv):
    _name = 'account.commitment.line'
    _description = "Account Commitment Line"
    _order = "id desc"

    _columns = {
        'account_id': fields.many2one('account.account', string="Account"),
        'amount': fields.float(string="Amount", digits_compute=dp.get_precision('Account')),
        'commit_id': fields.many2one('account.commitment', string="Commitment Entry"),
    }

    _defaults = {
        'amount': lambda *a: 0.0,
    }
account_commitment_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
