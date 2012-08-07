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
from dateutil.relativedelta import relativedelta
from osv import fields, osv
from tools.translate import _
from lxml import etree
from tools.misc import flatten
from destination_tools import many2many_sorted

class analytic_account(osv.osv):
    _name = "account.analytic.account"
    _inherit = "account.analytic.account"
    
    _columns = {
        'name': fields.char('Name', size=128, required=True),
        'code': fields.char('Code', size=24),
        'type': fields.selection([('view','View'), ('normal','Normal')], 'Type', help='If you select the View Type, it means you won\'t allow to create journal entries using that account.'),
        'date_start': fields.date('Active from', required=True),
        'date': fields.date('Inactive from', select=True),
        'category': fields.selection([('OC','Cost Center'),
            ('FUNDING','Funding Pool'),
            ('FREE1','Free 1'),
            ('FREE2','Free 2'),
            ('DEST', 'Destination')], 'Category', select=1),
        'cost_center_ids': fields.many2many('account.analytic.account', 'funding_pool_associated_cost_centers', 'funding_pool_id', 'cost_center_id', string='Cost Centers', domain="[('type', '!=', 'view'), ('category', '=', 'OC')]"),
        'for_fx_gain_loss': fields.boolean(string="For FX gain/loss", help="Is this account for default FX gain/loss?"),
        'destination_ids': fields.many2many('account.account', 'account_destination_link', 'destination_id', 'account_id', 'Accounts'),
        'tuple_destination_account_ids': many2many_sorted('account.destination.link', 'funding_pool_associated_destinations', 'funding_pool_id', 'tuple_id', "Account/Destination"),
        'tuple_destination_summary': fields.one2many('account.destination.summary', 'funding_pool_id', 'Destination by accounts'),
    }
    
    _defaults ={
        'date_start': lambda *a: (datetime.datetime.today() + relativedelta(months=-3)).strftime('%Y-%m-%d'),
        'for_fx_gain_loss': lambda *a: False,
    }
    def _check_unicity(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for account in self.browse(cr, uid, ids, context=context):
            bad_ids = self.search(cr, uid, [('category', '=', account.category),('|'),('name', '=ilike', account.name),('code', '=ilike', account.code)])
            if len(bad_ids) and len(bad_ids) > 1:
                return False
        return True

    def _check_gain_loss_account_unicity(self, cr, uid, ids, context=None):
        """
        Check that no more account is "for_fx_gain_loss" available.
        """
        if not context:
            context = {}
        search_ids = self.search(cr, uid, [('for_fx_gain_loss', '=', True)])
        if search_ids and len(search_ids) > 1:
            return False
        return True

    def _check_gain_loss_account_type(self, cr, uid, ids, context=None):
        """
        Check account type for fx_gain_loss_account: should be Normal type and Cost Center category
        """
        if not context:
            context = {}
        for account in self.browse(cr, uid, ids, context=context):
            if account.for_fx_gain_loss == True and (account.type != 'normal' or account.category != 'OC'):
                return False
        return True

    _constraints = [
        (_check_unicity, 'You cannot have the same code or name between analytic accounts in the same category!', ['code', 'name', 'category']),
        (_check_gain_loss_account_unicity, 'You can only have one account used for FX gain/loss!', ['for_fx_gain_loss']),
        (_check_gain_loss_account_type, 'You have to use a Normal account type and Cost Center category for FX gain/loss!', ['for_fx_gain_loss']),
    ]

    def copy(self, cr, uid, id, default=None, context=None, done_list=[], local=False):
        account = self.browse(cr, uid, id, context=context)
        if not default:
            default = {}
        default = default.copy()
        default['code'] = (account['code'] or '') + '(copy)'
        default['name'] = (account['name'] or '') + '(copy)'
        return super(analytic_account, self).copy(cr, uid, id, default, context=context)
    
    def set_funding_pool_parent(self, cr, uid, vals):
        if 'category' in vals and \
           'code' in vals and \
            vals['category'] == 'FUNDING' and \
            vals['code'] != 'FUNDING':
            # for all accounts except the parent one
            funding_pool_parent = self.search(cr, uid, [('category', '=', 'FUNDING'), ('parent_id', '=', False)])[0]
            vals['parent_id'] = funding_pool_parent

    def _check_date(self, vals):
        if 'date' in vals and vals['date'] is not False:
            if vals['date'] <= datetime.date.today().strftime('%Y-%m-%d'):
                 # validate the date (must be > today)
                 raise osv.except_osv(_('Warning !'), _('You cannot set an inactivity date lower than tomorrow!'))
            elif 'date_start' in vals and not vals['date_start'] < vals['date']:
                # validate that activation date 
                raise osv.except_osv(_('Warning !'), _('Activation date must be lower than inactivation date!'))

    def create(self, cr, uid, vals, context=None):
        """
        Some verifications before analytic account creation
        """
        self._check_date(vals)
        self.set_funding_pool_parent(cr, uid, vals)
        return super(analytic_account, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        """
        Some verifications before analytic account write
        """
        self._check_date(vals)
        self.set_funding_pool_parent(cr, uid, vals)
        return super(analytic_account, self).write(cr, uid, ids, vals, context=context)
    
    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        """
        No description found
        """
        if context and 'filter_inactive_accounts' in context and context['filter_inactive_accounts']:
            args.append(('date_start', '<=', datetime.date.today().strftime('%Y-%m-%d')))
            args.append('|')
            args.append(('date', '>', datetime.date.today().strftime('%Y-%m-%d')))
            args.append(('date', '=', False))
            
        if context and 'search_by_ids' in context and context['search_by_ids']:
            args2 = args[-1][2]
            del args[-1]
            ids = []
            for arg in args2:
                ids.append(arg[1])
            args.append(('id', 'in', ids))
        
        # Tuple Account/Destination search
        for i, arg in enumerate(args):
            if arg[0] and arg[0] == 'tuple_destination':
                fp_ids = []
                destination_ids = self.pool.get('account.destination.link').search(cr, uid, [('account_id', '=', arg[2][0]), ('destination_id', '=', arg[2][1])])
                for adl in self.pool.get('account.destination.link').read(cr, uid, destination_ids, ['funding_pool_ids']):
                    fp_ids.append(adl.get('funding_pool_ids'))
                fp_ids = flatten(fp_ids)
                args[i] = ('id', 'in', fp_ids)
        return super(analytic_account, self).search(cr, uid, args, offset, limit, order, context=context, count=count)
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if not context:
            context = {}
        view = super(analytic_account, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        try:
            oc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project')[1]
        except ValueError:
            oc_id = 0
        if view_type=='form':
            tree = etree.fromstring(view['arch'])
            fields = tree.xpath('/form/field[@name="cost_center_ids"]')
            for field in fields:
                field.set('domain', "[('type', '!=', 'view'), ('id', 'child_of', [%s])]" % oc_id)
            view['arch'] = etree.tostring(tree)
        return view
    
    def on_change_category(self, cr, uid, id, category):
        if not category:
            return {}
        res = {'value': {}, 'domain': {}}
        parent = self.search(cr, uid, [('category', '=', category), ('parent_id', '=', False)])[0]
        res['value']['parent_id'] = parent
        res['domain']['parent_id'] = [('category', '=', category), ('type', '=', 'view')]
        return res
    
    def unlink(self, cr, uid, ids, context=None):
        """
        Delete the dummy analytic account is forbidden!
        """
        # Some verification
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        analytic_accounts = []
        # Search dummy CC that have xml_id: analytic_account_project_dummy
        try:
            dummy_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project_dummy')[1]
        except ValueError:
            dummy_id = 0
        analytic_accounts.append(dummy_id)
        # Search OC CC
        try:
            oc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project')[1]
        except ValueError:
            oc_id = 0
        analytic_accounts.append(oc_id)
        # Search Funding Pool
        try:
            fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_funding_pool')[1]
        except ValueError:
            fp_id = 0
        analytic_accounts.append(fp_id)
        # Search Free 1
        try:
            f1_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_free_1')[1]
        except ValueError:
            f1_id = 0
        analytic_accounts.append(f1_id)
        # Search Free 2
        try:
            f2_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_free_2')[1]
        except ValueError:
            f2_id = 0
        analytic_accounts.append(f2_id)
        # Search MSF Private Fund
        try:
            msf_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            msf_id = 0
        analytic_accounts.append(msf_id)
        # Accounts verification
        for id in ids:
            if id in analytic_accounts:
                raise osv.except_osv(_('Error'), _('You cannot delete this Analytic Account!'))
        return super(analytic_account, self).unlink(cr, uid, ids, context=context)

    def is_blocked_by_a_contract(self, cr, uid, ids):
        """
        Return ids (analytic accounts) that are blocked by a contract (just FP1)
        """
        # Some verifications
        if isinstance(ids, (int, long)):
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

analytic_account()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
