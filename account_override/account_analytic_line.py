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
import decimal_precision as dp
from time import strftime
from tools.translate import _
import logging

class account_analytic_line(osv.osv):
    _inherit = 'account.analytic.line'

    def __init__(self, pool, cr):
        """
        Permits to OpenERP not attempt to update DB field with the old field_function
        """
        super(account_analytic_line, self).__init__(pool, cr)
        if self.pool._store_function.get(self._name, []):
            newstore = []
            for fct in self.pool._store_function[self._name]:
                if fct[1] not in ['currency_id', 'amount_currency']:
                    newstore.append(fct)
            self.pool._store_function[self._name] = newstore

    def join_without_redundancy(self, text='', string=''):
        return self.pool.get('account.move.line').join_without_redundancy(text, string)

    _columns = {
        'reversal_origin': fields.many2one('account.analytic.line', string="Reversal origin", readonly=True, help="Line that have been reversed."),
        'source_date': fields.date('Source date', help="Date used for FX rate re-evaluation"),
        'amount_currency': fields.float(string="Book. Amount", digits_compute=dp.get_precision('Account'), readonly=True, required=True, help="The amount expressed in an optional other currency.",),
        'currency_id': fields.many2one('res.currency', string="Book. Currency", required=True, readonly=True),
        'is_reversal': fields.boolean('Reversal?'),
        'is_reallocated': fields.boolean('Reallocated?'),
        'journal_id': fields.many2one('account.analytic.journal', 'Journal Code', required=True, ondelete='restrict', select=True, readonly=True),
        'date': fields.date('Posting Date', required=True, select=True, readonly=True),
        'document_date': fields.date('Document Date', readonly=True, required=True),
        'move_id': fields.many2one('account.move.line', 'Entry Sequence', ondelete='restrict', select=True, readonly=True, domain="[('account_id.user_type.code', 'in', ['expense', 'income'])]"), # UF-1719: Domain added for search view
        'functional_currency_id': fields.related('company_id', 'currency_id', string="Func. Currency", type="many2one", relation="res.currency", readonly=True),
        'amount': fields.float('Func. Amount', required=True, digits_compute=dp.get_precision('Account'),
            help='Calculated by multiplying the quantity and the price given in the Product\'s cost price. Always expressed in the company main currency.', readonly=True),
        'exported': fields.boolean("Exported"),
    }

    _defaults = {
        'is_reversal': lambda *a: False,
        'is_reallocated': lambda *a: False,
        'exported': lambda *a: False,
    }

    def reverse(self, cr, uid, ids, posting_date=strftime('%Y-%m-%d'), context=None):
        """
        Reverse an analytic line:
         - keep date as source_date
         - mark this line as reversal
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        for al in self.browse(cr, uid, ids, context=context):
            vals = {
                'name': self.join_without_redundancy(al.name, 'REV'),
                'amount': al.amount * -1,
                'date': posting_date,
                'source_date': al.source_date or al.date,
                'reversal_origin': al.id,
                'amount_currency': al.amount_currency * -1,
                'currency_id': al.currency_id.id,
                'is_reversal': True,
            }
            new_al = self.copy(cr, uid, al.id, vals, context=context)
            res.append(new_al)
        return res

    def _check_document_date(self, cr, uid, ids):
        """
        Check that document's date is done BEFORE posting date
        """
        for aal in self.browse(cr, uid, ids):
            if aal.document_date and aal.date and aal.date < aal.document_date:
                raise osv.except_osv(_('Error'), _('Posting date (%s) should be later than Document Date (%s).') % (aal.date, aal.document_date))
        return True

    def create(self, cr, uid, vals, context=None):
        """
        Filled in 'document_date' if we come from tests
        """
        if not context:
            context = {}
        # SP-50: If data is synchronized from another instance, just create it with the given document_date 
        if context.get('update_mode') in ['init', 'update']:
            if not context.get('sync_update_execution', False) or not vals.get('document_date', False):
                logging.getLogger('init').info('AAL: set document_date')
                vals['document_date'] = strftime('%Y-%m-%d')
        if vals.get('document_date', False) and vals.get('date', False) and vals.get('date') < vals.get('document_date'):
            raise osv.except_osv(_('Error'), _('Posting date (%s) should be later than Document Date (%s).') % (vals.get('date', False), vals.get('document_date', False)))
        return super(account_analytic_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Check document_date and date validity
        """
        if not context:
            context = {}
        res = super(account_analytic_line, self).write(cr, uid, ids, vals, context=context)
        self._check_document_date(cr, uid, ids)
        return res

account_analytic_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
