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
from osv import fields, osv
from tools.translate import _
from time import strftime

class account_analytic_chart(osv.osv_memory):
    _inherit = "account.analytic.chart"

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
        'fiscalyear': fields.many2one('account.fiscalyear', 'Fiscal year', help = 'Keep empty for all open fiscal years'),
        'output_currency_id': fields.many2one('res.currency', 'Output currency', help="Add a new column that display lines amounts in the given currency"),
        'period_from': fields.many2one('account.period', 'From',
                                       domain="[('fiscalyear_id', '=', fiscalyear)]"),
        'period_to': fields.many2one('account.period', 'To',
                                     domain="[('fiscalyear_id', '=', fiscalyear)]"),

        # US-1179 fields
        'granularity': fields.selection([
            ('account', 'By analytic account'),
            ('parent', 'By parent account'),
        ], 'Granularity', required=True),
        'instance_header': fields.function(_get_instance_header, type='string',
                                           method=True, string='Instances'),
    }

    _defaults = {
        'fiscalyear': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, datetime.date.today(), False, c),
        'granularity': 'parent',
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        res = super(account_analytic_chart, self).default_get(cr, uid, fields,
                                                              context=context, from_web=from_web)

        fy_id = res.get('fiscalyear', False)
        if fy_id:
            oc_rec = self.onchange_fiscalyear(cr, uid, False,
                                              fiscalyear_id=fy_id, context=context)
            if oc_rec and oc_rec.get('value', False):
                res.update({
                    'period_from': oc_rec['value'].get('period_from', False),
                    'period_to': oc_rec['value'].get('period_to', False),
                })

        return res

    def onchange_fiscalyear(self, cr, uid, ids, fiscalyear_id=False, context=None):
        res = {}
        res['value'] = {}

        # restrict periods to fiscal year
        domain = fiscalyear_id \
            and [ ('fiscalyear_id', '=', fiscalyear_id), ] or False
        res['domain'] = {
            'period_from': domain,
            'period_to': domain,
        }

        if fiscalyear_id:
            res['value'] = self.pool.get('account.fiscalyear')._get_normal_period_from_to(cr, uid, fiscalyear_id, context)

        return res

    def analytic_account_chart_open_window(self, cr, uid, ids, context=None):
        result = super(account_analytic_chart, self).analytic_account_chart_open_window(cr, uid, ids, context=context)
        # add 'active_test' to the result's context; this allows to show or hide inactive items
        context = eval(result['context'])
        wiz = self.browse(cr, uid, ids, context=context)[0]
        if wiz.period_from:
            context['from_date'] = wiz.period_from.date_start
        if wiz.period_to:
            context['to_date'] = wiz.period_to.date_stop
        if wiz.period_from and wiz.period_to and \
                wiz.period_from.date_start > wiz.period_to.date_start:
            raise osv.except_osv(_("Warning"),
                                 _("'From' period can not be after 'To' period"))
        context['filter_inactive'] = not wiz.show_inactive
        if wiz.currency_id:
            context['currency_id'] = wiz.currency_id.id
        result['name'] = _('Balance by analytic account')
        if wiz.fiscalyear:
            result['name'] += ': ' + wiz.fiscalyear.code
        if wiz.output_currency_id:
            context['output_currency_id'] = wiz.output_currency_id.id
        # Display FP on result
        context['display_fp'] = True
        result['context'] = unicode(context)
        xmlid = 'balance_analytic_tree'
        if wiz.granularity and wiz.granularity == 'account':
            # flat version, not drillable, only final accounts
            xmlid = 'balance_analytic_flat'
            result['domain'] = "[ ('type', '!=', 'view'), ]"
        try:
            tree_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', xmlid)
        except:
            tree_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'view_account_analytic_account_tree')
        finally:
            tree_view_id = tree_view_id and tree_view_id[1] or False
        result['view_id'] = [tree_view_id]
        result['views'] = [(tree_view_id, 'tree')]
        result['keep_open'] = 1
        return result

    def button_export(self, cr, uid, ids, context=None):
        """
        Export chart of analytic account in a XML file
        """
        if not context:
            context = {}
        account_ids = []
        wiz_fields = {}
        for wiz in self.browse(cr, uid, ids):
            #args = [('filter_active', '=', True)]
            #if wiz.show_inactive == True:
            #    args = [('filter_active', 'in', [True, False])]
            #context.update({'filter_inactive': not wiz.show_inactive})

            args = []
            context['filter_inactive'] = not wiz.show_inactive
            if wiz.granularity and wiz.granularity == 'account':
                args.append(('type', '!=', 'view'))

            if wiz.period_from and wiz.period_to and \
                    wiz.period_from.date_start > wiz.period_to.date_start:
                raise osv.except_osv(_("Warning"),
                                     _("'From' period can not be after 'To' period"))

            if wiz.currency_id:
                context.update({'currency_id': wiz.currency_id.id,})
            if wiz.instance_ids:
                context.update({'instance_ids': [x.id for x in wiz.instance_ids],})
            if wiz.output_currency_id:
                context.update({'output_currency_id': wiz.output_currency_id.id})
            if wiz.period_from:
                context['from_date'] = wiz.period_from.date_start
            if wiz.period_to:
                context['to_date'] = wiz.period_to.date_stop
            account_ids = self.pool.get('account.analytic.account').search(cr, uid, args, context=context)
            wiz_fields = {
                'fy': wiz.fiscalyear and wiz.fiscalyear.name or '',
                'period_from': wiz.period_from and wiz.period_from.date_start or False,
                'period_to': wiz.period_to and wiz.period_to.date_stop or False,
                'from_period_header': wiz.period_from and wiz.period_from.name or False,
                'to_period_header': wiz.period_to and wiz.period_to.name or False,
                'from_date': wiz.period_from and wiz.period_from.date_start or '',
                'to_date': wiz.period_to and wiz.period_to.date_stop or '',
                'show_inactive': wiz.show_inactive,
                'currency_filtering': wiz.currency_id and wiz.currency_id.name or _('All'),
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
            'target_filename': "Balance by analytic account_%s_%s" % (instance_code, strftime('%Y%m%d')),
            'keep_open': 1,
        } # context permit balance to be processed regarding context's elements
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.analytic.chart.export',
            'datas': datas,
        }

