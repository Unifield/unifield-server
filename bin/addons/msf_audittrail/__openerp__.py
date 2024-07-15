# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
    'name': 'MSF Audit Trail',
    'version': '1.0',
    'category': 'Generic Modules/Others',
    'description': """
    This module gives the administrator the rights
    to track every user operation on all the objects
    of the system.

    Administrator can subscribe rules for read,write and
    delete on objects and can check logs.
    """,
    'author': 'OpenERP SA, TeMPO Consulting, MSF',
    'website': 'http://www.unifield.org',
    'depends': ['base', 'purchase', 'account'],
    'init_xml': [],
    'update_xml': [
        'wizard/audittrail_view_log_view.xml',
        'audittrail_view.xml',
        'security/ir.model.access.csv',
        'security/audittrail_security.xml',
        'data/audittrail_data_sale.yml',
        'data/audittrail_data_purchase.yml',
        'data/audittrail_data_products.yml',
        'data/audittrail_data_products_category.yml',
        'data/audittrail_data_JI.yml',
        'data/audittrail_data_CV.yml',
        'data/audittrail_msf_instance.yml',
        'data/audittrail_res_users.yml',
        'data/audittrail_hr_employee.yml',
        'data/audittrail_res_partner.yml',
        'data/audittrail_account_analytic_journal.yml',
        'data/audittrail_account_journal.yml',
        'data/audittrail_account_account.yml',
        'data/audittrail_account_tax.yml',
        'data/audittrail_currency.yml',
        'data/audittrail_currency_rate.yml',
        'data/audittrail_currency_table.yml',
        'data/audittrail_res_company.yml',
        'data/audittrail_dest_cc_link.yml',
        'data/audittrail_hq_entry.yml',
        'data/audittrail_accrual.yml',
        'audittrail_report.xml',
        'audittrail_invoice_data.yml',
        'data/audittrail_data_asset.yml',
        'data/audittrail_account_model.yml',
        'data/audittrail_account_subscription.yml',
        'data/audittrail_data_sync.yml',
    ],
    'demo_xml': [],
    'installable': True,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
