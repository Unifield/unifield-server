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

import tools

class international_transport_cost_report(osv.osv):
    _name = 'international.transport.cost.report'
    _description = 'International Transport Costs'
    _auto = False
    _order = 'date_order desc, delivery_confirmed_date desc, partner_id, transport_mode'

    _columns = {
        'transport_mode': fields.selection([('regular_air', 'Air regular'), ('express_air', 'Air express'),
                                            ('ffc_air', 'Air FFC'), ('sea', 'Sea'),
                                            ('road', 'Road'), ('hand', 'Hand carry'),], string='Transport mode'),
        'transport_cost': fields.float(digits=(16,2), string='Transport cost'),
        'transport_currency_id': fields.many2one('res.currency', string='Currency'),
        'order_id': fields.many2one('purchase.order', string='PO Reference'),
        'date_order': fields.date(string='Creation date'),
        'delivery_confirmed_date': fields.date(string='Delivery Confirmed Date'),
        'partner_id': fields.many2one('res.partner', string='Supplier'),
        'nb_order': fields.integer(string='# Order'),
    }

    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, 'international_transport_cost_report')
        cr.execute("""
                create or replace view international_transport_cost_report as (
                    select
                        min(po.id) as id,
                        po.id as order_id,
                        count(po.id) as nb_order,
                        po.transport_mode as transport_mode,
                        sum(po.transport_cost) as transport_cost,
                        po.transport_currency_id as transport_currency_id,
                        po.date_order as date_order,
                        po.delivery_confirmed_date as delivery_confirmed_date,
                        po.partner_id as partner_id
                    from
                        purchase_order po
                    where
                        po.intl_supplier_ok = True
                    group by
                        po.id,
                        po.transport_mode,
                        po.transport_cost,
                        po.transport_currency_id,
                        po.date_order,
                        po.delivery_confirmed_date,
                        po.partner_id
                )""")

international_transport_cost_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
