# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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


class mission_stock_wizard(osv.osv_memory):
    _name = 'mission.stock.wizard'

    _columns = {
        'report_id': fields.many2one('stock.mission.report', string='Report'),
        'with_valuation': fields.selection([('true', 'Yes'), ('false', 'No')], string='Display stock valuation ?',
                                           required=True),
        'split_stock': fields.selection([('true', 'Yes'), ('false', 'No')], string='Split the Warehouse stock qty. to Stock and Unallocated Stock.',
                                           required=True),
        'last_update': fields.datetime(string='Last update', readonly=True),
        'export_ok': fields.boolean(string='XML Export ready'),
        'export_file': fields.binary(string='XML File'),
        'fname': fields.char('Filename',size=256),
    }

    _defaults = {
        'with_valuation': lambda *a: 'false',
        'split_stock': lambda *a: 'false',
        'fname': lambda *a: 'Mission stock report',
    }

    def default_get(self, cr, uid, fields, context=None):
        '''
        Choose the first local report as default
        '''
        res = super(mission_stock_wizard, self).default_get(cr, uid, fields, context=context)

        instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id
        if not instance_id:
            raise osv.except_osv(_('Error'), _('Mission stock report cannot be available if no instance was set on the company !'))

        local_id = self.pool.get('stock.mission.report').search(cr, uid, [('local_report', '=', True), ('full_view', '=', False)], context=context)
        if local_id:
            res['report_id'] = local_id[0]
            res['last_update'] = self.pool.get('stock.mission.report').browse(cr, uid, local_id[0], context=context).last_update
            res['export_ok'] = self.pool.get('stock.mission.report').browse(cr, uid, local_id[0], context=context).export_ok

        return res

    def report_change(self, cr, uid, ids, report_id, context=None):
        if isinstance(report_id, list):
            report_id = report_id[0]

        v = {}
        if report_id:
            report = self.pool.get('stock.mission.report').browse(cr, uid, report_id, context=context)
            v.update({'last_update': report.last_update, 'export_ok': report.export_ok})
        else:
            v.update({'last_update': False, 'export_ok': False})

        return {'value': v}

    def open_products_view(self, cr, uid, ids, context=None):
        '''
        Open the product list with report information
        '''
        if isinstance(ids, list):
            ids = ids[0]

        if not context:
            context = {}

        if not ids:
            raise osv.except_osv(_('Error'), _('You should choose a report to display.'))

        wiz_id = self.browse(cr, uid, ids, context=context)
        if not wiz_id.report_id:
            raise osv.except_osv(_('Error'), _('You should choose a report to display.'))
        if not wiz_id.report_id.last_update:
            raise osv.except_osv(_('Error'), _('The generation of this report is in progress. You could open this report when the last update field will be filled. Thank you for you comprehension.'))
        c = context.copy()
        c.update({'mission_report_id': wiz_id.report_id.id, 'with_valuation': wiz_id.with_valuation == 'true' and True or False, 'split_stock': wiz_id.split_stock == 'true' and True or False})

        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.mission.report.line',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'domain': [('mission_report_id', '=', wiz_id.report_id.id)],
                'context': c,
                'target': 'current'}

    def go_previous(self, cr, uid, ids, context=None):
        context = context or {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        return {'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'new',
                'context': context}

    def open_xml_file(self, cr, uid, ids, context=None):
        '''
        Open the XML file
        '''
        if isinstance(ids, list):
            ids = ids[0]

        if not context:
            context = {}

        if not ids:
            raise osv.except_osv(_('Error'), _('You should choose a report to display.'))

        wiz_id = self.browse(cr, uid, ids, context=context)
        if not wiz_id.report_id:
            raise osv.except_osv(_('Error'), _('You should choose a report to display.'))
        if not wiz_id.report_id.last_update:
            raise osv.except_osv(_('Error'), _('The generation of this report is in progress. You could open this report when the last update field will be filled. Thank you for your comprehension.'))

        # Get the good file according to parameters
        if wiz_id.split_stock == 'true' and wiz_id.with_valuation == 'true':
            report_file = wiz_id.report_id.s_v_file
        elif wiz_id.split_stock == 'true' and wiz_id.with_valuation == 'false':
            report_file = wiz_id.report_id.s_nv_file
        elif wiz_id.split_stock == 'false' and wiz_id.with_valuation == 'true':
            report_file = wiz_id.report_id.ns_v_file
        else:
            report_file = wiz_id.report_id.ns_nv_file

        self.write(cr, uid, [wiz_id.id], {'export_file': report_file,
                                          'fname': 'Stock_report_%s_%s.xls' % (wiz_id.report_id.name, wiz_id.report_id.last_update),
                                          }, context=context)

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'mission_stock', 'mission_stock_wizard_open_file_view')[1]
        return {'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': wiz_id.id,
                'view_id': [view_id],
                'target': 'new',
                'view_type': 'form',
                'view_mode': 'form',
                'context': context}

    def update(self, cr, uid, ids, context=None):
        ids = self.pool.get('stock.mission.report').search(cr, uid, [], context=context)
        return self.pool.get('stock.mission.report').background_update(cr, uid, ids)

mission_stock_wizard()
