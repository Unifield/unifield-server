# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

import datetime
from osv import fields
from osv import osv
from tools.translate import _
from .destination_tools import many2many_sorted
from .destination_tools import many2many_notlazy
from tools.misc import flatten

class analytic_account(osv.osv):
    _name = "account.analytic.account"
    _inherit = "account.analytic.account"


    def copy_data(self, cr, uid, a_id, default=None, context=None):
        if not context:
            context = {}
        if not default:
            default = {}

        default['destination_ids'] = []

        # Copy analytic distribution
        return super(analytic_account, self).copy_data(cr, uid, a_id, default, context)

    def _get_record_id(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for id in ids:
            res[id] = id
        return res

    def _get_active(self, cr, uid, ids, field_name, args, context=None):
        '''
        If date out of date_start/date of given analytic account, then account is inactive.
        The comparison could be done via a date given in context.
        '''
        res = {}
        cmp_date = datetime.date.today().strftime('%Y-%m-%d')
        if context.get('date', False):
            cmp_date = context.get('date')
        for a in self.browse(cr, uid, ids):
            res[a.id] = True
            if a.date_start > cmp_date:
                res[a.id] = False
            if a.date and a.date <= cmp_date:
                res[a.id] = False
        return res

    def is_blocked_by_a_contract(self, cr, uid, ids):
        """
        Return ids (analytic accounts) that are blocked by a contract (just FP1)
        """
        # Some verifications
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        res = []
        for aa in self.browse(cr, uid, ids):
            # Only check funding pool accounts
            if aa.category != 'FUNDING':
                continue
            link_ids = self.pool.get('financing.contract.funding.pool.line').search(cr, uid, [('funding_pool_id', '=', aa.id)])
            format_ids = []
            for link in self.pool.get('financing.contract.funding.pool.line').browse(cr, uid, link_ids):
                if link.contract_id:
                    format_ids.append(link.contract_id.id)
            contract_ids = self.pool.get('financing.contract.contract').search(cr, uid, [('format_id', 'in', format_ids)])
            for contract in self.pool.get('financing.contract.contract').browse(cr, uid, contract_ids):
                if contract.state in ['soft_closed', 'hard_closed']:
                    res.append(aa.id)
        return res

    def _search_closed_by_a_fp(self, cr, uid, ids, name, args, context=None):
        """
        UTP-423: Do not display analytic accounts linked to a soft/hard closed contract.
        """
        res = [('id', 'not in', [])]
        if args and args[0] and len(args[0]) == 3:
            if args[0][1] != '=':
                raise osv.except_osv(_('Error'), _('Operator not supported yet!'))
            # Search all fp_ids from soft_closed contract
            sql="""SELECT a.id
                FROM account_analytic_account a, financing_contract_contract fcc, financing_contract_funding_pool_line fcfl
                WHERE fcfl.contract_id = fcc.id
                AND fcfl.funding_pool_id = a.id
                AND fcc.state in ('soft_closed', 'hard_closed');"""
            cr.execute(sql)
            sql_res = cr.fetchall()
            if sql_res:
                aa_ids = self.is_blocked_by_a_contract(cr, uid, [x and x[0] for x in sql_res])
                if aa_ids:
                    if isinstance(aa_ids, int):
                        aa_ids = [aa_ids]
                    res = [('id', 'not in', aa_ids)]
        return res

    _columns = {
        'destination_ids': many2many_notlazy('account.account', 'account_destination_link', 'destination_id', 'account_id', 'Accounts'),
        'tuple_destination_account_ids': many2many_sorted('account.destination.link', 'funding_pool_associated_destinations', 'funding_pool_id', 'tuple_id', "Account/Destination"),
        'hide_closed_fp': fields.function(_get_active, fnct_search=_search_closed_by_a_fp, type="boolean", method=True, store=False, string="Linked to a soft/hard closed contract?"),
        'record_id': fields.function(_get_record_id, method=True, type='integer', string='Database ID'),
    }

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        """
        FIXME: this method do others things that not have been documented. Please complete here what method do.
        """
        if not context:
            context = {}
        if context and 'search_by_ids' in context and context['search_by_ids']:
            args2 = args[-1][2]
            del args[-1]
            ids = []
            for arg in args2:
                ids.append(arg[1])
            args.append(('id', 'in', ids))
        # UF-1713: Active/inactive functionnality was missing.
        if context and 'filter_inactive' in context and context['filter_inactive']:
            args.append(('filter_active', '=', context['filter_inactive']))
        # Tuple Account/Destination search
        for i, arg in enumerate(args):
            if arg[0] and arg[0] == 'tuple_destination':
                fp_ids = []
                destination_ids = self.pool.get('account.destination.link').search(cr, uid,
                                                                                   [('account_id', '=', arg[2][0]),
                                                                                    ('destination_id', '=', arg[2][1]),
                                                                                       ('disabled', '=', False)],
                                                                                   order='NO_ORDER')
                for adl in self.pool.get('account.destination.link').read(cr, uid, destination_ids, ['funding_pool_ids']):
                    fp_ids.append(adl.get('funding_pool_ids'))
                fp_ids = flatten(fp_ids)
                args[i] = ('id', 'in', fp_ids)
            elif arg[0] == 'destination_ids' and arg[1] == '=':
                link_obj = self.pool.get('account.destination.link')
                link_ids = link_obj.search(cr, uid, [('account_id', '=', arg[2]), ('disabled', '=', False)],
                                           context=context, order='NO_ORDER')
                dest_ids = []
                for dest in link_obj.read(cr, uid, link_ids, ['destination_id'], context=context):
                    dest_ids.append(dest['destination_id'][0])
                args[i] = ('id', 'in', dest_ids)
        return super(analytic_account, self).search(cr, uid, args, offset,
                                                    limit, order, context=context, count=count)

analytic_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
