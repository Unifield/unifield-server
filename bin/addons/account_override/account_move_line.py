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
from tools.translate import _
from time import strftime
from . import finance_export


class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'


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
        pattern = re.compile('%s([0-9]+) - ' % string)
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
            res[line.id] = False
            if line.reference:
                res[line.id] = line.reference
                continue
            elif line.move_id and line.move_id.ref:
                res[line.id] = line.move_id.ref
                continue
        return res

    def _set_fake_reference(self, cr, uid, aml_id, name=None, value=None, fnct_inv_arg=None, context=None):
        """
        Just used to not break default OpenERP behaviour
        """
        if name and value:
            sql = "UPDATE "+ self._table + " SET " + name + " = %s WHERE id = %s" # not_a_user_entry
            cr.execute(sql, (value, aml_id))
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
        for line in self.browse(cr, uid, ids, context=context,
                                fields_to_fetch=['reconcile_id', 'reconcile_partial_id', 'reconcile_txt']):
            if line.reconcile_id:
                for t in line.reconcile_id.line_id:
                    res.append(t.id)
            elif line.reconcile_partial_id:
                for p in line.reconcile_partial_id.line_partial_ids:
                    res.append(p.id)
            # when an "unreconciliation" is synchronized the reconcile_txt must be reset
            elif line.reconcile_txt and context.get('sync_update_execution'):
                res.append(line.id)
        return res

    def _balance_currency(self, cr, uid, ids, name, arg, context=None):
        # UTP-31
        if context is None:
            context = {}
        c = context.copy()
        c['initital_bal'] = True
        sql = """SELECT l2.id, SUM(l1.debit_currency-l1.credit_currency)
                    FROM account_move_line l1, account_move_line l2
                    WHERE l2.account_id = l1.account_id
                      AND l1.id <= l2.id
                      AND l2.id IN %s AND """ + \
            self._query_get(cr, uid, obj='l1', context=c) + \
            " GROUP BY l2.id" # not_a_user_entry

        cr.execute(sql, [tuple(ids)])
        result = dict(cr.fetchall())
        for i in ids:
            result.setdefault(i, 0.0)
        return result

    def _balance_currency_search(self, cursor, user, obj, name, args, domain=None, context=None):
        # UTP-31
        if context is None:
            context = {}
        if not args:
            return []
        where = ' AND '.join(['(abs(sum(debit_currency-credit_currency))'+x[1]+str(x[2])+')' for x in args])
        cursor.execute('SELECT id, SUM(debit_currency-credit_currency) FROM account_move_line \
                     GROUP BY id, debit_currency, credit_currency having '+where) # not_a_user_entry
        res = cursor.fetchall()
        if not res:
            return [('id', '=', '0')]
        return [('id', 'in', [x[0] for x in res])]

    def _get_is_reconciled(self, cr, uid, ids, field_names, args, context=None):
        """
        If reconcile_partial_id or reconcile_id present, then line is reconciled.
        """
        if context is None:
            context = {}
        res = {}
        for _id in ids:
            res[_id] = False
        for line in self.search(cr, uid, [('id', 'in', ids), '|', ('reconcile_partial_id', '!=', False), ('reconcile_id', '!=', False)], context=context):
            res[line] = True
        return res

    def _search_is_reconciled(self, cr, uid, obj, name, args, context):
        """
        Give lines that have a partial or total reconciliation.
        """
        if not context:
            context = {}
        if not args:
            return []

        # US-1031: consider reconciled only if full reconcile.
        # but kept _get_is_reconciled() behaviour: reconciled if full or partial for no firther impact
        if args[0][2] and args[0][2] == True:
            return [ ('reconcile_id', '!=', False), ]
        elif args[0] and args[0][2] in [False, 0]:
            # Add account_id.reconcile in #BKLG-70
            return [
                ('account_id.reconcile', '!=', False),
                '|',
                ('reconcile_id', '=', False),
                ('reconcile_partial_id', '!=', False),
            ]

        return []

    def _init_status_move(self, cr, ids, *a, **b):
        cr.execute('update account_move_line l set status_move = (select status from account_move m where m.id = l.move_id)')

    def _get_fake(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Returns False for all ids
        """
        if isinstance(ids, int):
            ids = [ids]
        ret = {}
        for i in ids:
            ret[i] = False
        return ret

    def _search_open_items(self, cr, uid, obj, name, args, context):
        """
        Returns a domain with all reconcilable JIs EXCEPT:
        - those fully reconciled at the period end date or before
        - those fully reconciled after the period end date, if all legs of the reconciliation are <= to the period end date
        """
        if not args:
            return []
        if args[0][1] != '=' or not args[0][2] or not isinstance(args[0][2], int):
            raise osv.except_osv(_('Error'), _('Filter not implemented. '
                                               'Please check that you have selected one Period in \"Open Items at\".'))
        if context is None:
            context = {}
        aml_list = []
        period_obj = self.pool.get('account.period')
        period_id = period_obj.browse(cr, uid, args[0][2], fields_to_fetch=['date_stop'], context=context)
        period_end_date = period_id.date_stop
        aml_query = '''
              SELECT aml.id, aml.reconcile_id
              FROM account_move_line aml
              INNER JOIN account_account acc ON aml.account_id = acc.id
              WHERE acc.reconcile = 't'
              AND (aml.reconcile_id IS NULL OR reconcile_date > %s);
              '''
        cr.execute(aml_query, (period_end_date,))
        lines = cr.dictfetchall()
        for l in lines:
            if not l['reconcile_id']:
                aml_list.append(l['id'])
            else:
                # get the JIs with the same reconcile_id
                same_rec_list = self.search(cr, uid, [('reconcile_id', '=', l['reconcile_id'])], order='NO_ORDER', context=context)
                # check that at least one of them has a posting date later than the period end date
                if self.search_exist(cr, uid, [('id', 'in', same_rec_list), ('date', '>', period_end_date)], context=context):
                    aml_list.append(l['id'])
        return [('id', 'in', aml_list)]

    def _get_db_id(self, cr, uid, ids, field_name=None, arg=None, context=None):
        """
        Returns a dict. with key containing the JI id, and value containing its DB id used for Vertical Integration
        """
        if isinstance(ids, int):
            ids = [ids]
        ret = {}
        for i in ids:
            ret[i] = finance_export.finance_archive._get_hash(cr, uid, [i], 'account.move.line')
        return ret

    _columns = {
        'source_date': fields.date('Source date', help="Date used for FX rate re-evaluation"),
        'move_state': fields.related('move_id', 'state', string="Move state", type="selection", selection=[('draft', 'Unposted'), ('posted', 'Posted')],
                                     help="This indicates the state of the Journal Entry."),
        'is_addendum_line': fields.boolean('Is an addendum line?', readonly=True,
                                           help="This inform account_reconciliation module that this line is an addendum line for reconciliations."),
        'move_id': fields.many2one('account.move', 'Entry Sequence', ondelete="cascade", help="The move of this entry line.", select=2, required=True, readonly=True, join=True),
        'name': fields.char('Description', size=64, required=True, readonly=True),
        'journal_id': fields.many2one('account.journal', 'Journal Code', required=True, select=1),
        'debit': fields.float('Func. Debit', digits_compute=dp.get_precision('Account')),
        'credit': fields.float('Func. Credit', digits_compute=dp.get_precision('Account')),
        'currency_id': fields.many2one('res.currency', 'Book. Currency', help="The optional other currency if it is a multi-currency entry.", select=1),
        'document_date': fields.date('Document Date', size=255, required=True, readonly=True, select=1),
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
        'is_reconciled': fields.function(_get_is_reconciled, fnct_search=_search_is_reconciled, type='boolean', method=True, string="Is reconciled", help="Is that line partially/totally reconciled?"),
        'open_items': fields.function(_get_fake, method=True, type='many2one', relation='account.period', string='Open Items at',
                                      store=False, fnct_search=_search_open_items, domain=[('state', '!=', 'created')]),
        'balance_currency': fields.function(_balance_currency, fnct_search=_balance_currency_search, method=True, string='Balance Booking'),
        'corrected_upstream': fields.boolean('Corrected from CC/HQ', readonly=True, help='This line have been corrected from Coordo or HQ level to a cost center that have the same level or superior.'),
        'line_number': fields.integer(string='Line Number'),
        'invoice_partner_link': fields.many2one('account.invoice', string="Invoice partner link", readonly=True,
                                                help="This link implies this line come from the total of an invoice, directly from partner account.", ondelete="cascade"),
        'invoice_line_id': fields.many2one('account.invoice.line', string="Invoice line origin", readonly=True,
                                           help="Invoice line which have produced this line.", ondelete="cascade"),
        'status_move': fields.related('move_id', 'status', type='char', readonly=True, size=128, store=True, write_relate=False, string="JE status", _fnct_migrate=_init_status_move),
        'sequence_move': fields.related('move_id', 'name', type='char',
                                        readonly=True, size=128, store=False, write_relate=False,
                                        string="Sequence"),
        'imported': fields.related('move_id', 'imported', string='Imported', type='boolean', required=False, readonly=True),
        'is_si_refund': fields.boolean('Is a SI refund line', help="In case of a refund Cancel or Modify all the lines linked "
                                                                   "to the original SI and to the SR created are marked as 'is_si_refund'"),
        'revaluation_date': fields.datetime(string='Revaluation date'),
        'revaluation_reference': fields.char(string='Revaluation reference', size=64,
                                             help="Entry sequence of the related Revaluation Entry"),
        # US-3874
        'partner_register_line_id': fields.many2one('account.bank.statement.line', string="Register Line", required=False, readonly=True,
                                                    help="Register line to which this partner automated entry is linked"),
        'db_id': fields.function(_get_db_id, method=True, type='char', size=32, string='DB ID',
                                 store=False, help='DB ID used for Vertical Integration'),
    }

    _defaults = {
        'is_addendum_line': lambda *a: False,
        'is_write_off': lambda *a: False,
        'document_date': lambda self, cr, uid, c: c.get('document_date', False) or strftime('%Y-%m-%d'),
        'date': lambda self, cr, uid, c: c.get('date', False) or strftime('%Y-%m-%d'),
        'exported': lambda *a: False,
        'corrected_upstream': lambda *a: False,
        'line_number': lambda *a: 0,
        'is_si_refund': lambda *a: False,
    }

    _order = 'move_id DESC, id'
    # see account_move_line_move_id_id_index on account_move_line

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        """
        UFTP-262: As we permit user to define its own reference for a journal item in a Manual Journal Entry, we display the reference from the Journal Entry as default value for Journal Item.
        """
        if context is None:
            context = {}
        res = super(account_move_line, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        if context.get('move_reference', False) and context.get('from_web_menu', False):
            if not 'reference' in res:
                res.update({'reference': context.get('move_reference')})
        return res

    def _accounting_balance(self, cr, uid, ids, context=None):
        """
        Get the accounting balance of given lines
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not ids:
            return 0.0
        # Create an sql query
        sql =  """
            SELECT SUM(COALESCE(debit,0) - COALESCE(credit,0))
            FROM account_move_line
            WHERE id in %s
        """

        cr.execute(sql, (tuple(ids),))
        res = cr.fetchall()
        if isinstance(ids, list):
            res = res[0]
        return res

    def _accounting_booking_balance(self, cr, uid, ids, context=None):
        """
        Get the accounting balance of the given lines in booking currency
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not ids:
            return 0.0
        sql = """
            SELECT SUM(COALESCE(debit_currency,0) - COALESCE(credit_currency,0))
            FROM account_move_line
            WHERE id in %s
        """
        cr.execute(sql, (tuple(ids),))
        res = cr.fetchall()
        if isinstance(ids, list):
            res = res[0]
        return res

    def _check_date(self, cr, uid, vals, context=None, check=True):
        if 'date' in vals and vals['date'] is not False and 'account_id' in vals:
            do_check = True

            account_obj = self.pool.get('account.account')
            account = account_obj.browse(cr, uid, vals['account_id'])
            if vals.get('period_id', False):
                period_obj = self.pool.get('account.period')
                if period_obj.browse(cr, uid, vals['period_id'],
                                     context=context).is_system:
                    # US-822: no check for system periods -sync or not-
                    # 0/16 periods entries -during FY deactivated accounts-
                    do_check = False

            if do_check:
                if vals['date'] < account.activation_date \
                    or (account.inactivation_date != False and \
                        vals['date'] >= account.inactivation_date):
                    raise osv.except_osv(_('Error !'), _('The selected account is not active: %s.') % (account.code or '',))
        return super(account_move_line, self)._check_date(cr, uid, vals, context, check)

    def _check_document_date(self, cr, uid, ids, vals=None, context=None):
        """
        Check that document's date is done BEFORE posting date
        """
        if not vals:
            vals = {}
        if context is None:
            context = {}
        if context.get('sync_update_execution') and not vals.get('date') and not vals.get('document_date'):
            return True
        for aml in self.browse(cr, uid, ids):
            dd = aml.document_date
            date = aml.date
            if vals.get('document_date', False):
                dd = vals.get('document_date')
            if vals.get('date', False):
                date = vals.get('date')
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               dd, date, show_date=True, context=context)
        return True

    def _check_date_validity(self, cr, uid, ids, vals=None):
        """
        Check that date is contained between period ' starting date and ending's date
        """
        if not vals:
            vals = {}
        for aml in self.browse(cr, uid, ids):
            date = aml.date
            if vals.get('date', False):
                date = vals.get('date')
            period = aml.move_id.period_id
            if vals.get('period_id', False):
                period = self.pool.get('account.period').browse(cr, uid, [vals.get('period_id')])[0]
            if date < period.date_start or date > period.date_stop:
                raise osv.except_osv(_('Warning'), _('Given date [%s] is outside defined period: %s') % (date, period and period.name or ''))
        return True

    def _check_accounts_partner_compat(self, cr, uid, aml_ids, context=None):
        if context and context.get('from_web_menu', False):
            if isinstance(aml_ids, int):
                aml_ids = [aml_ids]
            # get the values of the JI fields related to partner and account
            fields_to_read = ['partner_type', 'partner_txt', 'employee_id', 'transfer_journal_id', 'partner_id', 'account_id']
            for aml in self.read(cr, uid, aml_ids, fields_to_read, context=context):
                partner_type = aml['partner_type'] and 'selection' in aml['partner_type'] \
                    and aml['partner_type']['selection'] or False
                if partner_type:  # format is 'model_name,id'
                    pt_model, pt_id = tuple(partner_type.split(','))
                    if not pt_id:
                        partner_type = False
                account_id = aml['account_id'] and aml['account_id'][0] or False
                partner_txt = aml['partner_txt'] or False
                employee_id = aml['employee_id'] and aml['employee_id'][0] or False
                transfer_journal_id = aml['transfer_journal_id'] and aml['transfer_journal_id'][0] or False
                partner_id = aml['partner_id'] and aml['partner_id'][0] or False
                # US-672/2
                self.pool.get('account.account').is_allowed_for_thirdparty(
                    cr, uid, account_id, partner_type=partner_type, partner_txt=partner_txt, employee_id=employee_id,
                    transfer_journal_id=transfer_journal_id, partner_id=partner_id, from_vals=True, raise_it=True,
                    context=context)

    def create(self, cr, uid, vals, context=None, check=True):
        """
        Filled in 'document_date' if we come from tests.
        Check that reference field in fill in. If not, use those from the move.
        """
        if not context:
            context = {}
        # Create new line number with account_move sequence
        if 'move_id' in vals:
            move = self.pool.get('account.move').browse(cr, uid, vals['move_id'])
            if move and move.sequence_id:
                sequence = move.sequence_id
                line = sequence.get_id(code_or_id='id', context=context)
                vals.update({'line_number': line})
            if move.status == 'manu' and not vals.get('reference', False) and move.ref:
                vals.update({'reference': move.ref})
        # Some checks
        if not vals.get('document_date') and vals.get('date'):
            vals.update({'document_date': vals.get('date')})
        if vals.get('document_date', False) and vals.get('date', False):
            self.pool.get('finance.tools').check_document_date(cr, uid,
                                                               vals.get('document_date'), vals.get('date'), show_date=True,
                                                               context=context)
        if 'move_id' in vals and context.get('from_web_menu'):
            m = self.pool.get('account.move').browse(cr, uid, vals.get('move_id'))
            if m and m.document_date:
                vals.update({'document_date': m.document_date})
                context.update({'document_date': m.document_date})
            if m and m.date:
                vals.update({'date': m.date})
                context.update({'date': m.date})
            # UFTP-262: Add description from the move_id (US-2027) if there is not descr. on the line
            if m and m.manual_name and not vals.get('name'):
                vals.update({'name': m.manual_name})
        self.pool.get('data.tools').replace_line_breaks_from_vals(vals, ['name', 'reference', 'ref'], replace=['name'])
        # US-220: vals.ref must have 64 digits max
        if vals.get('ref'):
            vals['ref'] = vals['ref'][:64]
        res = super(account_move_line, self).create(cr, uid, vals, context=context, check=check)
        self._check_accounts_partner_compat(cr, uid, res, context=context)
        # UTP-317: Check partner (if active or not)
        if res and not (context.get('sync_update_execution', False) or context.get('addendum_line_creation', False)): #UF-2214: Not for the case of sync. # UTP-1022: Not for the case of addendum line creation
            aml = self.browse(cr, uid, [res], context)
            if aml and aml[0] and aml[0].partner_id and not aml[0].partner_id.active:
                raise osv.except_osv(_('Warning'), _("Partner '%s' is not active.") % (aml[0].partner_id.name or '',))

        # US-852: Make an extra call to post-check all move lines when the "last" line got executed
        if vals.get('move_id'):
            self.pool.get('account.move').validate_sync(cr, uid, vals.get('move_id'), context)
        return res

    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        """
        Check document_date and date validity
        """
        if not ids:
            return True
        if not context:
            context = {}
        if context.get('from_web_menu', False):
            for ml in self.browse(cr, uid, ids):
                # US-1822 When unreconciling entries, to check if the write can be done use the reconciliation status
                # (manual / auto) instead of the JI one
                if 'unreconcile_date' in vals and vals['unreconcile_date']:
                    reconciliation = ml.reconcile_id or ml.reconcile_partial_id or False
                    if reconciliation and reconciliation.type == 'auto':
                        raise osv.except_osv(_('Warning'), _('Only manually reconciled entries can be unreconciled.'))
                # prevent from modifying system JIs except for reversing a manual correction
                elif ml.move_id and ml.move_id.status == 'sys' and not context.get('from_manual_corr_reversal'):
                    raise osv.except_osv(_('Warning'), _('You cannot change Journal Items that comes from the system!'))
                # By default the name of a manual JI is the JE description
                if ml.status_move == 'manu':
                    no_ji_name = not vals.get('name') and not ml.name
                    new_ji_name_empty = 'name' in vals and not vals['name']
                    if no_ji_name or new_ji_name_empty:
                        vals.update({'name': ml.move_id.manual_name})
            # Check date validity with period
            self._check_date_validity(cr, uid, ids, vals)
            if 'move_id' in vals:
                m = self.pool.get('account.move').browse(cr, uid, vals.get('move_id'))
                if m and m.document_date:
                    vals.update({'document_date': m.document_date})
                    context.update({'document_date': m.document_date})
                if m and m.date:
                    vals.update({'date': m.date})
                    context.update({'date': m.date})
        # Note that _check_document_date HAVE TO be BEFORE the super write. If not, some problems appears in ournal entries document/posting date changes at the same time!
        self._check_document_date(cr, uid, ids, vals, context=context)
        self.pool.get('data.tools').replace_line_breaks_from_vals(vals, ['name', 'reference', 'ref'], replace=['name'])
        res = super(account_move_line, self).write(cr, uid, ids, vals, context=context, check=check, update_check=update_check)
        self._check_accounts_partner_compat(cr, uid, ids, context=context)
        # UFTP-262: Check reference field for all lines. Optimisation: Do nothing if reference is in vals as it will be applied on all lines.
        if context.get('from_web_menu', False) and not vals.get('reference', False):
            for ml in self.browse(cr, uid, ids):
                if ml.move_id and ml.move_id.status == 'manu' and not ml.reference:
                    # note: line breaks are removed from JE ref at JE creation/edition
                    super(account_move_line, self).write(cr, uid, [ml.id], {'reference': ml.move_id.ref}, context=context, check=False, update_check=False)
        return res

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        """
        Filtering regarding context
        """
        if not context:
            context = {}
        if context.get('currency_id'):
            args.append(('currency_id', '=', context.get('currency_id')))
        if context.get('move_state'):
            args.append(('move_state', '=', context.get('move_state')))
        if context.get('account_id'):
            args.append(('account_id', '=', context.get('account_id')))

        period_ids = []
        if context.get('periods'):
            period_ids = context.get('periods')
            if isinstance(period_ids, int):
                period_ids = [period_ids]
        elif context.get('fiscalyear'):
            fy = context.get('fiscalyear')
            period_obj = self.pool.get('account.period')
            period_ids = period_obj.search(cr, uid,
                                           [('fiscalyear_id', '=', fy)],
                                           context=context)
        elif context.get('period_from') and context.get('period_to'):
            p_from = context.get('period_from')
            p_to = context.get('period_to')
            period_obj = self.pool.get('account.period')
            period_ids = period_obj.build_ctx_periods(cr, uid, p_from, p_to)
        if period_ids:
            args.append(('period_id', 'in', period_ids))

        return super(account_move_line, self).search(cr, uid, args, offset,
                                                     limit, order, context=context, count=count)

    def copy(self, cr, uid, aml_id, default=None, context=None):
        """
        When duplicate a JI, don't copy:
        - the links to register lines
        - the reconciliation date
        - the unreconciliation date
        - the old reconciliation ref (unreconcile_txt)
        - the tag 'is_si_refund'
        - the fields related to revaluation and accruals
        """
        if context is None:
            context = {}
        if default is None:
            default = {}
        default.update({
            'imported_invoice_line_ids': [],
            'partner_register_line_id': False,
            'reconcile_date': None,
            'unreconcile_date': None,
            'unreconcile_txt': '',
            'is_si_refund': False,
            'revaluation_date': None,
            'revaluation_reference': '',
            'accrual': False,
            'accrual_line_id': False,
        })
        return super(account_move_line, self).copy(cr, uid, aml_id, default, context=context)

    def button_duplicate(self, cr, uid, ids, context=None):
        """
        Copy given lines for manual unposted entries
        """
        if not context:
            context = {}
        if isinstance(ids, int):
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
