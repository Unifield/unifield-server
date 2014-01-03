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

# Server imports
from osv import osv
from osv import fields
from tools.translate import _

# Module imports
from msf_order_date import TRANSPORT_TYPE


class wizard_import_in_simulation_screen(osv.osv):
    _name = 'wizard.import.in.simulation.screen'

    def _get_related_values(self, cr, uid, ids, field_name, args, context=None):
        '''
        Get the values related to the picking
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for simu in self.browse(cr, uid, ids, context=context):
            res[simu.id] = {'origin': simu.picking_id.origin,
                            'creation_date': simu.picking_id.date,
                            'purchase_id': simu.picking_id.purchase_id and simu.picking_id.purchase_id.id or False,
                            'backorder_id': simu.picking_id.backorder_id and simu.picking_id.backorder_id.id or False,
                            'header_notes': simu.picking_id.note,
                            'freight_number': simu.picking_id.shipment_ref,
                            'transport_mode': simu.picking_id and simu.picking_id.purchase_id and simu.picking_id.purchase_id.transport_mode or False}

        return res

    _columns = {
        'picking_id': fields.many2one('stock.picking', string='Incoming shipment', required=True, readonly=True),
        # Related fields
        'origin': fields.function(_get_related_values, method=True, string='Origin',
                                  readonly=True, type='char', size=128, multi='related'),
        'creation_date': fields.function(_get_related_values, method=True, string='Creation date',
                                         readonly=True, type='datetime', multi='related'),
        'purchase_id': fields.function(_get_related_values, method=True, string='Purchase Order',
                                       readonly=True, type='many2one', relation='purchase.order', multi='related'),
        'backorder_id': fields.function(_get_related_values, method=True, string='Back Order Of',
                                        readonly=True, type='many2one', relation='stock.picking', multi='related'),
        'header_notes': fields.function(_get_related_values, method=True, string='Header notes',
                                        readonly=True, type='text', multi='related'),
        'freight_number': fields.function(_get_related_values, method=True, string='Freight number',
                                          readonly=True, type='char', size=128, multi='related'),
        'transport_mode': fields.function(_get_related_values, method=True, string='Transport mode',
                                          readonly=True, type='selection', selection=TRANSPORT_TYPE, multi='related'),
        # Import fields
        'message_esc': fields.text(string='Message ESC', readonly=True),
                                         
    }

wizard_import_in_simulation_screen()
