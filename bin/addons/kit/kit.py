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

from osv import osv, fields
from tools.translate import _
from datetime import datetime
import decimal_precision as dp
import logging
import time

# xml parser
from lxml import etree

KIT_COMPOSITION_TYPE = [('theoretical', 'Theoretical'),
                        ('real', 'Real'),
                        ]

KIT_STATE = [('draft', 'Draft'),
             ('in_production', 'In Production'),
             ('completed', 'Completed'),
             ('done', 'Closed'),
             ('cancel', 'Cancelled'),
             ]

class composition_kit(osv.osv):
    '''
    kit composition class, representing both theoretical composition and actual ones
    '''
    _name = 'composition.kit'

    def action_cancel(self, cr, uid, ids, context=None):
        '''
        action cancel set the state of the composition kit to 'cancel'
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        # all specified kits must be in draft state
        if not context.get('flag_force_cancel_composition_kit', False) and not all([x['state'] == 'draft' for x in self.read(cr, uid, ids, ['state'], context=context)]):
            raise osv.except_osv(_('Warning !'), _('You can only cancel draft theoretical kit composition and kit composition list.'))
        else:
            self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        return True

    def get_default_expiry_date(self, cr, uid, ids, context=None):
        '''
        default value for kits
        '''
        return '9999-01-01'

    def _compute_expiry_date(self, cr, uid, ids, context=None):
        '''
        compute the expiry date of real composition.kit based on items
        '''
        # date tools object
        date_obj = self.pool.get('date.tools')
        db_date_format = date_obj.get_db_date_format(cr, uid, context=context)

        for obj in self.browse(cr, uid, ids, context=context):
            # if no expiry date from items (no perishable products or no expiry date entered), the default value is '9999-01-01'
            expiry_date = False
            # computation of expiry date makes sense only for real type
            if obj.composition_type != 'real':
                raise osv.except_osv(_('Warning !'), _('Computation of expiry date is only available for Composition List.'))
            for item in obj.composition_item_ids:
                if item.item_exp:
                    if not expiry_date or datetime.strptime(item.item_exp, db_date_format) < datetime.strptime(expiry_date, db_date_format):
                        expiry_date = item.item_exp
            if not expiry_date:
                expiry_date = self.get_default_expiry_date(cr, uid, ids, context=context)

        return expiry_date

    def modify_expiry_date(self, cr, uid, ids, context=None):
        '''
        open modify expiry date wizard
        '''
        # basic check
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # data
        name = _("Modify Expiry Date")
        model = 'modify.expiry.date'
        step = 'default'
        wiz_obj = self.pool.get('wizard')
        # get the date
        data = self.read(cr, uid, ids, ['composition_exp'], context=context)[0]
        date = data['composition_exp']
        # open the selected wizard
        res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context,
                                                                                                kit_id=ids[0],
                                                                                                date=date))
        return res

    def mark_as_completed(self, cr, uid, ids, context=None):
        '''
        button function
        set the state to 'completed'
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            if not len(obj.composition_item_ids):
                raise osv.except_osv(_('Warning !'), _('Kit Composition cannot be empty.'))
            if not obj.active:
                raise osv.except_osv(_('Warning !'), _('Cannot complete inactive kit.'))
            for item in obj.composition_item_ids:
                if item.item_qty <= 0:
                    raise osv.except_osv(_('Warning !'), _('Kit Items must have a quantity greater than 0.0.'))
                if item.kcl_id and item.item_qty > 1:
                    raise osv.except_osv(_('Warning !'), _('Kit Items with a KCL Reference must not have a quantity greater than 1.'))
        self.write(cr, uid, ids, {'state': 'completed'}, context=context)
        return True

    def mark_as_inactive(self, cr, uid, ids, context=None):
        '''
        button function
        set the active flag to False
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            if obj.composition_type != 'theoretical':
                raise osv.except_osv(_('Warning !'), _('Only theoretical kit can manipulate "active" field.'))
        self.write(cr, uid, ids, {'active': False}, context=context)
        return True

    def mark_as_active(self, cr, uid, ids, context=None):
        '''
        button function
        set the active flag to False
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            if obj.composition_type != 'theoretical':
                raise osv.except_osv(_('Warning !'), _('Only theoretical kit can manipulate "active" field.'))
        self.write(cr, uid, ids, {'active': True}, context=context)
        return True

    def close_kit(self, cr, uid, ids, flow_origin='', context=None):
        '''
        button function
        set the state to 'done'
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for kcl_id in ids:
            ftf = ['composition_product_id', 'composition_combined_ref_lot', 'composition_item_ids', 'kcl_used_by']
            kcl = self.browse(cr, uid, kcl_id, fields_to_fetch=ftf, context=context)
            if kcl.kcl_used_by and not context.get('recurcive_kcl_action') and \
                    flow_origin not in ['composition.kit', 'kit.creation', 'stock.move', 'real.average.consumption']:
                raise osv.except_osv(_('Warning !'), _('The KCL %s - %s is being used by %s, please close the other document first to close this one automatically.') %
                                     (kcl.composition_product_id.default_code, kcl.composition_combined_ref_lot, kcl.kcl_used_by))
            else:
                for item in kcl.composition_item_ids:
                    if item.item_product_id and item.item_product_id.subtype == 'kit' and item.kcl_id:
                        context['recurcive_kcl_action'] = True
                        self.close_kit(cr, uid, [item.kcl_id.id], self._name, context=context)
                        context.pop('recurcive_kcl_action')

        self.write(cr, uid, ids, {'state': 'done'}, context=context)
        return True

    def reactivate_kit(self, cr, uid, ids, context=None):
        '''
        set the state of a Kit Composition List to 'completed'
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        ftf = ['state', 'composition_product_id', 'composition_combined_ref_lot', 'kcl_used_by']
        for kit in self.browse(cr, uid, ids, fields_to_fetch=ftf, context=context):
            if kit.state != 'done':
                raise osv.except_osv(_('Error'), _('You can only re-activate a Closed Kit Composition.'))
            if kit.kcl_used_by:
                raise osv.except_osv(_('Warning !'), _('The KCL %s - %s has been used by %s and can not be re-activated.') %
                                     (kit.composition_product_id.default_code, kit.composition_combined_ref_lot, kit.kcl_used_by))

        self.write(cr, uid, ids, {'state': 'completed'}, context=context)
        return True

    def reset_to_version(self, cr, uid, ids, context=None):
        '''
        open confirmation wizard
        '''
        # data
        name = _("Reset Items to Version Reference. Are you sure?")
        model = 'confirm'
        step = 'default'
        question = 'The item list of current composition list will be reset to reference list from the selected Version. Are you sure ?'
        clazz = 'composition.kit'
        func = 'do_reset_to_version'
        args = [ids]
        kwargs = {}
        # to reset to version
        for obj in self.browse(cr, uid, ids, context=context):
            # must be a real kit
            if obj.composition_type != 'real':
                raise osv.except_osv(_('Warning !'), _('Only composition lists can be reset to a version.'))
            # a version must have been selected
            if not obj.composition_version_id:
                raise osv.except_osv(_('Warning !'), _('The composition list is not linked to any version.'))

        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context, question=question,
                                                                                                callback={'clazz': clazz,
                                                                                                          'func': func,
                                                                                                          'args': args,
                                                                                                          'kwargs': kwargs}))
        return res

    def do_reset_to_version(self, cr, uid, ids, context=None):
        '''
        remove all items and create one item for each item from the referenced version
        '''
        # objects
        item_obj = self.pool.get('composition.item')
        # unlink all composition items corresponding to selected kits
        item_ids = item_obj.search(cr, uid, [('item_kit_id', 'in', ids)], context=context)
        item_obj.unlink(cr, uid, item_ids, context=context)
        for obj in self.browse(cr, uid, ids, context=context):
            # copy all items from the version
            for item_v in obj.composition_version_id.composition_item_ids:
                values = {'item_module': item_v.item_module,
                          'item_product_id': item_v.item_product_id.id,
                          'item_qty': item_v.item_qty,
                          'item_uom_id': item_v.item_uom_id.id,
                          'item_lot': item_v.item_lot, # is set to False
                          'item_exp': item_v.item_exp, # is set to False
                          'item_kit_id': obj.id,
                          'item_description': item_v.item_description,
                          'comment': item_v.comment,
                          }
                item_obj.create(cr, uid, values, context=context)
            # we display the composition list view form
            return {'type': 'ir.actions.act_window_close'}

    def _generate_item_mirror_objects(self, cr, uid, ids, wizard_data, context=None):
        """
        Generate memory objects as mirror for kit items, which can be modified (batch number policy needs modification,
        we therefore cannot link items directly).
        """
        if context is None:
            context = {}
        # objects
        mirror_obj = self.pool.get('substitute.item.mirror')
        # returned list, list of created ids
        result = []
        for obj in self.browse(cr, uid, ids, context=context):
            for item in obj.composition_item_ids:
                # create a mirror object which can be later selected and modified in the many2many field
                lot_name = item.item_lot
                if lot_name and item.item_product_id.perishable and not item.item_product_id.batch_management:
                    lot_name = False
                values = {'wizard_id': wizard_data['res_id'],
                          'item_id_mirror': item.id,
                          'kit_id_mirror': item.item_kit_id.id,
                          'module_substitute_item': item.item_module,
                          'product_id_substitute_item': item.item_product_id.id,
                          'qty_substitute_item': item.item_qty,
                          'uom_id_substitute_item': item.item_uom_id.id,
                          'asset_id_substitute_item': item.item_asset_id.id,
                          'kcl_id_substitute_item': item.kcl_id and item.kcl_id.id or False,
                          'lot_mirror': lot_name,
                          'exp_substitute_item': item.item_exp,
                          'comment': item.comment,
                          }
                id = mirror_obj.create(cr, uid, values, context=context)
                result.append(id)
        return result

    def _get_new_context(self, cr, uid, ids, context=None):
        '''
        add attributes for wizard window

        kit + product + lot
        '''
        # get corresponding data
        datas = self.read(cr, uid, ids, ['composition_product_id', 'composition_lot_id'], context=context)
        # kit ids
        kit_id = ids[0]
        # product_id
        product_id = datas[0]['composition_product_id'][0]
        # prod lot
        prodlot_id = False
        if datas[0]['composition_lot_id']:
            prodlot_id = datas[0]['composition_lot_id'][0]
        # update the context with needed data
        context.update(kit_id=kit_id, product_id=product_id, prodlot_id=prodlot_id)

        return context

    def assert_available_stock(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        assert isinstance(ids, list)

        for kit in self.browse(cr, uid, ids, context=context):


            # For kits with a batch, take the stock of the batch
            # Otherwise, take the global stock of the product
            request_context = context.copy()
            request_context.update({ 'states': ('done',),
                                     'what': ('in', 'out'),
                                     'location_usage': ['internal'],
                                     'location_category': ['stock', 'consumption_unit', 'eprep'] })
            if not kit.composition_reference and kit.composition_lot_id:
                request_context['prodlot_id'] = kit.composition_lot_id.id

            stock = self.pool.get("product.product").get_product_available(cr, uid, [kit.composition_product_id.id], context=request_context)[kit.composition_product_id.id]

            if stock <= 0:
                raise osv.except_osv(_('Error'),
                                     _('This kit product / batch is not available in stock !'))


    def substitute_items(self, cr, uid, ids, context=None):
        '''
        substitute lines from the composition kit with created new lines
        '''

        # we need the context for the wizard switch
        if context is None:
            context = {}

        self.assert_available_stock(cr, uid, ids, context=context)

        # data
        name = _("Substitute Kit Items")
        model = 'substitute'
        step = 'substitute' # this value is used in substitute wizard for attrs of src location
        wiz_obj = self.pool.get('wizard')

        # get a context with needed data
        wiz_context = self._get_new_context(cr, uid, ids, context=dict(context))
        # open the selected wizard
        res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=wiz_context)
        # write wizard id back in the wizard object, cannot use ID in the wizard form... openERP bug ?
        self.pool.get(model).write(cr, uid, [res['res_id']], {'wizard_id': res['res_id']}, context=res['context'])
        # generate mirrors item objects
        self._generate_item_mirror_objects(cr, uid, ids, wizard_data=res, context=res['context'])
        return res

    def do_substitute(self, cr, uid, ids, context=None):
        '''
        call the modify expiry date window for possible modification of expiry date
        '''
        res = self.modify_expiry_date(cr, uid, ids, context=context)
        return res

    def de_kitting(self, cr, uid, ids, context=None):
        '''
        explode the kit, preselecting all mirror items
        '''
        # we need the context for the wizard switch
        if context is None:
            context = {}

        ftf = ['composition_product_id', 'composition_combined_ref_lot', 'kcl_used_by']
        for kit in self.browse(cr, uid, ids, fields_to_fetch=ftf, context=context):
            if kit.kcl_used_by:
                raise osv.except_osv(_('Warning !'),  _('The KCL %s - %s is being used by %s and can not be de-kitted.') %
                                     (kit.composition_product_id.default_code, kit.composition_combined_ref_lot, kit.kcl_used_by))

        self.assert_available_stock(cr, uid, ids, context=context)

        # data
        name = _("De-Kitting")
        model = 'substitute'
        step = 'de_kitting' # this value is used in substitute wizard for attrs of src location
        wiz_obj = self.pool.get('wizard')
        # get a context with needed data
        wiz_context = self._get_new_context(cr, uid, ids, context=dict(context))
        # open the selected wizard
        res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=wiz_context)
        # write wizard id back in the wizard object, cannot use ID in the wizard form... openERP bug ?
        self.pool.get(model).write(cr, uid, [res['res_id']], {'wizard_id': res['res_id']}, context=res['context'])
        # generate mirrors item objects
        data = self._generate_item_mirror_objects(cr, uid, ids, wizard_data=res, context=res['context'])
        # fill all elements into the many2many field
        self.pool.get(model).write(cr, uid, [res['res_id']], {'composition_item_ids': [(6,0,data)]}, context=res['context'])
        return res

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
        # date tools object
        date_obj = self.pool.get('date.tools')
        db_date_format = date_obj.get_db_date_format(cr, uid, context=context)
        date_format = date_obj.get_date_format(cr, uid, context=context)

        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            for f in fields:
                result[obj.id].update({f:False})
            # composition version
            if obj.composition_type == 'theoretical':
                result[obj.id].update({'composition_version': obj.composition_version_txt})
            elif obj.composition_type == 'real':
                result[obj.id].update({'composition_version': obj.composition_version_id and obj.composition_version_id.composition_version_txt or ''})
                # composition_combined_ref_lot: mix between both fields reference and batch number which are exclusive fields
                if obj.composition_expiry_check:
                    result[obj.id].update({'composition_combined_ref_lot': obj.composition_lot_id.name,
                                           'composition_exp': obj.composition_lot_id.life_date})
                else:
                    result[obj.id].update({'composition_combined_ref_lot': obj.composition_reference,
                                           'composition_exp': obj.composition_ref_exp})
            # name - ex: ITC - 01/01/2012
            date = datetime.strptime(obj.composition_creation_date, db_date_format)
            result[obj.id].update({'name': result[obj.id]['composition_version'] + ' - ' + date.strftime(date_format)})
            # mandatory nomenclature levels
            result[obj.id].update({'nomen_manda_0': obj.composition_product_id.nomen_manda_0.id})
            result[obj.id].update({'nomen_manda_1': obj.composition_product_id.nomen_manda_1.id})
            result[obj.id].update({'nomen_manda_2': obj.composition_product_id.nomen_manda_2.id})
            result[obj.id].update({'nomen_manda_3': obj.composition_product_id.nomen_manda_3.id})
            result[obj.id].update({'nomen_sub_0': obj.composition_product_id.nomen_sub_0.id})
            result[obj.id].update({'nomen_sub_1': obj.composition_product_id.nomen_sub_1.id})
            result[obj.id].update({'nomen_sub_2': obj.composition_product_id.nomen_sub_2.id})
            result[obj.id].update({'nomen_sub_3': obj.composition_product_id.nomen_sub_3.id})
            result[obj.id].update({'nomen_sub_4': obj.composition_product_id.nomen_sub_4.id})
            result[obj.id].update({'nomen_sub_5': obj.composition_product_id.nomen_sub_5.id})
        return result

    def _check_kcl_used(self, cr, uid, ids, fields, arg, context=None):
        '''
        Check if there is a KCL, Kitting Order, Pick, OUT or Real Consumption using a KCL Reference
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        kcli_obj = self.pool.get('composition.item')
        kol_obj = self.pool.get('kit.creation.to.consume')
        move_obj = self.pool.get('stock.move')
        out_m_proc_obj = self.pool.get('outgoing.delivery.move.processor')
        racl_obj = self.pool.get('real.average.consumption.line')
        res = {}
        for kcl_id in ids:
            kcli_ids = kcli_obj.search(cr, uid, [('kcl_id', '=', kcl_id), ('item_kit_id.composition_type', '=', 'real'),
                                                 ('kit_state', '!=', 'cancel')], limit=1, context=context)
            kol_ids = kol_obj.search(cr, uid, [('kcl_id', '=', kcl_id), ('state', '!=', 'cancel')], limit=1, context=context)
            # Picks/OUTs + Consumed components of Kitting Orders
            move_ids = move_obj.search(cr, uid, [('composition_list_id', '=', kcl_id), ('state', '!=', 'cancel'),
                                                 '|', '&', ('type', '=', 'out'), ('picking_subtype', 'in', ['picking', 'standard']),
                                                 '&', ('kit_creation_id_stock_move', '!=', False), ('kit_creation_id_stock_move.state', '!=', 'cancel')],
                                       limit=1, context=context)
            out_m_proc_ids = out_m_proc_obj.search(cr, uid, [('composition_list_id', '=', kcl_id),
                                                             ('wizard_id.draft', '=', True)], limit=1, context=context)
            racl_ids = racl_obj.search(cr, uid, [('kcl_id', '=', kcl_id), ('rac_state', '!=', 'cancel')], limit=1, context=context)
            if kcli_ids:
                kcli = kcli_obj.browse(cr, uid, kcli_ids, fields_to_fetch=['item_kit_id'], context=context)[0]
                res[kcl_id] = kcli.item_kit_id.composition_product_id.default_code + ' - ' + kcli.item_kit_id.composition_combined_ref_lot
            elif kol_ids:
                kol = kol_obj.browse(cr, uid, kol_ids, fields_to_fetch=['kit_creation_id_to_consume'], context=context)[0]
                res[kcl_id] = kol.kit_creation_id_to_consume.name
            elif move_ids:
                move = move_obj.browse(cr, uid, move_ids, fields_to_fetch=['picking_id', 'kit_creation_id_stock_move'], context=context)[0]
                res[kcl_id] = move.kit_creation_id_stock_move and move.kit_creation_id_stock_move.name or move.picking_id.name
            elif out_m_proc_ids:
                out_m_proc = out_m_proc_obj.browse(cr, uid, out_m_proc_ids, fields_to_fetch=['wizard_id'], context=context)[0]
                res[kcl_id] = out_m_proc.wizard_id.picking_id.name
            elif racl_ids:
                res[kcl_id] = racl_obj.browse(cr, uid, racl_ids, fields_to_fetch=['rac_id'], context=context)[0].rac_id.name
            else:
                res[kcl_id] = False
        return res

    def _search_kcl_used(self, cr, uid, obj, name, args, context=None):
        '''
        ONLY GIVES IDS OF KCLS NOT USED IN A LINE OF A KCL, KITTING ORDER, PICK, OUT AND REAL CONSUMPTION
        '''
        ids = []

        for arg in args:
            if arg[2] != False:
                osv.except_osv(_('Error !'), _("Please only use 'False' as last argument for domains on 'kcl_used_by'"))
            else:
                # Get the ids of the kcls used in documents' non-cancelled lines
                cr.execute("""SELECT DISTINCT(k.id) FROM composition_kit k 
                    LEFT JOIN composition_item ki ON ki.kcl_id = k.id AND ki.item_kit_type = 'real' AND ki.state != 'cancel'
                    LEFT JOIN kit_creation_to_consume kcc ON kcc.kcl_id = k.id AND kcc.state != 'cancel'
                    LEFT JOIN stock_move m ON m.composition_list_id = k.id AND m.state != 'cancel' 
                        AND ((m.type = 'out' AND m.picking_subtype IN ('standard', 'picking')) 
                        OR m.kit_creation_id_stock_move IS NOT NULL)
                    LEFT JOIN outgoing_delivery_move_processor mp ON mp.composition_list_id = k.id
                        LEFT JOIN outgoing_delivery_processor op ON op.id = mp.wizard_id AND op.draft = 't'
                    LEFT JOIN real_average_consumption_line cl ON cl.kcl_id = k.id
                        LEFT JOIN real_average_consumption c ON cl.rac_id = c.id AND c.state != 'cancel'
                    WHERE ki.kcl_id IS NOT NULL OR m.composition_list_id IS NOT NULL OR 
                        mp.composition_list_id IS NOT NULL OR cl.kcl_id IS NOT NULL OR kcc.kcl_id IS NOT NULL""")
                ids = [res[0] for res in cr.fetchall()]

        return [('id', 'not in', ids)]

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        change version name. add (copy)

        - theoretical kit can be copied. version -> version (copy)
        - real kit with batch number cannot be copied.
        - real kit without batch but with reference can be copied. reference -> reference (copy)
        '''
        if default is None:
            default = {}
        # state
        default.update(state='draft')
        # original reference
        data = self.read(cr, uid, id, ['composition_version_txt', 'composition_type', 'composition_reference', 'composition_lot_id'], context=context)
        if data['composition_type'] == 'theoretical':
            version = data['composition_version_txt']
            default.update(composition_version_txt='%s (copy)'%version, composition_creation_date=time.strftime('%Y-%m-%d'))
        elif data['composition_type'] == 'real' and data['composition_reference'] and not data['composition_lot_id']:
            reference = data['composition_reference']
            default.update(composition_reference='%s (copy)'%reference, composition_creation_date=time.strftime('%Y-%m-%d'))
        else:
            raise osv.except_osv(_('Warning !'), _('Kit Composition List with Batch Number cannot be copied!'))

        return super(composition_kit, self).copy(cr, uid, id, default, context=context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        cannot delete composition kit not draft
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            if obj.state != 'draft':
                raise osv.except_osv(_('Warning !'), _("Cannot delete Kits not in 'draft' state."))
        return super(composition_kit, self).unlink(cr, uid, ids, context=context)

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        columns for the tree
        """
        if context is None:
            context = {}
        # the search view depends on the type we want to display
        if view_type == 'search':
            if not context.get('composition_type', False) and not context.get('wizard_composition_type', False):
                # view search not from a menu -> picking process wizard, we are looking for composition list - by default the theoretical search view is displayed
                view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'kit', 'view_composition_kit_real_filter')
                if view:
                    view_id = view[1]
            # second level flag for wizards
            elif context.get('wizard_composition_type', False) == 'theoretical':
                view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'kit', 'view_composition_kit_theoretical_filter')
                if view:
                    view_id = view[1]

        if view_type == 'tree' and not view_id:
            if not context.get('composition_type', False) and not context.get('wizard_composition_type', False):
                # view tree not from a menu -> picking process wizard, we are looking for composition list - by default the theoretical search view is      displayed
                view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'kit', 'view_composition_kit_real_tree')
                if view:
                    view_id = view[1]
            # second level flag for wizards
            elif context.get('wizard_composition_type', False) == 'theoretical' or context.get('composition_type', False) == 'theoretical':
                view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'kit', 'view_composition_kit_tree')
                if view:
                    view_id = view[1]

        # call super
        result = super(composition_kit, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        # columns depending on type - fields from one2many field

        if view_type == 'form':
            if context.get('composition_type', False) == 'theoretical':
                # load the xml tree
                root = etree.fromstring(result['fields']['composition_item_ids']['views']['tree']['arch'])
                # xpath of fields to be modified
                list = ['//field[@name="item_lot"]', '//field[@name="item_exp"]', '//field[@name="item_asset_id"]']
                for xpath in list:
                    fields = root.xpath(xpath)
                    if not fields:
                        raise osv.except_osv(_('Warning !'), _('Element %s not found.')%xpath)
                    for field in fields:
                        field.set('invisible', 'True')
                result['fields']['composition_item_ids']['views']['tree']['arch'] = etree.tostring(root)

            # if the view is called from the menu "Kit Composition List" the button duplicate and delete are hidden
            if context.get('composition_type', False) == 'real':
                # load the xml tree
                root = etree.fromstring(result['arch'])
                # the root is form tag
                root.set('hide_duplicate_button', 'True')
                root.set('hide_delete_button', 'True')
                # fields to be modified
                result['arch'] = etree.tostring(root)

        return result

    def name_get(self, cr, uid, ids, context=None):
        '''
        override displayed name
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # date tools object
        date_obj = self.pool.get('date.tools')
        db_date_format = date_obj.get_db_date_format(cr, uid, context=context)
        date_format = date_obj.get_date_format(cr, uid, context=context)
        # result
        res = []

        for obj in self.browse(cr, uid, ids, context=context):
            version = obj.composition_version or 'no_version'
            if obj.composition_type == 'theoretical':
                date = datetime.strptime(obj.composition_creation_date, db_date_format)
                name = version + ' - ' + date.strftime(date_format)
            else:
                name = obj.composition_product_id.default_code + ' - ' + version

            res += [(obj.id, name)]
        return res

    def _get_report_name(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj = self.browse(cr, uid, ids[0], context)
        db_date_format = self.pool.get('date.tools').get_date_format(cr, uid, context=context)

        data = {
            'prodcode': obj.composition_product_id.code.replace('/',''),
            'date': time.strftime(db_date_format).replace('/','_')
        }
        if obj.composition_type == 'theoretical':
            data['version'] = obj.composition_version_txt or ''
            name = 'TKL %(prodcode)s %(version)s %(date)s' % data
        else:
            data['ref'] = obj.composition_reference
            data['version'] = obj.composition_version_id and obj.composition_version_id.composition_version_txt or ''
            name = 'KCL %(prodcode)s %(version)s %(date)s %(ref)s' % data

        return name

    def on_change_product_id(self, cr, uid, ids, product_id, context=None):
        '''
        when the product is changed, lot checks are updated - mandatory workaround for attrs use
        '''
        # product object
        prod_obj = self.pool.get('product.product')
        res = {'value': {'composition_batch_check': False,
                         'composition_expiry_check': False,
                         'composition_lot_id': False,
                         'composition_exp': False,
                         'composition_reference': False,
                         'composition_ref_exp': False,
                         'composition_version_id': False,
                         'composition_version_txt': False}}
        if not product_id:
            return res

        data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management'], context=context)[0]
        res['value']['composition_batch_check'] = data['batch_management']
        res['value']['composition_expiry_check'] = data['perishable']
        return res

    def on_change_lot_id(self, cr, uid, ids, lot_id, context=None):
        '''
        when the lot is changed, expiry date is updated, so the field is modified before the save happens
        '''
        # product object
        lot_obj = self.pool.get('stock.production.lot')
        res = {'value': {'composition_exp': False,
                         'composition_ref_exp': False}}
        if not lot_id:
            return res

        data = lot_obj.read(cr, uid, [lot_id], ['life_date'], context=context)[0]
        res['value']['composition_exp'] = data['life_date']
        return res

    def _get_composition_kit_from_product_ids(self, cr, uid, ids, context=None):
        '''
        ids represents the ids of product.product objects for which values have changed

        return the list of ids of composition.kit objects which need to get their fields updated

        self is product.product object
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        kit_obj = self.pool.get('composition.kit')
        result = kit_obj.search(cr, uid, [('composition_product_id', 'in', ids)], context=context)
        return result

    def _get_composition_kit_from_lot_ids(self, cr, uid, ids, context=None):
        '''
        ids represents the ids of stock.production.lot objects for which values have changed

        return the list of ids of composition.kit objects which need to get their fields updated

        self is stock.production.lot object
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        kit_obj = self.pool.get('composition.kit')
        result = kit_obj.search(cr, uid, [('composition_lot_id', 'in', ids)], context=context)
        return result

    def onChangeSearchNomenclature(self, cr, uid, ids, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        prod_obj = self.pool.get('product.product')
        return prod_obj.onChangeSearchNomenclature(cr, uid, ids, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=num, context=context)

    def _get_nomen_s(self, cr, uid, ids, fields, *a, **b):
        prod_obj = self.pool.get('product.template')
        return prod_obj._get_nomen_s(cr, uid, ids, fields, *a, **b)

    def _search_nomen_s(self, cr, uid, obj, name, args, context=None):
        prod_obj = self.pool.get('product.template')
        return prod_obj._search_nomen_s(cr, uid, obj, name, args, context=context)

    def _set_expiry_date(self, cr, uid, ids, field, value, arg, context=None):
        """
        if the kit is linked to a batch management product, we update the expiry date for the correponding batch number
        else we udpate the composition_ref_exp field
        """
        if not value or field != 'composition_exp':
            return False
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        lot_obj = self.pool.get('stock.production.lot')
        # date tools object
        date_obj = self.pool.get('date.tools')
        db_date_format = date_obj.get_db_date_format(cr, uid, context=context)
        date_format = date_obj.get_date_format(cr, uid, context=context)

        for obj in self.browse(cr, uid, ids, context=context):
            if obj.composition_expiry_check:
                # a lot is linked, we update its expiry date
                lot_obj.write(cr, uid, [obj.composition_lot_id.id], {'life_date': value}, context=context)
                lot_name = obj.composition_lot_id.name
                prod_name = obj.composition_product_id.name
                exp_obj = datetime.strptime(value, db_date_format)
                lot_obj.log(cr, uid, obj.composition_lot_id.id, _('Expiry Date of Batch Number %s for product %s has been updated to %s.')%(lot_name,prod_name,exp_obj.strftime(date_format)))
            else:
                # not lot because the product is not batch managment, we have a reference instead, we write in composition_ref_exp
                self.write(cr, uid, ids, {'composition_ref_exp': value}, context=context)
        return True

    _columns = {'composition_type': fields.selection(KIT_COMPOSITION_TYPE, string='Composition Type', readonly=True, required=True),
                'composition_description': fields.text(string='Composition Description'),
                'composition_product_id': fields.many2one('product.product', string='Product', required=True, domain=[('type', '=', 'product'), ('subtype', '=', 'kit')]),
                'composition_version_txt': fields.char(string='Version', size=1024),
                'composition_version_id': fields.many2one('composition.kit', string='Version'),
                'composition_creation_date': fields.date(string='Creation Date', required=True),
                'composition_reference': fields.char(string='Reference', size=1024),
                'composition_lot_id': fields.many2one('stock.production.lot', string='Batch Nb'),
                'composition_ref_exp': fields.date(string='Expiry Date for Kit with reference', readonly=True),
                #                'composition_kit_creation_id': fields.many2one('kit.creation', string='Kitting Order', readonly=True),
                'composition_item_ids': fields.one2many('composition.item', 'item_kit_id', string='Items'),
                'active': fields.boolean('Active', readonly=True),
                'state': fields.selection(KIT_STATE, string='State', readonly=True, required=True),
                # related
                'composition_batch_check': fields.related('composition_product_id', 'batch_management', type='boolean', string='Batch Number Mandatory', readonly=True, store=False),
                # expiry is always true if batch_check is true. we therefore use expry_check for now in the code
                'composition_expiry_check': fields.related('composition_product_id', 'perishable', type='boolean', string='Expiry Date Mandatory', readonly=True, store=False),
                # functions
                'name': fields.function(_vals_get, method=True, type='char', size=1024, string='Name', multi='get_vals',
                                        store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_product_id'], 10),}),
                'composition_version': fields.function(_vals_get, method=True, type='char', size=1024, string='Version', multi='get_vals',
                                                       store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_version_txt', 'composition_version_id'], 10),}),
                'composition_exp': fields.function(_vals_get, fnct_inv=_set_expiry_date, method=True, type='date', size=1024, string='Expiry Date', multi='get_vals', readonly=True,
                                                   store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_ref_exp', 'composition_lot_id'], 10),
                                                           'stock.production.lot': (_get_composition_kit_from_lot_ids, ['life_date'], 10)}),
                'composition_combined_ref_lot': fields.function(_vals_get, method=True, type='char', size=1024, string='Ref/Batch Nb', multi='get_vals',
                                                                store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_lot_id', 'composition_reference'], 10),}),
                'kcl_used_by': fields.function(_check_kcl_used, method=True, fnct_search=_search_kcl_used, type='char', size=64, string='KCL used by', store=False),
                # nomenclature
                'nomen_manda_0': fields.function(_vals_get, method=True, type='many2one', relation='product.nomenclature', string='Main Type', multi='get_vals', readonly=True, select=True,
                                                 store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_product_id'], 10),
                                                         'product.template': (_get_composition_kit_from_product_ids, ['nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3'], 10),}),
                'nomen_manda_1': fields.function(_vals_get, method=True, type='many2one', relation='product.nomenclature', string='Group', multi='get_vals', readonly=True, select=True,
                                                 store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_product_id'], 10),
                                                         'product.template': (_get_composition_kit_from_product_ids, ['nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3'], 10),}),
                'nomen_manda_2': fields.function(_vals_get, method=True, type='many2one', relation='product.nomenclature', string='Family', multi='get_vals', readonly=True, select=True,
                                                 store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_product_id'], 10),
                                                         'product.template': (_get_composition_kit_from_product_ids, ['nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3'], 10),}),
                'nomen_manda_3': fields.function(_vals_get, method=True, type='many2one', relation='product.nomenclature', string='Root', multi='get_vals', readonly=True, select=True,
                                                 store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_product_id'], 10),
                                                         'product.template': (_get_composition_kit_from_product_ids, ['nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3'], 10),}),
                'nomen_manda_0_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Main Type', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_manda_1_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Group', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_manda_2_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Family', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_manda_3_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Root', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_sub_0': fields.function(_vals_get, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 1', multi='get_vals', readonly=True, select=True,
                                               store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_product_id'], 10),
                                                       'product.template': (_get_composition_kit_from_product_ids, ['nomen_sub_0', 'nomen_sub_1', 'nomen_sub_2', 'nomen_sub_3', 'nomen_sub_4', 'nomen_sub_5'], 10),}),
                'nomen_sub_1': fields.function(_vals_get, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 2', multi='get_vals', readonly=True, select=True,
                                               store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_product_id'], 10),
                                                       'product.template': (_get_composition_kit_from_product_ids, ['nomen_sub_0', 'nomen_sub_1', 'nomen_sub_2', 'nomen_sub_3', 'nomen_sub_4', 'nomen_sub_5'], 10),}),
                'nomen_sub_2': fields.function(_vals_get, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 3', multi='get_vals', readonly=True, select=True,
                                               store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_product_id'], 10),
                                                       'product.template': (_get_composition_kit_from_product_ids, ['nomen_sub_0', 'nomen_sub_1', 'nomen_sub_2', 'nomen_sub_3', 'nomen_sub_4', 'nomen_sub_5'], 10),}),
                'nomen_sub_3': fields.function(_vals_get, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 4', multi='get_vals', readonly=True, select=True,
                                               store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_product_id'], 10),
                                                       'product.template': (_get_composition_kit_from_product_ids, ['nomen_sub_0', 'nomen_sub_1', 'nomen_sub_2', 'nomen_sub_3', 'nomen_sub_4', 'nomen_sub_5'], 10),}),
                'nomen_sub_4': fields.function(_vals_get, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 5', multi='get_vals', readonly=True, select=True,
                                               store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_product_id'], 10),
                                                       'product.template': (_get_composition_kit_from_product_ids, ['nomen_sub_0', 'nomen_sub_1', 'nomen_sub_2', 'nomen_sub_3', 'nomen_sub_4', 'nomen_sub_5'], 10),}),
                'nomen_sub_5': fields.function(_vals_get, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 6', multi='get_vals', readonly=True, select=True,
                                               store= {'composition.kit': (lambda self, cr, uid, ids, c=None: ids, ['composition_product_id'], 10),
                                                       'product.template': (_get_composition_kit_from_product_ids, ['nomen_sub_0', 'nomen_sub_1', 'nomen_sub_2', 'nomen_sub_3', 'nomen_sub_4', 'nomen_sub_5'], 10),}),
                'nomen_sub_0_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 1', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_sub_1_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 2', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_sub_2_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 3', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_sub_3_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 4', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_sub_4_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 5', fnct_search=_search_nomen_s, multi="nom_s"),
                'nomen_sub_5_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 6', fnct_search=_search_nomen_s, multi="nom_s"),
                'old_version_id': fields.many2one('composition.kit', string='Version to import', help='Used to select from which old version of this Kit Product you want to import the products'),
                }

    _defaults = {'composition_creation_date': lambda *a: time.strftime('%Y-%m-%d'),
                 'composition_type': lambda s, cr, uid, c: c.get('composition_type', False),
                 'composition_product_id': lambda s, cr, uid, c: c.get('composition_product_id', False),
                 'composition_lot_id': lambda s, cr, uid, c: c.get('composition_lot_id', False),
                 'composition_exp': lambda s, cr, uid, c: c.get('composition_exp', False),
                 'composition_batch_check': lambda s, cr, uid, c: c.get('composition_batch_check', False),
                 'composition_expiry_check': lambda s, cr, uid, c: c.get('composition_expiry_check', False),
                 'active': True,
                 'state': 'draft',
                 }

    _order = 'composition_creation_date desc'

    def _composition_kit_constraint(self, cr, uid, ids, context=None):
        '''
        constraint on kit composition - two kits 
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            # global
            if obj.composition_product_id.type != 'product' or obj.composition_product_id.subtype != 'kit':
                raise osv.except_osv(_('Warning !'), _('Only Kit products can be used for kits.'))
            # theoretical constraints
            if obj.composition_type == 'theoretical':
                search_ids = self.search(cr, uid, [('id', '!=', obj.id),
                                                   ('composition_product_id', '=', obj.composition_product_id.id),
                                                   ('composition_version_txt', '=ilike', obj.composition_version_txt),
                                                   ('composition_creation_date', '=', obj.composition_creation_date)], context=context)
                if search_ids:
                    #print self.read(cr, uid, ids, ['composition_product_id', 'composition_version_txt', 'composition_creation_date'], context=context)
                    raise osv.except_osv(_('Warning !'), _('The dataset (Product - Version - Creation Date) must be unique.'))
                # constraint on lot_id/reference/expiry date - forbidden for theoretical
                if obj.composition_reference or obj.composition_lot_id or obj.composition_exp or obj.composition_ref_exp:
                    raise osv.except_osv(_('Warning !'), _('Composition Reference / Batch Number / Expiry date is not available for Theoretical Kit.'))
                # constraint on version_id - forbidden for theoretical
                if obj.composition_version_id:
                    raise osv.except_osv(_('Warning !'), _('Composition Version Object is not available for Theoretical Kit.'))

            # real constraints
            if obj.composition_type == 'real':
                # constraint on lot_id/reference - mandatory for real kit
                if obj.composition_batch_check or obj.composition_expiry_check:
                    if obj.composition_reference:
                        raise osv.except_osv(_('Warning !'), _('Composition List with Batch Management Product does not allow Reference.'))
                    if not obj.composition_lot_id:
                        raise osv.except_osv(_('Warning !'), _('Composition List with Batch Management Product needs Batch Number.'))
                    # check the lot correspond to selected product
                    if obj.composition_lot_id.product_id.id != obj.composition_product_id.id:
                        raise osv.except_osv(_('Warning !'), _('Selected Batch Number\'s product does not correspond to kit composition list\' product.'))
                    if obj.composition_ref_exp:
                        raise osv.except_osv(_('Warning !'), _('Composition List with Batch Management Product does not allow Reference based Expiry Date.'))
                    # selected composition_lot_id must be unique among KCL with state in ['draft', 'in_production', 'completed']
                    # we can have multiple canceled or done KCL with the same lot reference
                    kcl_ids = self.search(cr, uid, [('composition_lot_id', '=', obj.composition_lot_id.id),
                                                    ('state', 'not in', ['done', 'cancel'])], context=context)
                    if len(kcl_ids) > 1:
                        raise osv.except_osv(_('Warning !'), _('Batch Number must be unique for Kit Composition List not canceled or closed.'))
                else:
                    if not obj.composition_reference:
                        raise osv.except_osv(_('Warning !'), _('Composition List without Batch Management Product needs Reference.'))
                    if obj.composition_lot_id:
                        raise osv.except_osv(_('Warning !'), _('Composition List without Batch Management Product does not allow Batch Number.'))
                # real composition must always be active
                if not obj.active:
                    raise osv.except_osv(_('Warning !'), _('Composition List cannot be inactive.'))
                # check that the selected version corresponds to the selected product
                if obj.composition_version_id and obj.composition_version_id.composition_product_id.id != obj.composition_product_id.id:
                    raise osv.except_osv(_('Warning !'), _('Selected Version is for a different product.'))

        return True

    def _check_active_product(self, cr, uid, ids, context=None):
        '''
        Check if the kit composition list contains a line with an inactive product
        '''
        inactive_lines = self.pool.get('composition.item').search(cr, uid, [('item_product_id.active', '=', False),
                                                                            ('item_kit_id', 'in', ids),
                                                                            ('item_kit_id.composition_type', '=', 'real'),
                                                                            ('item_kit_id.state', '=', 'completed')], context=context)
        if inactive_lines:
            plural = len(inactive_lines) == 1 and _('A product has') or _('Some products have')
            l_plural = len(inactive_lines) == 1 and _('line') or _('lines')
            p_plural = len(inactive_lines) == 1 and _('this inactive product') or _('those inactive products')
            raise osv.except_osv(_('Error'), _('%s been inactivated. If you want to validate this document you have to remove/correct the %s containing %s (see red %s of the document)') % (plural, l_plural, p_plural, l_plural))
            return False

        for kit in self.browse(cr, uid, ids, context=context):
            if kit.composition_type == 'real' and kit.state == 'completed' and not kit.composition_product_id.active:
                raise osv.except_osv(_('Error'), _('The product of the kit composition is inactive. Please change the product.'))
                return False

        return True

    _constraints = [(_composition_kit_constraint, 'Constraint error on Composition Kit.', []),
                    (_check_active_product, 'You cannot confirm this kit because it contains a line with an inactive product', ['state', 'composition_item_ids']),
                    ]
    _sql_constraints = [('unique_composition_kit_real_ref', "unique(composition_product_id,composition_reference)", 'Kit Composition List Reference must be unique for a given product.'),
                        # the composition list with lot A should not be taken into account if state is in ['done', 'cancel']
                        #                        ('unique_composition_kit_real_lot', "unique(composition_lot_id)", 'Batch Number can only be used by one Kit Composition List.'),
                        ]

    def import_from_old_version(self, cr, uid, ids, context=None):
        """
        Import products from previous theoretical kits of this product
        """
        if context is None:
            context = {}

        kit = self.browse(cr, uid, ids[0], context=context)
        if not kit.old_version_id:
            raise osv.except_osv(_('Warning !'), _('You must select an old version of the Kit to be able to import from it'))

        item_obj = self.pool.get('composition.item')
        for item in kit.old_version_id.composition_item_ids:
            values = {
                'item_module': item.item_module,
                'item_product_id': item.item_product_id.id,
                'item_qty': item.item_qty,
                'item_uom_id': item.item_uom_id.id,
                'item_lot': item.item_lot,
                'item_exp': item.item_exp,
                'item_kit_id': kit.id,
                'item_description': item.item_description,
            }
            item_obj.create(cr, uid, values, context=context)

        return {
            'name': 'Kit Composition List',
            'view_mode': 'form, tree',
            'view_type': 'form',
            'res_model': 'composition.kit',
            'res_id': kit.id,
            'type': 'ir.actions.act_window',
            'target': 'dummy',
            'domain': [('composition_type', '=', 'theoretical')],
            'context': {'composition_type': 'theoretical'},
        }


composition_kit()


class composition_item(osv.osv):
    '''
    kit composition items representing kit parts
    '''
    _name = 'composition.item'
    _order = 'item_module'

    def _common_update(self, cr, uid, vals, context=None):
        '''
        common function for values update during create and write
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        if 'item_product_id' in vals:
            if vals['item_product_id']:
                product_id = vals['item_product_id']
                data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management', 'type', 'subtype'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                type = data['type']
                subtype = data['subtype']
                # if management and we have a lot_id, we fill the expiry date
                if management and vals.get('item_lot'):
                    prodlot_id = vals.get('item_lot')
                    prod_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_id),
                                                            ('type', '=', 'standard'),
                                                            ('product_id', '=', product_id)], context=context)
                    # if it exists, we set the date
                    if prod_ids:
                        prodlot_id = prod_ids[0]
                        data = prodlot_obj.read(cr, uid, [prodlot_id], ['life_date'], context=context)
                        expired_date = data[0]['life_date']
                        vals.update({'item_exp': expired_date})
                elif perishable:
                    # nothing special here
                    pass
                else:
                    # not perishable nor management, exp and lot are False
                    vals.update(item_lot=False, item_exp=False)
                # if the product is not of type 'product' or type is 'product' but subtype is not 'asset', we set asset to False
                if (type != 'product') or (type == 'product' and subtype != 'asset'):
                    vals.update(item_asset_id=False)
            else:
                # product is False, exp and lot are set to False - asset is set to False
                vals.update(item_lot=False, item_exp=False, item_asset_id=False)

        return vals

    def create(self, cr, uid, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products

        force writing asset_id to False.
        '''
        vals = self._common_update(cr, uid, vals, context=context)
        return super(composition_item, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products
        '''
        if not ids:
            return True
        vals = self._common_update(cr, uid, vals, context=context)
        return super(composition_item, self).write(cr, uid, ids, vals, context=context)

    def on_product_change(self, cr, uid, ids, product_id, context=None):
        '''
        product is changed, we update the UoM
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        result = {'value': {'item_uom_id': False,
                            'item_asset_id': False,
                            'item_qty': 0.0,
                            'hidden_perishable_mandatory': False,
                            'hidden_batch_management_mandatory': False,
                            'hidden_asset_mandatory': False,
                            'item_exp': False,
                            'item_lot': False,
                            'kcl_id': False,
                            }}
        if product_id:
            product = prod_obj.browse(cr, uid, product_id, context=context)
            result['value']['item_uom_id'] = product.uom_id.id
            result['value']['item_uom_rounding_is_pce'] = product.uom_id.rounding == 1
            result['value']['hidden_perishable_mandatory'] = product.perishable
            result['value']['hidden_batch_management_mandatory'] = product.batch_management
            result['value']['hidden_asset_mandatory'] = product.type == 'product' and product.subtype == 'asset'
            result['value']['product_subtype'] = product.subtype

        return result

    def onchange_uom_qty(self, cr, uid, ids, uom_id, qty):
        '''
        Check round of qty according to UoM
        '''
        res = {}

        if qty:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, qty, 'item_qty', result=res)
        if not uom_id or self.pool.get('product.uom').browse(cr, uid, uom_id, fields_to_fetch=['rounding']).rounding != 1:
            res['value'].update({'item_uom_rounding_is_pce': False, 'kcl_id': False})

        return res

    def onchange_kcl_id(self, cr, uid, ids, kcl_id, qty):
        '''
        Check the KCL with the qty
        '''
        res = {}

        if kcl_id and qty and qty > 1:
            res.update({'value': {'kcl_id': False}, 'warning': {'title': _('Warning'),
                        'message': _('Kit Items with a KCL Reference must not have a quantity greater than 1.')}})

        return res

    def on_lot_change(self, cr, uid, ids, product_id, prodlot_id, context=None):
        '''
        if lot exists in the system the date is filled in

        prodlot_id is the NAME of the production lot
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        # result
        result = {'value': {}}
        if product_id:
            data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management'], context=context)[0]
            management = data['batch_management']
            if management and prodlot_id:
                prod_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_id),
                                                        ('type', '=', 'standard'),
                                                        ('product_id', '=', product_id)], context=context)
                # if it exists, we set the date
                if prod_ids:
                    prodlot_id = prod_ids[0]
                    result['value'].update(item_exp=prodlot_obj.browse(cr, uid, prodlot_id, context=context).life_date)

        return result

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        columns for the tree
        """
        if context is None:
            context = {}

        # call super
        result = super(composition_item, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        # columns depending on type

        if view_type == 'tree':
            if context.get('composition_type', False) == 'theoretical':
                # load the xml tree
                root = etree.fromstring(result['arch'])
                # get the original empty separator ref and hide it
                # fields to be modified
                list = ['//field[@name="item_lot"]', '//field[@name="item_exp"]', '//field[@name="item_asset_id"]']
                fields = []
                for xpath in list:
                    fields = root.xpath(xpath)
                    if not fields:
                        raise osv.except_osv(_('Warning !'), _('Element %s not found.')%xpath)
                    for field in fields:
                        field.set('invisible', 'True')

                result['arch'] = etree.tostring(root)
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
            # name
            result[obj.id].update({'name': obj.item_product_id.name})
            # version
            result[obj.id].update({'item_kit_version': obj.item_kit_id.composition_version})
            # type
            result[obj.id].update({'item_kit_type': obj.item_kit_id.composition_type})
            # state
            result[obj.id].update({'state': obj.item_kit_id.state})
            # batch management
            result[obj.id].update({'hidden_batch_management_mandatory': obj.item_product_id.batch_management})
            # perishable
            result[obj.id].update({'hidden_perishable_mandatory': obj.item_product_id.perishable})
            # hidden_asset_mandatory
            result[obj.id].update({'hidden_asset_mandatory': obj.item_product_id.type == 'product' and obj.item_product_id.subtype == 'asset'})
            # product UoM is PCE
            result[obj.id].update({'item_uom_rounding_is_pce': obj.item_uom_id and obj.item_uom_id.rounding == 1 or False})
            # product subtype
            result[obj.id].update({'product_subtype': obj.item_product_id and obj.item_product_id.subtype or False})

        return result

    def name_get(self, cr, uid, ids, context=None):
        '''
        override displayed name
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # date tools object
        # result
        res = []

        for obj in self.browse(cr, uid, ids, context=context):
            name = obj.item_product_id.name
            res += [(obj.id, name)]
        return res

    def _get_composition_item_ids(self, cr, uid, ids, context=None):
        '''
        ids represents the ids of composition.kit objects for which values have changed

        return the list of ids of composition.item objects which need to get their fields updated

        self is an composition.kit object
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        item_obj = self.pool.get('composition.item')
        result = item_obj.search(cr, uid, [('item_kit_id', 'in', ids)], context=context)
        return result

    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        '''
        Fill the error message if the product of the line is inactive
        '''
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'inactive_product': False,
                            'inactive_error': ''}
            if line.item_kit_id and line.item_kit_id.state not in ('cancel', 'done') and line.item_product_id and not line.item_product_id.active:
                res[line.id] = {
                    'inactive_product': True,
                    'inactive_error': _('The product in line is inactive !')
                }

        return res

    _columns = {'item_module': fields.char(string='Module', size=1024),
                'item_product_id': fields.many2one('product.product', string='Product', required=True),
                'item_qty': fields.float(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True, related_uom='item_uom_id'),
                'item_uom_id': fields.many2one('product.uom', string='UoM', required=True),
                'item_asset_id': fields.many2one('product.asset', string='Asset'),
                'item_lot': fields.char(string='Batch Nb', size=1024),
                'item_exp': fields.date(string='Expiry Date'),
                'item_kit_id': fields.many2one('composition.kit', string='Kit/Version', ondelete='cascade', required=True, readonly=True),
                'item_description': fields.text(string='Item Description'),
                'item_stock_move_id': fields.many2one('stock.move', string='Kitting Order Stock Move', readonly=True, help='This field represents the stock move corresponding to this item for Kit production.'),
                'item_kit_name': fields.related('item_kit_id', 'composition_product_id', type='many2one', relation='product.product', string="Kit Product Code", store=True, readonly=True),
                'item_kit_batch': fields.related('item_kit_id', 'composition_lot_id', type='many2one', relation='stock.production.lot', string="Kit/BN", store=True, readonly=True),
                'comment': fields.char(size=256, string='Comment'),
                'kit_state': fields.related('item_kit_id', 'state', type='char', size=64, string='Kit State', readonly=True),
                'to_consume_id': fields.many2one('kit.creation.to.consume', 'KO Components to Consume'),
                'kcl_id': fields.many2one('composition.kit', 'Kit', domain="[('id', '!=', item_kit_id), ('composition_product_id', '=', item_product_id), ('composition_type', '=', 'real'), ('state', '=', 'completed'), ('kcl_used_by', '=', False)]"),
                # functions
                'name': fields.function(_vals_get, method=True, type='char', size=1024, string='Name', multi='get_vals',
                                        store= {'composition.item': (lambda self, cr, uid, ids, c=None: ids, ['item_product_id'], 10),}),
                'item_kit_version': fields.function(_vals_get, method=True, type='char', size=1024, string='Kit Version', multi='get_vals',
                                                    store= {'composition.item': (lambda self, cr, uid, ids, c=None: ids, ['item_kit_id'], 10),
                                                            'composition.kit': (_get_composition_item_ids, ['composition_version_txt', 'composition_version_id'], 10)}),
                'item_kit_type': fields.function(_vals_get, method=True, type='char', size=1024, string='Kit Type', multi='get_vals',
                                                 store= {'composition.item': (lambda self, cr, uid, ids, c=None: ids, ['item_kit_id'], 10),
                                                         'composition.kit': (_get_composition_item_ids, ['composition_type'], 10)}),
                'state': fields.function(_vals_get, method=True, type='selection', selection=KIT_STATE, string='State', readonly=True, multi='get_vals',
                                         store= {'composition.item': (lambda self, cr, uid, ids, c=None: ids, ['item_kit_id'], 10),
                                                 'composition.kit': (_get_composition_item_ids, ['state'], 10)}),
                'hidden_perishable_mandatory': fields.function(_vals_get, method=True, type='boolean', string='Exp', multi='get_vals', store=False, readonly=True),
                'hidden_batch_management_mandatory': fields.function(_vals_get, method=True, type='boolean', string='B.Num', multi='get_vals', store=False, readonly=True),
                'hidden_asset_mandatory': fields.function(_vals_get, method=True, type='boolean', string='Asset', multi='get_vals', store=False, readonly=True),
                'item_uom_rounding_is_pce': fields.function(_vals_get, method=True, type='boolean', string="UoM Rounding is PCE", multi='get_vals', store=False, readonly=True),
                'product_subtype': fields.function(_vals_get, method=True, type='selection', string='Product Subtype', selection=[('single', 'Single Item'), ('kit', 'Kit/Module'), ('asset', 'Asset')], multi='get_vals', store=False, readonly=True),
                'inactive_product': fields.function(_get_inactive_product, method=True, type='boolean', string='Product is inactive', store=False, multi='inactive'),
                'inactive_error': fields.function(_get_inactive_product, method=True, type='char', string='System message', store=False, multi='inactive'),
                }

    _defaults = {'hidden_batch_management_mandatory': False,
                 'hidden_perishable_mandatory': False,
                 'hidden_asset_mandatory': False,
                 'inactive_product': False,
                 'inactive_error': lambda *a: '',
                 }

    def _composition_item_constraint(self, cr, uid, ids, context=None):
        '''
        constraint on item composition 
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            if not obj.hidden_perishable_mandatory:
                # no lot or date management product
                if obj.item_lot:
                    # not perishable nor batch management - no item_lot nor item_exp
                    raise osv.except_osv(_('Warning !'), _('Only Batch Number Mandatory Product can specify Batch Number.'))
                if obj.item_exp:
                    # not perishable nor batch management - no item_lot nor item_exp
                    raise osv.except_osv(_('Warning !'), _('Only Batch Number Mandatory or Expiry Date Mandatory can specify Expiry Date.'))

        return True

    def _uom_constraint(self, cr, uid, ids, context=None):
        for obj in self.browse(cr, uid, ids, context=context):
            if not self.pool.get('uom.tools').check_uom(cr, uid, obj.item_product_id.id, obj.item_uom_id.id, context):
                raise osv.except_osv(_('Error'), _('You have to select a product UOM in the same category than the purchase UOM of the product !'))
        return True

    _constraints = [(_composition_item_constraint, 'Constraint error on Composition Item.', []),
                    (_uom_constraint, 'Constraint error on Uom', [])]

composition_item()


class product_product(osv.osv):
    '''
    add a constraint - a product of subtype 'kit' cannot be perishable only, should be batch management or nothing
    '''
    _inherit = 'product.product'

    def _kit_product_constraints(self, cr, uid, ids, context=None):
        '''
        constraint on product
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for obj in self.read(cr, uid, ids, ['type', 'subtype', 'perishable', 'batch_management', 'default_code'], context=context):
            # kit
            if obj['type'] == 'product' and obj['subtype'] == 'kit':
                if obj['perishable'] and not obj['batch_management']:
                    raise osv.except_osv(_('Warning !'), _('The Kit product %s cannot be Expiry Date Mandatory only.') % (obj['default_code']))

        return True

    def _vals_get_kit(self, cr, uid, ids, fields, arg, context=None):
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
            for f in fields:
                result[obj.id].update({f:False})
        return result

    def _search_completed_kit(self, cr, uid, obj, name, args, context=None):
        '''
        Filter the search according to the args parameter
        '''
        # Some verifications
        if context is None:
            context = {}
        # ids of products to be returned
        ids = []
        # sql query
        sql_query = """
                    select distinct p.id from product_product as p
                    inner join composition_kit as k
                    on p.id=k.composition_product_id
                    inner join product_template as t
                    on p.product_tmpl_id=t.id
                    where t.type = 'product'
                    and t.subtype = 'kit'
                    and k.composition_type = 'theoretical'
                    and k.active = True
                    and k.state = 'completed'
                    """
        for arg in args:
            if arg[0] == 'has_active_completed_theo_kit_kit' and arg[1] == '=' and arg[2]:
                # execute query
                cr.execute(sql_query)
                results = cr.dictfetchall()
                for res in results:
                    ids.append(res['id'])
            else:
                assert False, 'Search Not implemented'

        return [('id', 'in', ids)]

    _columns = {'has_active_completed_theo_kit_kit': fields.function(_vals_get_kit, fnct_search=_search_completed_kit, method=True, type='boolean', string='Kit and completed theoretical list', multi='get_vals_kit', store=False),
                }

    _constraints = [(_kit_product_constraints, 'Constraint error on Kit Product.', []),
                    ]

product_product()


class product_nomenclature(osv.osv):
    '''
    decorator over

    def _getNumberOfProducts(self, cr, uid, ids, field_name, arg, context=None):
    '''
    _inherit = 'product.nomenclature'

    def _getNumberOfProducts(self, cr, uid, ids, field_name, arg, context=None):
        '''
        check if we are concerned with composition kit, if we do, we return the number of concerned kit, not product
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        if context.get('composition_type', False):
            composition_type = context.get('composition_type')
            res = {}
            for nomen in self.browse(cr, uid, ids, context=context):
                name = ''
                if nomen.type == 'mandatory':
                    name = 'nomen_manda_%s'%nomen.level
                if nomen.type == 'optional':
                    name = 'nomen_sub_%s'%nomen.sub_level
                kit_ids = self.pool.get('composition.kit').search(cr, uid, [('composition_type', '=', composition_type), (name, '=', nomen.id)], context=context)
                if not kit_ids:
                    res[nomen.id] = 0
                else:
                    res[nomen.id] = len(kit_ids)
            return res
        else:
            return super(product_nomenclature, self)._getNumberOfProducts(cr, uid, ids, field_name, arg, context=context)

    _columns = {'number_of_products': fields.function(_getNumberOfProducts, type='integer', method=True, store=False, string='Number of Products', readonly=True),
                }

product_nomenclature()


class stock_move(osv.osv):
    '''
    add the new method self.create_composition_list
    '''
    _inherit= 'stock.move'

    def create_composition_list(self, cr, uid, ids, context=None):
        '''
        return the form view of composition_list (real) with corresponding values from the context
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        obj = self.browse(cr, uid, ids[0], context=context)
        composition_type = 'real'
        composition_product_id = obj.product_id.id
        composition_lot_id = obj.prodlot_id and obj.prodlot_id.id or False
        composition_exp = obj.expired_date
        composition_batch_check = obj.product_id.batch_management
        composition_expiry_check = obj.product_id.perishable

        return {'name': 'Kit Composition List',
                'view_id': False,
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_model': 'composition.kit',
                'res_id': False,
                'type': 'ir.actions.act_window',
                'nodestroy': False,
                'target': 'current', # current: open a new tab, new: open a wizard
                'domain': "[('composition_type', '=', 'real')]",
                'context': dict(context,
                                composition_type=composition_type,
                                composition_product_id=composition_product_id,
                                composition_lot_id=composition_lot_id,
                                composition_exp=composition_exp, # set so we do not need to wait the save to see the expiry date
                                composition_batch_check=composition_batch_check,
                                composition_expiry_check=composition_expiry_check,
                                )
                }

    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data
        '''
        # variable parameters
        move = kwargs.get('move')
        assert move, 'missing move'
        partial_datas = kwargs.get('partial_datas')
        assert partial_datas, 'missing partial_datas'

        # calling super method
        defaults = super(stock_move, self)._do_partial_hook(cr, uid, ids, context, *args, **kwargs)
        assert defaults is not None

        kit_id = partial_datas.get('move%s'%(move.id), False).get('composition_list_id')
        if kit_id:
            defaults.update({'composition_list_id': kit_id})

        return defaults

    _columns = {'composition_list_id': fields.many2one('composition.kit', string='Kit')}


stock_move()


class stock_location(osv.osv):
    '''
    add a new reservation method, taking production lot into account
    '''
    _inherit = 'stock.location'

    def compute_availability(self, cr, uid, ids, consider_child_locations, product_id, uom_id, context=None):
        '''
        call stock computation function
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        # do we want the child location
        stock_context = dict(context, compute_child=consider_child_locations)
        stock_context['uom'] = uom_id
        stock_context['location'] = ids
        # we check for the available qty (in:done, out: assigned, done)
        return {'total': self.pool.get('product.product').read(cr, uid, product_id, ['qty_allocable'], context=stock_context).get('qty_allocable', 0)}

    def _product_reserve_lot(self, cr, uid, ids, product_id, needed_qty, uom_id, context=None, lock=False, prod_lot=False, lefo=False, assign_expired=False):
        """
        refactoring of original reserver method, taking production lot into account

        returning the original list-tuple structure + the total qty in each location
        """

        amount = 0.0
        if context is None:
            context = {}
        # objects
        pool_uom = self.pool.get('product.uom')
        # location ids depends on the compute_child parameter from the context
        if context.get('compute_child', True):
            location_ids = self.search(cr, uid, [('location_id', 'child_of', ids)], context=context)
        else:
            location_ids = ids

        # lock the database if needed
        if lock:
            try:
                # Must lock with a separate select query because FOR UPDATE can't be used with
                # aggregation/group by's (when individual rows aren't identifiable).
                # We use a SAVEPOINT to be able to rollback this part of the transaction without
                # failing the whole transaction in case the LOCK cannot be acquired.
                cr.execute("SAVEPOINT stock_location_product_reserve_lot")
                cr.execute("""SELECT id FROM stock_move
                              WHERE product_id=%s AND
                                      (
                                        (location_dest_id in %s AND
                                         location_id<>location_dest_id AND
                                         state='done')
                                        OR
                                        (location_id in %s AND
                                         location_dest_id<>location_id AND
                                         state in ('done', 'assigned'))
                                      )
                              FOR UPDATE of stock_move NOWAIT""", (product_id, tuple(location_ids),  tuple(location_ids)), log_exceptions=False)
            except Exception:
                # Here it's likely that the FOR UPDATE NOWAIT failed to get the LOCK,
                # so we ROLLBACK to the SAVEPOINT to restore the transaction to its earlier
                # state, we return False as if the products were not available, and log it:
                cr.execute("ROLLBACK TO stock_location_product_reserve_lot")
                logger = logging.getLogger('stock.location')
                logger.warn("Failed attempt to reserve product %s, likely due to another transaction already in progress. Next attempt is likely to work. Detailed error available at DEBUG level.", product_id)
                logger.debug("Trace of the failed product reservation attempt: ", exc_info=True)
                return {}


        factor = pool_uom.read(cr, uid, uom_id, ['factor'])['factor']
        sql = " (expired_date is null or expired_date >= CURRENT_DATE) "
        if prod_lot:
            if assign_expired:
                sql = " prodlot_id = %s" % prod_lot
            else:
                sql += " AND prodlot_id = %s" % prod_lot
        # Change BN/ED selection in Kitting Orders if Last Expired First Out is used
        flefo = lefo and "DESC" or "ASC"

        cr.execute("""
                    SELECT subs.location, subs.parent_left, subs.prodlot_id, subs.expired_date, sum(subs.product_qty) AS product_qty FROM
                        (SELECT m.location_dest_id as location, loc.parent_left, m.prodlot_id, lot.life_date as expired_date, sum(m.product_qty / move_uom.factor) AS product_qty
                            FROM stock_move m
                            LEFT JOIN stock_production_lot lot ON lot.id = m.prodlot_id
                            LEFT JOIN stock_location loc ON loc.id = m.location_dest_id
                            LEFT JOIN product_uom move_uom ON move_uom.id = m.product_uom
                            WHERE m.location_dest_id in %s AND
                            m.location_id<>m.location_dest_id AND
                            m.product_id=%s AND
                            m.state='done' AND
                            """ + sql + """
                            GROUP BY m.location_dest_id, loc.parent_left, m.prodlot_id, lot.life_date

                            UNION

                            SELECT m.location_id as location, loc.parent_left, m.prodlot_id, lot.life_date as expired_date, -sum(m.product_qty / move_uom.factor) AS product_qty
                            FROM stock_move m
                            LEFT JOIN stock_production_lot lot on lot.id = m.prodlot_id
                            LEFT JOIN stock_location loc on loc.id = m.location_id
                            LEFT JOIN product_uom move_uom ON move_uom.id = m.product_uom
                            WHERE m.location_id in %s AND
                            m.location_dest_id<>m.location_id AND
                            m.product_id=%s AND
                            m.state in ('done', 'assigned') AND
                            """ + sql + """
                            GROUP BY m.location_id, loc.parent_left, m.prodlot_id, lot.life_date) as subs
                    GROUP BY location, parent_left, prodlot_id, expired_date
                    ORDER BY expired_date """ + flefo + """, prodlot_id asc, parent_left
                   """,
                   (tuple(location_ids), product_id, tuple(location_ids), product_id))  # not_a_user_entry

        results = []
        for r in cr.dictfetchall():
            # consolidates the uom
            amount = r['product_qty'] * factor
            # total for all locations
            if amount <= 0:
                continue
            if amount >= needed_qty:
                if results and results[-1][1:4] == [r['location'], r['expired_date'], r['prodlot_id']]:
                    results[-1][0] += needed_qty
                else:
                    results.append([needed_qty, r['location'], r['expired_date'], r['prodlot_id']])
                return results

            if results and results[-1][1:4] == [r['location'], r['expired_date'], r['prodlot_id']]:
                results[-1][0] += amount
            else:
                results.append([amount, r['location'], r['expired_date'], r['prodlot_id']])

            needed_qty -= amount

        if not results:
            return []
        if needed_qty:
            results.append([needed_qty, False, False, False, False])

        return results

stock_location()


class stock_picking(osv.osv):
    '''
    treat the composition list
    '''
    _inherit = 'stock.picking'

    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data
        '''
        # variable parameters
        move = kwargs.get('move')
        assert move, 'missing move'
        partial_datas = kwargs.get('partial_datas')
        assert partial_datas, 'missing partial_datas'

        # calling super method
        defaults = super(stock_picking, self)._do_partial_hook(cr, uid, ids, context, *args, **kwargs)
        kit_id = partial_datas.get('move%s'%(move.id), {}).get('composition_list_id')
        if kit_id:
            defaults.update({'composition_list_id': kit_id})

        return defaults

stock_picking()


class purchase_order_line(osv.osv):
    '''
    add theoretical de-kitting capabilities
    '''
    _inherit = 'purchase.order.line'

    def de_kitting(self, cr, uid, ids, context=None):
        '''
        open theoretical kit selection
        '''
        if context is None:
            context = {}
        # data
        name = _("Replacement Items Selection")
        model = 'kit.selection'
        step = 'default'
        wiz_obj = self.pool.get('wizard')
        # this purchase order line replacement function can only be used when the po is in state ('draft', 'validated', 'validated_n'),
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.state not in ('draft', 'validated', 'validated_n'):
                raise osv.except_osv(_('Warning !'), _('Purchase order line kit replacement with components function is only available for Draft and Validated state.'))
        # open the selected wizard
        data = self.read(cr, uid, ids, ['product_id'], context=context)[0]
        product_id = data['product_id'][0]
        res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context,
                                                                                                product_id=product_id))
        return res

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
            result[obj.id] = {'kit_pol_check': False}
            # we want the possibility to explose the kit within the purchase order
            # - the product is a kit AND
            # - at least one theoretical kit exists for this product - is displayed anyway, because the user can now add products not from the theoretical template
            product = obj.product_id
            if product and product.type == 'product' and product.subtype == 'kit':
                result[obj.id].update({'kit_pol_check': True})
        return result

    _columns = {'kit_pol_check' : fields.function(_vals_get, method=True, string='Kit Mem Check', type='boolean', readonly=True, multi='get_vals_kit'),
                }

purchase_order_line()


class sale_order_line(osv.osv):
    '''
    add theoretical de-kitting capabilities
    '''
    _inherit = 'sale.order.line'

    def de_kitting(self, cr, uid, ids, context=None):
        '''
        open theoretical kit selection
        '''
        if context is None:
            context = {}
        # data
        name = _("Replacement Items Selection from Field Order")
        model = 'kit.selection.sale'
        step = 'default'
        wiz_obj = self.pool.get('wizard')
        # this purchase order line replacement function can only be used when the po is in state ('confirmed', 'Validated'),
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.so_state_stored not in ['draft', 'validated']:
                raise osv.except_osv(_('Warning !'), _('Sale order line kit replacement with components function is only available for Draft and Validated states.'))
        # open the selected wizard
        data = self.read(cr, uid, ids, ['product_id'], context=context)[0]
        product_id = data['product_id'][0]
        res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context,
                                                                                                product_id=product_id))
        return res

    def _vals_get_kit(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # objects
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {'kit_pol_check_sale_order_line': False}
            # we want the possibility to explose the kit within the purchase order
            # - the product is a kit AND
            # - at least one theoretical kit exists for this product - is displayed anyway, because the user can now add products not from the theoretical template
            product = obj.product_id
            if product and product.type == 'product' and product.subtype == 'kit':
                result[obj.id].update({'kit_pol_check_sale_order_line': True})
        return result

    _columns = {'kit_pol_check_sale_order_line' : fields.function(_vals_get_kit, method=True, string='Kit Mem Check', type='boolean', readonly=True, multi='get_vals_kit', store=False),
                }

sale_order_line()
