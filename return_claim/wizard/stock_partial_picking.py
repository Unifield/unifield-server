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
    _columns = {'register_a_claim_partial_picking': fields.boolean(string='Register a Claim to Supplier'),
                'claim_type_partial_picking' : fields.selection(lambda s, cr, uid, c: s.pool.get('return.claim').get_claim_event_type(), string='Claim Type'),
                'replacement_picking_expected_partial_picking': fields.boolean(string='Replacement expected for Return Claim?', help="An Incoming Shipment will be automatically created corresponding to returned products."),
                'description_partial_picking': fields.text(string='Claim Description')}

    _defaults = {'register_a_claim_partial_picking': False}
    
    def do_partial_hook(self, cr, uid, context, *args, **kwargs):
        '''
        add hook to do_partial
        '''
        partial_datas = super(stock_partial_picking, self).do_partial_hook(cr, uid, context=context, *args, **kwargs)
        assert partial_datas, 'partial_datas missing'
        
        # get pick object
        partial = kwargs['partial']
        # update partial data with claim policy
        partial_datas.update({'register_a_claim_partial_picking': False})
        if partial.register_a_claim_partial_picking:
            if not partial.claim_type_partial_picking:
                raise osv.except_osv(_('Warning !'), _('The type of claim must be selected.'))
            partial_datas.update({'register_a_claim_partial_picking': True,
                                  'claim_type_partial_picking': partial.claim_type_partial_picking,
                                  'replacement_picking_expected_partial_picking': partial.replacement_picking_expected_partial_picking,
                                  'description_partial_picking': partial.description_partial_picking})
        
        return partial_datas
    
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
                                <field name="register_a_claim_partial_picking"/><group colspan="2"/>
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
