# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

# Server imports
from osv import osv
from osv import fields
from tools.translate import _

# Module imports
from msf_order_date import TRANSPORT_TYPE


class wizard_import_in_simulation_screen(osv.osv):
    _name = 'wizard.import.in.simulation.screen'

    def _get_related_values(self, cr, uid, ids, field_name, args, context=None):
        '''
        Get the values related to the picking
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for simu in self.browse(cr, uid, ids, context=context):
            res[simu.id] = {'origin': simu.picking_id.origin,
                            'creation_date': simu.picking_id.date,
                            'purchase_id': simu.picking_id.purchase_id and simu.picking_id.purchase_id.id or False,
                            'backorder_id': simu.picking_id.backorder_id and simu.picking_id.backorder_id.id or False,
                            'header_notes': simu.picking_id.note,
                            'freight_number': simu.picking_id.shipment_ref,
                            'transport_mode': simu.picking_id and simu.picking_id.purchase_id and simu.picking_id.purchase_id.transport_mode or False}

        return res

    _columns = {
        'picking_id': fields.many2one('stock.picking', string='Incoming shipment', required=True, readonly=True),
        # File information
        'file_to_import': fields.binary(string='File to import'),               
        'filename': fields.char(size=64, string='Filename'),                    
        'filetype': fields.selection([('excel', 'Excel file'),                  
                                      ('xml', 'XML file')], string='Type of file',
                                     required=True),                           
        'error_file': fields.binary(string='File with errors'),                 
        'error_filename': fields.char(size=64, string='Lines with errors'),     
        'nb_file_lines': fields.integer(string='Total of file lines',           
                                        readonly=True),                         
        'nb_treated_lines': fields.integer(string='Nb treated lines',           
                                           readonly=True),                      
        'percent_completed': fields.float(string='Percent completed',           
                                          readonly=True),                       
        'import_error_ok': fields.boolean(string='Error at import'),
        # Related fields
        'origin': fields.function(_get_related_values, method=True, string='Origin',
                                  readonly=True, type='char', size=128, multi='related'),
        'creation_date': fields.function(_get_related_values, method=True, string='Creation date',
                                         readonly=True, type='datetime', multi='related'),
        'purchase_id': fields.function(_get_related_values, method=True, string='Purchase Order',
                                       readonly=True, type='many2one', relation='purchase.order', multi='related'),
        'backorder_id': fields.function(_get_related_values, method=True, string='Back Order Of',
                                        readonly=True, type='many2one', relation='stock.picking', multi='related'),
        'header_notes': fields.function(_get_related_values, method=True, string='Header notes',
                                        readonly=True, type='text', multi='related'),
        'freight_number': fields.function(_get_related_values, method=True, string='Freight number',
                                          readonly=True, type='char', size=128, multi='related'),
        'transport_mode': fields.function(_get_related_values, method=True, string='Transport mode',
                                          readonly=True, type='selection', selection=TRANSPORT_TYPE, multi='related'),
        # Import fields
        'message_esc': fields.text(string='Message ESC', readonly=True),
        # Lines
        'line_ids': fields.one2many('wizard.import.in.line.simulation.screen', 'simu_id', string='Stock moves'),
                                         
    }

wizard_import_in_simulation_screen()


class wizard_import_in_line_simulation_screen(osv.osv):
    _name = 'wizard.import.in.line.simulation.screen'

    def _get_values(self, cr, uid, ids, field_name, args, context=None):
        '''
        Compute values according to values in line
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            product = line.imp_product_id or line.move_product_id
            res[line.id] = {'lot_check': product.batch_management,
                            'exp_check': product.perishable,
                            'kc_check': product.heat_sensitive_item and True or False,
                            'dg_check': product.dangerous_goods,
                            'np_check': product.narcotic,}

        return res

    _columns = {
        'simu_id': fields.many2one('wizard.import.in.simulation.screen', string='Simu ID', required=True),
        # Values from move line
        'move_id': fields.many2one('stock.move', string='Move', readonly=True),
        'move_product_id': fields.many2one('product.product', string='Product', readonly=True),
        'move_product_qty': fields.float(digits=(16,2), string='Ordered Qty', readonly=True),
        'move_uom_id': fields.many2one('product.uom', string='Ordered UoM', readonly=True),
        'move_price_unit': fields.float(digits=(16,2), string='Price Unit', readonly=True),
        'move_currency_id': fields.many2one('res.currency', string='Curr.', readonly=True),
        # Values for the simu line
        'line_number': fields.integer(string='Line'),
        'change_type': fields.selection([('', ''),
                                         ('split', 'Split'),
                                         ('error', 'Error'),
                                         ('new', 'New')], string='CHG', readonly=True),
        # Values after import
        'imp_product_id': fields.many2one('product.product', string='Product', readonly=True),
        'imp_asset_id': fields.many2one('product.asset', string='Asset', readonly=True),
        'imp_product_qty': fields.float(digits=(16,2), string='Qty to Process', readonly=True),
        'imp_uom_id': fields.many2one('product.uom', string='UoM', readonly=True),
        'imp_price_unit': fields.float(digits=(16,2), string='Price Unit', readonly=True),
        'imp_cost': fields.float(digits=(16,2), string='Cost', readonly=True),
        'discrepancy': fields.float(digits=(16,2), string='Discre.', readonly=True),
        'imp_currency_id': fields.many2one('res.currency', string='Curr.', readonly=True),
        'imp_batch_id': fields.many2one('stock.production.lot', string='Batch Number', readonly=True),
        'imp_exp_date': fields.date(string='Expiry date', readonly=True),
        'message_esc1': fields.char(size=256, string='Message ESC 1', readonly=True),
        'message_esc2': fields.char(size=256, string='Message ESC 2', readonly=True),
        # Computed fields
        'lot_check': fields.function(_get_values, method=True, type='boolean',
                                     string='B.Num', readonly=True, store=False, multi='computed'),
        'exp_check': fields.function(_get_values, method=True, type='boolean',
                                     string='Exp', readonly=True, store=False, multi='computed'),
        'kc_check': fields.function(_get_values, method=True, type='boolean',
                                     string='KC', readonly=True, store=False, multi='computed'),
        'dg_check': fields.function(_get_values, method=True, type='boolean',
                                     string='DG', readonly=True, store=False, multi='computed'),
        'np_check': fields.function(_get_values, method=True, type='boolean',
                                     string='NP', readonly=True, store=False, multi='computed'),
    }

wizard_import_in_line_simulation_screen()
