# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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

import time


class stock_delivery_wizard(osv.osv_memory):
    _name = 'stock.delivery.wizard'
    _rec_name = 'report_date'

    _columns = {
        'report_date': fields.datetime(string='Date of the demand', readonly=True),
        'company_id': fields.many2one('res.company', string='Company', readonly=True),
        'moves_ids': fields.text(string='Moves', readonly=True),
        'start_date': fields.date(string='Date from'),
        'end_date': fields.date(string='Date to'),
        'partner_id': fields.many2one('res.partner', string='Partner'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Product Main Type'),
        'location_id': fields.many2one('stock.location', 'Source Location', select=True),
        'location_dest_id': fields.many2one('stock.location', 'Dest. Location', select=True),
    }

    _defaults = {
        'report_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
    }

    def get_values(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        '''
        move_obj = self.pool.get('stock.move')
        ir_data = self.pool.get('ir.model.data')

        dispatch_location = ir_data.get_object_reference(cr, uid, 'msf_outgoing', 'stock_location_dispatch')[1]

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        for wizard in self.browse(cr, uid, ids, context=context):
            move_domain = [('picking_id.type', '=', 'out'), ('product_qty', '!=', 0), '|']
            out_domain = [
                '&', '&',
                ('state', '=', 'done'),
                ('picking_id.subtype', '=', 'standard'),
                ('picking_id.state', 'in', ['done', 'delivered'])
            ]
            ppl_domain = [
                '&', '&', '&', '&', '&',
                ('location_dest_id', '!=', dispatch_location),
                ('picking_id.previous_step_id.state', '=', 'done'),
                ('picking_id.subtype', '=', 'packing'),
                ('picking_id.shipment_id', '!=', 'f'),
                ('picking_id.shipment_id.parent_id', '!=', 'f'),
                ('picking_id.shipment_id.state', 'in', ['done', 'delivered']),
            ]

            if wizard.start_date:
                out_domain.insert(0, '&')
                out_domain.append(('picking_id.date_done', '>=', wizard.start_date))
                ppl_domain.insert(0, '&')
                ppl_domain.append(('picking_id.shipment_id.shipment_actual_date', '>=', wizard.start_date))

            if wizard.end_date:
                out_domain.insert(0, '&')
                out_domain.append(('picking_id.date_done', '<=', wizard.end_date))
                ppl_domain.insert(0, '&')
                ppl_domain.append(('picking_id.shipment_id.shipment_actual_date', '<=', wizard.end_date))

            if wizard.location_id:
                out_domain.insert(0, '&')
                out_domain.append(('location_id', '=', wizard.location_id.id))
                ppl_domain.insert(0, '&')
                ppl_domain.append(('backmove_id.location_id', '=', wizard.location_id.id))

            move_domain.extend(out_domain)
            move_domain.extend(ppl_domain)

            if wizard.partner_id:
                move_domain.append(('picking_id.partner_id', '=', wizard.partner_id.id))

            if wizard.nomen_manda_0:
                move_domain.append(('product_id.nomen_manda_0', '=', wizard.nomen_manda_0.id))

            if wizard.location_dest_id:
                move_domain.append(('location_dest_id', '=', wizard.location_dest_id.id))

            move_ids = move_obj.search(cr, uid, move_domain, order='picking_id, line_number', context=context)

            if not move_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('No data found with these parameters'),
                )

            self.write(cr, uid, [wizard.id], {'moves_ids': move_ids}, context=context)

        return True

    def print_excel(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        self.get_values(cr, uid, ids, context=context)

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': _('Deliveries Report'),
            'report_name': 'stock.delivery.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context, 'target_filename': _('Deliveries Report_%s') % (time.strftime('%Y%m%d_%H_%M'),)}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'stock.delivery.report_xls',
            'datas': data,
            'context': context,
        }


stock_delivery_wizard()
