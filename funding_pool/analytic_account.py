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

class analytic_account(osv.osv):
    _name = "account.analytic.account"
    _inherit = "account.analytic.account"
    
    _columns = {
        'date_start': fields.date('Active from', required=True),
        'date': fields.date('Inactive from', select=True),
        'category': fields.selection([('OC','Cost Center'),
            ('FUNDING','Funding Pool'),
            ('FREE1','Free 1'),
            ('FREE2','Free 2')], 'Category', select=1),
        'cost_center_ids': fields.many2many('account.analytic.account', 'funding_pool_associated_cost_centers', 'funding_pool_id', 'cost_center_id', string='Cost Centers'),
        'account_ids': fields.many2many('account.account', 'funding_pool_associated_accounts', 'funding_pool_id', 'account_id', string='Accounts'),
    }
    
    _defaults ={
        'date_start': lambda *a: (datetime.datetime.today() + relativedelta(months=-3)).strftime('%Y-%m-%d')
    }

    #def _check_unicity(self, cr, uid, ids, context={}):
    #    if not context:
    #        context={}
    #    for account in self.browse(cr, uid, ids, context=context):
    #        bad_ids = self.search(cr, uid, [('category', '=', account.category),('|'),('name', '=ilike', account.name),('code', '=ilike', account.code)])
    #        if len(bad_ids) and len(bad_ids) > 1:
    #            return False
    #    return True

    #_constraints = [
    #    (_check_unicity, 'You cannot have the same code or name between analytic accounts in the same category!', ['code', 'name', 'category']),
    #]

    def copy(self, cr, uid, id, default={}, context=None, done_list=[], local=False):
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
        self._check_date(vals)
        self.set_funding_pool_parent(cr, uid, vals)
        return super(analytic_account, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        self._check_date(vals)
        self.set_funding_pool_parent(cr, uid, vals)
        return super(analytic_account, self).write(cr, uid, ids, vals, context=context)

    def search(self, cr, uid, args, offset=0, limit=None, order=None,
            context=None, count=False):
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
            
        return super(analytic_account, self).search(cr, uid, args, offset, limit,
                order, context=context, count=count)

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if not context:
            context = {}
        view = super(analytic_account, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        try:
            oc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'funding_pool', 'analytic_account_project')[1]
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
        res['domain']['parent_id'] = [('category', '=', category)]
        return res
analytic_account()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
