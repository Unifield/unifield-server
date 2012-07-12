# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF, Smile
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
from tools import cache

class ir_values(osv.osv):
    """
    we override ir.values because we need to filter where the button to print report is displayed (this was also done in register_accounting/account_bank_statement.py)
    """
    _name = 'ir.values'
    _inherit = 'ir.values'

    def get(self, cr, uid, key, key2, models, meta=False, context=None, res_id_req=False, without_user=True, key2_req=True):
        if context is None:
            context = {}
        values = super(ir_values, self).get(cr, uid, key, key2, models, meta, context, res_id_req, without_user, key2_req)
        if context.get('_terp_view_name') and key == 'action' and key2 == 'client_print_multi' and 'purchase.order' in [x[0] for x in models]:
            new_act = []
            for v in values :
                if v[2]['report_name'] == 'purchase.order_xls' and context['_terp_view_name'] == 'Purchase Orders' \
                or v[2]['report_name'] == 'purchase.msf.order' and context['_terp_view_name'] == 'Purchase Orders' \
                or v[2]['report_name'] == 'purchase.order.merged' and context['_terp_view_name'] == 'Purchase Orders' \
                or v[2]['report_name'] == 'po.line.allocation.report' and context['_terp_view_name'] == 'Purchase Orders' \
                or v[2]['report_name'] == 'purchase.msf.quotation' and context['_terp_view_name'] == 'Requests for Quotation' \
                or v[2]['report_name'] == 'request.for.quotation_xls' and context['_terp_view_name'] == 'Requests for Quotation' :
                    new_act.append(v)
                values = new_act
        elif context.get('_terp_view_name') and key == 'action' and key2 == 'client_print_multi' and 'sale.order' in [x[0] for x in models]:
            new_act = []
            for v in values:
                if v[2]['report_name'] == 'internal.request_xls' and context['_terp_view_name'] == 'Internal Requests' \
                or v[2]['report_name'] == 'msf.sale.order' and context['_terp_view_name'] == 'Field Orders' \
                or v[2]['report_name'] == 'sale.order_xls' and context['_terp_view_name'] == 'Field Orders' :
                    new_act.append(v)
                values = new_act
                
        elif context.get('_terp_view_name') and key == 'action' and key2 == 'client_print_multi' and 'stock.picking' in [x[0] for x in models]:
            new_act = []
            for v in values:
                if v[2]['report_name'] == 'picking.ticket' and context['_terp_view_name'] == 'Picking Tickets' and context.get('picking_screen', False)\
                or v[2]['report_name'] == 'pre.packing.list' and context['_terp_view_name'] == 'Pre-Packing Lists' and context.get('ppl_screen', False)\
                or v[2]['report_name'] == 'labels' and context['_terp_view_name'] in ['Picking Tickets', 'Pre-Packing Lists'] :
                    new_act.append(v)
                values = new_act
                
        elif context.get('_terp_view_name') and key == 'action' and key2 == 'client_print_multi' and 'shipment' in [x[0] for x in models]:
            new_act = []
            for v in values:
                if v[2]['report_name'] == 'packing.list' and context['_terp_view_name'] == 'Packing Lists' :
                    new_act.append(v)
                values = new_act
        elif context.get('picking_screen') and context.get('from_so'):
            new_act = []
            for v in values:
                if v[2].get('report_name', False) :
                    if v[2]['report_name'] == 'picking.ticket':
                        new_act.append(v)
                values = new_act
        return values

ir_values()