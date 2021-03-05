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

class purchase_order_line_nsl_validation_wizard(osv.osv_memory):
    _name = 'purchase.order.line.nsl.validation.wizard'

    _columns = {
        'pol_ids': fields.many2many('purchase.order.line', 'nsl_wiz_pol_rel', 'wiz_id', 'pol_id', string='PO lines'),
        'message': fields.text('Message'),
    }

    def validate(self, cr, uid, ids, context=None):
        '''
        Cancel the PO line 
        @param resource: do we have to resource the cancelled line ?
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        wiz = self.browse(cr , uid, ids[0], context=context)
        netsvc.LocalService("workflow").trg_validate(uid, 'purchase.order.line', [x.id for x in wiz.pol_ids], 'validated', cr)
        return {'type': 'ir.actions.act_window_close'}

purchase_order_line_nsl_validation_wizard()
