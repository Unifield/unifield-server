# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
    'name': 'Purchase Follow-Up',
    'version': '0.1',
    'category': 'Generic Modules/Sales & Purchases',
    'description': """
    Add wizard to allow users to have
        an overview of all related 
        documents to a sale order.   
    """,
    'author': 'TeMPO Consulting/MSF',
    'website': 'unifield.org',
    'depends': ['purchase'],
    'init_xml' : [ ],
    "update_xml": [
        "purchase_followup_view.xml",
        "report/purchase_follow_up_report.xml",
        "report/po_track_changes_report.xml",
        "wizard/po_track_changes_wizard_view.xml",
    ],
    'demo_xml' : [ ],
    'test': [
    ],
    'installable': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
