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



class ppl_set_pack_on_lines(osv.osv_memory):
    _name = 'ppl.set_pack_on_lines'
    _description = 'Wizard to set from/to pack on lines'

    _columns = {
        'picking_id': fields.many2one('stock.picking', string='PPL', readonly=True),
        'from_pack': fields.integer('From Pack', required=True),
        'to_pack': fields.integer('To Pack', required=True),
    }

    def set_pack(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        wiz = self.browse(cr, uid, ids[0], context=context)
        move_obj = self.pool.get('stock.move')
        m_ids = move_obj.search(cr, uid, [('picking_id', '=', wiz.picking_id.id), ('id', 'in', context.get('button_selected_ids', []))], context=context)

        move_obj.write(cr, uid, m_ids, {'from_pack': wiz.from_pack, 'to_pack': wiz.to_pack}, context=context)
        self.pool.get('stock.picking').check_ppl_integrity(cr, uid, [wiz.picking_id.id], context=context)
        return {'type': 'ir.actions.act_window_close', 'o2m_refresh': 'move_lines'}

    def change_pack(self, cr, uid, ids, fp, to, context=None):
        value = {}
        warning = []
        if not fp or not isinstance(fp, (int, long)):
            value['from_pack'] = 1
            warning.append(_('From Pack: please enter an integer value'))
        if not to or not isinstance(to, (int, long)):
            value['to_pack'] = 1
            warning.append(_('To Pack: please enter an integer value'))

        if not value:
            return {}

        return {
            'value': value,
            'warning': {
                'title': _('Warning'),
                'message': "\n".join(warning),
            }
        }

ppl_set_pack_on_lines()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

