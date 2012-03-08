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
import time
import netsvc
import decimal_precision as dp
from datetime import datetime, timedelta

from msf_outgoing import INTEGRITY_STATUS_SELECTION

class substitute(osv.osv_memory):
    '''
    substitute wizard
    '''
    _name = "substitute"
    
    def validate_item_mirror(self, cr, uid, ids, context=None):
        '''
        validate the mirror objects for lot and expiry date
        
        - lot AND expiry date are mandatory for batch management products
        - expiry date is mandatory for perishable products
        
        return True or False
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        lot_obj = self.pool.get('stock.production.lot')
        # errors
        errors = {'missing_lot': False,
                  'missing_date': False,
                  'wrong_lot_type_need_standard': False,
                  'no_lot_needed': False,
                  }
        for obj in self.browse(cr, uid, ids, context=context):
            for item in obj.composition_item_ids:
                # reset the integrity status
                item.write({'integrity_status': 'empty'}, context=context)
                # product management type
                data = prod_obj.read(cr, uid, [item.product_id_substitute_item.id], ['batch_management', 'perishable'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                if management:
                    if not item.lot_mirror:
                        # lot is needed
                        errors.update(missing_lot=True)
                        item.write({'integrity_status': 'missing_lot'}, context=context)
                    else:
                        # we check the lot type is standard if the lot exists
                        # the type is not specified, as 1) name must be unique for one product 2) lot type cannot be mixed for one product, either std or int, not both
                        prodlot_ids = lot_obj.search(cr, uid, [('name', '=', item.lot_mirror),
                                                               ('product_id', '=', item.product_id_substitute_item.id)], context=context)
                        if prodlot_ids:
                            data = lot_obj.read(cr, uid, prodlot_ids, ['life_date','name','type'], context=context)
                            lot_type = data[0]['type']
                            if lot_type != 'standard':
                                errors.update(wrong_lot_type_need_standard=True)
                                item.write({'integrity_status': 'wrong_lot_type_need_standard'}, context=context)
                        else:
                            # the lot does not exist, the expiry date is mandatory
                            if not item.exp_substitute_item:
                                errors.update(missing_date=True)
                                item.write({'integrity_status': 'missing_date'}, context=context)
                elif perishable and not item.exp_substitute_item:
                    # expiry date is needed
                    errors.update(missing_date=True)
                    item.write({'integrity_status': 'missing_date'}, context=context)
                else:
                    # no lot needed
                    if item.lot_mirror:
                        errors.update(no_lot_needed=True)
                        item.write({'integrity_status': 'no_lot_needed'}, context=context)
        # check the encountered errors
        return all([not x for x in errors.values()])
    
    def validate_item_from_stock(self, cr, uid, ids, context=None):
        '''
        validate the from stock objects for lot and expiry date
        
        - lot AND expiry date are mandatory for batch management products
        - expiry date is mandatory for perishable products
        
        return True or False
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        lot_obj = self.pool.get('stock.production.lot')
        # errors
        errors = {'missing_lot': False,
                  'missing_date': False,
                  'wrong_lot_type_need_standard': False,
                  'must_be_greater_than_0': False,
                  }
        for obj in self.browse(cr, uid, ids, context=context):
            for item in obj.replacement_item_ids:
                # reset the integrity status
                item.write({'integrity_status': 'empty'}, context=context)
                # product management type
                data = prod_obj.read(cr, uid, [item.product_id_substitute_item.id], ['batch_management', 'perishable'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                if management:
                    if not item.lot_id_substitute_item:
                        # lot is needed
                        errors.update(missing_lot=True)
                        item.write({'integrity_status': 'missing_lot'}, context=context)
                    else:
                        data = lot_obj.read(cr, uid, [item.lot_id_substitute_item.id], ['life_date','name','type'], context=context)
                        lot_type = data[0]['type']
                        if lot_type != 'standard':
                            errors.update(wrong_lot_type_need_standard=True)
                            item.write({'integrity_status': 'wrong_lot_type_need_standard'}, context=context)
                elif perishable:
                    if not item.exp_substitute_item:
                        # expiry date is needed
                        errors.update(missing_date=True)
                        item.write({'integrity_status': 'missing_date'}, context=context)
                else:
                    # no lot needed
                    if item.lot_id_substitute_item:
                        errors.update(no_lot_needed=True)
                        item.write({'integrity_status': 'no_lot_needed'}, context=context)
                # quantity check
                if item.qty_substitute_item <= 0:
                    errors.update(must_be_greater_than_0=True)
                    item.write({'integrity_status': 'must_be_greater_than_0'}, context=context)
        # check the encountered errors
        return all([not x for x in errors.values()])
    
    def check_integrity(self, cr, uid, ids, context=None):
        '''
        call both integrity validation methods
        '''
        return self.validate_item_mirror(cr, uid, ids, context=context) and self.validate_item_from_stock(cr, uid, ids, context=context)
    
    def _load_common_data(self, cr, uid, ids, context=None):
        '''
        load common data into context
        - date
        - reason_type
        - location ids
        - company id
        - ...
        '''
        if context is None:
            context = {}
        context.setdefault('common', {})
        # objects
        date_tools = self.pool.get('date.tools')
        obj_data = self.pool.get('ir.model.data')
        comp_obj = self.pool.get('res.company')
        # date format
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        context['common']['db_date_format'] = db_date_format
        date_format = date_tools.get_date_format(cr, uid, context=context)
        context['common']['date_format'] = date_format
        # date is today
        date = time.strftime('%Y-%m-%d')
        context['common']['date'] = date
        # default company id
        company_id = comp_obj._company_default_get(cr, uid, 'stock.picking', context=context)
        context['common']['company_id'] = company_id
        # reason type
        reason_type_id = obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_kit')[1]
        context['common']['reason_type_id'] = reason_type_id
        # kitting location
        kitting_id = obj_data.get_object_reference(cr, uid, 'stock', 'location_production')[1]
        context['common']['kitting_id'] = kitting_id
        
        return True
    
    def _create_picking(self, cr, uid, ids, obj, date, context=None):
        '''
        create internal picking object
        
        name of picking according to actual step
        '''
        # objects
        kit_obj = self.pool.get('composition.kit')
        pick_obj = self.pool.get('stock.picking')
        # different behavior depending on step
        if context.get('step', False) == 'substitute':
            text = 'Kit Substitution'
        elif context.get('step', False) == 'de_kitting':
            text = 'De-Kitting'
        # we create the internal picking object
        pick_values = {'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.internal'),
                       'origin': text + ': ' + obj.kit_id.composition_product_id.name + ' - ' + kit_obj.name_get(cr, uid, [obj.kit_id.id], context=context)[0][1],
                       'type': 'internal',
                       'state': 'draft',
                       'sale_id': False,
                       'address_id': False,
                       'note': text,
                       'date': context['common']['date'],
                       'company_id': context['common']['company_id'],
                       'reason_type_id': context['common']['reason_type_id'],
                       }
        pick_id = pick_obj.create(cr, uid, pick_values, context=context)
        return pick_id
    
    def _handle_compo_item(self, cr, uid, ids, obj, item, items_to_stock_ids, pick_id, context=None):
        '''
        handle compo item, creating movement and integrity checks
        '''
        # objects
        lot_obj = self.pool.get('stock.production.lot')
        move_obj = self.pool.get('stock.move')
        # date format
        db_date_format = context['common']['db_date_format']
        date_format = context['common']['date_format']
        # date is today
        date = context['common']['date']
        # default company id
        company_id = context['common']['company_id']
        # reason type
        reason_type_id = context['common']['reason_type_id']
        # kitting location
        kitting_id = context['common']['kitting_id']
        # add to "to delete" list
        if item.item_id_mirror in items_to_stock_ids:
            raise osv.except_osv(_('Warning !'), _('Duplicated lines in Items from Kit to Stock.'))
        items_to_stock_ids.append(item.item_id_mirror)
        # need to create a production lot if needed
        prodlot_id = False
        if item.product_id_substitute_item.batch_management:
            # lot number must have been filled in
            if not item.lot_mirror:
                raise osv.except_osv(_('Warning !'), _('Batch Number is missing for %s.'%item.product_id_substitute_item.name))
            # we search for existing standard lot, if does not exist, we create a new one
            prodlot_ids = lot_obj.search(cr, uid, [('name', '=', item.lot_mirror),
                                                   ('type', '=', 'standard'),
                                                   ('product_id', '=', item.product_id_substitute_item.id)], context=context)
            if prodlot_ids:
                # we must check the expiry date match
                data = lot_obj.read(cr, uid, prodlot_ids, ['life_date','name'], context=context)
                lot_name = data[0]['name']
                expired_date = data[0]['life_date']
                if expired_date != item.exp_substitute_item:
                    # we display a log message - we do not raise an error because the kit is presently completed
                    # and cannot therefore be modified. So if we entered a date for a given batch number which
                    # was correct at the time of kit completion, but no more at time of substitution, we
                    # do not want to be blocked.
                    exp_obj = datetime.strptime(expired_date, db_date_format)
                    if item.exp_substitute_item:
                        exp_item = datetime.strptime(item.exp_substitute_item, db_date_format)
                        exp_item_text = item.exp_substitute_item
                    else:
                        exp_item_text = 'n/a'
                    lot_obj.log(cr, uid, prodlot_ids[0], _('Batch Number %s for %s with Expiry Date %s does not match the Expiry Date from the composition list %s.'%(lot_name,item.product_id_substitute_item.name,exp_obj.strftime(date_format),exp_item_text)))
                # select production lot
                prodlot_id = prodlot_ids[0]
            else:
                # lot number must have been filled in
                if not item.exp_substitute_item:
                    raise osv.except_osv(_('Warning !'), _('Expiry Date is missing for %s.'%item.product_id_substitute_item.name))
                # the batch does not exist, we create a new one
                lot_name = item.lot_mirror# or self.pool.get('ir.sequence').get(cr, uid, 'kit.lot')
                exp_item = datetime.strptime(item.exp_substitute_item, db_date_format)
                lot_values = {'product_id': item.product_id_substitute_item.id,
                              'life_date': item.exp_substitute_item,
                              'name': lot_name,
                              'type': 'standard',
                              }
                prodlot_id = lot_obj.create(cr, uid, lot_values, context=context)
                # lot creation message
                lot_obj.log(cr, uid, prodlot_id, _('Batch Number %s for %s with Expiry Date %s has been created.'%(lot_name,item.product_id_substitute_item.name,exp_item.strftime(date_format))))
        elif item.product_id_substitute_item.perishable:
            # expiry date must have been filled in
            if not item.exp_substitute_item:
                raise osv.except_osv(_('Warning !'), _('Batch Number/Expiry Date is missing for %s.'%item.product_id_substitute_item.name))
            # we search for existing internal lot, if does not exist, we create a new one
            prodlot_ids = lot_obj.search(cr, uid, [('life_date', '=', item.exp_substitute_item),
                                                   ('type', '=', 'internal'),
                                                   ('product_id', '=', item.product_id_substitute_item.id)], context=context)
            if prodlot_ids:
                # select production lot
                prodlot_id = prodlot_ids[0]
            else:
                # no internal lot for the specified date, create a new one
                name = self.pool.get('ir.sequence').get(cr, uid, 'stock.lot.serial')
                lot_values = {'product_id': item.product_id_substitute_item.id,
                              'life_date': item.exp_substitute_item,
                              'name': name,
                              'type': 'internal',
                              }
                prodlot_id = lot_obj.create(cr, uid, lot_values, context=context)
        # create corresponding stock move
        move_values = {'name': item.product_id_substitute_item.name[:64],
                       'picking_id': pick_id,
                       'product_id': item.product_id_substitute_item.id,
                       'date': date,
                       'date_expected': date,
                       'product_qty': item.qty_substitute_item,
                       'product_uom': item.uom_id_substitute_item.id,
                       'product_uos_qty': item.qty_substitute_item,
                       'product_uos': item.uom_id_substitute_item.id,
                       'product_packaging': False,
                       'address_id': False,
                       'location_id': kitting_id,
                       'location_dest_id': obj.destination_location_id.id,
                       'sale_line_id': False,
                       'tracking_id': False,
                       'state': 'draft',
                       'note': 'Kit Substitution - Back to Stock',
                       'company_id': company_id,
                       'reason_type_id': reason_type_id,
                       'prodlot_id': prodlot_id,
                       }
        move_obj.create(cr, uid, move_values, context=context)
        return True
    
    def _validate_internal_picking(self, cr, uid, ids, pick_id, context=None):
        '''
        confirm and validate the internal picking
        '''
        # objects
        pick_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'stock.picking', pick_id, 'button_confirm', cr)
        # simulate check assign button, as stock move must be available
        pick_obj.force_assign(cr, uid, [pick_id])
        # trigger standard workflow
        pick_obj.action_move(cr, uid, [pick_id])
        wf_service.trg_validate(uid, 'stock.picking', pick_id, 'button_done', cr)
        return True
    
    def do_substitute(self, cr, uid, ids, context=None):
        '''
        substitute method, no check on products availability is performed
        '''
        # objects
        move_obj = self.pool.get('stock.move')
        kit_obj = self.pool.get('composition.kit')
        item_obj = self.pool.get('composition.item')
        # load default data
        self._load_common_data(cr, uid, ids, context=context)
        
        # date is today
        date = context['common']['date']
        # default company id
        company_id = context['common']['company_id']
        # reason type
        reason_type_id = context['common']['reason_type_id']
        # kitting location
        kitting_id = context['common']['kitting_id']
        # kit ids
        kit_ids = context['active_ids']
        # integrity constraint
        integrity_check = self.validate_item_mirror(cr, uid, ids, context=context) and self.validate_item_from_stock(cr, uid, ids, context=context)
        if not integrity_check:
            # the windows must be updated to trigger tree colors
            return self.pool.get('wizard').open_wizard(cr, uid, kit_ids, type='update', context=context)
        for obj in self.browse(cr, uid, ids, context=context):
            # we create the internal picking object
            pick_id = self._create_picking(cr, uid, ids, obj, date, context=context)
            # list of items to be deleted (replaced ones)
            items_to_stock_ids = []
            # items to replace cannot be empty
            if not len(obj.composition_item_ids):
                raise osv.except_osv(_('Warning !'), _('Items to replace cannot be empty.'))
            # for each item to replace, we create a stock move from kitting to destination location
            for item in obj.composition_item_ids:
                # analyze each item
                self._handle_compo_item(cr, uid, ids, obj, item, items_to_stock_ids, pick_id, context=context)
            # we delete the corresponding items from the kit
            item_obj.unlink(cr, uid, items_to_stock_ids, context=context)
            # items to replace cannot be empty
            if not len(obj.replacement_item_ids):
                raise osv.except_osv(_('Warning !'), _('Replacement Items cannot be empty.'))
            # for each replacement item, we create a stock move from source location to kitting location
            # and create a kit item
            for item in obj.replacement_item_ids:
                # we check the batch if exists, should be linked to selected product
                if item.lot_id_substitute_item:
                    if item.lot_id_substitute_item.product_id.id != item.product_id_substitute_item.id:
                        raise osv.except_osv(_('Warning !'), _('Selected Batch Number does not correspond to selected Product'))
                # we check product qty
                if item.qty_substitute_item <= 0:
                    raise osv.except_osv(_('Warning !'), _('Replacement Item quantity must be greater than 0.'))
                # create corresponding stock move
                move_values =  {'name': item.product_id_substitute_item.name[:64],
                                'picking_id': pick_id,
                                'product_id': item.product_id_substitute_item.id,
                                'date': date,
                                'date_expected': date,
                                'product_qty': item.qty_substitute_item,
                                'product_uom': item.uom_id_substitute_item.id,
                                'product_uos_qty': item.qty_substitute_item,
                                'product_uos': item.uom_id_substitute_item.id,
                                'product_packaging': False,
                                'address_id': False,
                                'location_id': item.location_id_substitute_item.id,
                                'location_dest_id': kitting_id,
                                'sale_line_id': False,
                                'tracking_id': False,
                                'state': 'draft',
                                'note': 'Kit Substitution - Go to Kit',
                                'company_id': company_id,
                                'reason_type_id': reason_type_id,
                                'prodlot_id': item.lot_id_substitute_item.id,
                                }
                move_obj.create(cr, uid, move_values, context=context)
                # create corresponding kit item
                item_values = {'item_module': item.module_substitute_item,
                               'item_product_id': item.product_id_substitute_item.id,
                               'item_qty': item.qty_substitute_item,
                               'item_uom_id': item.uom_id_substitute_item.id,
                               'item_lot': item.lot_id_substitute_item.name,
                               'item_exp': item.exp_substitute_item,
                               'item_kit_id': obj.kit_id.id,
                               'item_description': 'Replacement Item from %s location.'%item.location_id_substitute_item.name,
                               }
                item_obj.create(cr, uid, item_values, context=context)
            # confirm - force availability and validate the internal picking
            self._validate_internal_picking(cr, uid, ids, pick_id, context=context)

        # take care to pass KIT ids not wizard ones !
        res = kit_obj.do_substitute(cr, uid, kit_ids, context=context)
        return res
    
    def do_de_kitting(self, cr, uid, ids, context=None):
        '''
        de-kitting method
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        move_obj = self.pool.get('stock.move')
        kit_obj = self.pool.get('composition.kit')
        # load default data
        self._load_common_data(cr, uid, ids, context=context)
        
        # date is today
        date = context['common']['date']
        # default company id
        company_id = context['common']['company_id']
        # reason type
        reason_type_id = context['common']['reason_type_id']
        # kitting location
        kitting_id = context['common']['kitting_id']
        # kit ids
        kit_ids = context['active_ids']
        # integrity constraint
        integrity_check = self.validate_item_mirror(cr, uid, ids, context=context) and self.validate_item_from_stock(cr, uid, ids, context=context)
        if not integrity_check:
            # the windows must be updated to trigger tree colors
            return self.pool.get('wizard').open_wizard(cr, uid, kit_ids, type='update', context=context)
        for obj in self.browse(cr, uid, ids, context=context):
            # we create the internal picking object
            pick_id = self._create_picking(cr, uid, ids, obj, date, context=context)
            # list of items to be deleted (replaced ones)
            items_to_stock_ids = []
            # items to replace cannot be empty
            if not len(obj.composition_item_ids):
                raise osv.except_osv(_('Warning !'), _('Items to replace cannot be empty.'))
            # for each item to replace, we create a stock move from kitting to destination location
            for item in obj.composition_item_ids:
                # analyze each item
                self._handle_compo_item(cr, uid, ids, obj, item, items_to_stock_ids, pick_id, context=context)
            # the corresponding kit is set to done
            kit_obj.write(cr, uid, kit_ids, {'state': 'done'}, context=context)
            # a move with a kit from kitting location is created
            move_values =  {'name': obj.kit_id.composition_product_id.name[:64],
                            'picking_id': pick_id,
                            'product_id': obj.kit_id.composition_product_id.id,
                            'date': date,
                            'date_expected': date,
                            'product_qty': 1.0,
                            'product_uom': obj.kit_id.composition_product_id.uom_id.id,
                            'product_uos_qty': 1.0,
                            'product_uos': obj.kit_id.composition_product_id.uom_id.id,
                            'product_packaging': False,
                            'address_id': False,
                            'location_id': obj.destination_location_id.id,
                            'location_dest_id': kitting_id,
                            'sale_line_id': False,
                            'tracking_id': False,
                            'state': 'draft',
                            'note': 'De-Kitting - Go to Stock',
                            'company_id': company_id,
                            'reason_type_id': reason_type_id,
                            'prodlot_id': obj.kit_id.composition_lot_id and obj.kit_id.composition_lot_id.id or False,
                            }
            move_obj.create(cr, uid, move_values, context=context)
            # confirm - force availability and validate the internal picking
            self._validate_internal_picking(cr, uid, ids, pick_id, context=context)
        
        return {'type': 'ir.actions.act_window_close'}
        
    def check_availability(self, cr, uid, ids, context=None):
        '''
        check the availability of the replacement items
        
        - feedback in the integrity_status column
        '''
        # objects
        item_obj = self.pool.get('substitute.item')
        for obj in self.browse(cr, uid, ids, context=context):
            for item in obj.replacement_item_ids:
                # reset the integrity status if it was an availability status
                # other integrity have 
                if item.integrity_status == 'not_available':
                    item.write({'integrity_status': 'empty'}, context=context)
                # call common_on_change
                result = item_obj.common_on_change(cr, uid, [item.id], item.location_id_substitute_item.id, item.product_id_substitute_item.id, item.lot_id_substitute_item.id, item.uom_id_substitute_item.id, result=None, context=context)
                # update the available qty
                item.write({'hidden_stock_available': result['value']['qty_substitute_item']}, context=context)
                # check that selected qty is smaller or equal to available one (from on_change function)
                if item.qty_substitute_item > 0 and result['value']['qty_substitute_item'] < item.qty_substitute_item:
                    item.write({'integrity_status': 'not_available'}, context=context)
                    
        return True
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        remove items from stock for de-kitting
        """
        if context is None:
            context = {}
        # call super
        result = super(substitute, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        # display depends on step
        if view_type == 'form' and context.get('step', False) == 'substitute':
            # fields to be modified
            list = ['<button name="do_de_kitting"']
            replace_text = result['arch']
            replace_text = reduce(lambda x, y: x.replace(y, y+ ' invisible="True" '), [replace_text] + list)
            result['arch'] = replace_text
        if view_type == 'form' and context.get('step', False) == 'de_kitting':
            # fields to be modified
            list = ['<field name="replacement_item_ids"', '<button name="check_availability"', '<button name="do_substitute"']
            replace_text = result['arch']
            replace_text = reduce(lambda x, y: x.replace(y, y+ ' invisible="True" '), [replace_text] + list)
            result['arch'] = replace_text
        
        return result
        
    _columns = {'kit_id': fields.many2one('composition.kit', string='Substitute Items from Composition List', readonly=True),
                'wizard_id': fields.integer(string='Wizard Id', readonly=True),
                'destination_location_id': fields.many2one('stock.location', string='Destination Location', domain=[('usage', '=', 'internal')], required=True),
                'composition_item_ids': fields.many2many('substitute.item.mirror', 'substitute_items_rel', 'wizard_id', 'item_id', string='Items to replace'),
                'replacement_item_ids': fields.one2many('substitute.item', 'wizard_id', string='Replacement items'),
                }
    
    def _get_default_location(self, cr, uid, context=None):
        '''
        get the default location (stock of first warehouse)
        '''
        # objects
        wh_obj = self.pool.get('stock.warehouse')
        ids = wh_obj.search(cr, uid, [], context=context)
        if ids:
            return wh_obj.browse(cr, uid, ids[0], context=context).lot_stock_id.id
        return False
    
    _defaults = {'kit_id': lambda s, cr, uid, c: c.get('kit_id', False),
                 'destination_location_id': _get_default_location,
                 }

substitute()


class substitute_item(osv.osv_memory):
    '''
    substitute items
    '''
    _name = 'substitute.item'
    
    def create(self, cr, uid, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        if 'product_id_substitute_item' in vals:
            if vals['product_id_substitute_item']:
                product_id = vals['product_id_substitute_item']
                data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                # if management and we have a lot_id, we fill the expiry date
                if management and vals.get('lot_id_substitute_item'):
                    data = prodlot_obj.read(cr, uid, [vals.get('lot_id_substitute_item')], ['life_date'], context=context)
                    expired_date = data[0]['life_date']
                    vals.update({'exp_substitute_item': expired_date})
                elif perishable:
                    # nothing special here
                    pass
                else:
                    # not perishable nor management, exp and lot are False
                    vals.update(lot_id_substitute_item=False, exp_substitute_item=False)
            else:
                # product is False, exp and lot are set to False
                vals.update(lot_id_substitute_item=False, exp_substitute_item=False)
        return super(substitute_item, self).create(cr, uid, vals, context=context)
        
    def write(self, cr, uid, ids, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        if 'product_id_substitute_item' in vals:
            if vals['product_id_substitute_item']:
                product_id = vals['product_id_substitute_item']
                data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                # if management and we have a lot_id, we fill the expiry date
                if management and vals.get('lot_id_substitute_item'):
                    data = prodlot_obj.read(cr, uid, [vals.get('lot_id_substitute_item')], ['life_date'], context=context)
                    expired_date = data[0]['life_date']
                    vals.update({'exp_substitute_item': expired_date})
                elif perishable:
                    # nothing special here
                    pass
                else:
                    # not perishable nor management, exp and lot are False
                    vals.update(lot_id_substitute_item=False, exp_substitute_item=False)
            else:
                # product is False, exp and lot are set to False
                vals.update(lot_id_substitute_item=False, exp_substitute_item=False)
        return super(substitute_item, self).write(cr, uid, ids, vals, context=context)
    
    def common_on_change(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, result=None, context=None):
        '''
        commmon qty computation
        '''
        if context is None:
            context = {}
        if result is None:
            result = {}
        if not product_id or not location_id:
            result.setdefault('value', {}).update({'qty_substitute_item': 0.0, 'hidden_stock_available': 0.0})
            return result
        
        # objects
        loc_obj = self.pool.get('stock.location')
        prod_obj = self.pool.get('product.product')
        # corresponding product object
        product_obj = prod_obj.browse(cr, uid, product_id, context=context)
        # uom from product is taken by default if needed
        uom_id = uom_id or product_obj.uom_id.id
        # we do not want the children location
        stock_context = dict(context, compute_child=False)
        # we check for the available qty (in:done, out: assigned, done)
        res = loc_obj._product_reserve_lot(cr, uid, [location_id], product_id, uom_id, context=stock_context, lock=True)
        if prodlot_id:
            # if a lot is specified, we take this specific qty info - the lot may not be available in this specific location
            qty = res[location_id].get(prodlot_id, False) and res[location_id][prodlot_id]['total'] or 0.0
        else:
            # otherwise we take total according to the location
            qty = res[location_id]['total']
        # update the result
        result.setdefault('value', {}).update({'qty_substitute_item': qty,
                                               'uom_id_substitute_item': uom_id,
                                               'hidden_stock_available': qty,
                                               })
        return result
    
    def change_lot(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, context=None):
        '''
        prod lot changes, update the expiry date
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}}
        # reset expiry date or fill it
        if prodlot_id:
            result['value'].update(exp_substitute_item=prodlot_obj.browse(cr, uid, prodlot_id, context=context).life_date)
        else:
            result['value'].update(exp_substitute_item=False)
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result
    
    def change_expiry(self, cr, uid, ids, expiry_date, product_id, type_check, location_id, prodlot_id, uom_id, context=None):
        '''
        expiry date changes, find the corresponding internal prod lot
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}}
        
        if expiry_date and product_id:
            prod_ids = prodlot_obj.search(cr, uid, [('life_date', '=', expiry_date),
                                                    ('type', '=', 'internal'),
                                                    ('product_id', '=', product_id)], context=context)
            if not prod_ids:
                if type_check == 'in':
                    # the corresponding production lot will be created afterwards
                    result['warning'] = {'title': _('Info'),
                                     'message': _('The selected Expiry Date does not exist in the system. It will be created during validation process.')}
                    # clear prod lot
                    result['value'].update(lot_id_substitute_item=False)
                else:
                    # display warning
                    result['warning'] = {'title': _('Error'),
                                         'message': _('The selected Expiry Date does not exist in the system.')}
                    # clear date
                    result['value'].update(exp_substitute_item=False, lot_id_substitute_item=False)
            else:
                # return first prodlot
                prodlot_id = prod_ids[0]
                result['value'].update(lot_id_substitute_item=prodlot_id)
        else:
            # clear expiry date, we clear production lot
            result['value'].update(lot_id_substitute_item=False,
                                   exp_substitute_item=False,
                                   )
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result
    
    def on_change_location_id(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, context=None):
        """ 
        location changes
        """
        result = {}
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result
    
    def on_change_product_id(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, context=None):
        '''
        the product changes, set the hidden flag if necessary
        '''
        result = {}
        # product changes, prodlot is always cleared
        result.setdefault('value', {})['lot_id_substitute_item'] = False
        result.setdefault('value', {})['exp_substitute_item'] = False
        # clear uom
        result.setdefault('value', {})['uom_id_substitute_item'] = False
        # reset the hidden flags
        result.setdefault('value', {})['hidden_batch_management_mandatory'] = False
        result.setdefault('value', {})['hidden_perishable_mandatory'] = False
        if product_id:
            product_obj = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            # set the default uom
            uom_id = product_obj.uom_id.id
            result.setdefault('value', {})['uom_id_substitute_item'] = uom_id
            result.setdefault('value', {})['hidden_batch_management_mandatory'] = product_obj.batch_management
            result.setdefault('value', {})['hidden_perishable_mandatory'] = product_obj.perishable
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            # batch management
            result[obj.id].update({'hidden_batch_management_mandatory': obj.product_id_substitute_item.batch_management})
            # perishable
            result[obj.id].update({'hidden_perishable_mandatory': obj.product_id_substitute_item.perishable})
        return result
    
    _columns = {'integrity_status': fields.selection(string=' ', selection=INTEGRITY_STATUS_SELECTION, readonly=True),
                'wizard_id': fields.many2one('substitute', string='Substitute wizard'),
                'location_id_substitute_item': fields.many2one('stock.location', string='Source Location', required=True, domain=[('usage', '=', 'internal')]),
                'module_substitute_item': fields.char(string='Module', size=1024),
                'product_id_substitute_item': fields.many2one('product.product', string='Product', required=True),
                'qty_substitute_item': fields.float(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True),
                'uom_id_substitute_item': fields.many2one('product.uom', string='UoM', required=True),
                'lot_id_substitute_item': fields.many2one('stock.production.lot', string='Batch Nb'),
                'exp_substitute_item': fields.date(string='Expiry Date'),
                'type_check': fields.char(string='Type Check', size=1024,),
                'hidden_stock_available': fields.float(string='Available Stock', digits_compute=dp.get_precision('Product UoM'), invisible=True),
                # functions
                'hidden_perishable_mandatory': fields.function(_vals_get, method=True, type='boolean', string='Exp', multi='get_vals', store=False, readonly=True),
                'hidden_batch_management_mandatory': fields.function(_vals_get, method=True, type='boolean', string='Lot', multi='get_vals', store=False, readonly=True),
                }
    
    _defaults = {# in is used, meaning a new prod lot will be created if the specified expiry date does not exist
                 'type_check': 'out',
                 'hidden_stock_available': 0.0,
                 'integrity_status': 'empty',
                 }
    
substitute_item()


class substitute_item_mirror(osv.osv_memory):
    '''
    substitute items
    memory trick to get modifiable mirror objects for kit item
    '''
    _name = 'substitute.item.mirror'
    _inherit = 'substitute.item'
    
    def create(self, cr, uid, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        if 'product_id_substitute_item' in vals:
            if vals['product_id_substitute_item']:
                product_id = vals['product_id_substitute_item']
                data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                # if management and we have a lot_id, we fill the expiry date
                if management and vals.get('lot_mirror'):
                    prodlot_id = vals.get('lot_mirror')
                    prod_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_id),
                                                            ('type', '=', 'standard'),
                                                            ('product_id', '=', product_id)], context=context)
                    # if it exists, we set the date
                    if prod_ids:
                        prodlot_id = prod_ids[0]
                        data = prodlot_obj.read(cr, uid, [prodlot_id], ['life_date'], context=context)
                        expired_date = data[0]['life_date']
                        vals.update({'exp_substitute_item': expired_date})
                elif perishable:
                    # nothing special here
                    pass
                else:
                    # not perishable nor management, mirror, exp and lot are False
                    vals.update(lot_mirror=False, lot_id_substitute_item=False, exp_substitute_item=False)
            else:
                # product is False, mirror, exp and lot are set to False
                vals.update(lot_mirror=False, lot_id_substitute_item=False, exp_substitute_item=False)
        return super(substitute_item_mirror, self).create(cr, uid, vals, context=context)
        
    def write(self, cr, uid, ids, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        if 'product_id_substitute_item' in vals:
            if vals['product_id_substitute_item']:
                product_id = vals['product_id_substitute_item']
                data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                # if management and we have a lot_id, we fill the expiry date
                if management and vals.get('lot_mirror'):
                    prodlot_id = vals.get('lot_mirror')
                    prod_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_id),
                                                            ('type', '=', 'standard'),
                                                            ('product_id', '=', product_id)], context=context)
                    # if it exists, we set the date
                    if prod_ids:
                        prodlot_id = prod_ids[0]
                        data = prodlot_obj.read(cr, uid, [prodlot_id], ['life_date'], context=context)
                        expired_date = data[0]['life_date']
                        vals.update({'exp_substitute_item': expired_date})
                elif perishable:
                    # nothing special here
                    pass
                else:
                    # not perishable nor management, mirror, exp and lot are False
                    vals.update(lot_mirror=False, lot_id_substitute_item=False, exp_substitute_item=False)
            else:
                # product is False, mirror, exp and lot are set to False
                vals.update(lot_mirror=False, lot_id_substitute_item=False, exp_substitute_item=False)
        return super(substitute_item_mirror, self).write(cr, uid, ids, vals, context=context)
    
    def change_lot(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, context=None):
        '''
        prod lot changes, update the expiry date
        
        only available for batch management products
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}}
        # reset expiry date or fill it
        if prodlot_id:
            prod_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_id),
                                                    ('type', '=', 'standard'),
                                                    ('product_id', '=', product_id)], context=context)
            if prod_ids:
                prodlot_id = prod_ids[0]
                result['value'].update(exp_substitute_item=prodlot_obj.browse(cr, uid, prodlot_id, context=context).life_date)
        else:
            result['value'].update(exp_substitute_item=False)
        return result
    
    def change_expiry(self, cr, uid, ids, expiry_date, product_id, type_check, location_id, prodlot_id, uom_id, context=None):
        '''
        expiry date changes, find the corresponding internal prod lot
        
        only available for perishable products
        '''
        # objects
        prodlot_obj = self.pool.get('stock.production.lot')
        prod_obj = self.pool.get('product.product')
        result = {'value':{}}
        
        if product_id:
            if expiry_date:
                # product management type
                data = prod_obj.read(cr, uid, [product_id], ['batch_management', 'perishable'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                # if the product is batch management
                if management and prodlot_id:
                    # prodlot_id is here the name of the prodlot
                    # we check if we have a production lot, if yes, we check if it exists (the name is unique for a given product)
                    prod_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_id),
                                                            ('type', '=', 'standard'),
                                                            ('product_id', '=', product_id)], context=context)
                    # if it exists, we set the date
                    if prod_ids:
                        prodlot_id = prod_ids[0]
                        result['value'].update(exp_substitute_item=prodlot_obj.browse(cr, uid, prodlot_id, context=context).life_date)
                        
                elif perishable:
                    # if the product is perishable
                    prod_ids = prodlot_obj.search(cr, uid, [('life_date', '=', expiry_date),
                                                            ('type', '=', 'internal'),
                                                            ('product_id', '=', product_id)], context=context)
                    if not prod_ids:
                        if type_check == 'in':
                            # the corresponding production lot will be created afterwards
                            result['warning'] = {'title': _('Info'),
                                             'message': _('The selected Expiry Date does not exist in the system. It will be created during validation process.')}
                            # clear prod lot
                            result['value'].update(lot_mirror=False)
                        else:
                            # display warning
                            result['warning'] = {'title': _('Error'),
                                                 'message': _('The selected Expiry Date does not exist in the system.')}
                            # clear date
                            result['value'].update(exp_substitute_item=False, lot_mirror=False)
                    else:
                        # return first prodlot
                        prodlot_id = prod_ids[0]
                        # the lot is not displayed here, internal useless internal name for the user, lot is read only anyway for perishable products
                        #result['value'].update(lot_mirror=prodlot_id)
        else:
            # clear expiry date, we clear production lot
            result['value'].update(lot_mirror=False,
                                   exp_substitute_item=False,
                                   )
        return result
    
    _columns = {'item_id_mirror': fields.integer(string='Id of original Item', readonly=True),
                'kit_id_mirror': fields.many2one('composition.kit', string='Kit', readonly=True),
                'lot_mirror': fields.char(string='Batch Nb', size=1024),
                }
    
    _defaults = {'item_id_mirror': False,
                 'type_check': 'in',
                 }

substitute_item_mirror()
