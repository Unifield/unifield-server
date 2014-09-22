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
    }

    def account_chart_open_window(self, cr, uid, ids, context=None):

        result = super(account_chart, self).account_chart_open_window(cr, uid, ids, context=context)
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
        result['context'] = unicode(context)
        # UF-1718: Add a link on each account to display linked journal items
        try:
            tree_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_override', 'balance_account_tree') or False
        except:
            # Exception is for account tests that attempt to read balance_account_tree that doesn't exists
            tree_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'view_account_tree')
        finally:
            tree_view_id = tree_view_id and tree_view_id[1] or False
        result['view_id'] = [tree_view_id]
        result['views'] = [(tree_view_id, 'tree')]
        return result

    _defaults = {
        'show_inactive': lambda *a: False,
        'fiscalyear': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, datetime.date.today(), False, c),
    }

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
                args += [('active', 'in', [True, False])]
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
                'period_from': wiz.period_from and wiz.period_from.name or '',
                'period_to': wiz.period_to and wiz.period_to.name or '',
                'instances': wiz.instance_ids and ','.join([x.name for x in wiz.instance_ids]) or '',
                'show_inactive': wiz.show_inactive and 'X' or '',
                'currency_filtering': wiz.currency_id and wiz.currency_id.name or '',
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
