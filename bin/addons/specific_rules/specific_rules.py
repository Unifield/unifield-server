# -*- coding: utf-8 -*-
##############################################################################
#
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

from dateutil import parser, relativedelta
import operator
import time

from osv import osv, fields
import tools
from tools.translate import _

# warning messages
SHORT_SHELF_LIFE_MESS = 'Product with Short Shelf Life, check the accuracy of the order quantity, frequency and mode of transport.'


class sale_order_line(osv.osv):
    '''
    override to add message at sale order creation and update
    '''
    _inherit = 'sale.order.line'

    def _kc_dg(self, cr, uid, ids, name, arg, context=None):
        '''
        return 'CC' if cold chain or 'DG' if dangerous goods
        '''
        result = {}
        for id in ids:
            result[id] = ''

        for sol in self.browse(cr, uid, ids, context=context):
            if sol.product_id:
                if sol.product_id.is_kc:
                    result[sol.id] += sol.product_id.is_kc and _('CC') or ''
                if sol.product_id.dg_txt:
                    if result[sol.id]:
                        result[sol.id] += ' / '
                    result[sol.id] += sol.product_id.is_dg and _('DG') or '%s ?' % _('DG')

        return result

    _columns = {'kc_dg': fields.function(_kc_dg, method=True, string='CC/DG', type='char'),}

    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0, uom=False, qty_uos=0, uos=False, name='',
                          partner_id=False, lang=False, update_tax=True, date_order=False, packaging=False,
                          fiscal_position=False, flag=False, context=None):
        '''
        if the product is short shelf life we display a warning
        '''
        if context is None:
            context = {}

        # call to super
        result = super(sale_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty, uom, qty_uos,
                                                                uos, name, partner_id, lang, update_tax, date_order,
                                                                packaging, fiscal_position, flag, context=context)

        # if the product is short shelf life, display a warning
        if product:
            prod_obj = self.pool.get('product.product')
            if prod_obj.browse(cr, uid, product).is_ssl:
                warning = {
                    'title': 'Short Shelf Life product',
                    'message': _(SHORT_SHELF_LIFE_MESS)
                }
                result.update(warning=warning)

        return result

    def requested_product_id_change(self, cr, uid, ids, product_id, comment=False, categ=False, context=None):
        result = super(sale_order_line, self).requested_product_id_change(cr, uid, ids, product_id, comment, categ, context)
        if product_id:
            prod_obj = self.pool.get('product.product')
            if prod_obj.browse(cr, uid, product_id).is_ssl:
                warning = {'title': 'Short Shelf Life product', 'message': _(SHORT_SHELF_LIFE_MESS)}
                result.update(warning=warning)
        return result

sale_order_line()


class sale_order(osv.osv):
    '''
    add message when so is written, i.e when we add new so lines
    '''
    _inherit = 'sale.order'

    def ssl_products_in_line(self, cr, uid, ids, context=None):
        '''
        display message if contains short shelf life
        '''
        if isinstance(ids, int):
            ids = [ids]

        can_break = False
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.split_type_sale_order != 'original_sale_order' or can_break:
                break
            for line in obj.order_line:
                # log the message
                if line.product_id.is_ssl:
                    # log the message
                    self.log(cr, uid, obj.id, _(SHORT_SHELF_LIFE_MESS))
                    can_break = True
                    break

        return True

sale_order()


class purchase_order_line(osv.osv):
    '''
    override to add message at purchase order creation and update
    '''
    _inherit = 'purchase.order.line'

    def _kc_dg(self, cr, uid, ids, name, arg, context=None):
        '''
        return 'CC' if cold chain or 'DG' if dangerous goods
        '''
        result = {}
        for id in ids:
            result[id] = ''

        for pol in self.browse(cr, uid, ids, context=context):
            if pol.product_id:
                if pol.product_id.is_kc:
                    result[pol.id] += pol.product_id.is_kc and _('CC') or ''
                if pol.product_id.dg_txt:
                    if result[pol.id]:
                        result[pol.id] += ' / '
                    result[pol.id] += pol.product_id.is_dg and _('DG') or '%s ?' % _('DG')

        return result

    _columns = {'kc_dg': fields.function(_kc_dg, method=True, string='CC/DG', type='char'),}


purchase_order_line()


class purchase_order(osv.osv):
    '''
    add message when po is written, i.e when we add new po lines

    no need to modify the wkf_confirm_order as the wrtie method is called during the workflow
    '''
    _inherit = 'purchase.order'

    def ssl_products_in_line(self, cr, uid, ids, context=None):
        '''
        display message if contains short shelf life
        '''
        if isinstance(ids, int):
            ids = [ids]

        can_break = False
        for obj in self.browse(cr, uid, ids, context=context):
            if can_break:
                break
            for line in obj.order_line:
                # log the message
                if line.product_id.is_ssl:
                    # log the message
                    self.log(cr, uid, obj.id, _(SHORT_SHELF_LIFE_MESS))
                    can_break = True
                    break

        return True

purchase_order()


