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
from msf_order_date import TRANSPORT_TYPE


class international_transport_cost_report(osv.osv):
    _name = 'international.transport.cost.report'
    _rec_name = 'order_id'
    _description = 'International Transport Costs'
    _auto = False
    _order = 'date_order desc, delivery_confirmed_date desc, partner_id, transport_type'

    _columns = {
        'transport_type': fields.selection(selection=TRANSPORT_TYPE, string='Transport mode'),
        'func_transport_cost': fields.float(digits=(16,2), string='Func. Transport cost'),
        'func_currency_id': fields.many2one('res.currency', string='Func. Currency'),
        'transport_cost': fields.float(digits=(16,2), string='Transport cost'),
        'transport_currency_id': fields.many2one('res.currency', string='Currency'),
        'order_id': fields.many2one('purchase.order', string='PO Reference'),
        'order_state': fields.selection([('approved', 'Confirmed'), ('done', 'Closed')], string='State'),
        'date_order': fields.date(string='Creation date'),
        'delivery_confirmed_date': fields.date(string='Delivery Confirmed Date'),
        'partner_id': fields.many2one('res.partner', string='Supplier'),
        'nb_order': fields.integer(string='# Order'),
    }

    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, 'international_transport_cost_report')
        cr.execute("""
                create or replace view international_transport_cost_report as (
                    SELECT
                        min(po.id) as id,
                        po.id as order_id,
                        count(po.id) as nb_order,
                        po.transport_type as transport_type,
                        sum(round((po.transport_cost*(to_rate.rate/fr_rate.rate)/to_cur.rounding))*to_cur.rounding) as func_transport_cost,
                        po.transport_cost as transport_cost,
                        po.transport_currency_id as transport_currency_id,
                        po.date_order as date_order,
                        to_cur.id as func_currency_id,
                        po.delivery_confirmed_date as delivery_confirmed_date,
                        po.partner_id as partner_id,
                        po.state as order_state
                    FROM
                        purchase_order po
                    LEFT JOIN
                        res_company c 
                            ON po.company_id = c.id
                    LEFT JOIN
                        res_currency to_cur
                            ON c.currency_id = to_cur.id
                    LEFT JOIN
                        res_currency fr_cur
                            ON po.transport_currency_id = fr_cur.id
                    LEFT JOIN
                        (SELECT currency_id, rate FROM res_currency_rate WHERE name <= NOW() ORDER BY name desc) fr_rate
                            ON fr_cur.id = fr_rate.currency_id
                    LEFT JOIN
                        (SELECT currency_id, rate FROM res_currency_rate WHERE name <= NOW() ORDER BY name desc) to_rate
                            ON to_cur.id = to_rate.currency_id
                    WHERE
                        (po.intl_supplier_ok = True
                      OR
                        po.display_intl_transport_ok = True)
                      AND
                        po.state in ('approved', 'done')
                      AND
                        po.rfq_ok = False   
                      AND
                        po.transport_cost > 0.00
                    GROUP BY
                        po.id,
                        po.transport_type,
                        po.transport_cost,
                        po.transport_currency_id,
                        po.date_order,
                        po.delivery_confirmed_date,
                        po.partner_id,
                        to_cur.id,
                        po.state
                )""")

international_transport_cost_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
