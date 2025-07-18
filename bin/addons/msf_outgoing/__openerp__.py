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
    "name" : "MSF Outgoing Management",
    "version" : "0.1",
    "author" : "MSF, TeMPO Consulting",
    "developer": "pam",
    "category" : "Generic Modules/Inventory Control",
    "description": """
        MSF module covering business needs for outgoing movement from
        an MSF instance.

        Three main phases are used to describe the process:
            - PICKING
            - PACKING
            - SHIPMENT
        """,
    'website': 'http://www.unifield.org',
    'init_xml': [],
    "depends" : ["stock",
                 "purchase",
                 "sale",
                 "product_asset",
                 "kit",
                 "order_line_number",
                 "reason_types_moves",
                 "specific_rules",
                 "msf_order_date",
                 "stock_override",
                 "unifield_setup",
                 ],
    'update_xml': [
        'data/msf_outgoing_data.xml',
        'outgoing_sequence.xml',
        'security/ir.model.access.csv',
        'msf_outgoing_view.xml',
        'wizard/split_memory_move_view.xml',
        'wizard/picking_processor_view.xml',
        'wizard/incoming_shipment_processor_view.xml',
        'wizard/split_move_processor_view.xml',
        'wizard/ppl_processor_view.xml',
        'wizard/return_ppl_processor_view.xml',
        'wizard/return_shipment_processor_view.xml',
        'wizard/internal_move_processor_view.xml',
        'wizard/outgoing_delivery_processor_view.xml',
        'wizard/return_pack_shipment_processor_view.xml',
        'wizard/check_ppl_integrity.xml',
        'wizard/shipment_processor_view.xml',
        'wizard/ppl_set_pack_on_lines_view.xml',
        'msf_outgoing_report.xml',
        'msf_outgoing_workflow.xml',
        'data/audittrail_data_picking.yml',
        'sde_import_view.xml',
    ],
    "demo_xml": ['data/msf_outgoing_data.xml',
                 ],
    'test': [
    ],
    'installable': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
