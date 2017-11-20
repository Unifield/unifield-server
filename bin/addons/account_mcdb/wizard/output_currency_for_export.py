#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
from tools.translate import _
from lxml import etree

import time

class output_currency_for_export(osv.osv_memory):
    _name = 'output.currency.for.export'
    _description = 'Output currency choice wizard'

    _columns = {
        'currency_id': fields.many2one('res.currency', string="Output currency", help="Give an output currency that would be used for export", required=False),
        'fx_table_id': fields.many2one('res.currency.table', string="FX Table", required=False),
        'export_format': fields.selection([('xls', 'Excel'), ('csv', 'CSV'), ('pdf', 'PDF')], string="Export format", required=True),
        'domain': fields.text('Domain'),
        'export_selected': fields.boolean('Export only the selected items', help="The output is limited to 5000 records"),
        'state': fields.selection([('normal', 'Analytic Journal Items'), ('free', 'Free 1/Free 2')]),
        'background_time': fields.integer('Number of second before background processing'),
    }

    _defaults = {
        'export_format': lambda *a: 'xls',
        'domain': lambda cr, u, ids, c: c and c.get('search_domain',[]),
        'export_selected': lambda *a: False,
        'state': lambda *a: 'normal',
        'background_time': lambda *a: 20,
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Remove export_format for FREE1/FREE2 analytic accounts because it has no sens.
        """
        view = super(output_currency_for_export, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type == 'form' and context and context.get('active_ids', False) and context.get('from', False):
            if context.get('from') == 'account.analytic.line':
                ids = context.get('active_ids')
                if isinstance(ids, (int, long)):
                    ids = [ids]
                first_line = self.pool.get('account.analytic.line').browse(cr, uid, ids)[0]
                if first_line.account_id and first_line.account_id.category in ['FREE1', 'FREE2']:
                    tree = etree.fromstring(view['arch'])
                    fields = tree.xpath("/form/field[@name='export_format']")
                    for field in fields:
                        field.set('invisible', "1")
                    view['arch'] = etree.tostring(tree)
        return view

    def create(self, cr, uid, vals, context=None):
        """
        Check first given line to see if we come from Analytic Journal Items or Free1/Free2.
        This is to change state field value and permit to show the right export (for Free1/Free2)
        """
        if not context:
            context = {}
        if context.get('active_ids', False) and context.get('from', False):
            if context.get('from') == 'account.analytic.line':
                a_ids = context.get('active_ids')
                if isinstance(a_ids, (int, long)):
                    a_ids = [a_ids]
                first_line = self.pool.get('account.analytic.line').browse(cr, uid, a_ids)[0]
                if first_line.account_id and first_line.account_id.category in ['FREE1', 'FREE2']:
                    vals.update({'state': 'free'})
        return super(output_currency_for_export, self).create(cr, uid, vals, context=context)

    def onchange_fx_table(self, cr, uid, ids, fx_table_id, context=None):
        """
        Update output currency domain in order to show right currencies attached to given fx table
        """
        res = {}
        # Some verifications
        if not context:
            context = {}
        if fx_table_id:
            res.update({'domain': {'currency_id': [('currency_table_id', '=', fx_table_id), ('active', 'in', ['True', 'False'])]}, 'value': {'currency_id' : False}})
        return res

    def button_validate(self, cr, uid, ids, context=None, data_from_selector={}):
        """
        Launch export wizard
        """
        # Some verifications
        if (not context or not context.get('active_ids', False) or not context.get('active_model', False)) and not data_from_selector:
            raise osv.except_osv(_('Error'), _('An error has occurred. Please contact an administrator.'))
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        model = data_from_selector.get('model') or context.get('active_model')
        display_fp = context.get('display_fp', False)
        wiz = currency_id = choice = False
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        company_currency = user and user.company_id and user.company_id.currency_id and user.company_id.currency_id.id or False
        if data_from_selector:
            currency_id = 'output_currency_id' in data_from_selector and data_from_selector['output_currency_id'] or company_currency
            choice = data_from_selector.get('export_format')
        else:
            wiz = self.browse(cr, uid, ids, context=context)[0]
            currency_id = wiz and wiz.currency_id and wiz.currency_id.id or company_currency
            choice = wiz and wiz.export_format or False
            if not choice:
                raise osv.except_osv(_('Error'), _('Please choose an export format!'))
        datas = {}
        # Check user choice
        if data_from_selector and data_from_selector.get('ids'):
            datas = {'ids': data_from_selector['ids']}
        elif wiz and wiz.export_selected:
            datas = {'ids': context.get('active_ids', [])}
        else:
            #export_obj = self.pool.get(model)
            #args = context.get('search_domain')
            #datas = {'ids': export_obj.search(cr, uid, args, context=context)}
            context['from_domain'] = True
        # Update context with wizard currency or default currency
        context.update({'output_currency_id': currency_id})
        # Update datas for context
        datas.update({'context': context})
        display_output_curr = data_from_selector and data_from_selector.get('output_currency_id') or wiz and wiz.currency_id
        if display_output_curr:
            # seems that there is a bug on context, so using datas permit to transmit info
            datas.update({'output_currency_id': currency_id, 'context': context})
        # Update report name if come from analytic
        report_name = 'account.move.line'
        if data_from_selector:
            if model == 'account.move.line':
                report_name = 'gl.selector'
            else:
                report_name = 'analytic.selector'
        elif model == 'account.analytic.line':
            report_name = 'account.analytic.line'
        elif model == 'account.bank.statement.line':
            report_name = 'account.bank.statement.line'

        context.update({'display_fp': display_fp})

        if not data_from_selector and model == 'account.analytic.line' and wiz and wiz.state == 'free':
            report_name = 'account.analytic.line.free'
            context.update({'display_fp': False})

        if choice == 'csv':
            report_name += '_csv'
        elif choice == 'xls':
            report_name += '_xls'

        filename = data_from_selector.get('target_filename') or '%s_%s' % (context.get('target_filename_prefix', 'Export_search_result'), time.strftime('%Y%m%d'))
        datas['target_filename'] = filename

        if model in ('account.move.line', 'account.analytic.line') and choice in ('csv', 'xls', 'pdf'):
            background_id = self.pool.get('memory.background.report').create(cr, uid, {'file_name': datas['target_filename'], 'report_name': report_name}, context=context)
            context['background_id'] = background_id
            context['background_time'] = wiz and wiz.background_time or 2
        if data_from_selector:
            context['from_selector'] = True
            if data_from_selector.get('header'):
                datas['header'] = data_from_selector['header']
        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
            'context': context,
        }

output_currency_for_export()

class background_report(osv.osv_memory):
    _name = 'memory.background.report'
    _description = 'Report result'

    _columns = {
        'file_name': fields.char('Filename', size=256),
        'report_name': fields.char('Report Name', size=256),
        'report_id': fields.integer('Report id'),
        'percent': fields.float('Percent'),
        'finished': fields.boolean('Finished'),
    }

    _defaults = {
        'file_name': lambda *a: '',
        'report_name': lambda *a: '',
        'report_id': lambda *a: '',
        'percent': lambda *a: 0,
        'finished': lambda *a: False,
    }

    def update_percent(self, cr, uid, ids, percent, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if percent > 1.00:
            percent = 1.00
        self.write(cr, uid, ids, {'percent': percent})




background_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
