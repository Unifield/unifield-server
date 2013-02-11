# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv
import re
from tools.translate import _

class product_section_code(osv.osv):
    _name = "product.section.code"
    _columns = {
        'code': fields.char('Code', size=4),
        'section': fields.char('Section', size=32),
        'description': fields.char('Description', size=128),
    }
product_section_code()

class product_supply_source(osv.osv):
    _name = "product.supply.source"
    _columns = {
        'source': fields.char('Supply source', size=32),
    }
product_supply_source()

class product_justification_code(osv.osv):
    _name = "product.justification.code"
    _columns = {
        'code': fields.char('Justification Code', size=32),
        'description': fields.char('Justification Description', size=256),
    }
    
    def name_get(self, cr, user, ids, context=None):
        if not ids:
            return []
        reads = self.read(cr, user, ids, ['code'], context=context)
        res = []
        for record in reads:
            code = record['code']
            res.append((record['id'], code))
        return res
        
product_justification_code()

class product_attributes_template(osv.osv):
    _inherit = "product.template"
    
    _columns = {
        'type': fields.selection([('product','Stockable Product'),('consu', 'Non-Stockable')], 'Product Type', required=True, help="Will change the way procurements are processed. Consumables are stockable products with infinite stock, or for use when you have no inventory management in the system."),
    }
    
    _defaults = {
        'type': 'product',
        'cost_method': lambda *a: 'average',
    }
    
product_attributes_template()


class product_country_restriction(osv.osv):
    _name = 'res.country.restriction'
    
    _columns = {
        'name': fields.char(size=128, string='Restriction'),
        'product_ids': fields.one2many('product.product', 'country_restriction', string='Products'),
    }
    
product_country_restriction()


