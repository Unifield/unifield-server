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

from osv import fields, osv
from tools.translate import _

import time
import base64
import StringIO
import csv

class wizard_hq_report_oca(osv.osv_memory):
    _name = "wizard.hq.report.oca"
    
    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance', required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal year', required=True),
        'period_id': fields.many2one('account.period', 'Period', required=True),
        'selection': fields.selection([('unexported', 'Not yet exported'), ('all', 'All lines')], string="Select", required=True),
    }
    
    _defaults = {
        'fiscalyear_id': lambda self, cr, uid, c: self.pool.get('account.fiscalyear').find(cr, uid, time.strftime('%Y-%m-%d'), context=c),
        'selection': lambda *a: 'unexported',
    }
    
    def button_create_report(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids[0], context=context)
        data = {}
        # add parameters
        data['form'] = {}
        if wizard.instance_id:
            # Get projects below instance
            data['form'].update({'instance_ids': [wizard.instance_id.id] + [x.id for x in wizard.instance_id.child_ids]})
        if wizard.period_id:
            data['form'].update({'period_id': wizard.period_id.id})
        # UFTP-375: Permit user to select all lines or only previous ones
        data['form'].update({'selection': wizard.selection})
        data['target_filename'] = '%s_%s_%s' % (_('Export to HQ System'), wizard.instance_id and wizard.instance_id.code or '', time.strftime('%Y%m%d'))
        return {'type': 'ir.actions.report.xml', 'report_name': 'hq.oca', 'datas': data}
    
wizard_hq_report_oca()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
