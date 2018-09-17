# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2011 MSF, TeMPO Consulting.
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

import netsvc

class enter_reason(osv.osv_memory):
    '''
    wizard called to split a memory stock move from create picking wizard
    '''
    _name = "enter.reason"

    _columns = {
        'picking_id': fields.many2one('stock.picking', string='Incoming Shipment', readonly=True),
        'change_reason': fields.char(string='Change Reason', size=1024),
    }

    _defaults = {
        'picking_id': lambda obj, cr, uid, c: c and c.get('picking_id', False),
    }

    def do_cancel(self, cr, uid, ids, context=None):
        # quick integrity check
        assert context, 'No context defined, problem on method call'
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        picking_obj = self.pool.get('stock.picking')
        purchase_obj = self.pool.get('purchase.order')
        # workflow
        wf_service = netsvc.LocalService("workflow")
        # depending on the button clicked the behavior is different
        cancel_type = context.get('cancel_type', False)
        # picking ids
        picking_ids = context['active_ids']
        # integrity check
        for obj in self.browse(cr, uid, ids, context=context):
            if not obj.change_reason:
                raise osv.except_osv(_('Error !'), _('You must specify a reason.'))

        # change reason
        data = self.read(cr, uid, ids, ['change_reason'], context=context)[0]
        change_reason = data['change_reason']
        # update the object
        for obj in picking_obj.browse(cr, uid, picking_ids, context=context):
            # set the reason
            obj.write({'change_reason': change_reason}, context=context)

            if context.get('do_resource', False):
                self.pool.get('stock.move').write(cr, uid, [move.id for move in obj.move_lines], {'has_to_be_resourced': True}, context=context)

            context['allow_cancelled_pol_copy'] = True
            self.pool.get('stock.move').action_cancel(cr, uid, [move.id for move in obj.move_lines], context=context)

            # cancel the IN
            wf_service.trg_validate(uid, 'stock.picking', obj.id, 'button_cancel', cr)

            # correct the corresponding po manually if exists - should be in shipping exception
            if obj.purchase_id:
                wf_service.trg_validate(uid, 'purchase.order', obj.purchase_id.id, 'picking_ok', cr)
                purchase_obj.log(cr, uid, obj.purchase_id.id, _('The Purchase Order %s is %s%% received') % (obj.purchase_id.name, round(obj.purchase_id.shipped_rate, 2)))

            self.infolog(cr, uid, "The Incoming shipment id:%s (%s) has been canceled%s." % (
                obj.id, obj.name, cancel_type != 'update_out' and ' and resourced' or '',
            ))

        return {'type': 'ir.actions.act_window_close'}

enter_reason()
