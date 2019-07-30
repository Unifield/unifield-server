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
    "name": "Documents to Done",
    "version": "1.0",
    "depends": [
        "sale",
        "purchase_override",
        "stock_override",
        "tender_flow",
        "stock",
        "msf_outgoing",
        "object_query",
    ],
    "author": "TeMPO Consulting, MSF",
    "website": "http://www.unifield.org",
    "category": "Specific Modules",
    "description": """
        This module aims at set documents to 'Done' state.
    """,
    "init_xml": [
    ],
    'update_xml': [
        'security/ir.model.access.csv',
        'documents_done_view.xml',
    ],
    'demo_xml': [
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
