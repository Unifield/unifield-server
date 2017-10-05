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

{
    "name": "Procurement Report",
    "version": "1.0",
    "depends": ["base", "product", "procurement", "stock", "procurement_auto", "procurement_cycle", "stock_schedule",],
    "author": "TeMPO Consulting, MSF",
    "website": "",
    "category": "Warehouse/Reporting",
    "description": """
    This modoule adds a report to give a qucik and easy overview of the user on the split
    of the replenishment rules within categories and products, to identify easily the item
    without any replenishment rules...
    """,
    "init_xml": [
    ],
    'update_xml': [
        'procurement_report_view.xml',
        'procurement_batch_view.xml',
        'min_max_report_view.xml',
        'auto_supply_report_view.xml',
        'order_cycle_report_view.xml',
        'threshold_value_report_view.xml',
        'wizard/schedulers_all_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo_xml': [
    ],
    'installable': True,
    'active': False,
    #    'certificate': 'certificate',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
