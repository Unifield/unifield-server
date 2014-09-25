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

from osv import fields
from osv import osv
from tools.translate import _

from sourcing.sale_order_line import _SELECTION_PO_CFT

_SELECTION_TYPE = [
    ('make_to_stock', 'from stock'),
    ('make_to_order', 'on order'), ]

class multiple_sourcing_wizard(osv.osv_memory):
    _name = 'multiple.sourcing.wizard'
    
    _columns = {
        'line_ids': fields.many2many(
            'sale.order.line',
            'source_sourcing_line_rel',
            'line_id',
            'wizard_id',
            string='Sourcing lines',
        ),
        'type': fields.selection(
            _SELECTION_TYPE,
            string='Procurement Method',
            required=True,
        ),
        'po_cft': fields.selection(
            _SELECTION_PO_CFT,
            string='PO/CFT',
        ),
        'location_id': fields.many2one(
            'stock.location',
            string='Location',
        ),
        'supplier': fields.many2one(
            'res.partner',
            string='Supplier',
            help="If you have choose lines coming from Field Orders, only External/ESC suppliers will be available.",
        ),
        'company_id': fields.many2one(
            'res.company',
            string='Current company',
        ),
        'error_on_lines': fields.boolean(
            string='Error',
            help="If there is line without need sourcing on selected lines",
        ),
    }

    def default_get(self, cr, uid, fields_list, context=None):
        """
        Set lines with the selected lines to source
        """
        if not context:
            context = {}

        active_ids = context.get('active_ids')
        if not active_ids or len(active_ids) < 2:
            raise osv.except_osv(_('Error'), _('You should select at least two lines to process.'))

        res = super(multiple_sourcing_wizard, self).default_get(cr, uid, fields_list, context=context)

        res['line_ids'] = []
        res['error_on_lines'] = False
        
        # Check if all lines are with the same type, then set that type, otherwise set make_to_order

        # Ignore all lines which have already been sourced, if there are some alredy sourced lines, a message
        # will be displayed at the top of the wizard
        res['type'] = 'make_to_stock'
        res['po_cft'] = False
        loc = -1 # first location flag
        supplier = -1 # first location flag
        for line in self.pool.get('sale.order.line').browse(cr, uid, active_ids, context=context):
            if line.state == 'draft' and line.sale_order_state == 'validated':
                res['line_ids'].append(line.id)
            else:
                res['error_on_lines'] = True
                
            if line.type == 'make_to_order':
                res['type'] = 'make_to_order'
                res['po_cft'] = 'po'
                
                loc = False # always set False for location if source on order
                if not line.supplier: 
                    supplier = False
                else:
                    temp = line.supplier.id
                    if supplier == -1: # first location
                        supplier = temp
                    elif supplier != temp:
                        supplier = False
            else:
                # UTP-1021: Calculate the location to set into the wizard view if all lines are sourced from the same location
                supplier = False # if source from stock, always set False to partner
                temploc = line.location_id.id
                if loc == -1: # first location
                    loc = temploc
                elif temploc != loc:
                    loc = False
                    
        # UTP-1021: Set default values on openning the wizard
        if loc != -1:
            res['location_id'] = loc
        if supplier != -1:
            res['supplier'] = supplier
            
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

        line_obj = self.pool.get('sale.order.line')

        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.type == 'make_to_order':
                if not wiz.po_cft:
                    raise osv.except_osv(_('Error'), _('The Procurement method should be filled !'))
                elif wiz.po_cft != 'cft' and not wiz.supplier:
                    raise osv.except_osv(_('Error'), _('You should select a supplier !'))

            errors = {}
            for line in wiz.line_ids:
                if line.order_id.procurement_request and wiz.po_cft == 'dpo':
                    err_msg = 'You cannot choose Direct Purchase Order as method to source Internal Request lines.'
                    errors.setdefault(err_msg, [])
                    errors[err_msg].append((line.id, '%s of %s' % (line.line_number, line.order_id.name)))
                else:
                    try:
                        line_obj.write(cr, uid, [line.id], {'type': wiz.type,
                                                            'po_cft': wiz.po_cft,
                                                            'supplier': wiz.supplier and wiz.supplier.id or False,
                                                            'location_id': wiz.location_id.id and wiz.location_id.id or False}, 
                                                             context=context)
                    except osv.except_osv, e:
                        errors.setdefault(e.value, [])
                        errors[e.value].append((line.id, '%s of %s' % (line.line_number, line.order_id.name)))

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

        # Commit the result to avoid problem confirmLine in thread with new cursor
        cr.commit()

        return {'type': 'ir.actions.act_window_close'}

    def source_lines(self, cr, uid, ids, context=None):
        '''
        Confirm all lines
        '''
        # Objects
        line_obj = self.pool.get('sale.order.line')

        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        lines_to_confirm = []

        for wiz in self.browse(cr, uid, ids, context=context):
            for line in wiz.line_ids:
                if line.order_id.procurement_request and wiz.po_cft == 'dpo':
                    raise osv.except_osv(_('Error'), _('You cannot choose Direct Purchase Order as method to source Internal Request lines.'))
                lines_to_confirm.append(line.id)

        line_obj.confirmLine(cr, uid, lines_to_confirm, context=context)

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

    def change_type(self, cr, uid, ids, l_type, context=None):
        '''
        Unset the other fields if the type is 'from stock'
        '''
        if l_type == 'make_to_stock':
            return {'value': {'po_cft': False, 'supplier': False}}

        return {}

    def change_po_cft(self, cr, uid, ids, po_cft, context=None):
        '''
        Unset the supplier if tender is choosen
        '''
        if po_cft == 'cft':
            return {'value': {'supplier': False}}

        return {}

    def change_supplier(self, cr, uid, ids, supplier, context=None):
        '''
        Check if the partner has an address.
        '''
        partner_obj = self.pool.get('res.partner')

        result = {}

        if supplier:
            partner = partner_obj.browse(cr, uid, supplier, context)
            # Check if the partner has addresses
            if not partner.address:
                result['warning'] = {
                    'title': _('Warning'),
                    'message': _('The chosen partner has no address. Please define an address before continuing.'),
                }
        return result
    
    def change_location(self, cr, uid, ids, location_id, context=None):
        res = {'value': {}}
        if not location_id:
            return res

        if not context or not context[0] or not context[0][2]:
            return res
            
        line_obj = self.pool.get('sale.order.line')
        active_ids = context[0][2]
        
        context = {}             
        context.update({'from_multiple_line_sourcing': False})
        for line in self.pool.get('sale.order.line').browse(cr, uid, active_ids, context=context):
            line_obj.write(cr, uid, [line.id], {'type': 'make_to_stock',
                                                        'po_cft': False,
                                                        'supplier': False,
                                                        'location_id': location_id}, # UTP-1021: Update loc and ask the view to refresh 
                                                         context=context)                
        res = {'value':
               {'line_ids': active_ids, 'error_on_lines': False, 'po_cft':False,}}
        return res
      

multiple_sourcing_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
