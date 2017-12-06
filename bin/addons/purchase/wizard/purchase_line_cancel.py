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

from osv import osv, fields
import netsvc

class purchase_order_line_cancel_wizard(osv.osv_memory):
    _name = 'purchase.order.line.cancel.wizard'

    _columns = {
        'pol_id': fields.many2one('purchase.order.line', string='PO line to delete'),
        'linked_sol_id': fields.related('pol_id', 'linked_sol_id', type='many2one', relation='sale.order.line', string='SO line'),
    }

    def cancel_pol(self, cr, uid, ids, resource=False, context=None):
        '''
        Cancel the PO line 
        @param resource: do we have to resource the cancelled line ?
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")

        # cancel line:
        signal = 'cancel_r' if resource else 'cancel'
        for wiz in self.browse(cr, uid, ids, context=context):
            wf_service.trg_validate(uid, 'purchase.order.line', wiz.pol_id.id, signal, cr)

        return {'type': 'ir.actions.act_window_close'}


    def cancel_only_pol(self, cr, uid, ids, context=None):
        return self.cancel_pol(cr, uid, ids, resource=False, context=context)

    def cancel_and_resource(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        return self.cancel_pol(cr, uid, ids, resource=True, context=context)

purchase_order_line_cancel_wizard()
