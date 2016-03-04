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
from account_override import ACCOUNT_RESTRICTED_AREA
from tools.translate import _
from time import strftime
import datetime
from dateutil.relativedelta import relativedelta
import decimal_precision as dp
import netsvc

class account_account(osv.osv):
    '''
        To create a activity period, 2 new fields are created, and are NOT linked to the
        'active' field, since the behaviors are too different.
    '''
    _name = "account.account"
    _inherit = "account.account"

    def _get_active(self, cr, uid, ids, field_name, args, context=None):
        '''
        If date out of date_start/date of given account, then account is inactive.
        The comparison could be done via a date given in context.
        '''
        res = {}
        cmp_date = datetime.date.today().strftime('%Y-%m-%d')
        if context.get('date', False):
            cmp_date = context.get('date')
        for a in self.browse(cr, uid, ids):
            res[a.id] = True
            if a.activation_date > cmp_date:
                res[a.id] = False
            if a.inactivation_date and a.inactivation_date <= cmp_date:
                res[a.id] = False
        return res

    def _search_filter_active(self, cr, uid, ids, name, args, context=None):
        """
        Add the search on active/inactive account
        """
        arg = []
        cmp_date = datetime.date.today().strftime('%Y-%m-%d')
        if context.get('date', False):
            cmp_date = context.get('date')
        for x in args:
            if x[0] == 'filter_active' and x[2] == True:
                arg.append(('activation_date', '<=', cmp_date))
                arg.append('|')
                arg.append(('inactivation_date', '>', cmp_date))
                arg.append(('inactivation_date', '=', False))
            elif x[0] == 'filter_active' and x[2] == False:
                arg.append('|')
                arg.append(('activation_date', '>', cmp_date))
                arg.append(('inactivation_date', '<=', cmp_date))
        return arg

    #@@@override account.account_account.__compute
    def __compute(self, cr, uid, ids, field_names, arg=None, context=None,
                  query='', query_params=()):
        """ compute the balance, debit and/or credit for the provided
        account ids
        Arguments:
        `ids`: account ids
        `field_names`: the fields to compute (a list of any of
                       'balance', 'debit' and 'credit')
        `arg`: unused fields.function stuff
        `query`: additional query filter (as a string)
        `query_params`: parameters for the provided query string
                        (__compute will handle their escaping) as a
                        tuple
        """
        mapping = {
            'balance': "COALESCE(SUM(l.debit),0) " \
                       "- COALESCE(SUM(l.credit), 0) as balance",
            'debit': "COALESCE(SUM(l.debit), 0) as debit",
            'credit': "COALESCE(SUM(l.credit), 0) as credit"
        }
        #get all the necessary accounts
        children_and_consolidated = self._get_children_and_consol(cr, uid, ids, context=context)
        #compute for each account the balance/debit/credit from the move lines
        accounts = {}
        sums = {}
        query_params = []
        # Add some query/query_params regarding context
        link = " "
        if context.get('currency_id', False):
            if query:
                link = " AND "
            query += link + 'currency_id = %s'
            query_params.append(tuple([context.get('currency_id')]))
        link = " "
        if context.get('instance_ids', False):
            if query:
                link = " AND "
            instance_ids = context.get('instance_ids')
            if isinstance(instance_ids, (int, long)):
                instance_ids = [instance_ids]
            if len(instance_ids) == 1:
                query += link + 'l.instance_id = %s'
            else:
                query += link + 'l.instance_id in %s'
            query_params.append(tuple(instance_ids))
        # Do normal process
        if children_and_consolidated:
            aml_query = self.pool.get('account.move.line')._query_get(cr, uid, context=context)

            wheres = [""]
            if query.strip():
                wheres.append(query.strip())
            if aml_query.strip():
                wheres.append(aml_query.strip())
            filters = " AND ".join(wheres)
            # target_move from chart of account wizard
            filters = filters.replace("AND l.state <> 'draft'", '')
            prefilters = " "
            if context.get('move_state', False):
                prefilters += "AND l.move_id = m.id AND m.state = '%s'" % context.get('move_state')
            else:
                prefilters += "AND l.move_id = m.id AND m.state in ('posted', 'draft')"
            # Notifications
            self.logger.notifyChannel('account_override.'+self._name, netsvc.LOG_DEBUG,
                                      'Filters: %s'%filters)
            # IN might not work ideally in case there are too many
            # children_and_consolidated, in that case join on a
            # values() e.g.:
            # SELECT l.account_id as id FROM account_move_line l
            # INNER JOIN (VALUES (id1), (id2), (id3), ...) AS tmp (id)
            # ON l.account_id = tmp.id
            # or make _get_children_and_consol return a query and join on that
            request = ("SELECT l.account_id as id, " +\
                       ', '.join(map(mapping.__getitem__, field_names)) +
                       " FROM account_move_line l, account_move m" +\
                       " WHERE l.account_id IN %s " \
                            + prefilters + filters +
                       " GROUP BY l.account_id")
            params = [tuple(children_and_consolidated)]
            if query_params:
                for qp in query_params:
                    params.append(qp)
            cr.execute(request, params)
            self.logger.notifyChannel('account_override.'+self._name, netsvc.LOG_DEBUG,
                                      'Status: %s'%cr.statusmessage)

            for res in cr.dictfetchall():
                accounts[res['id']] = res

            # consolidate accounts with direct children
            children_and_consolidated.reverse()
            brs = list(self.browse(cr, uid, children_and_consolidated, context=context))
            currency_obj = self.pool.get('res.currency')
            while brs:
                current = brs[0]
                brs.pop(0)
                for fn in field_names:
                    sums.setdefault(current.id, {})[fn] = accounts.get(current.id, {}).get(fn, 0.0)
                    for child in current.child_id:
                        if child.company_id.currency_id.id == current.company_id.currency_id.id:
                            sums[current.id][fn] += sums[child.id][fn]
                        else:
                            sums[current.id][fn] += currency_obj.compute(cr, uid, child.company_id.currency_id.id, current.company_id.currency_id.id, sums[child.id][fn], context=context)
        res = {}
        null_result = dict((fn, 0.0) for fn in field_names)
        company_currency = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        for i in ids:
            res[i] = sums.get(i, null_result)
            # If output_currency_id in context, we change computation
            for f_name in ('debit', 'credit', 'balance'):
                if context.get('output_currency_id', False) and res[i].get(f_name, False):
                    new_amount = currency_obj.compute(cr, uid, context.get('output_currency_id'), company_currency, res[i].get(f_name), context=context)
                    res[i][f_name] = new_amount
        return res
    #@@@end

    def _get_restricted_area(self, cr, uid, ids, field_name, args, context=None):
        """
        FAKE METHOD
        """
        # Check
        if context is None:
            context = {}
        res = {}
        for account_id in ids:
            res[account_id] = True
        return res

    def _search_restricted_area(self, cr, uid, ids, name, args, context=None):
        """
        Search the right domain to apply to this account filter.
        For this, it uses the "ACCOUNT_RESTRICTED_AREA" variable in which we list all well-known cases.
        The key args is "restricted_area", the param is like "register_lines".
        In ACCOUNT_RESTRICTED_AREA, we use the param as key. It so return the domain to apply.
        If no domain, return an empty domain.
        """
        # Check
        if context is None:
            context = {}
        arg = []
        for x in args:
            if x[0] == 'restricted_area' and x[2]:
                if x[2] in ACCOUNT_RESTRICTED_AREA:
                    for subdomain in ACCOUNT_RESTRICTED_AREA[x[2]]:
                        arg.append(subdomain)
            elif x[0] != 'restricted_area':
                arg.append(x)
            else:
                raise osv.except_osv(_('Error'), _('Operation not implemented!'))
        return arg

    def _get_fake_cash_domain(self, cr, uid, ids, field_name, arg, context=None):
        """
        Fake method for domain
        """
        if context is None:
            context = {}
        res = {}
        for cd_id in ids:
            res[cd_id] = True
        return res

    def _search_cash_domain(self, cr, uid, ids, field_names, args, context=None):
        """
        Return a given domain (defined in ACCOUNT_RESTRICTED_AREA variable)
        """
        if context is None:
            context = {}
        arg = []
        for x in args:
            if x[0] and x[1] == '=' and x[2]:
                if x[2] in ['cash', 'bank', 'cheque']:
                    arg.append(('restricted_area', '=', 'journals'))
            else:
                raise osv.except_osv(_('Error'), _('Operation not implemented!'))
        return arg

    def _get_is_specific_counterpart(self, cr, uid, ids, field_names, args, context=None):
        """
        If this account is the same as default intermission counterpart OR rebilling intersection account, then return True. Otherwise return nothing.
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        res = {}
        account = False
        if field_names == 'is_intermission_counterpart':
            account = self.pool.get('res.users').browse(cr, uid, uid).company_id.intermission_default_counterpart
        elif field_names == 'is_intersection_counterpart':
            account = self.pool.get('res.users').browse(cr, uid, uid).company_id.import_invoice_default_account
        specific_account_id = account and account.id or False

        for account_id in ids:
            res[account_id] = False
        if specific_account_id in ids:
            res[specific_account_id] = True
        return res

    def _search_is_specific_counterpart(self, cr, uid, ids, field_names, args, context=None):
        """
        Return the intermission counterpart OR the rebilling intersection account ID.
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        arg = []
        account = False
        fieldname = False
        if field_names == 'is_intermission_counterpart':
            account = self.pool.get('res.users').browse(cr, uid, uid).company_id.intermission_default_counterpart
            fieldname = 'intermission_default_counterpart'
        elif field_names == 'is_intersection_counterpart':
            account = self.pool.get('res.users').browse(cr, uid, uid).company_id.import_invoice_default_account
            fieldname = 'import_invoice_default_account'
        specific_account_id = account and account.id or False

        for x in args:
            if x[0] == field_names and x[2] is True:
                if specific_account_id:
                    arg.append(('id', '=', specific_account_id))
            elif x[0] == field_names and x[2] is False:
                if specific_account_id:
                    arg.append(('id', '!=', specific_account_id))
            elif x[0] != field_names:
                arg.append(x)
            else:
                raise osv.except_osv(_('Error'), _('Filter on field %s not implemented! %s') % (field_names, x,))
        return arg

    def _get_fake(self, cr, uid, ids, name, args, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            res[id] = False
        return res

    def _get_search_is_partner_type_allowed(self, cr, uid, obj, name, args,
        context=None):
        """
        US-672
        search between following partner types operand:
        'internal'
        'section'
        'external'
        'esc'
        'intermission'
        'local'  # NAT employee
        'ex':  # Expat
        'book':  # transfer journal

        domain example:
        [('is_partner_type_allowed', '=', 'external')]
        [('is_partner_type_allowed', 'in', ['external', 'internal'])]
        """
        res = []
        if not len(args):
            return res
        if len(args) != 1:
            msg = _("Domain %s not suported") % (str(args), )
            raise osv.except_osv(_('Error'), msg)
        if args[0][1] not in ('=', 'in', ):
            msg = _("Operator '%s' not suported") % (args[0][1], )
            raise osv.except_osv(_('Error'), msg)

        partner_types = args[0][2]
        if not isinstance(partner_types, (list, tuple, )):
            partner_types = [ partner_types, ]
        for t in partner_types:
            res.append(('has_partner_type_%s' % (t, ), '=', True))
        return res

    _columns = {
        'name': fields.char('Name', size=128, required=True, select=True, translate=True),
        'activation_date': fields.date('Active from', required=True),
        'inactivation_date': fields.date('Inactive from'),
        'note': fields.char('Note', size=160),
        'type_for_register': fields.selection([('none', 'None'), ('transfer', 'Internal Transfer'), ('transfer_same','Internal Transfer (same currency)'),
            ('advance', 'Operational Advance'), ('payroll', 'Third party required - Payroll'), ('down_payment', 'Down payment'), ('donation', 'Donation'), ('disregard_rec', 'Reconciliation - Disregard 3rd party')], string="Type for specific treatment", required=True,
            help="""This permit to give a type to this account that impact registers. In fact this will link an account with a type of element
            that could be attached. For an example make the account to be a transfer type will display only registers to the user in the Cash Register
            when he add a new register line.
            You can also make an account to accept reconciliation even if the 3RD party is not the same.
            """),
        'shrink_entries_for_hq': fields.boolean("Shrink entries for HQ export", help="Check this attribute if you want to consolidate entries on this account before they are exported to the HQ system."),
        'filter_active': fields.function(_get_active, fnct_search=_search_filter_active, type="boolean", method=True, store=False, string="Show only active accounts",),
        'restricted_area': fields.function(_get_restricted_area, fnct_search=_search_restricted_area, type='boolean', method=True, string="Is this account allowed?"),
        'cash_domain': fields.function(_get_fake_cash_domain, fnct_search=_search_cash_domain, method=True, type='boolean', string="Domain used to search account in journals", help="This is only to change domain in journal's creation."),
        'balance': fields.function(__compute, digits_compute=dp.get_precision('Account'), method=True, string='Balance', multi='balance'),
        'debit': fields.function(__compute, digits_compute=dp.get_precision('Account'), method=True, string='Debit', multi='balance'),
        'credit': fields.function(__compute, digits_compute=dp.get_precision('Account'), method=True, string='Credit', multi='balance'),
        'is_intermission_counterpart': fields.function(_get_is_specific_counterpart, fnct_search=_search_is_specific_counterpart, method=True, type='boolean', string='Is the intermission counterpart account?'),
        'is_intersection_counterpart': fields.function(_get_is_specific_counterpart, fnct_search=_search_is_specific_counterpart, method=True, type='boolean', string='Is the intersection counterpart account?'),

        # US-672/1
        'has_partner_type_internal': fields.boolean('Internal'),
        'has_partner_type_section': fields.boolean('Inter-section'),
        'has_partner_type_external': fields.boolean('External'),
        'has_partner_type_esc': fields.boolean('ESC'),
        'has_partner_type_intermission': fields.boolean('Intermission'),
        'has_partner_type_local': fields.boolean('NAT'),  # NAT employee
        'has_partner_type_ex': fields.boolean('Expat'),  # Expat
        'has_partner_type_book': fields.boolean('Book'),  # transfer journal
        'is_partner_type_allowed': fields.function(_get_fake,
            fnct_search=_get_search_is_partner_type_allowed, method=True,
            type='boolean', string="Parner type allowed ?", readonly=True),
    }

    _defaults = {
        'activation_date': lambda *a: (datetime.datetime.today() + relativedelta(months=-3)).strftime('%Y-%m-%d'),
        'type_for_register': lambda *a: 'none',
        'shrink_entries_for_hq': lambda *a: True,

        # US-672/1: allow all partner types by default:
        # => master data retro-compat before ticket
        'has_partner_type_internal': True,
        'has_partner_type_section': True,
        'has_partner_type_external': True,
        'has_partner_type_esc': True,
        'has_partner_type_intermission': True,
        'has_partner_type_local': True,
        'has_partner_type_ex': True,
        'has_partner_type_book': True,
    }

    # UTP-493: Add a dash between code and account name
    def name_get(self, cr, uid, ids, context=None):
        """
        Use "-" instead of " " between name and code for account's default name
        """
        if not ids:
            return []
        reads = self.read(cr, uid, ids, ['name', 'code'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['code']:
                name = record['code'] + ' - '+name
            res.append((record['id'], name))
        return res

    def _get_parent_of(self, cr, uid, ids, limit=10, context=None):
        """
        Get all parents from the given accounts.
        To avoid problem of recursion, set a limit from 1 to 10.
        """
        # Some checks
        if context is None:
            context = {}
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        if limit < 1 or limit > 10:
            raise osv.except_osv(_('Error'), _("You're only allowed to use a limit between 1 and 10."))
        # Prepare some values
        account_ids = list(ids)
        sql = """
            SELECT parent_id
            FROM account_account
            WHERE id IN %s
            AND parent_id IS NOT NULL
            GROUP BY parent_id"""
        cr.execute(sql, (tuple(ids),))
        if not cr.rowcount:
            return account_ids
        parent_ids = [x[0] for x in cr.fetchall()]
        account_ids += parent_ids
        stop = 1
        while parent_ids:
            # Stop the search if we reach limit
            if stop >= limit:
                break
            stop += 1
            cr.execute(sql, (tuple(parent_ids),))
            if not cr.rowcount:
                parent_ids = False
            tmp_res = cr.fetchall()
            tmp_ids = [x[0] for x in tmp_res]
            if None in tmp_ids:
                parent_ids = False
            else:
                parent_ids = list(tmp_ids)
                account_ids += tmp_ids
        return account_ids

    def _check_date(self, vals, context=None):
        if context is None:
            context = {}

        if 'inactivation_date' in vals and vals['inactivation_date'] is not False:
            if vals['inactivation_date'] <= datetime.date.today().strftime('%Y-%m-%d') and not context.get('sync_update_execution', False):
                # validate the date (must be > today)
                raise osv.except_osv(_('Warning !'), _('You cannot set an inactivity date lower than tomorrow!'))
            elif 'activation_date' in vals and not vals['activation_date'] < vals['inactivation_date']:
                # validate that activation date
                raise osv.except_osv(_('Warning !'), _('Activation date must be lower than inactivation date!'))

    def create(self, cr, uid, vals, context=None):
        self._check_date(vals, context=context)
        return super(account_account, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        self._check_date(vals, context=context)
        return super(account_account, self).write(cr, uid, ids, vals, context=context)

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        """
        Filtering regarding context
        """
        if not context:
            context = {}
        if context.get('filter_inactive_accounts'):
            args_append = args.append
            args_append(('activation_date', '<=', datetime.date.today().strftime('%Y-%m-%d')))
            args_append('|')
            args_append(('inactivation_date', '>', datetime.date.today().strftime('%Y-%m-%d')))
            args_append(('inactivation_date', '=', False))
        return super(account_account, self).search(cr, uid, args, offset,
                limit, order, context=context, count=count)

    def _get_partner_types_list(self, cr, uid, ids, context=None):
        """
        get list of allowed partner types
        :return: {'id': ['internal', ...], ... }
        :rtype dict
        """
        types = (
            'internal',
            'section',
            'external',
            'esc',
            'intermission',

            'local',
            'ex',

            'book',
        )
        res = {}

        for r in self.browse(cr, uid, ids, context=context):
            l = []
            for t in types:
                field = 'has_partner_type_%s' % (t, )
                if hasattr(r, field) and getattr(r, field):
                    l.append(t)
            res[r.id] = l

        return res

account_account()

class account_journal(osv.osv):
    _name = 'account.journal'
    _inherit = 'account.journal'

    # @@@override account>account.py>account_journal>create_sequence
    def create_sequence(self, cr, uid, vals, context=None):
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = vals['name']
        code = vals['code'].lower()

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'active': True,
            'prefix': '',
            'padding': 4,
            'number_increment': 1
        }
        return seq_pool.create(cr, uid, seq)

    def _get_fake(self, cr, uid, ids, name, args, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            res[id] = False
        return res

    def _search_instance_filter(self, cr, uid, obj, name, args, context=None):
        # journals instance filter: let all default journals,
        # except specific cases
        res = False
        if not args:
            return res
        if len(args) != 1 or len(args[0]) != 3 or \
            args[0][0] != 'instance_filter' or args[0][1] != '=':
            raise osv.except_osv(_('Error'), 'invalid arguments')

        is_manual_view = context and context.get('from_manual_entry', False)
        if is_manual_view:
            self_instance = self.pool.get('res.users').browse(cr, uid, [uid],
                context=context)[0].company_id.instance_id
            if self_instance:
                forbid_levels = []
                if self_instance.level:
                    if self_instance.level == 'coordo':
                        # BKLG-19/7: forbid creation of MANUAL journal entries
                        # from COORDO on a PROJECT journal
                        forbid_levels = ['project']
                    elif self_instance.level == 'project':
                        # US-896: project should only see project journals
                        # (coordo register journals sync down to project for
                        #  example)
                        forbid_levels = ['coordo', 'section']
                if forbid_levels:
                    msf_instance_obj = self.pool.get('msf.instance')
                    forbid_instance_ids = msf_instance_obj.search(cr, uid, 
                        [('level', 'in', forbid_levels)], context=context)
                    if forbid_instance_ids:
                        res = [('instance_id', 'not in', forbid_instance_ids)]
        return res

    _columns = {
        # BKLG-19/7: journals instance filter 
        'instance_filter': fields.function(
            _get_fake, fnct_search=_search_instance_filter,
            method=True, type='boolean', string='Instance filter'
        ),
    }

account_journal()

class account_move(osv.osv):
    _inherit = 'account.move'

    def _journal_type_get(self, cr, uid, context=None):
        """
        Get journal types
        """
        return self.pool.get('account.journal').get_journal_type(cr, uid, context)

    _columns = {
        'name': fields.char('Entry Sequence', size=64, required=True),
        'statement_line_ids': fields.many2many('account.bank.statement.line', 'account_bank_statement_line_move_rel', 'statement_id', 'move_id',
            string="Statement lines", help="This field give all statement lines linked to this move."),
        'ref': fields.char('Reference', size=64, readonly=True, states={'draft':[('readonly',False)]}),
        'status': fields.selection([('sys', 'system'), ('manu', 'manual')], string="Status", required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True, states={'posted':[('readonly',True)]}, domain="[('state', '=', 'draft')]"),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True, states={'posted':[('readonly',True)]}, domain="[('type', 'not in', ['accrual', 'hq', 'inkind', 'cur_adj', 'system']), ('instance_filter', '=', True)]"),
        'document_date': fields.date('Document Date', size=255, required=True, help="Used for manual journal entries"),
        'journal_type': fields.related('journal_id', 'type', type='selection', selection=_journal_type_get, string="Journal Type", \
            help="This indicates which Journal Type is attached to this Journal Entry"),
        'sequence_id': fields.many2one('ir.sequence', string='Lines Sequence', ondelete='cascade',
            help="This field contains the information related to the numbering of the lines of this journal entry."),
        'manual_name': fields.char('Description', size=64, required=True),
        'imported': fields.boolean('Imported', help="Is this Journal Entry imported?", required=False, readonly=True),
    }

    _defaults = {
        'status': lambda self, cr, uid, c: c.get('from_web_menu', False) and 'manu' or 'sys',
        'document_date': lambda *a: False,
        'date': lambda *a: False,
        'period_id': lambda *a: '',
        'manual_name': lambda *a: '',
        'imported': lambda *a: False,
   }

    def _check_document_date(self, cr, uid, ids, context=None):
        """
        Check that document's date is done BEFORE posting date
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context.get('from_web_menu', False):
            for m in self.browse(cr, uid, ids):
                self.pool.get('finance.tools').check_document_date(cr, uid,
                    m.document_date, m.date, context=context)
        return True

    def _check_date_in_period(self, cr, uid, ids, context=None):
        """
        Check that date is inside defined period
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context.get('from_web_menu', False):
            for m in self.browse(cr, uid, ids):
                if m.date and m.period_id and m.period_id.date_start and m.date >= m.period_id.date_start and m.period_id.date_stop and m.date <= m.period_id.date_stop:
                    continue
                raise osv.except_osv(_('Error'), _('Posting date should be include in defined Period%s.') % (m.period_id and ': ' + m.period_id.name or '',))
        return True

    def _hook_check_move_line(self, cr, uid, move_line, context=None):
        """
        Check date on move line. Should be the same as Journal Entry (account.move)
        """
        if not context:
            context = {}
        res = super(account_move, self)._hook_check_move_line(cr, uid, move_line, context=context)
        if not move_line:
            return res
        if move_line.date != move_line.move_id.date:
            raise osv.except_osv(_('Error'), _("Journal item does not have same posting date (%s) as journal entry (%s).") % (move_line.date, move_line.move_id.date))
        return res

    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new journal entry
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Journal Items L' # For Journal Items Lines
        code = 'account.move'

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        }
        return seq_pool.create(cr, uid, seq)

    def create(self, cr, uid, vals, context=None):
        """
        Change move line's sequence (name) by using instance move prefix.
        Add default document date and posting date if none.
        """
        if not context:
            context = {}
        # Change the name for (instance_id.move_prefix) + (journal_id.code) + sequence number
        instance = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id
        journal = self.pool.get('account.journal').browse(cr, uid, vals['journal_id'])
        # Add default date and document date if none
        if not vals.get('date', False):
            vals.update({'date': self.pool.get('account.period').get_date_in_period(cr, uid, strftime('%Y-%m-%d'), vals.get('period_id'))})
        if not vals.get('document_date', False):
            vals.update({'document_date': vals.get('date')})
        if 'from_web_menu' in context:
            vals.update({'status': 'manu'})
            # Update context in order journal item could retrieve this @creation
            if 'document_date' in vals:
                context['document_date'] = vals.get('document_date')
            if 'date' in vals:
                context['date'] = vals.get('date')
            # UTFTP-262: Make manual_name mandatory
            if 'manual_name' not in vals or not vals.get('manual_name', False) or vals.get('manual_name') == '':
                raise osv.except_osv(_('Error'), _('Description is mandatory!'))
            if journal.type == 'system':
                raise osv.except_osv(_('Warning'), _('You can not record a Journal Entry on a system journal'))

        if context.get('seqnums',False):
            # utp913 - reuse sequence numbers if in the context
            vals['name'] = context['seqnums'][journal.id]
        else:
            # Create sequence for move lines
            period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, vals['date'])
            if not period_ids:
                raise osv.except_osv(_('Warning'), _('No period found for creating sequence on the given date: %s') % (vals['date'] or ''))
            period = self.pool.get('account.period').browse(cr, uid, period_ids)[0]
            # UF-2479: If the period is not open yet, raise exception for the move
            if period and period.state == 'created':
                raise osv.except_osv(_('Error !'), _('Period \'%s\' is not open! No Journal Entry is created') % (period.name,))

            # Context is very important to fetch the RIGHT sequence linked to the fiscalyear!
            sequence_number = self.pool.get('ir.sequence').get_id(cr, uid, journal.sequence_id.id, context={'fiscalyear_id': period.fiscalyear_id.id})
            if instance and journal and sequence_number and ('name' not in vals or vals['name'] == '/'):
                if not instance.move_prefix:
                    raise osv.except_osv(_('Warning'), _('No move prefix found for this instance! Please configure it on Company view.'))
                vals['name'] = "%s-%s-%s" % (instance.move_prefix, journal.code, sequence_number)

        # Create a sequence for this new journal entry
        res_seq = self.create_sequence(cr, uid, vals, context)
        vals.update({'sequence_id': res_seq,})
        # Default behaviour (create)
        res = super(account_move, self).create(cr, uid, vals, context=context)
        self._check_document_date(cr, uid, res, context)
        self._check_date_in_period(cr, uid, res, context)
        return res

    def name_get(self, cursor, user, ids, context=None):
        # Override default name_get (since it displays "*12" names for unposted entries)
        return super(osv.osv, self).name_get(cursor, user, ids, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Check that we can write on this if we come from web menu or synchronisation.
        """
        if not context:
            context = {}
        if context.get('from_web_menu', False) or context.get('sync_update_execution', False):
            # by default, from synchro, we just need to update period_id and journal_id
            fields = ['journal_id', 'period_id']
            # from web menu, we also update document_date and date
            if context.get('from_web_menu', False):
                fields += ['document_date', 'date']
            for m in self.browse(cr, uid, ids):
                if context.get('from_web_menu', False):
                    if m.status == 'sys':
                        raise osv.except_osv(_('Warning'), _('You cannot edit a Journal Entry created by the system.'))
                    if m.journal_id.type == 'system':
                        raise osv.except_osv(_('Warning'), _('You can not edit a Journal Entry on a system journal'))
                # Update context in order journal item could retrieve this @creation
                # Also update some other fields
                ml_vals = {}
                for el in fields:
                    if el in vals:
                        context[el] = vals.get(el)
                        ml_vals.update({el: vals.get(el)})
                # UFTP-262: For manual_name (description on account.move), update "name" on account.move.line
                if 'manual_name' in vals:
                    ml_vals.update({'name': vals.get('manual_name', '')})
                # Update document date AND date at the same time
                if ml_vals:
                    ml_id_list  = [ml.id for ml in m.line_id]
                    self.pool.get('account.move.line').write(cr, uid,
                            ml_id_list, ml_vals, context, False, False)
        res = super(account_move, self).write(cr, uid, ids, vals, context=context)
        self._check_document_date(cr, uid, ids, context)
        self._check_date_in_period(cr, uid, ids, context)
        return res

    def post(self, cr, uid, ids, context=None):
        """
        Add document date
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # If invoice in context, we come from self.action_move_create from invoice.py. So at invoice validation step.
        if context.get('invoice', False):
            inv_info = self.pool.get('account.invoice').read(cr, uid, context.get('invoice') and context.get('invoice').id, ['document_date'])
            if inv_info.get('document_date', False):
                self.write(cr, uid, ids, {'document_date': inv_info.get('document_date')})
        res = super(account_move, self).post(cr, uid, ids, context)
        return res

    def button_validate(self, cr, uid, ids, context=None):
        """
        Check that user can approve the move by searching 'from_web_menu' in context. If present and set to True and move is manually created, so User have right to do this.
        """
        if not context:
            context = {}
        for i in ids:
            ml_ids = self.pool.get('account.move.line').search(cr, uid, [('move_id', '=', i)])
            if not ml_ids:
                raise osv.except_osv(_('Warning'), _('No line found. Please add some lines before Journal Entry validation!'))
        if context.get('from_web_menu', False):
            for m in self.browse(cr, uid, ids):
                if m.status == 'sys':
                    raise osv.except_osv(_('Warning'), _('You are not able to approve a Journal Entry that comes from the system!'))
                # UFTP-105: Do not permit to validate a journal entry on a period that is not open
                if m.period_id and m.period_id.state != 'draft':
                    raise osv.except_osv(_('Warning'), _('You cannot post entries in a non-opened period: %s') % (m.period_id.name))
                prev_currency_id = False
                for ml in m.line_id:
                    if not prev_currency_id:
                        prev_currency_id = ml.currency_id.id
                        continue
                    if ml.currency_id.id != prev_currency_id:
                        raise osv.except_osv(_('Warning'), _('You cannot have two different currencies for the same Journal Entry!'))
        return super(account_move, self).button_validate(cr, uid, ids, context=context)

    def copy(self, cr, uid, a_id, default={}, context=None):
        """
        Copy a manual journal entry
        """
        if not context:
            context = {}
        context.update({'omit_analytic_distribution': False})
        je = self.browse(cr, uid, [a_id], context=context)[0]
        if je.status == 'sys' or (je.journal_id and je.journal_id.type == 'migration'):
            raise osv.except_osv(_('Error'), _("You can only duplicate manual journal entries."))
        vals = {
            'line_id': [],
            'state': 'draft',
            'document_date': je.document_date,
            'date': je.date,
            'name': ''
        }
        res = super(account_move, self).copy(cr, uid, a_id, vals, context=context)
        for line in je.line_id:
            line_default = {
                'move_id': res,
                'document_date': je.document_date,
                'date': je.date,
                'period_id': je.period_id and je.period_id.id or False,
                'reconcile_id': False,
                'reconcile_partial_id': False,
                'reconcile_txt': False,
            }
            self.pool.get('account.move.line').copy(cr, uid, line.id,
                line_default, context)
        self.validate(cr, uid, [res], context=context)
        return res

    def onchange_journal_id(self, cr, uid, ids, journal_id=False, context=None):
        """
        Change some fields when journal is changed.
        """
        res = {}
        if not context:
            context = {}
        return res

    def onchange_period_id(self, cr, uid, ids, period_id=False, date=False, context=None):
        """
        Check that given period is open.
        """
        res = {}
        if not context:
            context = {}
        if period_id:
            data = self.pool.get('account.period').read(cr, uid, period_id, ['state', 'date_start', 'date_stop'])
            if data.get('state', False) != 'draft':
                raise osv.except_osv(_('Error'), _('Period is not open!'))
        return res

    def button_delete(self, cr, uid, ids, context=None):
        """
        Delete manual and unposted journal entries if we come from web menu
        """
        if not context:
            context = {}
        to_delete = []
        if context.get('from_web_menu', False):
            for m in self.browse(cr, uid, ids):
                if m.status == 'manu' and m.state == 'draft':
                    to_delete.append(m.id)
        # First delete move lines to avoid "check=True" problem on account_move_line item
        if to_delete:
            ml_ids = self.pool.get('account.move.line').search(cr, uid, [('move_id', 'in', to_delete)])
            if ml_ids:
                if isinstance(ml_ids, (int, long)):
                    ml_ids = [ml_ids]
                self.pool.get('account.move.line').unlink(cr, uid, ml_ids, context, check=False)
        self.unlink(cr, uid, to_delete, context, check=False)
        return True

    def get_valid_but_unbalanced(self, cr, uid, context=None):
        cr.execute("select move_id, sum(debit-credit) from account_move_line where state='valid' group by move_id having abs(sum(debit-credit)) > 0.00001")
        return [x[0] for x in cr.fetchall()]

account_move()

class account_move_reconcile(osv.osv):
    _inherit = 'account.move.reconcile'

    def get_name(self, cr, uid, context=None):
        instance = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id
        sequence_number = self.pool.get('ir.sequence').get(cr, uid, 'account.move.reconcile')
        if instance and sequence_number:
            return instance.reconcile_prefix + "-" + sequence_number
        else:
            return ''

    _columns = {
        'name': fields.char('Entry Sequence', size=64, required=True),
        'statement_line_ids': fields.many2many('account.bank.statement.line', 'account_bank_statement_line_move_rel', 'statement_id', 'move_id',
            string="Statement lines", help="This field give all statement lines linked to this move."),
    }
    _defaults = {
        'name': lambda self,cr,uid,ctx={}: self.get_name(cr, uid, ctx),
    }

account_move_reconcile()

class account_account_type(osv.osv):
    _name = 'account.account.type'
    _inherit = 'account.account.type'

    _columns = {
        'not_correctible': fields.boolean(string="Prevent entries to be correctible on this account type.")
    }

    _defaults = {
        'not_correctible': lambda *a: False,
    }

account_account_type()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
