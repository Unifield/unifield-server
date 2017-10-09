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


{
    "name": "Sourcing Tool",
    "version": "0.1",
    "author": "MSF, TeMPO Consulting",
    "developer": "pam",
    "category": "Generic Modules/Inventory Control",
    "depends": [
        "sale",
        "purchase",
        "order_types",
        "order_line_number",
        "msf_order_date",
        "partner_modification",
        "procurement_request",
        "kit",
    ],
    "init_xml": [],
    "demo_xml": [],
    "description": """
    Add sourcing specification
    """,
    'test': [
    ],
    'update_xml': [
        'sourcing_view.xml',
        'related_sourcing_view.xml',
        'wizard/multiple_sourcing_view.xml',
    ],
    'installable': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
