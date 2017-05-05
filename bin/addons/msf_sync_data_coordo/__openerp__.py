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
    'name': 'Synchronization Utility: Datas Post-Synchronization (Coordo Side)',
    'version': '0.1',
    'category': 'Tools',
    'description': 'Must be installed after first synchronization',
    'author': 'MSF, OpenERP SA',
    'website': 'http://openerp.com',
    'depends': ['base', 'sync_client'],
    'init_xml': [],
    'data': [
        'data/res.partner.csv',
    ],
    'demo_xml': [],
    'test':[],
    'installable': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

