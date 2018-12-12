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

from osv import fields
from osv import osv
from tools.translate import _



class check_ppl_integrity(osv.osv_memory):
    _name = 'check.ppl.integrity'
    _description = 'Wizard to check PPL integrity'

    _columns = {
        'ppl_processor_id': fields.many2one('ppl.processor', string='PPL processor', readonly=True),
        'incoming_processor_id': fields.many2one('stock.incoming.processor', string='IN processor', readonly=True),
        'line_number_with_issue': fields.char('Line # with issue', size=512, readonly=True),
    }

    def next(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        wiz = self.browse(cr, uid, ids[0], context=context)

        if wiz.ppl_processor_id:
            res = self.pool.get('stock.picking').do_ppl_step1(cr, uid, [wiz.ppl_processor_id.id], context=context)
        elif wiz.incoming_processor_id:
            res = self.pool.get('stock.incoming.processor').do_process_to_ship(cr, uid, [wiz.incoming_processor_id.id], context=context)          

        return res


    def return_to_wizard(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        if not ids:
            raise osv.except_osv(
               _('Error'),
               _('No wizard found !')
            )

        wiz = self.browse(cr, uid, ids[0], context=context)
        if wiz.ppl_processor_id:
            res_model = 'ppl.processor'
            res_id = wiz.ppl_processor_id.id
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'ppl_processor_step1_form_view')[1]
        elif wiz.incoming_processor_id:
            res_model = 'stock.incoming.processor'
            res_id = wiz.incoming_processor_id.id
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'stock_incoming_processor_form_view')[1]

        return {
            'type': 'ir.actions.act_window',
            'res_model': res_model,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [view_id],
            'res_id': res_id,
            'target': 'new',
            'context': context,
        }


    def cancel(self, cr, uid, ids, context=None):
        return self.return_to_wizard(cr, uid, ids, context=context)


check_ppl_integrity()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

