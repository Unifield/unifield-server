# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
from osv import fields, osv
from tools.translate import _
from time import strftime

class account_chart(osv.osv_memory):
    _inherit = "account.chart"

    def _get_fake(self, cr, uid, ids, name, args, context=None):
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            res[id] = False
        return res
        
    def _get_instance_header(self, cr, uid, ids, field_names, args,
        context=None):
        def get_codes(instance_recs):
            instance_obj = self.pool.get('msf.instance')
            if not instance_recs:
                # get mission instances
                instance_ids = instance_obj.search(cr, uid, [
                        ('instance_to_display_ids', '=', True),
                    ], context=context)
                if instance_ids:
                    instance_recs = instance_obj.browse(cr, uid, instance_ids,
                        context=context)
                else:
                    instance_recs = []
            return [ i.code for i in instance_recs ]
        
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        for rec in self.browse(cr, uid, ids, context=context):
            res[rec.id] = ', '.join(get_codes(rec.instance_ids))
        return res

    _columns = {
        'show_inactive': fields.boolean('Show inactive accounts'),
        'currency_id': fields.many2one('res.currency', 'Currency', help="Only display items from the given currency"),
        'period_from': fields.many2one('account.period', 'From'),
        'period_to': fields.many2one('account.period', 'To'),
        'target_move': fields.selection([('posted', 'Posted Entries'),
                                         ('all', 'All Entries'),
                                         ('draft', 'Unposted Entries'),
                                        ], 'Move status', required = True),
        'output_currency_id': fields.many2one('res.currency', 'Output currency', help="Add a new column that display lines amounts in the given currency"),

        # US-1179 fields
        'initial_balance': fields.boolean("Include initial balances",
            help='It adds initial balance row on report which display previous sum amount of debit/credit/balance'),
        'is_initial_balance_available': fields.function(_get_fake, method=True,
            type='boolean', string="Is initial balance filter available ?"),
        'account_type': fields.selection([
            ('all', 'All'),
            ('pl', 'Profit & Loss'),
            ('bs', 'Balance Sheet'),
        ], 'B/S / P&L account', required=True),
        'granularity': fields.selection([
            ('account', 'By account'),
            ('parent', 'By parent account'),
        ], 'Granularity', required=True),
        'instance_header': fields.function(_get_instance_header, type='string',
            method=True, string='Instances'),
    }

    _defaults = {
        'show_inactive': lambda *a: False,
        'fiscalyear': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, datetime.date.today(), False, c),
        'is_initial_balance_available': True,
        'account_type': 'all',
        'granularity': 'parent',
    }

    def on_change_period(self, cr, uid, ids, period_from, fiscalyear_id,
        context=None):
        res = {}

        ib_available = fiscalyear_id
        if ib_available:
            if period_from:
                # allow IB entries if a FY selected and period start = FY 1st period
                fy_rec = self.pool.get('account.fiscalyear').browse(cr, uid,
                    fiscalyear_id, context=context)
                period_from_rec = self.pool.get('account.period').browse(cr,
                    uid, period_from, context=context)
                ib_available = period_from_rec.date_start == fy_rec.date_start
            else:
                ib_available = False

        res['value'] = {'is_initial_balance_available': ib_available, }
        if not ib_available:
            res['value']['initial_balance'] = False
        return res

    def _update_context(self, cr, uid, rec, context=None):
        if isinstance(rec, (list, tuple, )):
            rec = self.browse(cr, uid, rec[0], context=context)

        if rec.initial_balance:
            # include IB entries
            context['period0'] = True

    def account_chart_open_window(self, cr, uid, ids, context=None):
        result = super(account_chart, self).account_chart_open_window(cr, uid, ids, context=context)

        account_obj = self.pool.get('account.account')
        
        # add 'active_test' to the result's context; this allows to show or hide inactive items
        data = self.read(cr, uid, ids, [], context=context)[0]
        context = eval(result['context'])
        context['filter_inactive_accounts'] = not data['show_inactive']
        if data['currency_id']:
            context['currency_id'] = data['currency_id']

        # Search regarding move state. Delete original 'state' one
        if 'state' in context:
            del context['state']
        if data['target_move']:
            if data['target_move'] != 'all':
                context['move_state'] = data['target_move']
        if data['output_currency_id']:
            context['output_currency_id'] = data['output_currency_id']
        is_flat_view = data['granularity'] \
            and data['granularity'] == 'account' or False

        self._update_context(cr, uid, ids, context=context)
        result['context'] = unicode(context)

        domain_tuples_str = []
        if data['account_type']:
            if data['account_type'] == 'pl':
                rt = [ 'income', 'expense', ]
            elif data['account_type'] == 'bs':
                rt = [ 'asset', 'liability', ]
            else:
                rt = False

            if rt:
                at_domain = [
                    ('report_type', 'in' , rt),
                ]
                if 'asset' in rt or 'liability' in rt:
                    # US-227 include tax account for BS accounts selection
                    at_domain = [ '|', ('code', '=', 'tax') ] + at_domain
                account_types_ids = self.pool.get(
                    'account.account.type').search(cr, uid, at_domain,
                        context=context)
                if account_types_ids:
                    account_ids = account_obj.search(cr, uid, [
                            ('user_type', 'in', account_types_ids),
                        ], context=context)
                    if account_ids:
                        is_flat_view = True  # disable tree mode
                        """if not is_flat_view:
                            account_ids = account_obj._get_parent_of(cr, uid,
                                account_ids, context=context)"""
                        domain_tuples_str.append("('id', 'in', [%s])" % (
                            ','.join(map(str, account_ids)), ))

        xmlid = 'balance_account_tree'
        if is_flat_view:
            # flat version, not drillable, only final accounts
            xmlid = 'balance_account_flat'
            domain_tuples_str.append("('type', '!=', 'view')")
            result['domain'] = ''  # cancel drillable tree view start domain
        try:
            tree_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_override', xmlid) or False
        except:
            # Exception is for account tests that attempt to read balance_account_tree that doesn't exists
            tree_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'view_account_tree')
        finally:
            tree_view_id = tree_view_id and tree_view_id[1] or False
        result['view_id'] = [tree_view_id]
        result['views'] = [(tree_view_id, 'tree')]
        if domain_tuples_str:
           if not is_flat_view:
                domain_tuples_str.insert(0, "('parent_id','=',False)")
           result['domain'] = "[%s]" % (', '.join(domain_tuples_str), )
        return result

    def button_export(self, cr, uid, ids, context=None):
        """
        Export chart of account in a XML file
        """
        if not context:
            context = {}
        account_ids = []
        wiz_fields = {}
        target_move = ''
        for wiz in self.browse(cr, uid, ids):
            args = [('active', '=', True)]
            if wiz.show_inactive == True:
                args.append(('active', 'in', [True, False]))
            if wiz.granularity and wiz.granularity == 'account':
                args.append(('type', '!=', 'view'))

            if wiz.currency_id:
                context.update({'currency_id': wiz.currency_id.id,})
            if wiz.instance_ids:
                context.update({'instance_ids': [x.id for x in wiz.instance_ids],})
            if wiz.target_move and wiz.target_move != 'all':
                context.update({'move_state': wiz.target_move})
            if wiz.output_currency_id:
                context.update({'output_currency_id': wiz.output_currency_id.id})
            if wiz.fiscalyear:
                context['fiscalyear'] = wiz.fiscalyear.id
            if wiz.period_from:
                context['period_from'] = wiz.period_from.id
            if wiz.period_to:
                context['period_to'] = wiz.period_to.id
            self._update_context(cr, uid, wiz, context=context)

            account_ids = self.pool.get('account.account').search(cr, uid, args, context=context)
            # fetch target move value
            o = wiz
            field = 'target_move'
            sel = self.pool.get(o._name).fields_get(cr, uid, [field])
            target_move = dict(sel[field]['selection']).get(getattr(o,field),getattr(o,field))
            name = '%s,%s' % (o._name, field)
            tr_ids = self.pool.get('ir.translation').search(cr, uid, [('type', '=', 'selection'), ('name', '=', name),('src', '=', target_move)])
            if tr_ids:
                target_move = self.pool.get('ir.translation').read(cr, uid, tr_ids, ['value'])[0]['value']
            # Prepare a dict to keep all wizard fields values
            wiz_fields = {
                'fy': wiz.fiscalyear and wiz.fiscalyear.name or '',
                'target': target_move or '',
                'initial_balance': wiz.initial_balance,
                'period_from': wiz.period_from and wiz.period_from.name or '',
                'period_to': wiz.period_to and wiz.period_to.name or '',
                'instance_header': wiz.instance_header,
                'show_inactive': wiz.show_inactive,
                'currency_filtering': wiz.currency_id and wiz.currency_id.name or _('All'),
                'account_type': wiz.account_type,
                'granularity': wiz.granularity,
                'instance_header': wiz.instance_header,
            }
        # UF-1718: Add currency name used from the wizard. If none, set it to "All" (no currency filtering)
        currency_name = _("No one specified")
        if context.get('output_currency_id', False):
            currency_name = self.pool.get('res.currency').browse(cr, uid, context.get('output_currency_id')).name or currency_name
        else:
            currency_name = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.name or currency_name
        # Prepare datas for the report
        instance_code = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id.code
        datas = {
            'ids': account_ids,
            'context': context,
            'currency': currency_name,
            'wiz_fields': wiz_fields,
            'target_filename': "Balance by account_%s_%s" % (instance_code, strftime('%Y%m%d')),
        } # context permit balance to be processed regarding context's elements
