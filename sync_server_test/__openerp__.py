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
    'name': 'Testing module for Synchronization Utility Server',
    'version': '0.1',
    'category': 'Tools',
    'description': """
        
    """,
    'author': 'OpenERP SA',
    'website': 'http://openerp.com',
    'depends': ['base', 'sync_server', 'account', 'account_analytic_plans'],
    'init_xml': [],
    'data': [
        'sync.server.group_type.csv',
        'sync.server.entity_group.csv',
        'sync.server.entity.csv',
        'sync_server.sync_rule.csv',
        'sync_server.message_rule.csv',
    ],
    'demo_xml': [
    ],
    'test':[
    ],
    'installable': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
