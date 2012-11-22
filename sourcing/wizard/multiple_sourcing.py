# -*- coding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

_SELECTION_TYPE = [
    ('make_to_stock', 'from stock'),
    ('make_to_order', 'on order'),]

_SELECTION_PO_CFT = [
    ('po', 'Purchase Order'),
    ('dpo', 'Direct Purchase Order'),
    ('cft', 'Tender'),]


class multiple_sourcing_wizard(osv.osv_memory):
    _name = 'multiple.sourcing.wizard'

    _columns = {
        'line_ids': fields.many2many('sourcing.line', 'source_sourcing_line_rel', 'line_id', 'wizard_id',
                                     string='Sourcing lines'),
        'type': fields.selection(_SELECTION_TYPE, string='Procurement Method', required=True),
        'po_cft': fields.selection(_SELECTION_PO_CFT, string='PO/CFT'),
        'supplier': fields.many2one('res.partner', 'Supplier', help='If you have choose lines coming from Field Orders, only External/ESC suppliers will be available.'),
        'company_id': fields.many2one('res.company', 'Current company'),
        'error_on_lines': fields.boolean('If there is line without need sourcing on selected lines'),
    }

    def default_get(self, cr, uid, fields, context=None):
        '''
        Set lines with the selected lines
        '''
        if not context:
            context = {}

        if not context.get('active_ids') or len(context.get('active_ids')) < 2:
            raise osv.except_osv(_('Error'), _('You should select at least two lines to process.'))

        res = super(multiple_sourcing_wizard, self).default_get(cr, uid, fields, context=context)

        res['line_ids'] = []
        res['error_on_lines'] = False
        res['type'] = 'make_to_order'
        res['po_cft'] = 'po'

        for line in self.pool.get('sourcing.line').browse(cr, uid, context.get('active_ids'), context=context):
            if line.state == 'draft' and line.sale_order_state == 'validated':
                res['line_ids'].append(line.id)
            else:
                res['error_on_lines'] = True

        if not res['line_ids']:
            raise osv.except_osv(_('Error'), _('No non-sourced lines are selected. Please select non-sourced lines'))

        res['company_id'] = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        
        return res

    def source_lines(self, cr, uid, ids, context=None):
        '''
        Set values to sourcing lines and confirm them
        '''
        if not context:
            context = {}

        line_obj = self.pool.get('sourcing.line')

        for wiz in self.browse(cr, uid, ids, context=context):
            todo_ids = []
            for line in wiz.line_ids:
                todo_ids.append(line.id)

            line_obj.write(cr, uid, todo_ids, {'type': wiz.type, 'po_cft': wiz.po_cft, 'supplier': wiz.supplier and wiz.supplier.id or False}, context=context)
            line_obj.confirmLine(cr, uid, todo_ids, context=context)

        return {'type': 'ir.actions.act_window_close'}


    def change_type(self, cr, uid, ids, type, context=None):
        '''
        Set to null the other fields if the type is 'from stock'
        '''
        if type == 'make_to_stock':
            return {'value': {'po_cft': False, 'supplier': False}}

        return {}

    def change_po_cft(self, cr, uid, ids, po_cft, context=None):
        '''
        Unset the supplier if tender is choosen
        '''
        if po_cft == 'cft':
            return {'value': {'supplier': False}}

        return {}

multiple_sourcing_wizard()


class res_partner(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'

    def _get_dummy(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for id in ids:
            res[id] = True

        return res

    def _src_contains_fo(self, cr, uid, obj, name, args, context=None):
        res = []
        for arg in args:
            if arg[0] == 'line_contains_fo':
                if type(arg[2]) == type(list()):
                    for line in self.pool.get('sourcing.line').browse(cr, uid, arg[2][0][2], context=context):
                        if not line.procurement_request:
                            res.append(('partner_type', 'in', ['external', 'esc']))

        return res

    _columns = {
        'line_contains_fo': fields.function(_get_dummy, fnct_search=_src_contains_fo, method=True, string='Lines contains FO', type='boolean', store=False),
    }

res_partner()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