class product_attributes(osv.osv):
    _inherit = "product.product"
    
    def _get_nomen(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        
        for product in self.browse(cr, uid, ids, context=context):
            res[product.id] = []
            res[product.id].append(product.nomen_manda_0.id)
            res[product.id].append(product.nomen_manda_1.id)
            res[product.id].append(product.nomen_manda_2.id)
            res[product.id].append(product.nomen_manda_3.id)
            res[product.id].append(product.nomen_sub_0.id)
            res[product.id].append(product.nomen_sub_1.id)
            res[product.id].append(product.nomen_sub_2.id)
            res[product.id].append(product.nomen_sub_3.id)
            res[product.id].append(product.nomen_sub_4.id)
            res[product.id].append(product.nomen_sub_5.id)
            
        return res
    
    def _search_nomen(self, cr, uid, obj, name, args, context=None):
        '''
        Filter the search according to the args parameter
        '''
        if not context:
            context = {}
            
        ids = []
            
        for arg in args:
            if arg[0] == 'nomen_ids' and arg[1] == '=' and arg[2]:
                nomen = self.pool.get('product.nomenclature').browse(cr, uid, arg[2], context=context)
                if nomen.type == 'mandatory':
                    ids = self.search(cr, uid, [('nomen_manda_%s' % nomen.level, '=', nomen.id)], context=context)
                else:
                    ids = self.search(cr, uid, [('nomen_sub_0', '=', nomen.id)], context=context)
                    ids.append(self.search(cr, uid, [('nomen_sub_1', '=', nomen.id)], context=context))
                    ids.append(self.search(cr, uid, [('nomen_sub_2', '=', nomen.id)], context=context))
                    ids.append(self.search(cr, uid, [('nomen_sub_3', '=', nomen.id)], context=context))
                    ids.append(self.search(cr, uid, [('nomen_sub_4', '=', nomen.id)], context=context))
                    ids.append(self.search(cr, uid, [('nomen_sub_5', '=', nomen.id)], context=context))
            elif arg[0] == 'nomen_ids' and arg[1] == 'in' and arg[2]:
                for nomen in self.pool.get('product.nomenclature').browse(cr, uid, arg[2], context=context):
                    if nomen.type == 'mandatory':
                        ids = self.search(cr, uid, [('nomen_manda_%s' % nomen.level, '=', nomen.id)], context=context)
                    else:
                        ids = self.search(cr, uid, [('nomen_sub_0', '=', nomen.id)], context=context)
                        ids.append(self.search(cr, uid, [('nomen_sub_1', '=', nomen.id)], context=context))
                        ids.append(self.search(cr, uid, [('nomen_sub_2', '=', nomen.id)], context=context))
                        ids.append(self.search(cr, uid, [('nomen_sub_3', '=', nomen.id)], context=context))
                        ids.append(self.search(cr, uid, [('nomen_sub_4', '=', nomen.id)], context=context))
                        ids.append(self.search(cr, uid, [('nomen_sub_5', '=', nomen.id)], context=context))
            else:
                return []
            
        return [('id', 'in', ids)] 
    
    _columns = {
        'duplicate_ok': fields.boolean('Is a duplicate'),
        'loc_indic': fields.char('Indicative Location', size=64),
        'description2': fields.text('Description 2'),
        'old_code' : fields.char('Old code', size=64),
        'new_code' : fields.char('New code', size=64),
        'international_status': fields.selection([('itc','ITC'),('esc', 'ESC'),('hq', 'HQ'),('local','Local'),('temp','Temporary')], 
                                                 string='Product Creator', required=True),
        'state': fields.selection([('',''),
            ('draft','Introduction'),
            ('sellable','Normal'),
            ('transfer','Transfer'),
            ('end_alternative','End of Life (alternative available)'),
            ('end','End of Life (not supplied anymore)'),
            ('obsolete','Warning list')], 'Status', help="Tells the user if he can use the product or not."),
        'perishable': fields.boolean('Expiry Date Mandatory'),
        'batch_management': fields.boolean('Batch Number Mandatory'),
        'product_catalog_page' : fields.char('Product Catalog Page', size=64),
        'product_catalog_path' : fields.char('Product Catalog Path', size=64),
        'short_shelf_life': fields.boolean('Short Shelf Life'),
        'criticism': fields.selection([('',''),
            ('exceptional','1-Exceptional'),
            ('specific','2-Specific'),
            ('important','3-Important'),
            ('medium','4-Medium'),
            ('common','5-Common'),
            ('other','X-Other')], 'Criticality'),
        'narcotic': fields.boolean('Narcotic/Psychotropic'),
        'abc_class': fields.selection([('',''),
            ('a','A'),
            ('b','B'),
            ('c','C')], 'ABC Class'),
        'section_code_ids': fields.many2many('product.section.code','product_section_code_rel','product_id','section_code_id','Section Code'),
        'library': fields.selection([('',''),
            ('l1','L1'),
            ('l2','L2'),
            ('l3','L3'),
            ('l4','L4')], 'Library'),
        'supply_source_ids': fields.many2many('product.supply.source','product_supply_source_rel','product_id','supply_source_id','Supply Source'),
        'sublist' : fields.char('Sublist', size=64),
        'composed_kit': fields.boolean('Kit Composed of Kits/Modules'),
        'options_ids': fields.many2many('product.product','product_options_rel','product_id','product_option_id','Options'),
        'heat_sensitive_item': fields.selection([('',''),
            ('KR','Keep refrigerated but not cold chain (+2 to +8°C) for transport'),
            ('*','Keep Cool'),
            ('**','Keep Cool, airfreight'),
            ('***','Cold chain, 0° to 8°C strict')], string='Temperature sensitive item'),
        'cold_chain': fields.selection([('',''),
            ('3*','3* Cold Chain * - Keep Cool: used for a kit containing cold chain module or item(s)'),
            ('6*0','6*0 Cold Chain *0 - Problem if any window blue'),
            ('7*0F','7*0F Cold Chain *0F - Problem if any window blue or Freeze-tag = ALARM'),
            ('8*A','8*A Cold Chain *A - Problem if B, C and/or D totally blue'),
            ('9*AF','9*AF Cold Chain *AF - Problem if B, C and/or D totally blue or Freeze-tag = ALARM'),
            ('10*B','10*B Cold Chain *B - Problem if C and/or D totally blue'),
            ('11*BF','11*BF Cold Chain *BF - Problem if C and/or D totally blue or Freeze-tag = ALARM'),
            ('12*C','12*C Cold Chain *C - Problem if D totally blue'),
            ('13*CF','13*CF Cold Chain *CF - Problem if D totally blue or Freeze-tag = ALARM'),
            ('14*D','14*D Cold Chain *D - Store and transport at -25°C (store in deepfreezer, transport with dry-ice)'),
            ('15*F','15*F Cold Chain *F - Cannot be frozen: check Freeze-tag '),
            ('16*25','16*25 Cold Chain *25 - Must be kept below 25°C (but not necesseraly in cold chain)'),
            ('17*25F','17*25F Cold Chain *25F - Must be kept below 25°C and cannot be frozen: check  Freeze-tag '),
            ], 'Cold Chain'),
        'sterilized': fields.selection([('yes', 'Yes'), ('no', 'No')], string='Sterile'),
        'single_use': fields.selection([('yes', 'Yes'),('no', 'No')], string='Single Use'),
        'justification_code_id': fields.many2one('product.justification.code', 'Justification Code'),
        'med_device_class': fields.selection([('',''),
            ('I','Class I (General controls)'),
            ('II','Class II (General control with special controls)'),
            ('III','Class III (General controls and premarket)')], 'Medical Device Class'),
        'closed_article': fields.selection([('yes', 'Yes'), ('no', 'No'),],string='Closed Article'),
        'dangerous_goods': fields.boolean('Dangerous Goods'),
        'restricted_country': fields.boolean('Restricted in the Country'),
        'country_restriction': fields.many2one('res.country.restriction', 'Country Restriction'),
        # TODO: validation on 'un_code' field
        'un_code': fields.char('UN Code', size=7),
        'gmdn_code' : fields.char('GMDN Code', size=5),
        'gmdn_description' : fields.char('GMDN Description', size=64),
        'life_time': fields.integer('Product Life Time',
            help='The number of months before a production lot may become dangerous and should not be consumed.'),
        'use_time': fields.integer('Product Use Time',
            help='The number of months before a production lot starts deteriorating without becoming dangerous.'),
        'removal_time': fields.integer('Product Removal Time',
            help='The number of months before a production lot should be removed.'),
        'alert_time': fields.integer('Product Alert Time', help="The number of months after which an alert should be notified about the production lot."),
        'currency_id': fields.many2one('res.currency', string='Currency', readonly=True),
        'field_currency_id': fields.many2one('res.currency', string='Currency', readonly=True),
        'nomen_ids': fields.function(_get_nomen, fnct_search=_search_nomen,
                             type='many2many', relation='product.nomenclature', method=True, string='Nomenclatures'),
        'controlled_substance': fields.boolean(string='Controlled substance'),
    }
    
    _defaults = {
        'international_status': 'itc',
        'duplicate_ok': True,
        'perishable': False,
        'batch_management': False,
        'short_shelf_life': False,
        'narcotic': False,
        'composed_kit': False,
        'dangerous_goods': False,
        'restricted_country': False,
        'currency_id': lambda obj, cr, uid, c: obj.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id,
        'field_currency_id': lambda obj, cr, uid, c: obj.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id,
    }
    
    def _check_gmdn_code(self, cr, uid, ids, context=None):
        int_pattern = re.compile(r'^\d*$')
        for product in self.browse(cr, uid, ids, context=context):
            if product.gmdn_code and not int_pattern.match(product.gmdn_code):
                return False
        return True
    
    def create(self, cr, uid, vals, context=None):
        if 'batch_management' in vals:
            vals['track_production'] = vals['batch_management']
            vals['track_incoming'] = vals['batch_management']
            vals['track_outgoing'] = vals['batch_management']
            if vals['batch_management']:
                vals['perishable'] = True
        if 'default_code' in vals:
            if vals['default_code'] == 'XXX':
                vals.update({'duplicate_ok': True})
            else:
                vals.update({'duplicate_ok': False})
        return super(product_attributes, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        if 'batch_management' in vals:
            vals['track_production'] = vals['batch_management']
            vals['track_incoming'] = vals['batch_management']
            vals['track_outgoing'] = vals['batch_management']
            if vals['batch_management']:
                vals['perishable'] = True
        if 'default_code' in vals:
            if vals['default_code'] == 'XXX':
                vals.update({'duplicate_ok': True})
            else:
                vals.update({'duplicate_ok': False})
        return super(product_attributes, self).write(cr, uid, ids, vals, context=context)
    
    def reactivate_product(self, cr, uid, ids, context=None):
        '''
        Re-activate product.
        '''
        for product in self.browse(cr, uid, ids, context=context):
            if product.active:
                raise osv.except_osv(_('Error'), _('The product [%s] %s is already active.') % (product.default_code, product.name))
        
        self.write(cr, uid, ids, {'active': True}, context=context)
        
        return True
    
    def deactivate_product(self, cr, uid, ids, context=None):
        '''
        De-activate product. 
        Check if the product is not used in any document in Unifield
        '''
        if not context:
            context = {}
            
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        location_obj = self.pool.get('stock.location')
        po_line_obj = self.pool.get('purchase.order.line')
        tender_line_obj = self.pool.get('tender.line')
        fo_line_obj = self.pool.get('sale.order.line')
        move_obj = self.pool.get('stock.move')
        kit_obj = self.pool.get('composition.item')
        inv_obj = self.pool.get('stock.inventory.line')
        in_inv_obj = self.pool.get('initial.stock.inventory.line')
        auto_supply_obj = self.pool.get('stock.warehouse.automatic.supply')
        auto_supply_line_obj = self.pool.get('stock.warehouse.automatic.supply.line')
        cycle_obj = self.pool.get('stock.warehouse.order.cycle')
        cycle_line_obj = self.pool.get('stock.warehouse.order.cycle.line')
        threshold_obj = self.pool.get('threshold.value')
        threshold_line_obj = self.pool.get('threshold.value.line')
        orderpoint_obj = self.pool.get('stock.warehouse.orderpoint')
        invoice_obj = self.pool.get('account.invoice.line')

        error_obj = self.pool.get('product.deactivation.error')
        error_line_obj = self.pool.get('product.deactivation.error.line')
        
        internal_loc = location_obj.search(cr, uid, [('usage', '=', 'internal')], context=context)
        
        c = context.copy()
        c.update({'location_id': internal_loc})
        
        for product in self.browse(cr, uid, ids, context=context):
            # Raise an error if the product is already inactive
            if not product.active:
                raise osv.except_osv(_('Error'), _('The product [%s] %s is already inactive.') % (product.default_code, product.name))
            
            # Check if the product is in some purchase order lines or request for quotation lines
            has_po_line = po_line_obj.search(cr, uid, [('product_id', '=', product.id),
                                                       ('order_id.state', 'not in', ['draft', 'done', 'cancel'])], context=context)
                
            # Check if the product is in some tender lines
            has_tender_line = tender_line_obj.search(cr, uid, [('product_id', '=', product.id),
                                                               ('tender_id.state', 'not in', ['draft', 'done', 'cancel'])], context=context)
                
            # Check if the product is in field order lines or in internal request lines
            context.update({'procurement_request': True})
            has_fo_line = fo_line_obj.search(cr, uid, [('product_id', '=', product.id),
                                                       ('order_id.state', 'not in', ['draft', 'done', 'cancel'])], context=context)
            
            # Check if the product is in stock picking
            # All stock moves in a stock.picking not draft/cancel/done or all stock moves in a shipment not delivered/done/cancel
            has_move_line = move_obj.search(cr, uid, [('product_id', '=', product.id),
                                                      ('picking_id', '!=', False),
                                                      '|', ('picking_id.state', 'not in', ['draft', 'done', 'cancel']),
                                                      '&', ('picking_id.shipment_id', '!=', False),
                                                      ('picking_id.shipment_id.state', 'not in', ['delivered', 'done', 'cancel']),
                                                      ], context=context)
#            has_move_line = move_obj.search(cr, uid, [('product_id', '=', product.id),
#                                                      ('picking_id', '!=', False),
#                                                      '|', '&', ('picking_id.state', 'not in', ['draft', 'done', 'cancel']),
#                                                      ('picking_id.shipment_id', '!=', False),
#                                                      ('picking_id.shipment_id.state', 'not in', ['delivered', 'done', 'cancel'])], context=context)
                
            # Check if the product is in a stock inventory
            has_inventory_line = inv_obj.search(cr, uid, [('product_id', '=', product.id),
                                                          ('inventory_id', '!=', False),
                                                          ('inventory_id.state', 'not in', ['draft', 'done', 'cancel'])], context=context)
            
            # Check if the product is in an initial stock inventory
            has_initial_inv_line = in_inv_obj.search(cr, uid, [('product_id', '=', product.id),
                                                          ('inventory_id', '!=', False),
                                                          ('inventory_id.state', 'not in', ['draft', 'done', 'cancel'])], context=context)
                
            # Check if the product is in a real kit composition
            has_kit = kit_obj.search(cr, uid, [('item_product_id', '=', product.id),
                                               ('item_kit_id.composition_type', '=', 'real'),
                                               ('item_kit_id.state', '=', 'completed'),
                                              ], context=context)

            # Check if the product is in an invoice
            has_invoice_line = invoice_obj.search(cr, uid, [('product_id', '=', product.id),
                                                            ('invoice_id', '!=', False),
                                                            ('invoice_id.state', 'not in', ['draft', 'done', 'cancel'])], context=context)
            
            # Check if the product has stock in internal locations
            has_stock = product.qty_available
            
            opened_object = has_kit or has_initial_inv_line or has_inventory_line or has_move_line or has_fo_line or has_tender_line or has_po_line or has_invoice_line
            if has_stock or opened_object:
                # Create the error wizard
                wizard_id = error_obj.create(cr, uid, {'product_id': product.id,
                                                       'stock_exist': has_stock and True or False,
                                                       'opened_object': opened_object}, context=context)
                
                # Create lines for error in PO/RfQ
                po_ids = []
                for po_line in po_line_obj.browse(cr, uid, has_po_line, context=context):
                    if po_line.order_id.id not in po_ids:
                        po_ids.append(po_line.order_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': po_line.order_id.rfq_ok and 'Request for Quotation' or 'Purchase order',
                                                        'internal_type': 'purchase.order',
                                                        'doc_ref': po_line.order_id.name,
                                                        'doc_id': po_line.order_id.id}, context=context)
                        
                # Create lines for error in Tender
                tender_ids = []
                for tender_line in tender_line_obj.browse(cr, uid, has_tender_line, context=context):
                    if tender_line.tender_id.id not in tender_ids:
                        tender_ids.append(tender_line.tender_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': 'Tender',
                                                        'internal_type': 'tender',
                                                        'doc_ref': tender_line.tender_id.name,
                                                        'doc_id': tender_line.tender_id.id}, context=context)
                        
                # Create lines for error in FO/IR
                fo_ids = []
                for fo_line in fo_line_obj.browse(cr, uid, has_fo_line, context=context):
                    if fo_line.order_id.id not in fo_ids:
                        fo_ids.append(fo_line.order_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': fo_line.order_id.procurement_request and 'Internal request' or 'Field order',
                                                        'internal_type': 'sale.order',
                                                        'doc_ref': fo_line.order_id.name,
                                                        'doc_id': fo_line.order_id.id}, context=context)
                        
                # Create lines for error in picking
                pick_ids = []
                ship_ids = []
                pick_type = {'in': 'Incoming shipment',
                             'internal': 'Internal move',
                             'out': 'Delivery Order'}
                pick_subtype = {'standard': 'Delivery Order', 
                                'picking': 'Picking Ticket', 
                                'ppl': 'PPL', 
                                'packing': 'Packing'}
                for move in move_obj.browse(cr, uid, has_move_line, context=context):
                    # Get the name of the stock.picking object
                    picking_type = pick_type.get(move.picking_id.type)
                    if move.picking_id.type == 'out':
                        picking_type = pick_subtype.get(move.picking_id.subtype)
                    
                    # If the error picking is in a shipment, display the shipment instead of the picking
                    if move.picking_id.shipment_id and move.picking_id.id not in ship_ids:
                        ship_ids.append(move.picking_id.shipment_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': 'Shipment',
                                                        'internal_type': 'shipment',
                                                        'doc_ref': move.picking_id.shipment_id.name,
                                                        'doc_id': move.picking_id.shipment_id.id}, context=context)
                        
                    elif not move.picking_id.shipment_id and move.picking_id.id not in pick_ids:
                        pick_ids.append(move.picking_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': picking_type,
                                                        'internal_type': 'stock.picking',
                                                        'doc_ref': move.picking_id.name,
                                                        'doc_id': move.picking_id.id}, context=context)
                        
                # Create lines for error in kit composition
                kit_ids = []
                for kit in kit_obj.browse(cr, uid, has_kit, context=context):
                    if kit.id not in kit_ids:
                        kit_ids.append(kit.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': kit.item_kit_id.composition_type == 'real' and 'Kit Composition' or 'Theorical Kit Composition',
                                                        'internal_type': 'composition.kit',
                                                        'doc_ref': kit.item_kit_id.composition_type == 'real' and kit.item_kit_id.composition_reference or kit.item_kit_id.name,
                                                        'doc_id': kit.item_kit_id.id}, context=context)
                        
                # Create lines for error in inventory
                inv_ids = []
                for inv in inv_obj.browse(cr, uid, has_inventory_line, context=context):
                    if inv.inventory_id.id not in inv_ids:
                        inv_ids.append(inv.inventory_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': 'Physical Inventory',
                                                        'internal_type': 'stock.inventory',
                                                        'doc_ref': inv.inventory_id.name,
                                                        'doc_id': inv.inventory_id.id}, context=context)
                        
                # Create lines for error in inventory
                inv_ids = []
                for inv in in_inv_obj.browse(cr, uid, has_initial_inv_line, context=context):
                    if inv.inventory_id.id not in inv_ids:
                        inv_ids.append(inv.inventory_id.id)
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': 'Initial stock inventory',
                                                        'internal_type': 'initial.stock.inventory',
                                                        'doc_ref': inv.inventory_id.name,
                                                        'doc_id': inv.inventory_id.id}, context=context)

                # Create lines for error in invoices
                invoice_ids = []
                for invoice in invoice_obj.browse(cr, uid, has_invoice_line, context=context):
                    if invoice.invoice_id.id not in invoice_ids:
                        invoice_ids.append(invoice.invoice_id.id)
                        obj = invoice.invoice_id
                        type_name = 'Invoice'
                        # Debit Note
                        if obj.type == 'out_invoice' and obj.is_debit_note and not obj.is_kind_donation:
                            type_name = 'Debit Note'
                        # Donation (in-kind donation)
                        elif obj.type == 'in_invoice' and not obj.is_debit_not and obj.is_kind_donation:
                            type_name = 'In-kind Donation'
                        # Intermission voucher out
                        elif obj.type == 'out_invoice' and not obj.is_debit_not and not obj.is_kind_donation and obj.is_intermission:
                            type_name = 'Intermission Voucher Out'
                        # Intermission voucher in
                        elif obj.type == 'in_invoice' and not obj.is_debit_note and not obj.is_inkind_donation and obj.is_intermission:
                            type_name = 'Intermission Voucher In'
                        # Customer Invoice
                        elif obj.type == 'out_invoice' and not obj.is_debit_note and not obj.is_kind_donation:
                            type_name = 'Customer Invoice'
                        # Supplier Invoice
                        elif obj.type == 'in_invoice' not register_line_ids and not obj.is_debit_note and not obj.is_kind_donation:
                            type_name = 'Supplier Invoice'
                        # Supplier Direct Invoice
                        elif obj.type == 'in_invoice' and obj.register_line_ids:
                            type_name = 'Supplier Direct Invoice'

                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': type_name,
                                                        'internal_type': 'account.invoice',
                                                        'doc_ref': invoice.invoice_id.number,
                                                        'doc_id': invoice.invoice_id.id}, context=context)
                
                return {'type': 'ir.actions.act_window',
                        'res_model': 'product.deactivation.error',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_id': wizard_id,
                        'target': 'new',
                        'context': context}
        
        # Remove the replenishment rules associated to this product
        # Automatic supply
        auto_line_ids = auto_supply_line_obj.search(cr, uid, [('product_id', 'in', ids)], context=context)
        for auto in auto_supply_line_obj.browse(cr, uid, auto_line_ids, context=context):
            if len(auto.supply_id.line_ids) == 1:
                auto_supply_obj.unlink(cr, uid, [auto.supply_id.id], context=context)
            else:
                auto_supply_line_obj.unlink(cr, uid, [auto.id], context=context)
                
        # Order cycle
        cycle_ids = cycle_line_obj.search(cr, uid, [('product_id', 'in', ids)], context=context)
        for cycle in cycle_line_obj.browse(cr, uid, cycle_ids, context=context):
            if len(cycle.order_cycle_id.product_line_ids) == 1:
                cycle_obj.unlink(cr, uid, [cycle.order_cycle_id.id], context=context)
            else:
                cycle_line_obj.unlink(cr, uid, [cycle.id], context=context)
                
        # Threshold value
        threshold_ids = threshold_line_obj.search(cr, uid, [('product_id', 'in', ids)], context=context)
        for threshold in threshold_line_obj.browse(cr, uid, threshold_ids, context=context):
            if len(threshold.threshold_value_id.line_ids) == 1:
                threshold_obj.unlink(cr, uid, [threshold.threshold_value_id.id], context=context)
            else:
                threshold_line_obj.unlink(cr, uid, [threshold.id], context=context)
                
        # Minimum stock rules
        orderpoint_ids = orderpoint_obj.search(cr, uid, [('product_id', 'in', ids)], context=context)
        orderpoint_obj.unlink(cr, uid, orderpoint_ids, context=context)
        
        self.write(cr, uid, ids, {'active': False}, context=context)
        
        return True
    
    def onchange_batch_management(self, cr, uid, ids, batch_management, context=None):
        '''
        batch management is modified -> modification of Expiry Date Mandatory (perishable)
        '''
        if batch_management:
            return {'value': {'perishable': True}}
        return {}
    
    def copy(self, cr, uid, id, default=None, context=None):
        product_xxx = self.search(cr, uid, [('default_code', '=', 'XXX')])
        if product_xxx:
            raise osv.except_osv(_('Warning'), _('A product with a code "XXX" already exists please edit this product to change its Code.'))
        product2copy = self.read(cr, uid, [id], ['default_code', 'name'])[0]
        if default is None:
            default = {}
        copy_pattern = _("%s (copy)")
        copydef = dict(name=(copy_pattern % product2copy['name']),
                       default_code="XXX",
                       # we set international_status to "temp" so that it won't be synchronized with this status
                       international_status='temp',
                       )
        copydef.update(default)
        return super(product_attributes, self).copy(cr, uid, id, copydef, context)
    
    def onchange_code(self, cr, uid, ids, default_code):
        '''
        Check if the code already exists
        '''
        res = {}
        if default_code:
            cr.execute("SELECT * FROM product_product pp where pp.default_code = '%s'" % default_code)
            duplicate = cr.fetchall()
            if duplicate:
                res.update({'warning': {'title': 'Warning', 'message':'The Code already exists'}})
        return res
    
    _constraints = [ 
        (_check_gmdn_code, 'Warning! GMDN code must be digits!', ['gmdn_code'])
    ]

