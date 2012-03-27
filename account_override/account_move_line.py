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

    def _get_move_lines(self, cr, uid, ids, context={}):
        """
        Return default behaviour
        """
        return super(account_move_line, self)._get_move_lines(cr, uid, ids, context=context)

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
        'document_date': fields.date('Document Date', size=255, readonly=True),
        'date': fields.related('move_id','date', string='Posting date', type='date', required=True, select=True,
                store = {
                    'account.move': (_get_move_lines, ['date'], 20)
                }),
        'is_write_off': fields.boolean('Is a write-off line?', readonly=True, 
            help="This inform that no correction is possible for a line that come from a write-off!"),
    }

    _defaults = {
        'is_addendum_line': lambda *a: False,
        'is_write_off': lambda *a: False,
    }

    def _accounting_balance(self, cr, uid, ids, context={}):
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

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
