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
    'name': 'Synchronization Utility',
    'version': '0.1',
    'category': 'Tools',
    'description': """\
Synchronization Engine - Client Module
""",
    'author': 'OpenERP SA',
    'website': 'http://openerp.com',
    'depends': ['sync_common', 'account', 'analytic_distribution', 'msf_instance'],
    'init_xml': [],
    'data': [
        'sync_client_view.xml',
        'backup_view.xml',
        'backup_report.xml',
        'update_view.xml',
        'message_view.xml',
        'operations_view.xml',
        'hq_monitor_view.xml',
        'log_sale_purchase_view.xml',
        'wizard/sync_wiz_view.xml',
        'wizard/monitoring_view.xml',
        'wizard/view_entity_id.xml',
        'monitor_view.xml',
        'open_update_view.xml',
        'data/cron.xml',
        'data/cron_ops.xml',
        'data/backupconfig.xml',
        'data/hq_monitor.xml',
        'security/ir.model.access.csv'
    ],
    'demo_xml': [
    ],
    'test':[
    ],
    'installable': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