class product_uom(osv.osv):
    _name = 'product.uom'
    _inherit = 'product.uom'

    def _get_uom_by_product(self, cr, uid, ids, field_name, args, context=None):
        '''
        return false for each id
        '''
        if isinstance(ids,int):
            ids = [ids]

        result = {}
        for id in ids:
            result[id] = False
        return result

    def _search_uom_by_product(self, cr, uid, obj, name, args, context=None):
        dom = []

        for arg in args:
            if arg[0] == 'uom_by_product' and arg[1] != '=':
                raise osv.except_osv(_('Error'), _('Bad comparison operator in domain'))
            elif arg[0] == 'uom_by_product':
                product_id = arg[2]
                if product_id and isinstance(product_id, int):
                    product_id = [product_id]

                if product_id:
                    product = self.pool.get('product.product').browse(cr, uid, product_id[0], context=context)
                    dom.append(('category_id', '=', product.uom_id.category_id.id))

        return dom

    def _get_uom_by_parent(self, cr, uid, ids, field_name, args, context=None):
        '''
        return false for each id
        '''
        if isinstance(ids,int):
            ids = [ids]

        result = {}
        for id in ids:
            result[id] = False
        return result

    def _search_uom_by_parent(self, cr, uid, obj, name, args, context=None):
        dom = []
        for arg in args:
            if arg[0] == 'uom_by_parent' and arg[1] != '=':
                raise osv.except_osv(_('Error'), _('Bad comparison operator in domain'))
            elif arg[0] == 'uom_by_parent':
                product_uom = arg[2]
                if product_uom:
                    if isinstance(product_uom, int):
                        product_uom = [product_uom]
                    product_uom_obj = self.browse(cr, uid, product_uom[0], context=context)
                    dom.append(('category_id', '=', product_uom_obj.category_id.id))

        return dom

    def _search_uom_by_stock_product(self, cr, uid, obj, name, args, context=None):
        dom = []

        for arg in args:
            if arg[0] == 'uom_by_stock_product' and arg[1] != '=':
                raise osv.except_osv(_('Error'), _('Bad comparison operator in domain'))
            elif arg[0] == 'uom_by_stock_product':
                product_id = arg[2]
                if product_id and isinstance(product_id, int):
                    product_id = [product_id]
                    if product_id:
                        product = self.pool.get('product.product').read(cr, uid, product_id[0], ['uom_id'], context=context)
                        if product['uom_id']:
                            dom = [('id', '=', product['uom_id'][0])]
        return dom
    _columns = {
        'uom_by_product': fields.function(_get_uom_by_product, fnct_search=_search_uom_by_product, string='UoM by Product',
                                          method=True, help='Field used to filter the UoM for a specific product'),
        'uom_by_parent': fields.function(_get_uom_by_parent, fnct_search=_search_uom_by_parent, string='UoM by Parent',
                                         method=True, help='Field used to filter the UoM for a specific product'),
        'uom_by_stock_product': fields.function(_get_uom_by_product, fnct_search=_search_uom_by_stock_product, string='Stock UoM by Product',
                                                method=True, help='Field used to filter the UoM for a specific product'),
    }

product_uom()



