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

from osv import fields, osv
from tools.translate import _
import time

class stock_partial_picking(osv.osv_memory):
    '''
    new field for claim selection
    '''
    _inherit = "stock.partial.picking"
    
    def _get_default_supplier(self, cr, uid, context=None):
        '''
        try to find the suppier of corresponding IN for chained picking
        '''
        # objects
        pick_obj = self.pool.get('stock.picking')
        
        if not context.get('active_ids'):
            return False
        
        picking_ids = context['active_ids']
        for obj in pick_obj.browse(cr, uid, picking_ids, context=context):
            if obj.chained_from_in_stock_picking:
                return obj.corresponding_in_picking_stock_picking.partner_id2.id
            
    def _get_has_supplier(self, cr, uid, context=None):
        '''
        try to find the suppier of corresponding IN for chained picking
        '''
        # objects
        pick_obj = self.pool.get('stock.picking')
        
        if not context.get('active_ids'):
            return False
        
        picking_ids = context['active_ids']
        for obj in pick_obj.browse(cr, uid, picking_ids, context=context):
            if obj.chained_from_in_stock_picking:
                if obj.corresponding_in_picking_stock_picking.partner_id2:
                    return True
                else:
                    return False
    
    _columns = {'register_a_claim_partial_picking': fields.boolean(string='Register a Claim to Supplier'),
                'in_has_partner_id_partial_picking': fields.boolean(string='IN has Partner specified.', readonly=True),
                'partner_id_partial_picking': fields.many2one('res.partner', string='Supplier', required=True),
                'claim_type_partial_picking' : fields.selection(lambda s, cr, uid, c: s.pool.get('return.claim').get_claim_event_type(), string='Claim Type'),
                'replacement_picking_expected_partial_picking': fields.boolean(string='Replacement expected for Return Claim?', help="An Incoming Shipment will be automatically created corresponding to returned products."),
                'description_partial_picking': fields.text(string='Claim Description')}

    _defaults = {'register_a_claim_partial_picking': False,
                 'partner_id_partial_picking': _get_default_supplier,
                 'in_has_partner_id_partial_picking': _get_has_supplier,
                 'replacement_picking_expected_partial_picking': False}
    
    def do_partial_hook(self, cr, uid, context, *args, **kwargs):
        '''
        add hook to do_partial
        '''
        partial_datas = super(stock_partial_picking, self).do_partial_hook(cr, uid, context=context, *args, **kwargs)
        assert partial_datas, 'partial_datas missing > return_claim > wizard > stock_partial_picking'
        
        # get pick object
        partial = kwargs['partial']
        # update partial data with claim policy
        partial_datas.update({'register_a_claim_partial_picking': False})
        if partial.register_a_claim_partial_picking:
            if not partial.claim_type_partial_picking:
                raise osv.except_osv(_('Warning !'), _('The type of claim must be selected.'))
            if not partial.partner_id_partial_picking:
                raise osv.except_osv(_('Warning !'), _('The partner of claim must be selected.'))
            partial_datas.update({'register_a_claim_partial_picking': True,
                                  'partner_id_partial_picking': partial.partner_id_partial_picking.id,
                                  'claim_type_partial_picking': partial.claim_type_partial_picking,
                                  'replacement_picking_expected_partial_picking': partial.replacement_picking_expected_partial_picking,
                                  'description_partial_picking': partial.description_partial_picking})
        
        return partial_datas
    
    def return_hook_do_partial(self, cr, uid, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the do_partial method from stock_override>wizard>stock_partial_picking.py>stock_partial_picking
        
        - allow to modify returned value from button method
        '''
        # depending on the claim, we return a different view
        # return claim to supplier: standard out view
        # we do not need to test the claim type (supplier, customer, tranpsport), as
        # only supplier claims can be registered from picking wizard
        # objects
        obj_data = self.pool.get('ir.model.data')
        # get partial datas
        partial_datas = kwargs['partial_datas']
        # res
        res = kwargs['res']
        if 'register_a_claim_partial_picking' in partial_datas and partial_datas['register_a_claim_partial_picking']:
            if partial_datas['claim_type_partial_picking'] == 'return':
                view_id = obj_data.get_object_reference(cr, uid, 'stock', 'view_picking_out_form')
                view_id = view_id and view_id[1] or False
                # id of treated picking (can change according to backorder or not)
                pick_id = res.values()[0]['delivered_picking']
                return {'name': _('Delivery Orders'),
                        'view_mode': 'form,tree',
                        'view_id': [view_id],
                        'view_type': 'form',
                        'res_model': 'stock.picking',
                        'res_id': pick_id,
                        'type': 'ir.actions.act_window',
                        'target': 'crash',
                        'domain': '[]',
                        'context': context}
        
        return {'type': 'ir.actions.act_window_close'}
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        result = super(stock_partial_picking, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

        pick_obj = self.pool.get('stock.picking')
        picking_ids = context.get('active_ids', False)

        if not picking_ids:
            # not called through an action (e.g. buildbot), return the default.
            return result

        # is it possible to register a claim - internal + chained picking from incoming shipment
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            register_ok = pick.chained_from_in_stock_picking
        
        if register_ok:
            arch = result['arch']
            arch = arch.replace('<separator string="" colspan="4" />',
                                '''
                                <separator string="Register a Claim to the Supplier for selected products." colspan="4" />
                                <notebook colspan="4">
                                <page string="Claim">
                                <field name="register_a_claim_partial_picking"/><field name="in_has_partner_id_partial_picking" invisible="True" />
                                <field name="partner_id_partial_picking" attrs="{\'readonly\': ['|', (\'register_a_claim_partial_picking\', \'=\', False), (\'in_has_partner_id_partial_picking\', \'=\', True)]}"
                                        context="{'search_default_supplier': True}"/>
                                <field name="claim_type_partial_picking" attrs="{\'readonly\': [(\'register_a_claim_partial_picking\', \'=\', False)]}"/>
                                <field name="replacement_picking_expected_partial_picking" attrs="{\'invisible\': [(\'claim_type_partial_picking\', \'!=\', 'return')]}"/>
                                </page>
                                <page string="Claim Description">
                                <field name="description_partial_picking" colspan="4" nolabel="True"/>
                                </page>
                                </notebook>
                                <separator string="" colspan="4"/>''')
            result['arch'] = arch
        
        return result
    

stock_partial_picking()
