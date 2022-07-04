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
from tools import ustr
import netsvc
import decimal_precision as dp
from datetime import datetime

# xml parser
from lxml import etree

from msf_outgoing import INTEGRITY_STATUS_SELECTION
from kit import SELECTION_AVAILABLE

class substitute(osv.osv_memory):
    '''
    substitute wizard
    '''
    _name = "substitute"

    def validate_item_mirror(self, cr, uid, ids, context=None):
        '''
        integrity must be OK

        'integrity_status_func_substitute_item'

        return True or False
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            for item in obj.composition_item_ids:
                # integrity is not met
                if item.integrity_status_func_substitute_item != 'empty':
                    return False

        return True

    def validate_item_from_stock(self, cr, uid, ids, context=None):
        '''
        both integrity and availability must be OK

        'availability_status_func_substitute_item'
        'integrity_status_func_substitute_item'

        return True or False
        '''
        if context is None:
            context = {}

        kit_obj = self.pool.get('composition.kit')

        for obj in self.browse(cr, uid, ids, context=context):

            kit_obj.assert_available_stock(cr, uid, [obj.kit_id.id], context=context)

            for item in obj.replacement_item_ids:
                # integrity is not met
                if item.integrity_status_func_substitute_item != 'empty':
                    return False
                # availability is not met - we use the hidden one, used for testing with fixed selection values
                if item.availability_status_hidden_func_substitute_item != 'available':
                    return False

        return True

    def check_integrity(self, cr, uid, ids, context=None):
        '''
        simply refresh the wizard - line level fields.function are recomputed
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # kit ids
        kit_ids = context['active_ids']
        # simple refresh the wizard, as availability is now a function at line level
        return self.pool.get('wizard').open_wizard(cr, uid, kit_ids, w_type='update', context=context)

    def _check_integrity(self, cr, uid, ids, context=None):
        '''
        call both integrity validation methods
        '''
        return self.validate_item_mirror(cr, uid, ids, context=context) and self.validate_item_from_stock(cr, uid, ids, context=context)

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
        name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.internal')
        data = name.split('/')
        name = data[0] + '/' + 'KIT' + data[1]
        pick_values = {'name': name,
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
                raise osv.except_osv(_('Warning !'), _('Batch Number is missing for %s.')%item.product_id_substitute_item.name)
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
                    lot_obj.log(cr, uid, prodlot_ids[0], _('Batch Number %s for %s with Expiry Date %s does not match the Expiry Date from the composition list %s.')%(lot_name,item.product_id_substitute_item.name,exp_obj.strftime(date_format),exp_item_text))
                # select production lot
                prodlot_id = prodlot_ids[0]
            else:
                # lot number must have been filled in
                if not item.exp_substitute_item:
                    raise osv.except_osv(_('Warning !'), _('Expiry Date is missing for %s.')%item.product_id_substitute_item.name)
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
                lot_obj.log(cr, uid, prodlot_id, _('Batch Number %s for %s with Expiry Date %s has been created.')%(lot_name,item.product_id_substitute_item.name, ustr(exp_item.strftime(date_format))))
        elif item.product_id_substitute_item.perishable:
            # expiry date must have been filled in
            if not item.exp_substitute_item:
                raise osv.except_osv(_('Warning !'), _('Batch Number/Expiry Date is missing for %s.')%item.product_id_substitute_item.name)
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
                       'asset_id': item.asset_id_substitute_item.id,
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
        data_tools_obj = self.pool.get('data.tools')
        # load default data
        data_tools_obj.load_common_data(cr, uid, ids, context=context)

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
        integrity_check = self._check_integrity(cr, uid, ids, context=context)
        if not integrity_check:
            # the windows must be updated to trigger tree colors
            return self.pool.get('wizard').open_wizard(cr, uid, kit_ids, w_type='update', context=context)
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
                                'asset_id': item.asset_id_substitute_item.id,
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
                               'item_asset_id': item.asset_id_substitute_item.id,
                               'item_lot': item.lot_id_substitute_item.name,
                               'item_exp': item.exp_substitute_item,
                               'item_kit_id': obj.kit_id.id,
                               'item_description': 'Replacement Item from %s location.'%item.location_id_substitute_item.name,
                               'comment': item.comment or '',
                               }
                item_obj.create(cr, uid, item_values, context=context)
            # confirm - force availability and validate the internal picking
            self._validate_internal_picking(cr, uid, ids, pick_id, context=context)

        # take care to pass KIT ids not wizard ones !
        res = kit_obj.do_substitute(cr, uid, kit_ids, context=context)
        return res

    def do_de_kitting(self, cr, uid, ids, context=None):
        '''
        check if confirmation wizard is needed
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # objects
        item_obj = self.pool.get('substitute.item')

        for obj in self.browse(cr, uid, ids, context=context):
            # we check the availability of selected src location for processed product - uom_id is false, we take the default one from kit product
            res = item_obj.common_on_change(cr, uid, ids, obj.source_location_id.id, obj.product_id_substitute.id, obj.lot_id_substitute.id, uom_id=False, result=None, context=context)
            # de-kitting need 1 PCE, if less available, we open the confirmation wizard
            available_qty = res['value']['qty_substitute_item']
            if available_qty < 1.0:
                # we display the back button - hide close button
                raise osv.except_osv(_("Error"),
                                     _("The Kit \'%s\' is not available from selected source location \'%s\'"
                                       %(obj.product_id_substitute.name, obj.source_location_id.name)))
            else:
                return self._do_de_kitting(cr, uid, ids, context=context)

    def _do_de_kitting(self, cr, uid, ids, context=None):
        '''
        de-kitting method
        '''
        if isinstance(ids, int):
            ids = [ids]
        # objects
        move_obj = self.pool.get('stock.move')
        kit_obj = self.pool.get('composition.kit')
        data_tools_obj = self.pool.get('data.tools')
        comp_item_obj = self.pool.get('composition.item')
        # load default data
        data_tools_obj.load_common_data(cr, uid, ids, context=context)

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
        integrity_check = self._check_integrity(cr, uid, ids, context=context)
        if not integrity_check:
            # the windows must be updated to trigger tree colors
            return self.pool.get('wizard').open_wizard(cr, uid, kit_ids, w_type='update', context=context)
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
                if item.item_id_mirror:
                    comp_item_obj.write(cr, uid, item.item_id_mirror, {'item_lot': item.lot_mirror, 'item_exp': item.exp_substitute_item}, context=context)
            # the corresponding kit is set to done
            kit_obj.close_kit(cr, uid, kit_ids, context=context)
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
                            'location_id': obj.source_location_id.id,
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
        simply refresh the wizard - line level fields.function are recomputed
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # kit ids
        kit_ids = context['active_ids']
        # simple refresh the wizard, as availability is now a function at line level
        return self.pool.get('wizard').open_wizard(cr, uid, kit_ids, w_type='update', context=context)

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
            # load the xml tree
            root = etree.fromstring(result['arch'])
            # xpath of fields to be modified
            list = ['//button[@name="do_de_kitting"]', '//field[@name="source_location_id"]']
            for xpath in list:
                fields = root.xpath(xpath)
                if not fields:
                    raise osv.except_osv(_('Warning !'), _('Element %s not found.')%xpath)
                for field in fields:
                    field.set('invisible', 'True')
            result['arch'] = etree.tostring(root, encoding='unicode')
            # remove the hide_new_button/hide_delete button
            # both button are originally hidden, because in de-kitting, we do not want the user to change anything
            # for substitute, we need these button because the user can choose the products from the kit
            # load the xml tree
            root = etree.fromstring(result['fields']['composition_item_ids']['views']['tree']['arch'])
            # root is the tree, we change the attribute to False
            root.set('hide_new_button', 'False')
            root.set('hide_delete_button', 'False')
            result['fields']['composition_item_ids']['views']['tree']['arch'] = etree.tostring(root, encoding='unicode')

        if view_type == 'form' and context.get('step', False) == 'de_kitting':
            # load the xml tree
            root = etree.fromstring(result['arch'])
            # fields to be modified
            list = ['//field[@name="replacement_item_ids"]', '//button[@name="check_availability"]', '//button[@name="do_substitute"]']
            for xpath in list:
                fields = root.xpath(xpath)
                if not fields:
                    raise osv.except_osv(_('Warning !'), _('Element %s not found.')%xpath)
                for field in fields:
                    field.set('invisible', 'True')
            result['arch'] = etree.tostring(root, encoding='unicode')

        return result

    _columns = {'wizard_id': fields.integer(string='Wizard Id', readonly=True),
                'kit_id': fields.many2one('composition.kit', string='Substitute Items from Composition List', readonly=True),
                'step_substitute': fields.char(string='Step', size=1024, readonly=True),
                'product_id_substitute': fields.many2one('product.product', string='Product', readonly=True),
                'lot_id_substitute': fields.many2one('stock.production.lot', string='Batch Nb', readonly=True),
                'destination_location_id': fields.many2one('stock.location', string='Destination Location of Items', domain=[('usage', '=', 'internal')], required=True),
                'source_location_id': fields.many2one('stock.location', string='Source Location of Kit', domain=[('usage', '=', 'internal')]),
                # m2m
                'composition_item_ids': fields.many2many('substitute.item.mirror', 'substitute_items_rel', 'wizard_id', 'item_id', string='Items to replace'),
                # o2m
                'replacement_item_ids': fields.one2many('substitute.item', 'wizard_id', string='Replacement items'),
                }

    _defaults = {'kit_id': lambda s, cr, uid, c: c.get('kit_id', False), # from _get_new_context
                 'step_substitute': lambda s, cr, uid, c: c.get('step', False), # comes from open_wizard function
                 'product_id_substitute': lambda s, cr, uid, c: c.get('product_id', False), # from _get_new_context
                 'lot_id_substitute': lambda s, cr, uid, c: c.get('prodlot_id', False), # from _get_new_context
                 #                 'destination_location_id': lambda obj, cr, uid, c: obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock') and obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1] or False,
                 #                 'source_location_id': lambda obj, cr, uid, c: obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock') and obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1] or False,
                 }

    def update_lines_bned(self, cr, uid, ids, context=None):
        if not ids:
            return {}
        lot_obj = self.pool.get('stock.production.lot')
        wiz = self.browse(cr, uid, ids[0], context=context)
        line_ids_to_write = {}
        product_code_to_write = set()
        for line in wiz.composition_item_ids:
            to_write = {}
            if line.product_id_substitute_item.perishable and not line.exp_substitute_item:
                to_write['exp_substitute_item'] = '2999-12-31'
            if line.product_id_substitute_item.batch_management and not line.lot_mirror:
                to_write['lot_mirror'] = 'TO-BE-REPLACED'
            elif line.product_id_substitute_item.batch_management and line.lot_mirror and line.lot_mirror.startswith('MSFBN/'):
                if not lot_obj.search_exists(cr, uid, [('product_id', '=', line.product_id_substitute_item.id), ('name', '=', line.lot_mirror), ('type', '=', 'standard')], context=context):
                    to_write['lot_mirror'] = 'TO-BE-REPLACED'
            elif line.product_id_substitute_item.perishable and not line.product_id_substitute_item.batch_management and line.lot_mirror:
                to_write['lot_mirror'] = False
            if not line.product_id_substitute_item.batch_management and not line.product_id_substitute_item.perishable and (line.exp_substitute_item or line.lot_mirror):
                to_write.update({'lot_mirror': False, 'exp_substitute_item': False})
            if to_write:
                line_ids_to_write[line.id] = to_write
                product_code_to_write.add(line.product_id_substitute_item.default_code)

        if product_code_to_write:
            cr.execute('''
                    select p.default_code
                    from
                        audittrail_log_line l, product_product p, ir_model_fields f
                    where
                        p.product_tmpl_id = l.res_id and
                        f.name in ('perishable', 'batch_management') and
                        f.model = 'product.product' and
                        l.field_id = f.id and
                        l.timestamp >= %s and
                        p.default_code in %s
                    group by p.default_code
                ''', (wiz.kit_id.composition_creation_date, tuple(product_code_to_write)))

            product_code_to_write = list(product_code_to_write - set([x[0] for x in cr.fetchall()]))
            if product_code_to_write:
                if len(product_code_to_write) > 10:
                    product_code_to_write = product_code_to_write[0:9] + ['...']
                raise osv.except_osv(_('Warning !'), "%s:\n%s" % (_('Cannot update these products, ED/BN attributes have not changed since the KCL creation'), ','.join(product_code_to_write)))

        for line_id in line_ids_to_write:
            self.pool.get('substitute.item.mirror').write(cr, uid, line_id, line_ids_to_write[line_id], context=context)

        return self.pool.get('wizard').open_wizard(cr, uid, wiz.kit_id.id, w_type='update', context=context)
substitute()


class substitute_item(osv.osv_memory):
    '''
    substitute items
    '''
    _name = 'substitute.item'

    def _common_update(self, cr, uid, vals, context=None):
        '''
        common function for values update during create and write
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        if 'product_id_substitute_item' in vals:
            if vals['product_id_substitute_item']:
                product_id = vals['product_id_substitute_item']
                data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management', 'type', 'subtype'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                type = data['type']
                subtype = data['subtype']
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
                # if the product is not of type 'product' or type is 'product' but subtype is not 'asset', we set asset to False
                if (type != 'product') or (type == 'product' and subtype != 'asset'):
                    vals.update(asset_id_substitute_item=False)
            else:
                # product is False, exp and lot are set to False - asset set to False
                vals.update(lot_id_substitute_item=False, exp_substitute_item=False, asset_id_substitute_item=False)

        return vals

    def create(self, cr, uid, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products
        '''
        vals = self._common_update(cr, uid, vals, context=context)
        return super(substitute_item, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products
        '''
        if not ids:
            return True
        vals = self._common_update(cr, uid, vals, context=context)
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
            result.setdefault('value', {}).update({'qty_substitute_item': 0.0})
            return result

        prod_obj = self.pool.get('product.product')
        # corresponding product object
        ctx = context.copy()
        ctx['location'] = location_id
        if uom_id:
            ctx['uom'] = uom_id
        if prodlot_id:
            ctx['prodlot_id'] = prodlot_id
        else:
            ctx['prodlot_id'] = False
        product_obj = prod_obj.browse(cr, uid, product_id, fields_to_fetch=['qty_allocable'], context=ctx)
        # update the result
        result.setdefault('value', {}).update({'qty_substitute_item': product_obj.qty_allocable,
                                               'uom_id_substitute_item': uom_id,
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

    def on_change_product_id(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, composition_item_ids=False, comment=False, context=None):
        '''
        the product changes, set the hidden flag if necessary
        '''
        result = {}
        # product changes, prodlot is always cleared - asset is cleared
        result.setdefault('value', {})['lot_id_substitute_item'] = False
        result.setdefault('value', {})['exp_substitute_item'] = False
        result.setdefault('value', {})['asset_id_substitute_item'] = False
        # clear uom
        result.setdefault('value', {})['uom_id_substitute_item'] = False
        # reset the hidden flags
        result.setdefault('value', {})['hidden_batch_management_mandatory'] = False
        result.setdefault('value', {})['hidden_perishable_mandatory'] = False
        result.setdefault('value', {})['hidden_asset_mandatory'] = False
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            # set the default uom
            uom_id = product.uom_id.id
            result.setdefault('value', {})['uom_id_substitute_item'] = uom_id
            result.setdefault('value', {})['hidden_batch_management_mandatory'] = product.batch_management
            result.setdefault('value', {})['hidden_perishable_mandatory'] = product.perishable
            result.setdefault('value', {})['hidden_asset_mandatory'] = product.type == 'product' and product.subtype == 'asset'
        # Set the comment of the product to substitute if there is only one in the "Products to remove from the Kit"
        if not comment and composition_item_ids:
            comp_item_ids = composition_item_ids[0][2]
            if len(comp_item_ids) == 1:
                comp_items = self.pool.get('substitute.item.mirror').browse(cr, uid, comp_item_ids, fields_to_fetch=['comment'], context=context)
                result.setdefault('value', {})['comment'] = comp_items[0].comment or ''
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result

    def onchange_uom_qty(self, cr, uid, ids, uom_id, qty):
        '''
        Check round of qty according to UoM
        '''
        res = {}

        if qty:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, qty, 'qty_substitute_item', result=res)

        return res

    def _validate_item_from_stock(self, cr, uid, id, context=None):
        '''
        validate the from stock objects for lot and expiry date

        - lot AND expiry date are mandatory for batch management products
        - expiry date is mandatory for perishable products

        return corresponding key error for selection

        from stock and mirror need different validation function
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        lot_obj = self.pool.get('stock.production.lot')
        # browse the object
        item = self.browse(cr, uid, id, context=context)
        # by default we return empty result
        result = 'empty'
        # product management type - cannot use hidden checks, because validate is called within get_vals function, would result in infinite loop
        data = prod_obj.read(cr, uid, [item.product_id_substitute_item.id], ['batch_management', 'perishable', 'type', 'subtype'], context=context)[0]
        management = data['batch_management']
        perishable = data['perishable']
        type = data['type']
        subtype = data['subtype']
        if management:
            if not item.lot_id_substitute_item:
                # lot is needed
                result = 'missing_lot'
            else:
                data = lot_obj.read(cr, uid, [item.lot_id_substitute_item.id], ['life_date','name','type'], context=context)
                lot_type = data[0]['type']
                if lot_type != 'standard':
                    result = 'wrong_lot_type_need_standard'
        elif perishable:
            if not item.exp_substitute_item:
                # expiry date is needed
                result = 'missing_date'
        else:
            # no lot needed
            if item.lot_id_substitute_item:
                result = 'no_lot_needed'
        # quantity check
        if item.qty_substitute_item <= 0:
            result = 'must_be_greater_than_0'
        # asset check - asset is not mandatory for moves performed internally
        if type == 'product' and subtype == 'asset':
            pass
#            if not item.asset_id_substitute_item:
#                result = 'missing_asset'
        else:
            if item.asset_id_substitute_item:
                result = 'not_asset_needed'

        # we return the found result
        return result

    def validate_item(self, cr, uid, id, context=None):
        '''
        validation interface to allow modifying behavior in inherited classes
        '''
        return self._validate_item_from_stock(cr, uid, id, context=context)

    def _vals_get_substitute_item(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            # batch management
            result[obj.id].update({'hidden_batch_management_mandatory': obj.product_id_substitute_item.batch_management})
            # perishable
            result[obj.id].update({'hidden_perishable_mandatory': obj.product_id_substitute_item.perishable})
            # hidden_asset_mandatory
            result[obj.id].update({'hidden_asset_mandatory': obj.product_id_substitute_item.type == 'product' and obj.product_id_substitute_item.subtype == 'asset'})
            # call common_on_change
            compute_avail = self.common_on_change(cr, uid, [obj.id], obj.location_id_substitute_item.id, obj.product_id_substitute_item.id, obj.lot_id_substitute_item.id, obj.uom_id_substitute_item.id, result=None, context=context)
            # availability_value_func_substitute_item
            result[obj.id].update({'availability_value_func_substitute_item': compute_avail['value']['qty_substitute_item']})
            # integrity_status_func_substitute_item
            result[obj.id].update({'integrity_status_func_substitute_item': self.validate_item(cr, uid, obj.id, context=context)})
            # availability_status_func_substitute_item
            result[obj.id].update({'availability_status_func_substitute_item': (compute_avail['value']['qty_substitute_item'] >= obj.qty_substitute_item and 'Available (%.2f %s)' or 'Not Enough Available (%.2f %s)')%(compute_avail['value']['qty_substitute_item'], obj.uom_id_substitute_item.name)})
            # availability_status_hidden_func_substitute_item
            result[obj.id].update({'availability_status_hidden_func_substitute_item': compute_avail['value']['qty_substitute_item'] >= obj.qty_substitute_item and 'available' or 'not_available'})

        return result

    _columns = {'wizard_id': fields.many2one('substitute', string='Substitute wizard'),
                'location_id_substitute_item': fields.many2one('stock.location', string='Source Location', required=True, domain=[('usage', '=', 'internal')]),
                'module_substitute_item': fields.char(string='Module', size=1024),
                'product_id_substitute_item': fields.many2one('product.product', string='Product', required=True),
                'qty_substitute_item': fields.float(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True, related_uom='uom_id_substitute_item'),
                'uom_id_substitute_item': fields.many2one('product.uom', string='UoM', required=True),
                'asset_id_substitute_item': fields.many2one('product.asset', string='Asset'),
                'lot_id_substitute_item': fields.many2one('stock.production.lot', string='Batch Nb'),
                'exp_substitute_item': fields.date(string='Expiry Date'),
                'type_check': fields.char(string='Type Check', size=1024, readonly=True),
                'comment': fields.char(size=256, string='Comment'),
                # functions
                'hidden_perishable_mandatory': fields.function(_vals_get_substitute_item, method=True, type='boolean', string='Exp', multi='get_vals_substitute_item', store=False, readonly=True),
                'hidden_batch_management_mandatory': fields.function(_vals_get_substitute_item, method=True, type='boolean', string='B.Num', multi='get_vals_substitute_item', store=False, readonly=True),
                'hidden_asset_mandatory': fields.function(_vals_get_substitute_item, method=True, type='boolean', string='Asset', multi='get_vals_substitute_item', store=False, readonly=True),
                'availability_value_func_substitute_item': fields.function(_vals_get_substitute_item, method=True, type='float', string='Availability Value', multi='get_vals_substitute_item', store=False, readonly=True),
                'availability_status_func_substitute_item': fields.function(_vals_get_substitute_item, method=True, type='char', size=1024, string='Availability', multi='get_vals_substitute_item', store=False, readonly=True),
                'availability_status_hidden_func_substitute_item': fields.function(_vals_get_substitute_item, method=True, type='selection', selection=SELECTION_AVAILABLE, string='Hidden availability', multi='get_vals_substitute_item', store=False, readonly=True),
                'integrity_status_func_substitute_item': fields.function(_vals_get_substitute_item, method=True, type='selection', selection=INTEGRITY_STATUS_SELECTION, string=' ', multi='get_vals_substitute_item', store=False, readonly=True),
                }

    def _get_comment(self, cr, uid, context=None):
        '''
        Get the comment of the product to substitute if there is only one
        '''
        if context is None:
            context = {}

        comment = ''
        if self._name == 'substitute.item' and context.get('comp_item_ids'):
            # Strange behavior while adding a new "Products from the stock to the Kit" or changing the product of one
            # while both treeviews are in edition
            if 'comment' in context.get('comp_item_ids'):
                comment = context.get('comp_item_ids').get('comment', '')
            else:
                comp_item_ids = context.get('comp_item_ids')[0][2]
                if len(comp_item_ids) == 1:
                    comp_items = self.pool.get('substitute.item.mirror').browse(cr, uid, comp_item_ids, fields_to_fetch=['comment'], context=context)
                    comment = comp_items[0].comment or ''

        return comment

    _defaults = {
        'type_check': 'out',  # in is used, meaning a new prod lot will be created if the specified expiry date does not exist
        'comment': _get_comment,
    }

substitute_item()


class substitute_item_mirror(osv.osv_memory):
    '''
    substitute items
    memory trick to get modifiable mirror objects for kit item
    '''
    _name = 'substitute.item.mirror'
    _inherit = 'substitute.item'

    def _common_update(self, cr, uid, vals, context=None):
        '''
        common function for values update during create and write
        '''
        return vals # called by super create/write...
        # objects
        prod_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        if 'product_id_substitute_item' in vals:
            if vals['product_id_substitute_item']:
                product_id = vals['product_id_substitute_item']
                data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management', 'type', 'subtype'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                type = data['type']
                subtype = data['subtype']
                # if management and we have a lot_id, we fill the expiry date
                if management and vals.get('lot_mirror', False):
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
                elif perishable and vals.get('exp_substitute_item', False):
                    # check the date, if an internal lot exists, we set the name in lot_mirror
                    exp_date = vals.get('exp_substitute_item')
                    prod_ids = prodlot_obj.search(cr, uid, [('life_date', '=', exp_date),
                                                            ('type', '=', 'internal'),
                                                            ('product_id', '=', product_id)], context=context)
                    # if exists, we set the lot name
                    if prod_ids:
                        prodlot_id = prod_ids[0]
                        data = prodlot_obj.read(cr, uid, [prodlot_id], ['name'], context=context)
                        name = data[0]['name']
                        vals.update({'lot_mirror': name})
                else:
                    # not perishable nor management, mirror, exp and lot are False
                    vals.update(lot_mirror=False, lot_id_substitute_item=False, exp_substitute_item=False)
                # if the product is not of type 'product' or type is 'product' but subtype is not 'asset', we set asset to False
                if (type != 'product') or (type == 'product' and subtype != 'asset'):
                    vals.update(asset_id_substitute_item=False)
            else:
                # product is False, mirror, exp and lot are set to False - why set lot_id to False? it is not used in mirror...
                vals.update(lot_mirror=False, lot_id_substitute_item=False, exp_substitute_item=False, asset_id_substitute_item=False)

        return vals

    def create(self, cr, uid, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products

        is it really needed as product is readonly?
        - the product does not change, so no problem with readonly which was not readonly
        - when we write sth in readonly field (as batch name for perishable), it will anyway
          not work because product_id is not sent (readonly)
        I would say no, this is of no use.
        '''
        #vals = self._common_update(cr, uid, vals, context=context)
        return super(substitute_item_mirror, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products

        is it really needed as product is readonly?
        - the product does not change, so no problem with readonly which was not readonly
        - when we write sth in readonly field (as batch name for perishable), it will anyway
          not work because product_id is not sent (readonly)
        I would say no, this is of no use.

        product_id is readonly, we're getting into trouble over. write forced for lot with perishable will simply not work.
        there is however not fonctional issue about this point. as the name of the lot is not used for perishable when processing the screen.
        '''
        if not ids:
            return True
        #vals = self._common_update(cr, uid, vals, context=context)
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
                        # get the name
                        data = prodlot_obj.read(cr, uid, prodlot_id, ['name'], context=context)
                        name = data['name']
                        # we write the name of the prod lot (mirror move)
                        result['value'].update(lot_mirror=name)
        else:
            # clear expiry date, we clear production lot
            result['value'].update(lot_mirror=False,
                                   exp_substitute_item=False,
                                   )
        return result

    def _validate_item_mirror(self, cr, uid, id, context=None):
        '''
        validate the mirror objects for lot and expiry date

        - lot AND expiry date are mandatory for batch management products
        - expiry date is mandatory for perishable products

        return True or False

        from stock and mirror need different validation function
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        lot_obj = self.pool.get('stock.production.lot')
        # browse the mirror object
        item = self.browse(cr, uid, id, context=context)
        # by default we return empty result
        result = 'empty'
        # product management type - cannot use hidden checks, because validate is called within get_vals function, would result in infinite loop
        data = prod_obj.read(cr, uid, [item.product_id_substitute_item.id], ['batch_management', 'perishable', 'type', 'subtype'], context=context)[0]
        management = data['batch_management']
        perishable = data['perishable']
        type = data['type']
        subtype = data['subtype']
        if management:
            if not item.lot_mirror:
                # lot is needed
                result = 'missing_lot'
            elif not item.exp_substitute_item:
                result = 'missing_date'
            else:
                # we check the lot type is standard if the lot exists
                # the type is not specified, as 1) name must be unique for one product 2) lot type cannot be mixed for one product, either std or int, not both
                prodlot_ids = lot_obj.search(cr, uid, [
                                            ('name', '=', item.lot_mirror),
                                            ('product_id', '=', item.product_id_substitute_item.id),
                                            ('life_date', '=', item.exp_substitute_item)
                ], context=context)
                if prodlot_ids:
                    data = lot_obj.read(cr, uid, prodlot_ids, ['type'], context=context)
                    lot_type = data[0]['type']
                    if lot_type != 'standard':
                        result = 'wrong_lot_type_need_standard'
        elif perishable:
            if not item.exp_substitute_item:
                # expiry date is needed
                result = 'missing_date'
        else:
            # no lot needed - no date needed
            if item.lot_mirror or item.exp_substitute_item:
                result = 'no_lot_needed'
        # asset check - asset is not mandatory for internal moves
        if type == 'product' and subtype == 'asset':
            pass
#            if not item.asset_id_substitute_item:
#                result = 'missing_asset'
        else:
            if item.asset_id_substitute_item:
                result = 'not_asset_needed'

        # return the corresponding integrity problem
        return result

    def validate_item(self, cr, uid, id, context=None):
        '''
        validation interface to allow modifying behavior in inherited classes
        '''
        return self._validate_item_mirror(cr, uid, id, context=context)

    _columns = {'item_id_mirror': fields.integer(string='Id of original Item', readonly=True),
                'kit_id_mirror': fields.many2one('composition.kit', string='Kit', readonly=True),
                'lot_mirror': fields.char(string='Batch Nb', size=1024),
                }

    _defaults = {'item_id_mirror': False,
                 'type_check': 'in',
                 }

substitute_item_mirror()