account_analytic_chart()

class account_analytic_coa(osv.osv_memory):
    _name = 'account.analytic.coa'
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
        Open a chart of analytic account as a tree/tree
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
            periods = self.pool.get('account.analytic.chart').onchange_fiscalyear(cr, uid, ids, data['fiscalyear'], context)
            if 'value' in periods:
                data.update(periods.get('value'))
        # Create result
        result = mod_obj.get_object_reference(cr, uid, 'account', 'action_account_analytic_account_tree2')
        i = result and result[1] or False
        result = act_obj.read(cr, uid, [i], context=context)[0]
        result['periods'] = []
        if data.get('period_from', False) and data.get('period_to', False):
            result['periods'] = period_obj.build_ctx_periods(cr, uid, data['period_from'], data['period_to'])
        result['context'] = str({'fiscalyear': data['fiscalyear'], 'periods': result['periods']})
        result['name'] = _('Chart of Analytic Accounts')
        if data['fiscalyear']:
            result['name'] += ': ' + fy_obj.read(cr, uid, [data['fiscalyear']], context=context)[0]['code']
        # Set context regarding show_inactive field
        context['filter_inactive'] = not data['show_inactive']
        # Display FP on result
        context['display_fp'] = True
        result['context'] = unicode(context)
        # UF-1718: Add a link on each account to display linked analytic items
        tree_view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'view_account_analytic_account_tree_coa')
        tree_view_id = tree_view_id and tree_view_id[1] or False
        result['view_id'] = [tree_view_id]
        result['views'] = [(tree_view_id, 'tree')]
        return result

account_analytic_coa()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