product_attributes()


class product_deactivation_error(osv.osv_memory):
    _name = 'product.deactivation.error'
    
    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True, readonly=True),
        'stock_exist': fields.boolean(string='Stocks exist (internal locations)', readonly=True),
        'opened_object': fields.boolean(string='Product is contain in opened documents', readonly=True),
        'error_lines': fields.one2many('product.deactivation.error.line', 'error_id', string='Error lines'),
    }
    
    _defaults = {
        'stock_exist': False,
        'opened_object': False,
    }
    
product_deactivation_error()

class product_deactivation_error_line(osv.osv_memory):
    _name = 'product.deactivation.error.line'
    
    _columns = {
        'error_id': fields.many2one('product.deactivation.error', string='Error', readonly=True),
        'type': fields.char(size=64, string='Documents type'),
        'internal_type': fields.char(size=64, string='Internal document type'),
        'doc_ref': fields.char(size=64, string='Reference'),
        'doc_id': fields.integer(string='Internal Reference'),
        'view_id': fields.integer(string='Reference of the view to open'),
    }
    
    def open_doc(self, cr, uid, ids, context=None):
        '''
        Open the associated documents
        '''
        if not context:
            context = {}
            
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        for line in self.browse(cr, uid, ids, context=context):
            view_id, context = self._get_view(cr, uid, line, context=context)
            return {'type': 'ir.actions.act_window',
                    'name': line.type,
                    'res_model': line.internal_type,
                    'res_id': line.doc_id,
                    'view_mode': 'form,tree',
                    'view_type': 'form',
                    'target': 'current',
                    'view_id': view_id,
                    'nodestroy': True,
                    'context': context}

    def _get_view(self, cr, uid, line, context=None):
        '''
        Return the good view according to the type of the object
        '''
        if not context:
            context = {}
            
        view_id = False
        obj = self.pool.get(line.internal_type).browse(cr, uid, line.doc_id)
        
        if line.internal_type == 'composition.kit':
            context.update({'composition_type': 'theoretical'})
            if obj.composition_type == 'real':
                context.update({'composition_type': 'real'})
        elif line.internal_type == 'stock.picking':
            view_id = [self.pool.get('stock.picking')._hook_picking_get_view(cr, uid, [line.doc_id], context=context, pick=obj)[1]]
        elif line.internal_type == 'sale.order':
            context.update({'procurement_request': obj.procurement_request})
        elif line.internal_type == 'purchase.order':
            context.update({'rfq_ok': obj.rfq_ok})
        elif line.internal_type == 'account.invoice':
            # Debit Note
            if obj.type == 'out_invoice' and obj.is_debit_note and not obj.is_kind_donation:
                context.update({'type':'out_invoice', 'journal_type': 'sale', 'is_debit_note': True})
            # Donation (in-kind donation)
            elif obj.type == 'in_invoice' and not obj.is_debit_not and obj.is_kind_donation:
                context.update({'type':'in_invoice', 'journal_type': 'inkind'})
            # Intermission voucher out
            elif obj.type == 'out_invoice' and not obj.is_debit_not and not obj.is_kind_donation and obj.is_intermission:
                context.update({'type':'out_invoice', 'journal_type': 'intermission'})
            # Intermission voucher in
            elif obj.type == 'in_invoice' and not obj.is_debit_note and not obj.is_inkind_donation and obj.is_intermission:
                context.update({{'type':'in_invoice', 'journal_type': 'intermission'}})
            # Customer Invoice
            elif obj.type == 'out_invoice' and not obj.is_debit_note and not obj.is_kind_donation:
                context.update({'type':'out_invoice', 'journal_type': 'sale'})
            # Supplier Invoice
            elif obj.type == 'in_invoice' not register_line_ids and not obj.is_debit_note and not obj.is_kind_donation:
                context.update({'type':'in_invoice', 'journal_type': 'purchase'})
            # Supplier Direct Invoice
            elif obj.type == 'in_invoice' and obj.register_line_ids:
                context.update({'type':'in_invoice', 'journal_type': 'purchase'})

                
        return view_id, context

product_deactivation_error_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
