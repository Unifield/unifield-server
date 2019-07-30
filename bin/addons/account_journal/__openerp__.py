# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011-2012 MSF, TeMPO Consulting.
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
    "name" : "Accounting Journal for MSF",
    "version" : "1.0",
    "author" : "MSF, TeMPO Consulting",
    "category": 'Generic Modules/Accounting',
    "description": '''
        Journals view and datas
    ''',
    'init_xml': [],
    "depends" : ["analytic_override", "finance", "analytic_distribution"],
    'update_xml': [
        'account_journal_view.xml',
    ],
    'demo_xml': [
        'account_journal_demo.xml'
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
    #'certificate': 'certificate',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