class stock_picking(osv.osv):
    '''
    modify hook function
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
        assetId = partial_datas.get('move%s'%(move.id), {}).get('asset_id')
        if assetId:
            defaults.update({'asset_id': assetId})

        return defaults

    _columns = {}

stock_picking()


class stock_location(osv.osv):
    '''
    override stock location to add:
    - stock_real
    - stock_virtual
    '''
    _inherit = 'stock.location'

    def replace_field_key(self, fieldsDic, search, replace):
        '''
        will replace 'stock_real' by 'stock_real_specific'
        and 'stock_virtual' by 'stock_virtual_specific'

        and return a new dictionary
        '''
        return dict((replace if key == search else key, (self.replace_field_key(value, search, replace) if isinstance(value, dict) else value)) for key, value in list(fieldsDic.items()))

    def _product_value_specific_rules(self, cr, uid, ids, field_names, arg, context=None):
        '''
        add two fields for custom stock computation, if no product selected, both stock are set to 0.0
        '''
        if context is None:
            context = {}
        # initialize data
        result = {}
        for id in ids:
            result[id] = {}
            for f in field_names:
                result[id].update({f: False,})
        # if product is set to False, it does not make sense to return a stock value, return False for each location
        if not context.get('product_id'):
            return result

        result = super(stock_location, self)._product_value(cr, uid, ids, ['stock_real', 'stock_virtual'], arg, context=context)
        # replace stock real
        result = self.replace_field_key(result, 'stock_real', 'stock_real_specific')
        # replace stock virtual
        result = self.replace_field_key(result, 'stock_virtual', 'stock_virtual_specific')
        return result

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        display the modified stock values (stock_real_specific, stock_virtual_specific) if needed
        """
        if context is None:
            context = {}
        # warehouse wizards or inventory screen
        if not view_id and view_type == 'tree':
            view = False
            if context.get('specific_rules_tree_view', False) and context.get('product_id'):
                view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_location_tree_specific_rule')
            elif not context.get('product_id'):
                view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_location_tree_simple')
            if view:
                view_id = view[1]

        return super(osv.osv, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)

    _columns = {'stock_real_specific': fields.function(_product_value_specific_rules, method=True, type='float', string='Real Stock', multi="get_vals_specific_rules"),
                'stock_virtual_specific': fields.function(_product_value_specific_rules, method=True, type='float', string='Virtual Stock', multi="get_vals_specific_rules"),
                }

stock_location()


class stock_inventory(osv.osv):
    '''
    override the action_confirm to create the production lot if needed
    '''
    _inherit = 'stock.inventory'

    def _check_line_data(self, cr, uid, ids, context=None):
        for inv in self.browse(cr, uid, ids, context=context):
            if inv.state not in ('draft', 'cancel'):
                for line in inv.inventory_line_id:
                    if line.product_qty != 0.00 and not line.location_id:
                        return False

        return True

    def copy(self, cr, uid, inventory_id, defaults, context=None):
        '''
        Set the creation date of the document to the current date
        '''
        if not defaults:
            defaults = {}

        defaults.update({'date': time.strftime('%Y-%m-%d %H:%M:%S'), 'move_ids': False})
        return super(stock_inventory, self).copy(cr, uid, inventory_id, defaults, context=context)

    _columns = {
        'sublist_id': fields.many2one('product.list', string='List/Sublist', ondelete='set null'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', ondelete='set null'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', ondelete='set null'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', ondelete='set null'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', ondelete='set null'),
    }

    _constraints = [
        (_check_line_data, "You must define a stock location for each line", ['state']),
    ]

    def onChangeSearchNomenclature(self, cr, uid, ids, position, n_type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, n_type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})

    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        line_obj = self.pool.get('stock.inventory.line')
        product_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        discrepancy_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]

        for inv in self.browse(cr, uid, ids, context=context):
            product_ids = []

            nom = False
            field = False
            # Get all products for the defined nomenclature
            if inv.nomen_manda_3:
                nom = inv.nomen_manda_3.id
                field = 'nomen_manda_3'
            elif inv.nomen_manda_2:
                nom = inv.nomen_manda_2.id
                field = 'nomen_manda_2'
            elif inv.nomen_manda_1:
                nom = inv.nomen_manda_1.id
                field = 'nomen_manda_1'
            elif inv.nomen_manda_0:
                nom = inv.nomen_manda_0.id
                field = 'nomen_manda_0'
            if nom:
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [(field, '=', nom)], context=context))

            # Get all products for the defined list
            if inv.sublist_id:
                for line in inv.sublist_id.product_ids:
                    product_ids.append(line.name.id)

            for product in product_obj.browse(cr, uid, product_ids, context=context):
                # Check if the product is not already in the list
                if product.type not in ('consu', 'service', 'service_recep') and\
                   not line_obj.search(cr, uid, [('inventory_id', '=', inv.id),
                                                 ('product_id', '=', product.id),
                                                 ('product_uom', '=', product.uom_id.id)], context=context):
                    line_obj.create(cr, uid, {'inventory_id': inv.id,
                                              'product_id': product.id,
                                              'reason_type_id': discrepancy_id,
                                              'product_uom': product.uom_id.id}, context=context)

        return True

    def get_nomen(self, cr, uid, ids, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, ids, field, context={'withnum': 1})

    def _hook_dont_move(self, cr, uid, *args, **kwargs):
        res = super(stock_inventory, self)._hook_dont_move(cr, uid, *args, **kwargs)
        if 'line' in kwargs:
            return res and not kwargs['line'].dont_move
        if 'dont_move' in kwargs:
            return res and not kwargs['dont_move']

        return res

    def check_integrity(self, cr, uid, ids, context=None):
        """
        Check if there is only one line with couple location/product
        """
        if isinstance(ids, int):
            ids = [ids]

        sql_req = """
            SELECT count(l.id) AS nb_lines
            FROM
                %s_line l
            WHERE
                l.inventory_id in %%s
            GROUP BY l.product_id, l.location_id, l.%s, l.expiry_date
            HAVING count(l.id) > 1
            ORDER BY count(l.id) DESC""" % (  # not_a_user_entry
            self._name.replace('.', '_'),
            self._name == 'stock.inventory' and 'prod_lot_id' or 'prodlot_name',
        )
        cr.execute(sql_req, (tuple(ids),))
        check_res = cr.dictfetchall()
        if check_res:
            raise osv.except_osv(
                _("Error"),
                _("""Some lines have the same data for Location/Product/Batch/
Expiry date. Only one line with same data is expected."""))

        return True

    def action_confirm(self, cr, uid, ids, context=None):
        '''
        if the line is perishable without prodlot, we create the prodlot
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        product_obj = self.pool.get('product.product')
        line_ids = []

        self.check_integrity(cr, uid, ids, context=context)

        # treat the needed production lot
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.import_error_ok:
                raise osv.except_osv(
                    _('Error'),
                    _('Plase fix issue on red lines before confirm the inventory.')
                )

            if any(l.to_correct_ok for l in obj.inventory_line_id):
                raise osv.except_osv(
                    _('Error'),
                    _('Please fix issue on red lines before confirm the inventory.')
                )

            for line in obj.inventory_line_id:
                if self._name == 'initial.stock.inventory' and line.product_qty == 0.00:
                    line.write({'dont_move': True})
                    continue

                if line.hidden_perishable_mandatory and not line.expiry_date:
                    raise osv.except_osv(_('Error'), _('The product %s is perishable but the line with this product has no expiry date') % product_obj.name_get(cr, uid, [line.product_id.id])[0][1])
                if line.hidden_batch_management_mandatory and not line.prod_lot_id:
                    raise osv.except_osv(_('Error'), _('The product %s is batch mandatory but the line with this product has no batch') % product_obj.name_get(cr, uid, [line.product_id.id])[0][1])

                if line.product_id and line.product_id.state.code != 'forbidden':
                    # Check constraints on lines
                    product_obj._get_restriction_error(cr, uid, [line.product_id.id], {'location_id': line.location_id.id}, context=context)

                # if perishable product
                if line.hidden_perishable_mandatory and not line.hidden_batch_management_mandatory:
                    # integrity test
                    if not line.product_id.perishable:
                        raise osv.except_osv(
                            _('Error'),
                            _('Product is not perishable but line is.')
                        )
                    if not line.expiry_date:
                        raise osv.except_osv(
                            _('Error'),
                            _('Expiry date is not set'),
                        )
                    # if no production lot, we create a new one
                    if not line.prod_lot_id:
                        # double check to find the corresponding prodlot
                        prodlot_ids = prodlot_obj.search(cr, uid, [('life_date', '=', line.expiry_date),
                                                                   ('type', '=', 'internal'),
                                                                   ('product_id', '=', line.product_id.id)], context=context)
                        # no prodlot, create a new one
                        if not prodlot_ids:
                            vals = {'product_id': line.product_id.id,
                                    'life_date': line.expiry_date,
                                    'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.lot.serial'),
                                    'type': 'internal',
                                    }
                            prodlot_id = prodlot_obj.create(cr, uid, vals, context=context)
                        else:
                            prodlot_id = prodlot_ids[0]
                        prodlot_name = prodlot_obj.read(cr, uid, prodlot_id, ['name'], context=context)['name']
                        # update the line
                        line.write({'prod_lot_id': prodlot_id, 'prodlot_name': prodlot_name},)

                if line.prod_lot_id and not line.expiry_date:
                    line.write({'expiry_date': line.prod_lot_id.life_date})

                line_ids.append(line.id)

        if line_ids:
            self.pool.get('%s.line' % (self._name)).write(cr, uid, line_ids, {'comment': ''}, context=context)

        # super function after production lot creation - production lot are therefore taken into account at stock move creation
        result = super(stock_inventory, self).action_confirm(cr, uid, ids, context=context)

        self.infolog(cr, uid, 'The %s inventor%s %s (%s) ha%s been validated' % (
            self._name == 'initial.stock.inventory' and 'Initial stock' or 'Physical',
            len(ids) > 1 and 'ies' or 'y',
            ids, ', '.join(x['name'] for x in self.read(cr, uid, ids, ['name'], context=context)),
            len(ids) > 1 and 've' or 's',
        ))

        return result

    def action_cancel_draft(self, cr, uid, ids, context=None):
        res = super(stock_inventory, self).action_cancel_draft(cr, uid, ids, context=context)

        for inv in self.read(cr, uid, ids, ['name'], context=context):
            self.infolog(cr, uid, "The %s inventory id:%s (%s) has been re-set to draft" % (
                self._name == 'initial.stock.inventory' and 'Initial stock' or 'Physical',
                inv['id'], inv['name'],
            ))

        if self._name == 'initial.stock.inventory':
            line_obj = self.pool.get('initial.stock.inventory.line')
        else:
            line_obj = self.pool.get('stock.inventory.line')

        line_inactive = line_obj.search(cr, uid, [('inventory_id', 'in', ids), ('location_id.active', '=', False)], context=context)
        if line_inactive:
            line_obj.write(cr, uid, line_inactive, {'comment': _('Location is inactive'), 'location_id': False, 'location_not_found': True}, context=context)
            # should be done in 2 passes
            line_obj.write(cr, uid, line_inactive, {'to_correct_ok': True}, context=context)

        return res

    def action_done(self, cr, uid, ids, context=None):
        res = super(stock_inventory, self).action_done(cr, uid, ids, context=context)

        self.infolog(cr, uid, 'The Physical inventor%s %s (%s) ha%s been confirmed' % (
            len(ids) > 1 and 'ies' or 'y',
            ids, ', '.join(x['name'] for x in self.read(cr, uid, ids, ['name'], context=context)),
            len(ids) > 1 and 've' or 's',
        ))

        return res

