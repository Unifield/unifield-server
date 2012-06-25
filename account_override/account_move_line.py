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
import re
import decimal_precision as dp
from time import strftime
import logging
from tools.translate import _

class account_move_line(osv.osv):
    _inherit = 'account.move.line'
    _name = 'account.move.line'
    
    def join_without_redundancy(self, text='', string=''):
        """
        Add string @ begining of text like that:
            mystring1 - mysupertext
        
        If mystring1 already exist, increment 1:
            mystring1 - mysupertext
        give:
            mystring2 - mysupertext

        NB: for 'REV' string, do nothing about incrementation
        """
        result = ''.join([string, '1 - ', text])
        if string == 'REV':
            result = ''.join([string, ' - ', text])
        if text == '' or string == '':
            return result
        pattern = re.compile('\%s([0-9]*) - ' % string)
        m = re.match(pattern, text)
        if m and m.groups():
            number = m.groups() and m.groups()[0]
            replacement = string + str(int(number) + 1) + ' - '
            if string == 'REV':
                replacement = string + ' - '
            result = re.sub(pattern, replacement, text, 1)
        return result

    def _get_move_lines(self, cr, uid, ids, context=None):
        """
        Return default behaviour
        """
        return super(account_move_line, self)._get_move_lines(cr, uid, ids, context=context)

    def _get_reference(self, cr, uid, ids, field_names, args, context=None):
        """
        Give reference field content from account_move_line first. Then search move_id.reference field, otherwise display ''.
        """
        res = {}
        for line in self.browse(cr, uid, ids):
            res[line.id] = ''
            if line.reference:
                res[line.id] = line.reference
                continue
            elif line.move_id and line.move_id.ref:
                res[line.id] = line.move_id.ref
                continue
        return res

    def _set_fake_reference(self, cr, uid, id, name=None, value=None, fnct_inv_arg=None, context=None):
        """
        Just used to not break default OpenERP behaviour
        """
        if name and value:
            sql = "UPDATE %s SET %s = %s WHERE id = %s" % (self._table, 'ref', value, id)
            cr.execute(sql)
        return True

    def _search_reference(self, cr, uid, obj, name, args, context):
        """
        Account MCDB (Selector) seems to be the only one that search on this field.
        It use 'ilike' operator
        """
        if not context:
            context = {}
        if not args:
            return []
        if args[0][2]:
            return [('move_id.reference', '=', args[0][2])]
        return []

    _columns = {
        'source_date': fields.date('Source date', help="Date used for FX rate re-evaluation"),
        'move_state': fields.related('move_id', 'state', string="Move state", type="selection", selection=[('draft', 'Draft'), ('posted', 'Posted')], 
            help="This indicates the state of the Journal Entry."),
        'is_addendum_line': fields.boolean('Is an addendum line?', readonly=True,
            help="This inform account_reconciliation module that this line is an addendum line for reconciliations."),
        'move_id': fields.many2one('account.move', 'Entry Sequence', ondelete="cascade", help="The move of this entry line.", select=2, required=True),
        'name': fields.char('Description', size=64, required=True),
        'journal_id': fields.many2one('account.journal', 'Journal Code', required=True, select=1),
        'debit': fields.float('Func. Debit', digits_compute=dp.get_precision('Account')),
        'credit': fields.float('Func. Credit', digits_compute=dp.get_precision('Account')),
        'currency_id': fields.many2one('res.currency', 'Book. Currency', help="The optional other currency if it is a multi-currency entry."),
        'document_date': fields.date('Document Date', size=255, readonly=True, required=True),
        'date': fields.related('move_id','date', string='Posting date', type='date', required=True, select=True,
                store = {
                    'account.move': (_get_move_lines, ['date'], 20)
                }),
        'is_write_off': fields.boolean('Is a write-off line?', readonly=True, 
            help="This inform that no correction is possible for a line that come from a write-off!"),
        'reference': fields.char(string='Reference', size=64),
        'ref': fields.function(_get_reference, fnct_inv=_set_fake_reference, fnct_search=_search_reference, string='Reference', method=True, type='char', size=64, store=True),
    }

    _defaults = {
        'is_addendum_line': lambda *a: False,
        'is_write_off': lambda *a: False,
    }

    _order = 'move_id DESC'

    def _accounting_balance(self, cr, uid, ids, context=None):
        """
        Get the accounting balance of given lines
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Create an sql query
        sql =  """
            SELECT SUM(debit - credit)
            FROM account_move_line
            WHERE id in %s
        """
        cr.execute(sql, [tuple(ids)])
        res = cr.fetchall()
        if isinstance(ids, list):
            res = res[0]
        return res

    def _check_document_date(self, cr, uid, ids):
        """
        Check that document's date is done BEFORE posting date
        """
        for aml in self.browse(cr, uid, ids):
            if aml.document_date and aml.date_invoice and aml.date_invoice < aml.document_date:
                raise osv.except_osv(_('Error'), _('Posting date should be later than Document Date.'))
        return True

    def create(self, cr, uid, vals, context=None, check=True):
        """
        Filled in 'document_date' if we come from tests
        """
        if not context:
            context = {}
        if not vals.get('document_date') and vals.get('date'):
            vals.update({'document_date': vals.get('date')})
        if vals.get('document_date', False) and vals.get('date', False) and vals.get('date') < vals.get('document_date'):
            raise osv.except_osv(_('Error'), _('Posting date should be later than Document Date.'))
        return super(account_move_line, self).create(cr, uid, vals, context=context, check=check)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Check document_date and date validity
        """
        if not context:
            context = {}
        res = super(account_move_line, self).write(cr, uid, ids, vals, context=context)
        self._check_document_date(cr, uid, ids)
        return res

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