# filename
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.chart.export',
            'datas': datas,
        }

account_chart()

class account_coa(osv.osv_memory):
    _name = 'account.coa'
    _columns = {
        'fiscalyear': fields.many2one('account.fiscalyear', 'Fiscalyear'),
        'show_inactive': fields.boolean('Show inactive accounts'),
    }

    _defaults = {
        'show_inactive': lambda *a: False,
        'fiscalyear': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, datetime.date.today(), False, c),
    }

    def button_validate(self, cr, uid, ids, context=None):
        """
        Open a chart of accounts as a tree/tree.
        """
        # Some checks
        if not context:
            context = {}
        # Prepare some values
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')
        period_obj = self.pool.get('account.period')
        fy_obj = self.pool.get('account.fiscalyear')
        data = self.read(cr, uid, ids, [], context=context)[0]
        # Set period_from/to if fiscalyear given
        if data['fiscalyear']:
            periods = self.pool.get('account.chart').onchange_fiscalyear(cr, uid, ids, data['fiscalyear'], context)
            if 'value' in periods:
                data.update(periods.get('value'))
        # Create result
        result = mod_obj.get_object_reference(cr, uid, 'account', 'action_account_tree')
        view_id = result and result[1] or False
        result = act_obj.read(cr, uid, [view_id], context=context)[0]
        result['periods'] = []
        if data.get('period_from', False) and data.get('period_to', False):
            result['periods'] = period_obj.build_ctx_periods(cr, uid, data['period_from'], data['period_to'])
        result['context'] = str({'fiscalyear': data['fiscalyear'], 'periods': result['periods']})
        result['name'] = _('Chart of Accounts')
        if data['fiscalyear']:
            result['name'] += ': ' + fy_obj.read(cr, uid, [data['fiscalyear']], context=context)[0]['code']
        # Set context regarding show_inactive field
        context['filter_inactive_accounts'] = not data['show_inactive']
        result['context'] = unicode(context)
        # UF-1718: Add a link on each account to display linked journal items
        tree_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'view_account_tree')
        tree_view_id = tree_view_id and tree_view_id[1] or False
        result['view_id'] = [tree_view_id]
        result['views'] = [(tree_view_id, 'tree')]
        return result

account_coa()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
