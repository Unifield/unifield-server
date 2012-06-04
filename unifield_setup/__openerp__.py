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
    "name": "Unifield Setup",
    "version": "1.0",
    "depends": [
                "base",
                "product",
    ],
    "author": "TeMPO Consulting, MSF",
    "website": "",
    "category": "General",
    "description": """
    This module aims at implementing the configuration of a Unifield instance.
    """,
    "init_xml": [
    ],
    'update_xml': [
        "setup_data.xml",
        # Installer views
        "installer/project_addresses_view.xml",
        "installer/project_lead_time_view.xml",
        "installer/delivery_process_view.xml",
        "installer/allocation_setup_view.xml",
        "installer/sales_price_view.xml",
        "security/ir.model.access.csv",
    ],
    'demo_xml': [
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
