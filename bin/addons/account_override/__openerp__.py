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
    "name" : "Account override",
    "version" : "1.0",
    "author" : "MSF, TeMPO Consulting",
    "description" : """
    Account Module Extension for MSF.
    """,
    "website": "http://unifield.msf.org",
    "depends" : ["account", "account_chart"],
    "category" : "Generic Modules/Accounting",
    "init_xml" : [
        'data/computation.xml',
        'data/account_type.xml'
    ],
    "demo_xml" : [],
    "update_xml" : [
        'res_partner_view.xml',
        'product_product_view.xml',
        'account_view.xml',
        'account_invoice_view.xml',
        'account_invoice_report.xml',
        'wizard/account_chart.xml',
        'wizard/import_invoice.xml',
        'wizard/split_invoice.xml',
        'wizard/integrity_finance_wizard_view.xml',
        'attachment_view.xml'
    ],
    'test': [],
    'installable': True,
    'active': False,
}
