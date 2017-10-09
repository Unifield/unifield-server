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

class purchase_order_line_manually_confirmed_wizard(osv.osv_memory):
    _name = 'purchase.order.line.manually.confirmed.wizard'

    _columns = {
        'pol_to_confirm': fields.many2one('purchase.order.line', string='PO line to confirm'),
    }

    def confirm_pol(self, cr, uid, ids, context=None):
        '''
        Cancel the PO line 
        @param resource: do we have to resource the cancelled line ?
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")

        pol_ids_to_confirm = context.get('pol_ids_to_confirm', False)
        if pol_ids_to_confirm:
            for pol_id in pol_ids_to_confirm:
                wf_service.trg_validate(uid, 'purchase.order.line', pol_id, 'confirmed', cr)

        # confirm line:
        for wiz in self.browse(cr, uid, ids, context=context):
            wf_service.trg_validate(uid, 'purchase.order.line', wiz.pol_to_confirm.id, 'confirmed', cr)

        return {'type': 'ir.actions.act_window_close'}


    def close_wizard(self, cr, uid, ids, context=None):
        '''
        Just close the wizard
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]
        return {'type': 'ir.actions.act_window_close'}


purchase_order_line_manually_confirmed_wizard()
