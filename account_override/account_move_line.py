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
from time import strftime

class account_move_line(osv.osv):
    _inherit = 'account.move.line'
    _name = 'account.move.line'

    # @@@override account>account_move_line.py>account_move_line>name_get
    def name_get(self, cr, uid, ids, context=None):
        # Override default name_get (since it displays the move line reference)
        if not ids:
            return []
        result = []
        for line in self.browse(cr, uid, ids, context=context):
            result.append((line.id, line.move_id.name))
        return result

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
        pattern = re.compile('\%s([0-9]+) - ' % string)
        m = re.match(pattern, text)
        if m and m.groups():
            number = m.groups() and m.groups()[0]
            # Add a check on number due to UF-1396
            if not isinstance(number, int):
                try:
                    nn = int(number)
                except ValueError:
                    nn = 0
            replacement = string + str(nn + 1) + ' - '
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
            sql = "UPDATE "+ self._table + " SET " + name + " = %s WHERE id = %s"
            cr.execute(sql, (value, id))
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

    def _journal_type_get(self, cr, uid, context=None):
        """
        Get journal types
        """
        return self.pool.get('account.journal').get_journal_type(cr, uid, context)

    def _get_reconcile_txt(self, cr, uid, ids, field_names, args, context=None):
        """
        Get total/partial reconcile name
        """
        res = {}
        for aml in self.browse(cr, uid, ids):
            res[aml.id] = ''
            r_id = None
            if aml.reconcile_id:
                r_id = aml.reconcile_id.id
            elif aml.reconcile_partial_id:
                r_id = aml.reconcile_partial_id.id
            if r_id:
                d = self.pool.get('account.move.reconcile').name_get(cr, uid, [r_id])
                name = ''
                if d and d[0] and d[0][1]:
                    name = d[0][1]
                res[aml.id] = name
        return res

    def _get_move_lines_for_reconcile(self, cr, uid, ids, context=None):
        res = []
        for r in self.pool.get('account.move.reconcile').browse(cr, uid, ids):
            for t in r.line_id:
                res.append(t.id)
            for p in r.line_partial_ids:
                res.append(p.id)
        return res

    def _get_reconciled_move_lines(self, cr, uid, ids, context=None):
        res = []
        for line in self.browse(cr, uid, ids):
            if line.reconcile_id:
                for t in line.reconcile_id.line_id:
                    res.append(t.id)
            elif line.reconcile_partial_id:
                for p in line.reconcile_partial_id.line_partial_ids:
                    res.append(p.id)
        return res

    _columns = {
        'source_date': fields.date('Source date', help="Date used for FX rate re-evaluation"),
        'move_state': fields.related('move_id', 'state', string="Move state", type="selection", selection=[('draft', 'Draft'), ('posted', 'Posted')], 
            help="This indicates the state of the Journal Entry."),
        'is_addendum_line': fields.boolean('Is an addendum line?', readonly=True,
            help="This inform account_reconciliation module that this line is an addendum line for reconciliations."),
        'move_id': fields.many2one('account.move', 'Entry Sequence', ondelete="cascade", help="The move of this entry line.", select=2, required=True, readonly=True),
        'name': fields.char('Description', size=64, required=True),
        'journal_id': fields.many2one('account.journal', 'Journal Code', required=True, select=1),
        'debit': fields.float('Func. Debit', digits_compute=dp.get_precision('Account')),
        'credit': fields.float('Func. Credit', digits_compute=dp.get_precision('Account')),
        'currency_id': fields.many2one('res.currency', 'Book. Currency', help="The optional other currency if it is a multi-currency entry."),
        'document_date': fields.date('Document Date', size=255, required=True, readonly=True),
        'date': fields.related('move_id','date', string='Posting date', type='date', required=True, select=True,
                store = {
                    'account.move': (_get_move_lines, ['date'], 20)
                }, readonly=True),
        'is_write_off': fields.boolean('Is a write-off line?', readonly=True, 
            help="This inform that no correction is possible for a line that come from a write-off!"),
        'reference': fields.char(string='Reference', size=64),
        'ref': fields.function(_get_reference, fnct_inv=_set_fake_reference, fnct_search=_search_reference, string='Reference', method=True, type='char', size=64, store=True, readonly=True),
        'state': fields.selection([('draft','Invalid'), ('valid','Valid')], 'State', readonly=True,
            help='When new move line is created the state will be \'Draft\'.\n* When all the payments are done it will be in \'Valid\' state.'),
        'journal_type': fields.related('journal_id', 'type', string="Journal Type", type="selection", selection=_journal_type_get, readonly=True, \
        help="This indicates the type of the Journal attached to this Journal Item"),
        'exported': fields.boolean("Exported"),
        'reconcile_txt': fields.function(_get_reconcile_txt, type='text', method=True, string="Reconcile",
            help="Help user to display and sort Reconciliation",
            store = {
                'account.move.reconcile': (_get_move_lines_for_reconcile, ['name', 'line_id', 'line_partial_ids'], 10),
                'account.move.line': (_get_reconciled_move_lines, ['reconcile_id', 'reconcile_partial_id', 'debit', 'credit'], 10),
            }
        ),
    }

    _defaults = {
        'is_addendum_line': lambda *a: False,
        'is_write_off': lambda *a: False,
        'document_date': lambda self, cr, uid, c: c.get('document_date', False) or strftime('%Y-%m-%d'),
        'date': lambda self, cr, uid, c: c.get('date', False) or strftime('%Y-%m-%d'),
        'exported': lambda *a: False,
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
        if not ids:
            return 0.0
        # Create an sql query
        sql =  """
            SELECT SUM(debit - credit)
            FROM account_move_line
            WHERE id in %s
        """
        cr.execute(sql, (tuple(ids),))
        res = cr.fetchall()
        if isinstance(ids, list):
            res = res[0]
        return res

    def _check_document_date(self, cr, uid, ids):
        """
        Check that document's date is done BEFORE posting date
        """
        for aml in self.browse(cr, uid, ids):
            if aml.document_date and aml.date and aml.date < aml.document_date:
                raise osv.except_osv(_('Error'), _('Posting date should be later than Document Date.'))
        return True

    def _check_date_validity(self, cr, uid, ids):
        """
        Check that date is contained between period ' starting date and ending's date
        """
        for aml in self.browse(cr, uid, ids):
            if aml.date < aml.move_id.period_id.date_start or aml.date > aml.move_id.period_id.date_stop:
                raise osv.except_osv(_('Warning'), _('Given date [%s] is outside defined period: %s') % (aml.date, aml.move_id and aml.move_id.period_id and aml.move_id.period_id.name or ''))
        return True

    def _get_partner_id_from_vals(self, cr, uid, vals, context=None):
        """
        Search for partner_id in given vals
        """
        # Prepare some values
        res = False
        # Do some checks
        if not vals:
            return res
        if not context:
            context = {}
        if vals.get('partner_id', False):
            res = vals.get('partner_id')
        elif vals.get('partner_type', False):
            p_type = vals.get('partner_type').split(',')
            if p_type[0] == 'res.partner' and p_type[1]:
                if isinstance(p_type[1], str):
                    p_type[1] = int(p_type[1])
                res = p_type[1]
        return res

    def create(self, cr, uid, vals, context=None, check=True):
        """
        Filled in 'document_date' if we come from tests
        """
        if not context:
            context = {}
        # UTP-317: Check partner (if active or not)
        partner_id = self._get_partner_id_from_vals(cr, uid, vals, context)
        if partner_id:
            partner = self.pool.get('res.partner').browse(cr, uid, [partner_id])
            if partner and partner[0] and not partner[0].active:
                raise osv.except_osv(_('Warning'), _("Partner '%s' is not active.") % (partner[0] and partner[0].name or '',))
        # Some checks
        if not vals.get('document_date') and vals.get('date'):
            vals.update({'document_date': vals.get('date')})
        if vals.get('document_date', False) and vals.get('date', False) and vals.get('date') < vals.get('document_date'):
            raise osv.except_osv(_('Error'), _('Posting date should be later than Document Date.'))
        if 'move_id' in vals and context.get('from_web_menu'):
            m = self.pool.get('account.move').browse(cr, uid, vals.get('move_id'))
            if m and m.document_date:
                vals.update({'document_date': m.document_date})
                context.update({'document_date': m.document_date})
            if m and m.date:
                vals.update({'date': m.date})
                context.update({'date': m.date})
        return super(account_move_line, self).create(cr, uid, vals, context=context, check=check)

    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        """
        Check document_date and date validity
        """
        if not context:
            context = {}
        if context.get('from_web_menu', False):
            for ml in self.browse(cr, uid, ids):
                if ml.move_id and ml.move_id.status == 'sys':
                    raise osv.except_osv(_('Warning'), _('You cannot change Journal Items that comes from the system!'))
            # Check date validity with period
            self._check_date_validity(cr, uid, ids)
            if 'move_id' in vals:
                m = self.pool.get('account.move').browse(cr, uid, vals.get('move_id'))
                if m and m.document_date:
                    vals.update({'document_date': m.document_date})
                    context.update({'document_date': m.document_date})
                if m and m.date:
                    vals.update({'date': m.date})
                    context.update({'date': m.date})
        res = super(account_move_line, self).write(cr, uid, ids, vals, context=context, check=check, update_check=update_check)
        self._check_document_date(cr, uid, ids)
        return res

    def button_duplicate(self, cr, uid, ids, context=None):
        """
        Copy given lines for manual unposted entries
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        ml_copied_ids = []
        for ml in self.browse(cr, uid, ids):
            if ml.move_id and ml.move_id.state == 'draft' and ml.move_id.status == 'manu':
                self.copy(cr, uid, ml.id, {'move_id': ml.move_id.id, 'name': '(copy) ' + ml.name or '', 'document_date': ml.move_id.document_date, 'date': ml.move_id.date}, context)
                ml_copied_ids.append(ml.id)
        return ml_copied_ids

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=80):
        """
        In search view permit to search regarding Entry Sequence from journal entry (move_id.name field).
        This comes from UF-1719.
        """
        if args is None:
            args = []
        if context is None:
            context = {}
        ids = []
        if name:
            ids = self.search(cr, user, ['|', ('name', 'ilike', name), ('move_id.name', 'ilike', name)]+ args, limit=limit)
        if not ids:
            ids = self.search(cr, user, [('name', operator, name)]+ args, limit=limit)
        return self.name_get(cr, user, ids, context=context)

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
