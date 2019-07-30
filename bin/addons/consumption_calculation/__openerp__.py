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
    "name": "Consumption Calculation",
    "version": "1.0",
    "depends": ["product", "stock", "product_nomenclature",
                "product_list", "reason_types_moves"],
    "author": "TeMPO Consulting, MSF",
    "website": "",
    "category": "Specific Modules",
    "description": """
        This module aims at defining different kind of consumption calculation.
    """,
    "init_xml": [
    ],
    'update_xml': [
        'consumption_data.xml',
        'consumption_sequence.xml',
        'consumption_view.xml',
        'expiry_calculation_view.xml',
        'history_consumption_view.xml',
        'consumption_calculation_report.xml',
        'expiry_calculation_report.xml',
        'weekly_forecast_report_view.xml',
        'wizard/wizard_import_fmc_view.xml',
        'wizard/wizard_import_rac_view.xml',
        'wizard/wizard_export_fmc_rac_view.xml',
        'wizard/wizard_valid_lines_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo_xml': [
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
    #    'certificate': 'certificate',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
