# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
from osv import orm
from tools.translate import _
from datetime import datetime
import tools
import time
import pprint
import so_po_common
pp = pprint.PrettyPrinter(indent=4)

"""
    This class is just for test purpose
    A proof of concept for message passing
"""

class sale_order_sync(osv.osv):
    _inherit = "sale.order"
    
    _columns = {
                'received': fields.boolean('Received by Client', readonly=True),
    }
    
    def create_so(self, cr, uid, source, po_info, context=None):
        if not context:
            context = {}
        so_po_common = self.pool.get('so.po.common')
        partner_id = so_po_common.get_partner_id(cr, uid, source, context)
        address_id = so_po_common.get_partner_address_id(cr, uid, partner_id, context)
        lines = so_po_common.get_lines(cr, uid, po_info, False, context)
        default = self.default_get(cr, uid, ['name'], context=context)
        data = {                        'client_order_ref' : source + "." + po_info.name,
                                        'partner_id' : partner_id,
                                        'partner_order_id' : address_id,
                                        'partner_shipping_id': address_id,
                                        'partner_invoice_id' : address_id,
                                        'pricelist_id' : so_po_common.get_price_list_id(cr, uid, partner_id, context),
                                        
                                        'priority' : po_info.priority,
                                        'categ' : po_info.categ,
                                        'note' : po_info.notes,
                                        'details' : po_info.details,
                                         
                                        'delivery_requested_date' : po_info.delivery_requested_date,
                                        'order_line' : lines}


                                        #'analytic_distribution_id' : self.ppol.dsdasas.copy(analytic_distrib.id),
        rec_id = so_po_common.get_record_id(cr, uid, context, po_info.analytic_distribution_id)
        if rec_id:
            data['analytic_distribution_id'] = rec_id 

        
        default.update(data)
        res_id = self.create(cr, uid, default , context=context)
        return True

    def picking_received(self, cr, uid, source, picking_info, context=None):
        if not context:
            context = {}
        name = picking_info.purchase_id.name
        ids = self.search(cr, uid, [('client_order_ref', '=', source + "." + name)])
        self.write(cr, uid, ids, {'received' : True}, context=context)
        return True
sale_order_sync()

class account_period_sync(osv.osv):
    
    _inherit = "account.period"
    
    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        print "generate xml name for period"
        period = self.browse(cr, uid, res_id)
        return period.fiscalyear_id.code + "/" + period.name + "_" + period.date_start
    
account_period_sync()