stock_inventory()


class stock_inventory_line(osv.osv):
    '''
    add mandatory or readonly behavior to prodlot
    '''
    _inherit = 'stock.inventory.line'
    _rec_name = 'product_id'

    def onchange_uom_qty(self, cr, uid, ids, product_uom, product_qty):
        '''
        Check the rounding of the qty according to the UoM
        '''
        return self.pool.get('product.uom')._change_round_up_qty(cr, uid, product_uom, product_qty, 'product_qty')

    def common_on_change(self, cr, uid, ids, location_id, product, prod_lot_id, uom=False, to_date=False, result=None):
        '''
        commmon qty computation
        '''
        if result is None:
            result = {}
        if not product:
            return result
        product_obj = self.pool.get('product.product').browse(cr, uid, product)
        product_uom = product_obj.uom_id.id
        if uom:
            uom_obj = self.pool.get('product.uom').browse(cr, uid, uom)
            if uom_obj.category_id.id == product_obj.uom_id.category_id.id:
                product_uom = uom
        #uom = uom or product_obj.uom_id.id
        # UF-2427: Add one little minute to make sure that all inventories created in the same minute will be included
        if to_date:
            # UFTP-321: Adapt the call to use full namespace
            # TODO JFB
            to_date = (parser.parse(to_date) + relativedelta.relativedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
        stock_context = {'uom': product_uom, 'to_date': to_date,
                         'prodlot_id':prod_lot_id,}
        if location_id:
            # if a location is specified, we do not list the children locations, otherwise yes
            stock_context.update({'compute_child': False,})
        amount = self.pool.get('stock.location')._product_get(cr, uid, location_id, [product], stock_context)[product]
        result.setdefault('value', {}).update({'product_qty': amount, 'product_uom': product_uom})
        return result

    def change_lot(self, cr, uid, ids, location_id, product, prod_lot_id, uom=False, to_date=False,):
        '''
        prod lot changes, update the expiry date
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        prod_obj = self.pool.get('product.product')
        result = {'value':{}}
        # reset expiry date or fill it
        if prod_lot_id:
            expiry_date = prodlot_obj.browse(cr, uid, prod_lot_id).life_date
        else:
            expiry_date = False
        result['value'].update({
            'expiry_date': expiry_date,
            'inv_expiry_date': expiry_date,
        })
        if expiry_date:
            prod_brw = prod_obj.browse(cr, uid, product)
            # UFTP-50: got an expiry value,
            # flagging hidden_perishable_mandatory to True:
            # expiry_date field should pass to not readable bc available,
            # and to be sendable by client into create/write vals
            # for adhoc comment column
            result['value']['hidden_perishable_mandatory'] = not prod_brw.batch_management and prod_brw.perishable
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product, prod_lot_id, uom, to_date, result=result)
        return result

    def change_expiry(self, cr, uid, id, expiry_date, product_id, type_check, context=None):
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
                    result['value'].update(prod_lot_id=False)
                else:
                    # display warning
                    result['warning'] = {'title': _('Error'),
                                         'message': _('The selected Expiry Date does not exist in the system.')}
                    # clear date
                    result['value'].update(expiry_date=False, prod_lot_id=False)
            else:
                # return first prodlot
                result['value'].update(prod_lot_id=prod_ids[0])
        else:
            # clear expiry date, we clear production lot
            result['value'].update(prod_lot_id=False,
                                   expiry_date=False,
                                   )
        return result

    def on_change_location_id(self, cr, uid, ids, location_id, product, prod_lot_id, uom=False, to_date=False,):
        """ Changes UoM and name if product_id changes.
        @param location_id: Location id
        @param product: Changed product_id
        @param uom: UoM product
        @return:  Dictionary of changed values
        """
        result = {}
        if not product:
            # do nothing
            result.setdefault('value', {}).update({'product_qty': 0.0,})
            return result

        if product and location_id:
            product_obj = self.pool.get('product.product')
            result, test = product_obj._on_change_restriction_error(cr, uid, product, field_name='location_id', values=result, vals={'location_id': location_id})
            if test:
                return result

        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product, prod_lot_id, uom, to_date, result=result)
        return result

    def on_change_product_id_specific_rules(self, cr, uid, ids, location_id, product, prod_lot_id, uom=False, to_date=False,):
        '''
        the product changes, set the hidden flag if necessary
        '''
        result = super(stock_inventory_line, self).on_change_product_id(cr, uid, ids, location_id, product, uom, to_date)
        # product changes, prodlot is always cleared
        result.setdefault('value', {})['prod_lot_id'] = False
        result.setdefault('value', {})['expiry_date'] = False
        result.setdefault('value', {})['lot_check'] = False
        result.setdefault('value', {})['exp_check'] = False
        result.setdefault('value', {})['dg_check'] = ''
        result.setdefault('value', {})['kc_check'] = ''
        result.setdefault('value', {})['np_check'] = ''
        # reset the hidden flags
        result.setdefault('value', {})['hidden_batch_management_mandatory'] = False
        result.setdefault('value', {})['hidden_perishable_mandatory'] = False
        if product:
            product_obj = self.pool.get('product.product').browse(cr, uid, product)
            if location_id and product_obj.state.code != 'forbidden':
                result, test = self.pool.get('product.product')._on_change_restriction_error(cr, uid, product, field_name='product_id', values=result, vals={'location_id': location_id})
                if test:
                    return result
            if product_obj.batch_management:
                result.setdefault('value', {})['hidden_batch_management_mandatory'] = True
                result.setdefault('value', {})['lot_check'] = True
                result.setdefault('value', {})['exp_check'] = True
            elif product_obj.perishable:
                result.setdefault('value', {})['hidden_perishable_mandatory'] = True
                result.setdefault('value', {})['exp_check'] = True
            # cold chain
            result.setdefault('value', {})['kc_check'] = product_obj.is_kc and 'X' or ''
            # ssl
            result.setdefault('value', {})['ssl_check'] = product_obj.ssl_txt
            # dangerous goods
            result.setdefault('value', {})['dg_check'] = product_obj.dg_txt
            # narcotic
            result.setdefault('value', {})['np_check'] = product_obj.cs_txt
            # if not product, result is 0.0 by super
            # compute qty
            result = self.common_on_change(cr, uid, ids, location_id, product, prod_lot_id, uom, to_date, result=result)
        return result

    def create(self, cr, uid, vals, context=None):
        '''
        complete info normally generated by javascript on_change function
        '''
        prod_obj = self.pool.get('product.product')
        if vals.get('product_id', False):
            # complete hidden flags - needed if not created from GUI
            product = prod_obj.browse(cr, uid, vals.get('product_id'), context=context)
            if product.batch_management:
                vals.update(hidden_batch_management_mandatory=True)
            elif product.perishable:
                vals.update(hidden_perishable_mandatory=True)
            else:
                vals.update(
                    hidden_batch_management_mandatory=False,
                    hidden_perishable_mandatory=False,
                    expiry_date=False,
                    prodlot_name=False,
                )
        # complete expiry date from production lot - needed if not created from GUI
        #prodlot_obj = self.pool.get('stock.production.lot')
        #if vals.get('prod_lot_id', False):
        #    vals.update(expiry_date=prodlot_obj.browse(cr, uid, vals.get('prod_lot_id'), context=context).life_date)
        # call super
        result = super(stock_inventory_line, self).create(cr, uid, vals, context=context)
        return result

    def copy_data(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}

        if 'dont_move' not in default:
            default['dont_move'] = False
        return super(stock_inventory_line, self).copy_data(cr, uid, id, default, context)


    def write(self, cr, uid, ids, vals, context=None):
        '''
        complete info normally generated by javascript on_change function
        '''
        if not ids:
            return True
        prod_obj = self.pool.get('product.product')
        if vals.get('product_id', False):
            # complete hidden flags - needed if not created from GUI
            product = prod_obj.browse(cr, uid, vals.get('product_id'), context=context)
            if product.batch_management:
                vals.update(hidden_batch_management_mandatory=True)
            elif product.perishable:
                vals.update(hidden_perishable_mandatory=True)
            else:
                vals.update(
                    hidden_batch_management_mandatory=False,
                    hidden_perishable_mandatory=False,
                    expiry_date=False,
                    prodlot_name=False,
                )
        # complete expiry date from production lot - needed if not created from GUI
        prodlot_obj = self.pool.get('stock.production.lot')
        if vals.get('prod_lot_id', False):
            vals.update(expiry_date=prodlot_obj.browse(cr, uid, vals.get('prod_lot_id'), context=context).life_date)

        # call super
        result = super(stock_inventory_line, self).write(cr, uid, ids, vals, context=context)
        return result

    def _get_checks_all(self, cr, uid, ids, name, arg, context=None):
        '''
        function for CC/SSL/DG/NP products
        '''
        result = {}
        for id in ids:
            result[id] = {}
            for f in name:
                result[id].update({f: False,})

        for obj in self.browse(cr, uid, ids, context=context):
            # cold chain
            result[obj.id]['kc_check'] = obj.product_id.is_kc and 'X' or ''
            # ssl
            result[obj.id]['ssl_check'] = obj.product_id.ssl_txt
            # dangerous goods
            result[obj.id]['dg_check'] = obj.product_id.dg_txt
            # narcotic
            result[obj.id]['np_check'] = obj.product_id.cs_txt
            # lot management
            if obj.product_id.batch_management:
                result[obj.id]['lot_check'] = True
            # expiry date management
            if obj.product_id.perishable:
                result[obj.id]['exp_check'] = True

            # has a problem
            # Line will be displayed in red if it's not correct
            result[obj.id]['has_problem'] = False
            if not obj.location_id \
               or not self._check_perishable(cr, uid, [obj.id]) \
               or not self._check_batch_management(cr, uid, [obj.id]):
                result[obj.id]['has_problem'] = True

            result[obj.id]['duplicate_line'] = False
            src_domain = [
                ('inventory_id', '=', obj.inventory_id.id),
                ('location_id', '=', obj.location_id.id),
                ('product_id', '=', obj.product_id.id),
                ('expiry_date', '=', obj.expiry_date or False),
                ('id', '!=', obj.id),
            ]

            if self._name == 'initial.stock.inventory.line':
                src_domain.append(('prodlot_name', '=', obj.prodlot_name))
            else:
                src_domain.append(('prod_lot_id', '=', obj.prod_lot_id and obj.prod_lot_id.id or False))
            if self.search(cr, uid, src_domain, limit=1, context=context):
                result[obj.id]['duplicate_line'] = True
        return result

    def _check_batch_management(self, cr, uid, ids, context=None):
        '''
        check for batch management
        '''
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.inventory_id.state not in ('draft', 'cancel') and obj.product_id.batch_management:
                if not obj.prod_lot_id or obj.prod_lot_id.type != 'standard':
                    return False
        return True

    def _check_perishable(self, cr, uid, ids, context=None):
        """
        check for perishable ONLY
        """
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.inventory_id.state not in ('draft', 'cancel') and obj.product_id.perishable and not obj.product_id.batch_management:
                if (not obj.prod_lot_id and not obj.expiry_date) or (obj.prod_lot_id and obj.prod_lot_id.type != 'internal'):
                    return False
        return True

    def _check_prodlot_need(self, cr, uid, ids, context=None):
        """
        If the inv line has a prodlot but does not need one, return False.
        """
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.prod_lot_id:
                if not obj.product_id.perishable and not obj.product_id.batch_management:
                    return False
        return True

    def _get_bm_perishable(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {
                'hidden_batch_management_mandatory': line.product_id.batch_management,
                'hidden_perishable_mandatory': line.product_id.perishable,
            }

        return res

    def _get_products(self, cr, uid, ids, context=None):
        inv_ids = self.pool.get('stock.inventory').search(cr, uid, [
            ('state', 'not in', ['done', 'cancel']),
        ], context=context)
        return self.pool.get('stock.inventory.line').search(cr, uid, [
            ('inventory_id', 'in', inv_ids),
            ('product_id', 'in', ids),
        ], context=context)

    _columns = {
        'hidden_perishable_mandatory': fields.function(
            _get_bm_perishable,
            type='boolean',
            method=True,
            string='Hidden Flag for Perishable product',
            multi='bm_perishable',
            store={
                'stock.inventory.line': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 10),
                'product.product': (_get_products, ['perishable'], 20),
            },
        ),
        'hidden_batch_management_mandatory': fields.function(
            _get_bm_perishable,
            type='boolean',
            method=True,
            string='Hidden Flag for Perishable product',
            multi='bm_perishable',
            store={
                'stock.inventory.line': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 10),
                'product.product': (_get_products, ['batch_management'], 20),
            },
        ),
        # Remove the 'required' attribute on location_id to allow the possiblity to fill lines with list or nomenclature
        # The required attribute is True on the XML view
        'location_id': fields.many2one('stock.location', 'Location'),
        'prod_lot_id': fields.many2one('stock.production.lot', 'Batch', domain="[('product_id','=',product_id)]"),
        'expiry_date': fields.date(string='Expiry Date'),
        'type_check': fields.char(string='Type Check', size=1024,),
        'kc_check': fields.function(
            _get_checks_all,
            method=True,
            string='CC',
            type='char',
            size=8,
            readonly=True,
            multi="m",
        ),
        'ssl_check': fields.function(
            _get_checks_all,
            method=True,
            string='SSL',
            type='char',
            size=8,
            readonly=True,
            multi="m",
        ),
        'dg_check': fields.function(
            _get_checks_all,
            method=True,
            string='DG',
            type='char',
            size=8,
            readonly=True,
            multi="m",
        ),
        'np_check': fields.function(
            _get_checks_all,
            method=True,
            string='CS',
            type='char',
            size=8,
            readonly=True,
            multi="m",
        ),
        'lot_check': fields.function(
            _get_checks_all,
            method=True,
            string='BN',
            type='boolean',
            readonly=True,
            multi="m",
        ),
        'exp_check': fields.function(
            _get_checks_all,
            method=True,
            string='ED',
            type='boolean',
            readonly=True,
            multi="m",
        ),
        'has_problem': fields.function(
            _get_checks_all,
            method=True,
            string='Has problem',
            type='boolean',
            readonly=True,
            multi="m",
        ),
        'duplicate_line': fields.function(
            _get_checks_all,
            method=True,
            string='Duplicate line',
            type='boolean',
            readonly=True,
            multi="m",
        ),
        'dont_move': fields.boolean(
            string='Don\'t create stock.move for this line',
        ),
    }

    _defaults = {# in is used, meaning a new prod lot will be created if the specified expiry date does not exist
                 'type_check': 'in',
                 'dont_move': lambda *a: False,
    }

    def _uom_constraint(self, cr, uid, ids, context=None):
        for obj in self.browse(cr, uid, ids, context=context):
            if not self.pool.get('uom.tools').check_uom(cr, uid, obj.product_id.id, obj.product_uom.id, context):
                raise osv.except_osv(_('Error'), _('You have to select a product UOM in the same category than the purchase UOM of the product !'))
        return True

    _constraints = [(_check_batch_management,
                     'You must assign a Batch Number which corresponds to Batch Number Mandatory Products.',
                     ['prod_lot_id']),
                    (_check_perishable,
                     'You must assign a Batch Numbre which corresponds to Expiry Date Mandatory Products.',
                     ['prod_lot_id']),
                    (_check_prodlot_need,
                     'The selected product is neither Batch Number Mandatory nor Expiry Date Mandatory',
                     ['prod_lot_id']),
                    (_uom_constraint, 'Constraint error on Uom', [])
                    ]

    def btn_dl(self, cr, uid, ids, context=None):
        """
        Return the information message that the line is duplicated
        """
        raise osv.except_osv(
            _('Error'),
            _('An other line in this inventory has the same parameters. Please remove it.')
        )

stock_inventory_line()


RSI_TOTAL_FILTER_OPERATOR = {
    '<': 'lt',
    '<=': 'le',
    '=': 'eq',
    '!=': 'ne',
    '<>': 'ne',
    '>': 'gt',
    '>=': 'ge',
}
class report_stock_inventory(osv.osv):
    '''
    UF-565: add group by expired_date
    '''
    _inherit = "report.stock.inventory"
    _rec_name = 'date'
    _auto = False

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'report_stock_inventory')
        cr.execute("""
CREATE OR REPLACE view report_stock_inventory AS (
    (SELECT
        min(m.id) as id, m.date as date,
        m.expired_date as expired_date,
        m.address_id as partner_id, m.location_id as location_id,
        m.product_id as product_id, pt.categ_id as product_categ_id, l.usage as location_type,
        m.company_id,
        m.state as state, m.prodlot_id as prodlot_id,
        CASE when pt.uom_id = m.product_uom
        THEN
        coalesce(sum(-pt.standard_price * m.product_qty)::decimal, 0.0)
        ELSE
        coalesce(sum((-pt.standard_price * m.product_qty) / u.factor * pu.factor)::decimal, 0.0) END as value,
        CASE when pt.uom_id = m.product_uom
        THEN
        coalesce(sum(-m.product_qty)::decimal, 0.0)
        ELSE
        coalesce(sum(-m.product_qty / u.factor * pu.factor)::decimal, 0.0) END as product_qty,
        pt.uom_id as uom_id
    FROM
        stock_move m
            LEFT JOIN stock_picking p ON (m.picking_id=p.id)
            LEFT JOIN product_product pp ON (m.product_id=pp.id)
                LEFT JOIN product_template pt ON (pp.product_tmpl_id=pt.id)
                LEFT JOIN product_uom pu ON (pt.uom_id=pu.id)
            LEFT JOIN product_uom u ON (m.product_uom=u.id)
            LEFT JOIN stock_location l ON (m.location_id=l.id)
    WHERE
        pt.type='product'
    GROUP BY
        m.id, m.product_id, m.product_uom, pt.categ_id, m.address_id, m.location_id,  m.location_dest_id,
        m.prodlot_id, m.expired_date, m.date, m.state, l.usage, m.company_id,pt.uom_id
) UNION ALL (
    SELECT
        -m.id as id, m.date as date,
        m.expired_date as expired_date,
        m.address_id as partner_id, m.location_dest_id as location_id,
        m.product_id as product_id, pt.categ_id as product_categ_id, l.usage as location_type,
        m.company_id,
        m.state as state, m.prodlot_id as prodlot_id,
        CASE when pt.uom_id = m.product_uom
        THEN
        coalesce(sum(pt.standard_price * m.product_qty )::decimal, 0.0)
        ELSE
        coalesce(sum((pt.standard_price * m.product_qty) / u.factor * pu.factor )::decimal, 0.0) END as value,
        CASE when pt.uom_id = m.product_uom
        THEN
        coalesce(sum(m.product_qty)::decimal, 0.0)
        ELSE
        coalesce(sum(m.product_qty / u.factor * pu.factor)::decimal, 0.0) END as product_qty,
        pt.uom_id as uom_id
    FROM
        stock_move m
            LEFT JOIN stock_picking p ON (m.picking_id=p.id)
            LEFT JOIN product_product pp ON (m.product_id=pp.id)
                LEFT JOIN product_template pt ON (pp.product_tmpl_id=pt.id)
                LEFT JOIN product_uom pu ON (pt.uom_id=pu.id)
            LEFT JOIN product_uom u ON (m.product_uom=u.id)
            LEFT JOIN stock_location l ON (m.location_dest_id=l.id)
    WHERE
        pt.type='product'
    GROUP BY
        m.id, m.product_id, m.product_uom, pt.categ_id, m.address_id, m.location_id, m.location_dest_id,
        m.prodlot_id, m.expired_date, m.date, m.state, l.usage, m.company_id,pt.uom_id
    )
);
        """)

    _columns = {
        'prodlot_id': fields.many2one('stock.production.lot', 'Batch', readonly=True),
        'expired_date': fields.date(string='Expiry Date',),
    }

    def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
        if context is None:
            context = {}
        if fields is None:
            fields = []
        context['with_expiry'] = 1
        return super(report_stock_inventory, self).read(cr, uid, ids, fields, context, load)

    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, count=False):
        '''
        UF-1546: This method is to remove the lines that have quantity = 0 from the list view
        '''

        """UTP-582: we parse domain to get 'product_qty' in it
        this filter must be applied in total and not in stock move line
        so we do not inject it in read_group but post use it in res
        (we remove it from domain even if not supported operators 'in', 'not in')
        [('state', '=', 'done'), ('location_type', '=', 'internal'), ('product_qty', '<', 100)]
        """
        product_qty_tuple = False
        if domain:
            product_qty_found_tuple = False
            for domain_tuple in domain:
                if domain_tuple[0] == 'product_qty':
                    # product qty filter found
                    product_qty_found_tuple = domain_tuple
                    product_qty_tuple = tuple(product_qty_found_tuple)
            if product_qty_found_tuple:
                domain.remove(product_qty_found_tuple)

        res = super(report_stock_inventory, self).read_group(cr, uid, domain, fields, groupby, offset, limit, context, orderby, count=count)

        # UTP-582: product qty filter (default with != 0.0)
        if not product_qty_tuple:
            product_qty_tuple = ('product_qty', '!=', 0.0)
        product_qty_op_fct = False
        if product_qty_tuple[1] in RSI_TOTAL_FILTER_OPERATOR:
            # valid operator found
            product_qty_op_fct = getattr(operator, RSI_TOTAL_FILTER_OPERATOR[product_qty_tuple[1]])
        if not product_qty_op_fct:
            product_qty_tuple = ('product_qty', '!=', 0.0)
            product_qty_op_fct = getattr(operator, 'ne')

        if self._name == 'report.stock.inventory' and res:
            return [data for data in res if product_qty_op_fct(data.get(product_qty_tuple[0], 10), product_qty_tuple[2])]
        return res

report_stock_inventory()

class product_product(osv.osv):
    _inherit = 'product.product'
    def open_stock_by_location(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if context.get('active_ids', False) and len(context['active_ids']) > 1:
            raise osv.except_osv(_('Warning !'), _('Several products have been selected (ticked). This report can only be displayed for one product'))

        ctx = {'product_id': context.get('active_id'), 'compute_child': False}
        if context.get('lang'):
            ctx['lang'] = context['lang']
        ctx['default_tree_sort'] = 'posz,name'
        ctx['search_location'] = False
        name = _('Stock by Location')
        if ids:
            prod = self.pool.get('product.product').read(cr, uid, ids[0], ['name', 'code'], context=ctx)
            name = "%s: [%s] %s"%(name, prod['code'], prod['name'])
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_override', 'view_location_tree_tree')[1]
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'stock.location',
            'view_type': 'tree',
            'view_id': [view_id],
            'domain': [('location_id','=',False)],
            'view_mode': 'tree',
            'context': ctx,
            'target': 'current',
        }

product_product()
