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
    "name": "MSF Tools",
    "version": "1.0",
    "depends": ["base",
                "product",
                "object_query",
                ],
    "author": "MSF, TeMPO Consulting",
    "website": "",
    "category": "Specific Modules",
    "description": """
        Interface for Msf Tools
    """,
    "init_xml": [
    ],
    'update_xml': [
        'views/automated_import_view.xml',
        'views/automated_import_function_view.xml',
        'views/automated_import_job_view.xml',
        'views/automated_import_files_available.xml',
        'views/automated_export_view.xml',
        'views/automated_export_function_view.xml',
        'views/automated_export_job_view.xml',
        'security/ir.model.access.csv',
        'report/report_stopped_products_view.xml',
        'report/report_stopped_products_report.xml',
        'report/report_inconsistencies_view.xml',
        'report/report_inconsistencies_report.xml',
        'report/report_stock_pipe_per_product_instance_view.xml',
        'automated_import_data.xml',
        'automated_export_data.xml',
        'delete_old_supplier_catalogue_view.xml',
        'deactivate_phase_out_partners_view.xml',
    ],
    'demo_xml': [
    ],
    'test': [# tests should be performed in base classes to avoid cyclic dependencies
    ],
    'installable': True,
    'active': False,
}
