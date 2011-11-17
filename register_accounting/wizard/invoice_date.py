#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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

from osv import osv
from osv import fields
from tools.translate import _
import netsvc
import decimal_precision as dp


class wizard_invoice_date(osv.osv_memory):
    _name = "wizard.invoice.date"
    _columns = {
        'invoice_id': fields.many2one('account.invoice','Invoice', required=True),
        'date': fields.date('Invoice Date'),
        'period_id': fields.many2one('account.period', 'Force Period', domain=[('state','<>','done')], help="Keep empty to use the period of the validation(invoice) date."),
        'amount_total': fields.float('Computed Total', digits_compute=dp.get_precision('Account'), readonly=1),
        'check_total': fields.float('Total', digits_compute=dp.get_precision('Account')),
        'state': fields.selection([('both','Both'), ('amount', 'amount'), ('date','date')], 'State'),
    }

    def validate(self, cr, uid, ids, context={}):
        inv_obj = self.pool.get('account.invoice')
        wf_service = netsvc.LocalService("workflow")
        for wiz in self.browse(cr, uid, ids):
            values = {}
            if wiz.date:
                values = {'date_invoice': wiz.date, 'period_id': wiz.period_id and wiz.period_id.id or False}
            if wiz.check_total:
                values['check_total'] = wiz.check_total

            inv_obj.write(cr, uid, [wiz.invoice_id.id], values)
            wf_service.trg_validate(uid, 'account.invoice', wiz.invoice_id.id, 'invoice_open', cr)
        return { 'type': 'ir.actions.act_window_close', }
       
wizard_invoice_date()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
