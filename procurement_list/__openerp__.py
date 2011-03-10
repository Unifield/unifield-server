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
    'name' : 'Purchase list',
    'version' : '1.0',
    'author' : 'TeMPO Consulting, MSF',
    'category': 'Generic Modules/Sales & Purchases',
    'description': '''
        This module allows you to create a list of items to procure. You can create automatically RfQ for these lists after choosing a list \
        of suppliers. You can also compare these RfQ, choose the best supplier for each product and create automatically the associated \
        purchase orders.
    ''',
    'website': 'http://unifield.msf.org',
    'init_xml': [
    ],
    'depends' : [
        'purchase',
    ],
    'update_xml': [
        'procurement_list_sequence.xml',
        'procurement_list_view.xml',
        'procurement_list_wizard.xml',
        'wizard/wizard_import_list_view.xml',
        'wizard/choose_supplier_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo_xml': [
    ],
    'test': [
        'test/procurement_list.yml',
    ],
    'installable': True,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
