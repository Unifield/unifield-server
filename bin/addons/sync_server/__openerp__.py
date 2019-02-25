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
    'name': 'Synchronization Utility Server',
    'version': '0.1',
    'category': 'Tools',
    'description': """

    """,
    'author': 'OpenERP SA',
    'website': 'http://openerp.com',
    'depends': ['sync_common', 'msf_tools', 'useability_dashboard_and_menu',
                'sync_client', 'product_attributes', 'sale'],
    'init_xml': [
        'sync_server_menu.xml',
    ],
    'data': [
        'sync_server_view.xml',
        'update_view.xml',
        'message_view.xml',
        'rules_view.xml',
        'security/group.xml',
        'security/ir.model.access.csv',
        'data/cron.xml',
        'data/alert_email.xml',
        'data/audittrail_sync_server.yml',
        'data/automated_import_sync_groups.xml',
        'sync_disabled_view.xml',
    ],
    'demo_xml': [
    ],
    'test':[
    ],
    'installable': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
