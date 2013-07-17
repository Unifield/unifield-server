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
        Set lines with the selected lines to source
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

        # Ignore all lines which have already been sourced, if there are some alredy sourced lines, a message
        # will be displayed at the top of the wizard
        for line in self.pool.get('sourcing.line').browse(cr, uid, context.get('active_ids'), context=context):
            if line.state == 'draft' and line.sale_order_state == 'validated':
                res['line_ids'].append(line.id)
            else:
                res['error_on_lines'] = True

        if not res['line_ids']:
            raise osv.except_osv(_('Error'), _('No non-sourced lines are selected. Please select non-sourced lines'))

        res['company_id'] = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        
        return res

    def save_lines(self, cr, uid, ids, context=None):
        '''
        Set values to sourcing lines
        '''
        if not context:
            context = {}

        line_obj = self.pool.get('sourcing.line')

        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.type == 'make_to_order':
                if not wiz.po_cft:
                    raise osv.except_osv(_('Error'), _('The Procurement method should be filled !'))
                elif wiz.po_cft != 'cft' and not wiz.supplier:
                    raise osv.except_osv(_('Error'), _('You should select a supplier !'))

            errors = {}
            for line in wiz.line_ids:
                if line.sale_order_id.procurement_request and wiz.po_cft == 'dpo':
                    err_msg = 'You cannot choose Direct Purchase Order as method to source Internal Request lines.'
                    errors.setdefault(err_msg, [])
                    errors[err_msg].append((line.id, '%s of %s' % (line.line_number, line.sale_order_id.name)))
                else:
                    try:
                        line_obj.write(cr, uid, [line.id], {'type': wiz.type, 
                                                            'po_cft': wiz.po_cft, 
                                                            'supplier': wiz.supplier and wiz.supplier.id or False}, context=context)
                    except osv.except_osv, e:
                        errors.setdefault(e.value, [])
                        errors[e.value].append((line.id, '%s of %s' % (line.line_number, line.sale_order_id.name)))
                        
            if errors:
                error_msg = ''
                for e in errors:
                    if error_msg:
                        error_msg += ' // '
                    if len(errors[e]) > 1:
                        error_msg += 'Lines %s ' % ', '.join(str(x[1]) for x in errors[e])
                    else:
                        error_msg += 'Line %s ' % ', '.join(str(x[1]) for x in errors[e])
                    error_msg += ': %s' % e
                raise osv.except_osv(_('Errors'), _('There are some errors on sourcing lines : %s') % error_msg)
                
            
        return {'type': 'ir.actions.act_window_close'}

    def source_lines(self, cr, uid, ids, context=None):
        '''
        Confirm all lines
        '''
        if not context:
            context = {}

        line_obj = self.pool.get('sourcing.line')

        for wiz in self.browse(cr, uid, ids, context=context):
            for line in wiz.line_ids:
                if line.sale_order_id.procurement_request and wiz.po_cft == 'dpo':
                    raise osv.except_osv(_('Error'), _('You cannot choose Direct Purchase Order as method to source Internal Request lines.'))
                
                line_obj.confirmLine(cr, uid, [line.id], context=context)

        return {'type': 'ir.actions.act_window_close'}

    def save_source_lines(self, cr, uid, ids, context=None):
        '''
        Set values to sourcing lines and confirm them
        '''
        if not context:
            context = {}

        self.save_lines(cr, uid, ids, context=context)
        self.source_lines(cr, uid, ids, context=context)

        return {'type': 'ir.actions.act_window_close'}


    def change_type(self, cr, uid, ids, type, context=None):
        '''
        Unset the other fields if the type is 'from stock'
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


#############################################################
#                                                           #
# This modification on res.partner avoid the selection      #
# of internal/inter-section/intermission partners           #
# if a line on multiple sourcing wizard coming from a FO    #
#                                                           #
#############################################################
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
                        if not line.sale_order_id.procurement_request:
                            res.append(('partner_type', 'in', ['external', 'esc']))

        return res

    _columns = {
        'line_contains_fo': fields.function(_get_dummy, fnct_search=_src_contains_fo, method=True, string='Lines contains FO', type='boolean', store=False),
    }

res_partner()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

