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
from lxml import etree
import tools
from datetime import datetime

import logging
import logging.handlers

from base.res.signature import _register_log
import requests
from . import unidata_sync
import json

class product_section_code(osv.osv):
    _name = "product.section.code"
    _rec_name = 'section'

    _columns = {
        'code': fields.char('Code', size=4),
        'section': fields.char('Section', size=32),
        'description': fields.char('Description', size=128),
    }
product_section_code()

class product_status(osv.osv):
    _name = "product.status"
    _columns = {
        'code': fields.char('Code', size=256),
        'name': fields.char('Name', size=256, required=True, translate=1),
        'no_external': fields.boolean(string='External partners orders'),
        'no_esc': fields.boolean(string='ESC partners orders'),
        'no_internal': fields.boolean(string='Internal partners orders'),
        'no_consumption': fields.boolean(string='Consumption'),
        'no_storage': fields.boolean(string='Storage'),
        'active': fields.boolean('Active'),
        'mapped_to': fields.many2one('product.status', string='Replaced by'),
    }

    _defaults = {
        'active': True,
    }
    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        ids_p = self.pool.get('product.product').search(cr, uid,
                                                        [('state','in',ids)], limit=1, order='NO_ORDER')
        if ids_p:
            raise osv.except_osv(_('Error'), _('You cannot delete this status because it\'s used at least in one product'))
        return super(product_status, self).unlink(cr, uid, ids, context=context)

product_status()

class product_international_status(osv.osv):
    _name = "product.international.status"
    _columns = {
        'code': fields.char('Code', size=256),
        'name': fields.char('Name', size=256, required=True, translate=1),
        'no_external': fields.boolean(string='External partners orders'),
        'no_esc': fields.boolean(string='ESC partners orders'),
        'no_internal': fields.boolean(string='Internal partners orders'),
        'no_consumption': fields.boolean(string='Consumption'),
        'no_storage': fields.boolean(string='Storage'),
    }
    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Raise an error if the status is used in a product
        ids_p = self.pool.get('product.product').search(cr, uid,
                                                        [('international_status','in',ids)],
                                                        limit=1, order='NO_ORDER')
        if ids_p:
            raise osv.except_osv(_('Error'), _('You cannot delete this product creator because it\'s used at least in one product'))

        # Raise an error if the status is ITC or Temporary because there are used in some product.product methods
        tmp_int_1 = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_1')
        int_1 = tmp_int_1[1] or False
        tmp_int_5 = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_5')
        int_5 = tmp_int_5[1] or False

        if int_1 and int_1 in ids:
            raise osv.except_osv(_('Error'), _('You cannot remove the \'ITC\' international status because it\'s a system value'))
        if int_5 and int_5 in ids:
            raise osv.except_osv(_('Error'), _('You cannot remove the \'Temporary\' international status because it\'s a system value'))

        return super(product_international_status, self).unlink(cr, uid, ids, context=context)

product_international_status()

class product_heat_sensitive(osv.osv):
    _name = "product.heat_sensitive"
    _order = 'code desc'
    _columns = {
        'code': fields.char(
            string='Code',
            size=256,
        ),
        'name': fields.char(
            string='Name',
            size=256,
            required=True,
            translate=1,
        ),
        'active': fields.boolean(
            string='Active',
        )
    }

    _defaults = {
        'active': True,
    }

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        ids_p = self.pool.get('product.product').search(cr, uid, [
            ('heat_sensitive_item', 'in', ids),
        ], limit=1, order='NO_ORDER')
        if ids_p:
            raise osv.except_osv(
                _('Error'),
                _('You cannot delete this heat sensitive because it\'s used at least in one product'),
            )
        return super(product_heat_sensitive, self).unlink(cr, uid, ids, context=context)

    def name_search(self, cr, uid, name='', args=None, operator='ilike', context=None, limit=100):
        """
        In context of sync. update execution, look for active and inactive heat sensitive items
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param name: Object name to search
        :param args: List of tubles specifying search criteria [('field_name', 'operator', 'value'), ...]
        :param operatior: Operator for search criterion
        :param context: Context of the call
        :param limit: Optional max number of records to return
        :return: List of objects names matching the search criteria, used to provide completion for to-many relationships
        """
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if args is None:
            args = []

        if context.get('sync_update_execution'):
            item_id = data_obj.get_object_reference(cr, uid, 'product_attributes', 'heat_yes')
            if item_id:
                ids = self._search(cr, uid, [('id', '=', item_id[1])], limit=limit, context=context,
                                   access_rights_uid=uid)
                return self.name_get(cr, uid, ids, context)

        return super(product_heat_sensitive, self).name_search(cr, uid, name, args, operator, context=context, limit=limit)

product_heat_sensitive()

class product_cold_chain(osv.osv):
    _name = "product.cold_chain"
    _columns = {
        'code': fields.char('Code', size=256),
        'ud_code': fields.char(string='Code', size=256),
        'name': fields.char('Name', size=256, required=True, translate=1),
        'cold_chain': fields.boolean('Cold Chain'),
        'mapped_to': fields.many2one('product.cold_chain', string='Mapped to', readonly=1),
    }

    _defaults = {
        'cold_chain': False,
    }
    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        ids_p = self.pool.get('product.product').search(cr, uid,
                                                        [('cold_chain','in',ids)],
                                                        limit=1, order='NO_ORDER')
        if ids_p:
            raise osv.except_osv(_('Error'), _('You cannot delete this cold chain because it\'s used at least in one product'))
        return super(product_cold_chain, self).unlink(cr, uid, ids, context=context)

    def name_search(self, cr, uid, name='', args=None, operator='ilike', context=None, limit=100):
        """
        In context of sync. update execution, look for active and inactive heat sensitive items
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param name: Object name to search
        :param args: List of tubles specifying search criteria [('field_name', 'operator', 'value'), ...]
        :param operatior: Operator for search criterion
        :param context: Context of the call
        :param limit: Optional max number of records to return
        :return: List of objects names matching the search criteria, used to provide completion for to-many relationships
        """
        data_obj = self.pool.get('ir.model.data')
        if context is None:
            context = {}

        if args is None:
            args = []

        if context.get('sync_update_execution'):
            match_dict = {
                tools.ustr('3* Cold Chain * - Keep Cool: used for a kit containing cold chain module or item(s)'): 'cold_1',
                tools.ustr('6*0 Cold Chain *0 - Problem if any window blue'): 'cold_2',
                tools.ustr('7*0F Cold Chain *0F - Problem if any window blue or Freeze-tag = ALARM'): 'cold_3',
                tools.ustr('8*A Cold Chain *A - Problem if B, C and/or D totally blue'): 'cold_4',
                tools.ustr('9*AF Cold Chain *AF - Problem if B, C and/or D totally blue or Freeze-tag = ALARM'): 'cold_5',
                tools.ustr('10*B Cold Chain *B - Problem if C and/or D totally blue'): 'cold_6',
                tools.ustr('11*BF Cold Chain *BF - Problem if C and/or D totally blue or Freeze-tag = ALARM'): 'cold_7',
                tools.ustr('12*C Cold Chain *C - Problem if D totally blue'): 'cold_8',
                tools.ustr('13*CF Cold Chain *CF - Problem if D totally blue or Freeze-tag = ALARM'): 'cold_9',
                tools.ustr('14*D Cold Chain *D - Store and transport at -25°C (store in deepfreezer, transport with dry-ice)'): 'cold_10',
                tools.ustr('15*F Cold Chain *F - Cannot be frozen: check Freeze-tag'): 'cold_11',
                tools.ustr('16*25 Cold Chain *25 - Must be kept below 25°C (but not necesseraly in cold chain)'): 'cold_12',
                tools.ustr('17*25F Cold Chain *25F - Must be kept below 25°C and cannot be frozen: check  Freeze-tag'): 'cold_13',
            }

            if name in list(match_dict.keys()):
                item_id = data_obj.get_object_reference(cr, uid, 'product_attributes', match_dict[name])
                if item_id:
                    ids = self._search(cr, uid, [('id', '=', item_id[1])], limit=limit, context=context,
                                       access_rights_uid=uid)
                    return self.name_get(cr, uid, ids, context)

        return super(product_cold_chain, self).name_search(cr, uid, name, args, operator, context=context, limit=limit)

product_cold_chain()

class product_supply_source(osv.osv):
    _name = "product.supply.source"
    _rec_name = 'source'

    _columns = {
        'source': fields.char('Supply source', size=32),
    }
product_supply_source()

class product_justification_code(osv.osv):
    _name = "product.justification.code"
    _order = 'code'
    _rec_name = 'code'
    _columns = {
        'code': fields.char('Justification Code', size=32, required=True, translate=True),
        'description': fields.char('Justification Description', size=256, required=True, translate=True),
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
        'state': fields.many2one('product.status', 'UniField Status', help="Tells the user if he can use the product or not.", required=1),
    }

    def _get_valid_stat(self, cr, uid, context=None):
        st_ids = self.pool.get('product.status').search(cr, uid, [('code', '=', 'valid')], context=context)
        return st_ids and st_ids[0]

    _defaults = {
        'type': 'product',
        'state': _get_valid_stat,
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

    merged_fields_to_keep = ['procure_method', 'soq_quantity', 'description_sale', 'description_purchase', 'procure_delay']
    mapping_ud = {
        'valid': 'valid',
        'outdated': 'valid',
        'discontinued': 'valid',
        'forbidden': 'forbidden',
        'archived': 'archived',
    }

    def execute_migration(self, cr, moved_column, new_column):
        super(product_attributes, self).execute_migration(cr, moved_column, new_column)

        if new_column not in ['standard_ok', 'dangerous_goods', 'short_shelf_life', 'controlled_substance']:
            return

        # Get the list of ID of product.product that will be updated to make a touch() on it to trigger a new sync. update
        ids_req = 'SELECT id FROM product_product WHERE %s = True' % moved_column
        if new_column == 'controlled_substance':
            ids_req = '%s OR narcotic = True' % ids_req

        cr.execute('''UPDATE ir_model_data SET
                            last_modification = now(),
                            touched='[''%s'']'
                        WHERE model = 'product.product'
                        AND res_id IN (%s)
        ''' % (new_column, ids_req))  # not_a_user_entry

        # Make the migration
        if new_column == 'standard_ok':
            request = 'UPDATE product_product SET standard_ok = \'True\' WHERE %s = True' % moved_column  # not_a_user_entry
            cr.execute(request)

        if new_column == 'dangerous_goods':
            request = 'UPDATE product_product SET is_dg = True, dg_txt = \'X\', dangerous_goods = \'True\' WHERE %s = True' % moved_column  # not_a_user_entry
            cr.execute(request)

        if new_column == 'short_shelf_life':
            request = 'UPDATE product_product SET is_ssl = True, ssl_txt = \'X\', short_shelf_life = \'True\' WHERE %s = True' % moved_column  # not_a_user_entry
            cr.execute(request)

        if new_column == 'controlled_substance':
            # Update old ticked controlled substance but not narcotic
            request = '''UPDATE product_product SET
                              controlled_substance = 'True',
                              is_cs = True,
                              cs_txt = 'X'
                            WHERE %s = True OR narcotic = True''' % moved_column  # not_a_user_entry
            cr.execute(request)

        return

    def _get_nomen(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        for product in self.browse(cr, uid, ids, context=context):
            res[product.id] = []
            nomen_field_names = ['nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3', 'nomen_sub_0', 'nomen_sub_1', 'nomen_sub_2', 'nomen_sub_3', 'nomen_sub_4', 'nomen_sub_5']
            for field in nomen_field_names:
                value = getattr(product, field, False).id
                if value:
                    res[product.id].append(value)
        return res

    def _search_nomen(self, cr, uid, obj, name, args, context=None):
        '''
        Filter the search according to the args parameter
        '''
        if context is None:
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

    def _get_int_status_code(self, cr, uid, ids, field_name, args, context=None):
        if context is None:
            context = {}
        res = {}

        for product in self.browse(cr, uid, ids, fields_to_fetch=['international_status'], context=context):
            res[product.id] = product.international_status.code

        return res

    def _get_restriction(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        product_state = self.pool.get('product.status')
        intl_state = self.pool.get('product.international.status')
        for product in self.read(cr, uid, ids, ['state', 'international_status'], context=context):
            res[product['id']] = {
                'no_external': False,
                'no_esc': False,
                'no_internal': False,
                'no_consumption': False,
                'no_storage': False
            }
            fields = ['no_external', 'no_esc', 'no_internal', 'no_consumption', 'no_storage']
            state = None
            intl = None
            if product['state']:
                state = product_state.read(cr, uid, product['state'][0], fields, context=context)
            if product['international_status']:
                intl = intl_state.read(cr, uid, product['international_status'][0], fields, context=context)

            if state or intl:
                for f in fields:
                    res[product['id']][f] = (state and state[f]) or (intl and intl[f]) or False

        return res

    def _get_product_status(self, cr, uid, ids, context=None):
        return self.pool.get('product.product').search(cr, uid, [('state', 'in', ids)], context=context)

    def _get_international_status(self, cr, uid, ids, context=None):
        return self.pool.get('product.product').search(cr, uid, [('international_status', 'in', ids)], context=context)

    def _get_dummy(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for id in ids:
            res[id] = False

        return res

    def _get_vat_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the system configuration VAT management is set to True
        '''
        vat_ok = self.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok
        res = {}
        for id in ids:
            res[id] = vat_ok

        return res

    # This method is here because the following domain didn't work on field order/purchase order lines
    # [('no_internal', '=', parent.partner_type != 'internal'), ('no_external', '=', parent.partner_type != 'external'),('no_esc', '=', parent.partner_type != 'esc'),
    def _src_available_for_restriction(self, cr, uid, obj, name, args, context=None):
        '''
        Search available products for the partner given in args
        '''
        if context is None:
            context = {}

        for arg in args:
            if arg[0] == 'available_for_restriction' and arg[1] == '=' and arg[2]:
                if isinstance(arg[2], dict) and arg[2].get('location_id'):
                    # Compute the constraint if a location is passed in vals
                    location = self.pool.get('stock.location').browse(cr, uid, arg[2].get('location_id'), context=context)
                    bef_scrap_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_override', 'stock_location_quarantine_scrap')[1]
                    if location.usage != 'inventory' and not location.destruction_location and (not bef_scrap_id or location.id != bef_scrap_id):
                        return [('no_storage', '=', False)]

                if arg[2] == 'external':
                    return [('no_external', '=', False)]
                elif arg[2] == 'esc':
                    return [('no_esc', '=', False)]
                elif arg[2] in ('internal', 'intermission', 'section'):
                    if context.get('sale_id') and arg[2] == 'internal':
                        forbidden_ids = self.pool.get('product.status').search(cr, uid, [('code', '=', 'forbidden')], context=context)
                        if forbidden_ids:
                            return ['|', ('no_internal', '=', False), ('state', '=', forbidden_ids[0])]
                    return [('no_internal', '=', False)]
                elif arg[2] == 'consumption':
                    return [('no_consumption', '=', False)]
                elif arg[2] == 'storage':
                    return [('no_storage', '=', False)]
                elif arg[2] in ('picking', 'tender'):
                    return [('no_external', '=', False), ('no_internal', '=', False), ('no_esc', '=', False)]

        return []


    def _compute_kc_dg_cs_ssl_values(self, cr, uid, ids, field_names, args, context=None):
        """
        Compute the character to display ('X' or '?' or '') according to product values
        for Cold Chain, Dangerous Goods, Controlled Substance and Short Shelf Life.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of product.product to compute values
        :param field_names: Name of the fields to compute
        :param args: Additionnal arguments
        :param context: Conetxt of the call
        :return: A dictionary with the ID of product.product as keys and
                 a dictionary with computed field values for each ID in ids.
        """
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        if not isinstance(field_names, list):
            field_names = [field_names]

        res = {}
        for product in self.browse(cr, uid, ids, fields_to_fetch=['short_shelf_life', 'cold_chain', 'dangerous_goods', 'controlled_substance'], context=context):
            res[product.id] = {}
            if product.short_shelf_life == 'True':
                is_ssl = True
                ssl_txt = 'X'
            elif product.short_shelf_life == 'no_know':
                is_ssl = False
                ssl_txt = '?'
            else:
                is_ssl = False
                ssl_txt = ''

            if product.dangerous_goods == 'True':
                is_dg = True
                dg_txt = 'X'
            elif product.dangerous_goods == 'no_know':
                is_dg = False
                dg_txt = '?'
            else:
                is_dg = False
                dg_txt = ''


            if 'is_ssl' in field_names or 'ssl_txt' in field_names:
                res[product.id].update({
                    'is_ssl': is_ssl,
                    'ssl_txt': ssl_txt
                })

            if 'is_kc' in field_names:
                res[product.id]['is_kc'] = product.cold_chain and product.cold_chain.cold_chain or False

            if 'is_dg' in field_names or 'dg_txt' in field_names:
                res[product.id].update({
                    'is_dg': is_dg,
                    'dg_txt': dg_txt,
                })

            if 'is_cs' in field_names or 'cs_txt' in field_names:
                res[product.id].update({
                    'is_cs': product.controlled_substance,
                    'cs_txt': product.controlled_substance and 'X' or '',
                })

        return res

    def do_not_migrate(self, cr, ids):
        """
        Don't compute this fields.function because values are already set with execute_migration method
        and patch.
        """
        return True

    def _get_batch_attributes(self, cr, uid, ids, field_name, args, context=None):
        ret = {}
        for prod in self.read(cr, uid, ids, ['batch_management', 'perishable'], context=context):
            if prod['batch_management']:
                ret[prod['id']] = 'bn'
            elif prod['perishable']:
                ret[prod['id']] = 'ed'
            else:
                ret[prod['id']] = 'no'
        return ret

    def _search_batch_attributes(self, cr, uid, obj, name, args, context=None):

        dom = []
        for arg in args:
            if arg[0] == 'batch_attributes':
                if arg[1] != '=':
                    raise osv.except_osv(_('Warning'), _('This filter is not implemented yet'))
                if arg[2] == 'no':
                    dom += [ '&', ('batch_management', '=', False), ('perishable', '=', False)]
                elif arg[2] == 'bn':
                    dom += [ '&', ('batch_management', '=', True), ('perishable', '=', True)]
                elif arg[2] == 'ed':
                    dom += [ '&', ('batch_management', '=', False), ('perishable', '=', True)]
        return dom

    def _search_incompatible_oc_default_values(self, cr, uid, obj, name, args, context=None):
        dom = []
        oc_def = self.pool.get('unidata.default_product_value')
        for arg in args:
            if arg[1] == '=':
                if not arg[2]:
                    raise osv.except_osv(_('Warning'), _('This filter is not implemented'))

                oc_def_ids = oc_def.search(cr, uid, [], context=context)
            elif arg[1] == 'in':
                if not isinstance(arg[2], list):
                    raise osv.except_osv(_('Warning'), _('This filter is not implemented'))
                oc_def_ids = arg[2]
            else:
                raise osv.except_osv(_('Warning'), _('This filter is not implemented'))

            temp_dom = []
            for oc_val in oc_def.browse(cr, uid, oc_def_ids, context=context):
                value = oc_val.value
                if value == 'f':
                    value = False
                temp_dom.append(['&', ('nomen_manda_%d' % oc_val.nomenclature.level, '=', oc_val.nomenclature.id), (oc_val.field, '!=', value)])

            ud_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_6')[1]
            if temp_dom:
                dom += temp_dom[0]
                for d in temp_dom[1:]:
                    dom.insert(0, '|')
                    dom += d
                dom = ['&', ('international_status', '=', ud_id)] + dom

        return dom

    def _search_show_ud(self, cr, uid, obj, name, args, context=None):
        dom = []
        for arg in args:
            if arg[1] != '=':
                raise osv.except_osv(_('Warning'), _('This filter is not implemented yet'))
            if arg[2]:
                dom = [('international_status', '=', 'UniData'), ('active', '=', True), ('standard_ok', 'in', ['non_standard', 'standard']), ('replace_product_id', '=', False)]
            else:
                dom = [('international_status', '=', 'UniData'), ('active', 'in', ['t', 'f']), ('standard_ok', '=', 'non_standard_local'), ('replace_product_id', '=', False)]

        return dom

    def _get_local_from_hq(self, cr, uid, ids, field_name, args, context=None):
        '''
            used by sync to set active=False at coo / proj
        '''

        res = {}
        level = self.pool.get('res.company')._get_instance_level(cr, uid)
        for _id in ids:
            res[_id] = {'local_from_hq': False, 'level_source': level}

        if level == 'section':
            for _id in self.search(cr, uid, [('id', 'in', ids), ('standard_ok', '=', 'non_standard_local'), ('international_status', '=', 'UniData'), ('active', 'in', ['t', 'f'])], context=context):
                res[_id]['local_from_hq'] =  True

        return res

    def _get_local_activation_from_merge(self, cr, uid, ids, field_name, args, context=None):
        '''
        Used by sync to not sync down active=True from coo to proj.
        Activation of UD prod from COO will be done by the sync merge update for non non-standard local products
        '''
        res = {}
        for _id in ids:
            res[_id] = False

        if self.pool.get('res.company')._get_instance_level(cr, uid) == 'coordo':
            prod_domain = [('id', 'in', ids), ('international_status', '=', 'UniData'), ('active', '=', True),
                           ('replace_product_id', '!=', False), ('standard_ok', '!=', 'non_standard_local')]
            for _id in self.search(cr, uid, prod_domain, context=context):
                res[_id] = True

        return res

    def _get_product_instance_level(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        level = self.pool.get('res.company')._get_instance_level(cr, uid)
        for _id in ids:
            res[_id] = level or False
        return res

    def _get_allow_merge(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for _id in ids:
            res[_id] = False
        if context is None:
            context = {}
        if context.get('sync_update_execution') or self.pool.get('res.company')._get_instance_level(cr, uid) == 'coordo':
            dom = [('id', 'in', ids), ('international_status', '=', 'UniData'), ('replace_product_id', '=', False)]
            if context.get('sync_update_execution'):
                # UD prod deactivated in coordo + merge + sync : proj does not see the deactivation
                dom += [('active', 'in', ['t', 'f'])]
            else:
                dom += ['|', '&', ('active', 'in', ['t', 'f']), ('standard_ok', '=', 'non_standard_local'), '&', ('active', '=', True), ('standard_ok', 'in', ['non_standard', 'standard'])]
            for p_id in self.search(cr, uid, dom, context=context):
                res[p_id] = True
        return res

    def _get_nsl_merged(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for _id in ids:
            res[_id] = False
        s_domain = [('id', 'in', ids), ('replaced_by_product_id', '!=', False), ('local_product_merged', '=', False), ('active', 'in', ['t', 'f'])]
        for _id in self.search(cr, uid, s_domain, context=context):
            res[_id] = True
        return res

    def _get_cold_chain_products(self, cr, uid, ids, context=None):
        # do not return product ids to write to not trigger mass update

        for cold in self.pool.get('product.cold_chain').read(cr, uid, ids, ['cold_chain'], context=context):
            is_kc = cold['cold_chain']
            cr.execute('''
                update product_product  set
                    is_kc=%(is_kc)s
                where
                    cold_chain = %(cold_id)s and
                    is_kc != %(is_kc)s
            ''', {'cold_id': cold['id'], 'is_kc': is_kc})
            nb_updated = cr.rowcount
            if nb_updated:
                logging.getLogger('cold chain').info('Cold chain id:%s, update %s products' % (cold['id'], nb_updated))
            return []

    def _get_can_be_hq_merged(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for _id in ids:
            res[_id] = False

        if self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.level != 'section':
            return res

        for _id in self.search(cr, uid, [('id', 'in', ids), ('active', '=', True), ('international_status', '=', 'UniData'), ('kept_product_id', '=', False)], context=context):
            if self.search(cr, uid, [('active', 'in', ['t', 'f']), ('kept_product_id', '=', _id)], count=True, context=context) < 2:
                res[_id] = True
        return res

    def _get_oc_coordo_restrictions(self, cr, uid, ids, field_name, args, context=None):
        if not ids:
            return {}
        ret = {}
        for _id in ids:
            ret[_id] = {'oc_coordo_restrictions': [], 'oc_instance_restrictions': []}

        cr.execute('''select
                p.id, array_agg(distinct(inst.id))
            from
                product_product p, product_country_rel c_rel, unidata_project up, msf_instance inst
            where
                p.id in %s
                and p.id = c_rel.product_id
                and up.country_id = c_rel.unidata_country_id
                and inst.id = up.instance_id
                and inst.level = 'coordo'
            group by p.id
            ''', (tuple(ids), ))

        for x in cr.fetchall():
            ret[x[0]]['oc_coordo_restrictions'] = x[1]

        cr.execute('''select
                p.id, array_agg(distinct(uf_i.instance_id))
            from
                product_product p, product_project_rel p_rel, unidata_project up, unifield_instance uf_i
            where
                p.id in %s
                and p.id = p_rel.product_id
                and up.id = p_rel.unidata_project_id
                and up.unifield_instance_id = uf_i.id
            group by p.id
            ''', (tuple(ids), ))

        for x in cr.fetchall():
            ret[x[0]]['oc_instance_restrictions'] = x[1]
        return ret

    def _get_valid_msl_instance(self, cr, uid, ids, field_name, args, context=None):
        """
            list unidata.project with activated MSL
        """
        if not ids:
            return {}
        ret = {}

        for _id in ids:
            ret[_id] = []

        cr.execute('''
            select
                rel.product_id, array_agg(p.unifield_instance_id order by p.instance_name)
            from
                product_msl_rel rel, unidata_project p
            where
                rel.msl_id = p.id
                and rel.product_id in %s
                and p.uf_active = 't'
                and rel.creation_date is not null
                and p.publication_date is not null
            group by
                rel.product_id
            ''', (tuple(ids), )
        )

        for prod in cr.fetchall():
            ret[prod[0]] = list(set(prod[1]))

        return ret


    def _get_restrictions_txt(self, cr, uid, ids, field_name, args, context=None):
        if not ids:
            return {}
        ret = {}

        temp_ret = {}
        for _id in ids:
            temp_ret[_id] = []

        mission_t = _('Missions')
        cr.execute('''select
                c_rel.product_id, array_agg(distinct inst.code order by inst.code)
            from
                product_country_rel c_rel, unidata_project up, msf_instance inst
            where
                c_rel.product_id in %s
                and up.country_id = c_rel.unidata_country_id
                and inst.id = up.instance_id
                and inst.level = 'coordo'
            group by c_rel.product_id
            ''', (tuple(ids), ))


        for x in cr.fetchall():
            temp_ret[x[0]] = ['%s: %s' % (mission_t, ', ' .join(x[1]))]


        project_t = _('Projects')
        cr.execute('''select
                p_rel.product_id, array_agg(distinct inst.code order by inst.code)
            from
                product_project_rel p_rel, unidata_project up, msf_instance inst
            where
                p_rel.product_id in %s
                and up.id =  p_rel.unidata_project_id
                and inst.id = up.instance_id
            group by p_rel.product_id
            ''', (tuple(ids), ))

        for x in cr.fetchall():
            temp_ret[x[0]] += ['%s: %s' % (project_t, ', ' .join(x[1]))]

        for _id in temp_ret:
            ret[_id] = "\n".join(temp_ret[_id])

        return ret

    def _get_is_ud_golden(self, cr, uid, ids, field_name, args, context=None):
        if not ids:
            return {}
        ret = {}

        for _id in ids:
            ret[_id] = False

        cr.execute('''
            select p.id
            from product_product p, product_international_status st
            where
                st.code ='unidata' and
                st.id = p.international_status and
                p.id in %s and
                p.golden_status = 'Golden'
            ''', (tuple(ids), ))

        for x in cr.fetchall():
            ret[x[0]] = True

        return ret

    def _search_is_ud_golden(self, cr, uid, obj, name, args, context=None):
        if context is None:
            context = {}

        unidata_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_6')[1]
        dom = [('international_status', '=', unidata_id)]
        for arg in args:
            if arg[0] == 'is_ud_golden':
                if arg[1] not in ('=', '!='):
                    raise osv.except_osv(_('Error'), _('Filter not implemented on %s') % (name, ))
                if not arg[2] or arg[2] in ('f', 'False', 'false'):
                    value = False
                else:
                    value = True
                if arg[1] == '!=':
                    value = not value

                if value:
                    dom += [('golden_status', '=', 'Golden')]
                else:
                    dom += [('golden_status', '!=', 'Golden')]

        return dom


    _columns = {
        'duplicate_ok': fields.boolean('Is a duplicate'),
        'loc_indic': fields.char('Indicative Location', size=64),
        'description2': fields.text('Description 2'),
        'old_code' : fields.char(
            string='Old code',
            size=1024,
        ),
        'new_code': fields.char('New code', size=64),
        'international_status': fields.many2one('product.international.status', 'Product Creator', required=False),
        'int_status_code': fields.function(_get_int_status_code, method=True, readonly=True, type="char", size=64, string="Code of Product Creator", store=False),
        'perishable': fields.boolean('Expiry Date Mandatory'),
        'batch_management': fields.boolean('Batch Number Mandatory'),
        'batch_attributes': fields.function(_get_batch_attributes, type='selection', selection=[('no', 'X'), ('bn', 'BN+ED'), ('ed', 'ED only')], method=True, fnct_search=_search_batch_attributes, string="Batch Attr."),
        'product_catalog_page' : fields.char('Product Catalog Page', size=64),
        'product_catalog_path' : fields.char('Product Catalog Path', size=1024),
        'is_ssl': fields.function(
            _compute_kc_dg_cs_ssl_values,
            _fnct_migrate=do_not_migrate,
            method=True,
            type='boolean',
            string='Is Short Shelf Life ?',
            multi='ssl',
            readonly=True,
            store={
                'product.product': (lambda self, cr, uid, ids, c=None: ids, ['short_shelf_life'], 10),
            }
        ),
        'ssl_txt': fields.function(
            _compute_kc_dg_cs_ssl_values,
            _fnct_migrate=do_not_migrate,
            method=True,
            type='char',
            size=8,
            string='Short Shelf Life icon',
            multi='ssl',
            readonly=True,
            store={
                'product.product': (lambda self, cr, uid, ids, c=None: ids, ['short_shelf_life'], 10),
            }
        ),
        'short_shelf_life': fields.selection(
            selection=[
                ('False', 'No'),
                ('True', 'Yes'),
                ('no_know', 'tbd'),
            ],
            string='Short Shelf Life',
            required=True,
        ),
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

        'is_kc': fields.function(
            _compute_kc_dg_cs_ssl_values,
            _fnct_migrate=do_not_migrate,
            method=True,
            type='boolean',
            string='Is Cold Chain ?',
            multi='ssl',
            readonly=True,
            store={
                'product.product': (lambda self, cr, uid, ids, c=None: ids, ['cold_chain'], 10),
                'product.cold_chain': (_get_cold_chain_products, ['cold_chain'], 20),
            }
        ),
        'heat_sensitive_item': fields.many2one(
            'product.heat_sensitive',
            string='Temperature sensitive item',
            required=True,
        ),
        'cold_chain': fields.many2one('product.cold_chain', 'Thermosensitivity'),
        'show_cold_chain': fields.boolean('Show cold chain'),
        # Inverse of m2m options_ids
        'options_ids_inv': fields.many2many('product.product', 'product_options_rel', 'product_option_id', 'product_id', 'Options Inv.'),
        'sterilized': fields.selection(
            selection=[
                ('yes', 'Yes'),
                ('no', 'No'),
                ('no_know', 'tbd'),
            ],
            string='Sterile',
            required=True,
        ),
        'single_use': fields.selection(
            selection=[
                ('yes', 'Yes'),
                ('no', 'No'),
                ('no_know', 'tbd'),
            ],
            string='Single Use',
            required=True,
        ),
        'justification_code_id': fields.many2one('product.justification.code', 'Justification Code'),
        'med_device_class': fields.selection([('',''),
                                              ('I','Class I (General controls)'),
                                              ('II','Class II (General control with special controls)'),
                                              ('III','Class III (General controls and premarket)')], 'Medical Device Class'),
        'manufacturer_txt': fields.text(
            string='Manufacturer',
        ),
        'manufacturer_ref': fields.char(
            size=1024,
            string='Manufacturer Ref.'
        ),
        'closed_article': fields.selection(
            selection=[
                ('yes', 'Yes'),
                ('no', 'No'),
                ('recommanded', 'Recommended'),
            ],
            string='Closed Article',
            required=True,
        ),
        'is_dg': fields.function(
            _compute_kc_dg_cs_ssl_values,
            _fnct_migrate=do_not_migrate,
            method=True,
            type='boolean',
            string='Is a Dangerous Goods ?',
            multi='ssl',
            readonly=True,
            store={
                'product.product': (lambda self, cr, uid, ids, c=None: ids, ['dangerous_goods'], 10),
            }
        ),
        'dg_txt': fields.function(
            _compute_kc_dg_cs_ssl_values,
            _fnct_migrate=do_not_migrate,
            method=True,
            type='char',
            size=8,
            string='Dangerous Goods icon',
            multi='ssl',
            readonly=True,
            store={
                'product.product': (lambda self, cr, uid, ids, c=None: ids, ['dangerous_goods'], 10),
            }
        ),
        'dangerous_goods': fields.selection(
            selection=[
                ('False', 'No'),  # False is put as key for migration (see US-752)
                ('True', 'Yes'),  # True is put as key for migration (see US-752)
                ('no_know', 'tbd'),
            ],
            string='Dangerous goods',
            required=True,
        ),
        'restricted_country': fields.boolean('Restricted in the Country'),
        'country_restriction': fields.many2one('res.country.restriction', 'Country Restriction'),
        'state_ud': fields.selection(
            selection=[
                ('valid', 'Valid'),
                ('outdated', 'Outdated'),
                ('discontinued', 'Discontinued'),
                ('phase_out', 'Phase Out'),
                ('stopped', 'Stopped'),
                ('archived', 'Archived'),
                ('forbidden', 'Forbidden'),
            ],
            string='UniData Status',
            readonly=True,
            help="Automatically filled with UniData information.",
        ),
        'golden_status': fields.selection([('Golden', 'Golden'), ('Unmatched', 'Unmatched'), ('Merged', 'Merged'), ('Deleted', 'Deleted')], 'UD Golden State', select=1, readonly=1),
        'is_ud_golden': fields.function(_get_is_ud_golden, type='boolean', method=1, string='UD Golden', fnct_search=_search_is_ud_golden),
        'ud_seen': fields.boolean('UD seen in last full sync', select=1, readonly=1),
        'oc_subscription': fields.boolean(string='OC Subscription'),
        # TODO: validation on 'un_code' field
        'un_code': fields.char('UN Code', size=32),
        'hs_code': fields.char('HS Code', size=12, readonly=1),
        'gmdn_code' : fields.char('GMDN Code', size=5),
        'gmdn_description' : fields.char('GMDN Description', size=64),
        'life_time': fields.integer('Product Life Time',
                                    help='The number of months before a production lot may become dangerous and should not be consumed.'),
        'use_time': fields.integer('Product Use Time',
                                   help='The number of months before a production lot starts deteriorating without becoming dangerous.'),
        'removal_time': fields.integer('Product Removal Time',
                                       help='The number of months before a production lot should be removed.'),
        'alert_time': fields.integer('Product Alert Time', help="The number of months after which an alert should be notified about the production lot."),
        'currency_id': fields.many2one('res.currency', string='Currency', readonly=True, hide_default_menu=True),
        'field_currency_id': fields.many2one('res.currency', string='Currency', readonly=True, hide_default_menu=True),
        'nomen_ids': fields.function(_get_nomen, fnct_search=_search_nomen,
                                     type='many2many', relation='product.nomenclature', method=True, string='Nomenclatures'),
        'controlled_substance': fields.selection(
            selection=[
                ('!', '! - Requires national export license'),
                ('N1', 'N1 - Narcotic 1'),
                ('N2', 'N2 - Narcotic 2'),
                ('P1', 'P1 - Psychotrop 1'),
                ('P2', 'P2 - Psychotrop 2'),
                ('P3', 'P3 - Psychotrop 3'),
                ('P4', 'P4 - Psychotrop 4'),
                ('DP', 'DP - Drug Precursor'),
                ('Y', 'Y - Kit or module with controlled substance'),
                ('True', 'CS / NP - Controlled Substance / Narcotic / Psychotropic')
            ],
            string='Controlled substance',
        ),
        'is_cs': fields.function(
            _compute_kc_dg_cs_ssl_values,
            _fnct_migrate=do_not_migrate,
            method=True,
            type='boolean',
            string='Is Controlled subst.',
            multi='ssl',
            readonly=True,
            store={
                'product.product': (lambda self, cr, uid, ids, c=None: ids, ['controlled_substance'], 10),
            }
        ),
        'cs_txt': fields.function(
            _compute_kc_dg_cs_ssl_values,
            _fnct_migrate=do_not_migrate,
            method=True,
            type='char',
            size=8,
            string='Controlled subst. icon',
            multi='ssl',
            readonly=True,
            store={
                'product.product': (lambda self, cr, uid, ids, c=None: ids, ['controlled_substance'], 10),
            }
        ),
        'uom_category_id': fields.related('uom_id', 'category_id', string='Uom Category', type='many2one', relation='product.uom.categ', write_relate=False),
        'no_external': fields.function(_get_restriction, method=True, type='boolean', string='External partners orders', readonly=True, multi='restriction',
                                       store={'product.product': (lambda self, cr, uid, ids, c=None: ids, ['international_status', 'state'], 20),
                                              'product.status': (_get_product_status, ['no_external'], 10),
                                              'product.international.status': (_get_international_status, ['no_external'], 10),}),
        'no_esc': fields.function(_get_restriction, method=True, type='boolean', string='ESC partners orders', readonly=True, multi='restriction',
                                  store={'product.product': (lambda self, cr, uid, ids, c=None: ids, ['international_status', 'state'], 20),
                                         'product.status': (_get_product_status, ['no_esc'], 10),
                                         'product.international.status': (_get_international_status, ['no_esc'], 10),}),
        'no_internal': fields.function(_get_restriction, method=True, type='boolean', string='Internal partners orders', readonly=True, multi='restriction',
                                       store={'product.product': (lambda self, cr, uid, ids, c=None: ids, ['international_status', 'state'], 20),
                                              'product.status': (_get_product_status, ['no_internal'], 10),
                                              'product.international.status': (_get_international_status, ['no_internal'], 10),}),
        'no_consumption': fields.function(_get_restriction, method=True, type='boolean', string='Comsumption', readonly=True, multi='restriction',
                                          store={'product.product': (lambda self, cr, uid, ids, c=None: ids, ['international_status', 'state'], 20),
                                                 'product.status': (_get_product_status, ['no_consumption'], 10),
                                                 'product.international.status': (_get_international_status, ['no_consumption'], 10),}),
        'no_storage': fields.function(_get_restriction, method=True, type='boolean', string='Storage', readonly=True, multi='restriction',
                                      store={'product.product': (lambda self, cr, uid, ids, c=None: ids, ['international_status', 'state'], 20),
                                             'product.status': (_get_product_status, ['no_storage'], 10),
                                             'product.international.status': (_get_international_status, ['no_storage'], 10),}),
        'available_for_restriction': fields.function(_get_dummy, fnct_search=_src_available_for_restriction, method=True, type='boolean',
                                                     store=False, string='Available for the partner', readonly=True),
        'form_value': fields.text(string='Form', translate=True),
        'fit_value': fields.text(string='Fit', translate=True),
        'function_value': fields.text(string='Function', translate=True),
        'standard_ok': fields.selection(
            selection=[
                #('True', 'Standard'),
                #('False', 'Non-standard'),
                ('standard', 'Standard'),
                ('non_standard', 'Non-standard'),
                ('non_standard_local', 'Non-standard Local'),
            ],
            size=20,
            string='Standardization Level',
            required=True,
        ),
        'local_from_hq': fields.function(_get_local_from_hq, method=1, type='boolean', string='Non-Standard Local from HQ', help='Set to True when HQ generates a sync update on NSL product', internal=1, multi='sync_helper'),
        'level_source': fields.function(_get_local_from_hq, method=1, type='char', string='Instance level which has generated the sync update', internal=1, multi='sync_helper'),
        'local_activation_from_merge': fields.function(_get_local_activation_from_merge, method=1, type='boolean', string='Non-Standard Local from COO', help='Activate on COO from merge', internal=1),
        'active_change_date': fields.datetime('Date of last active change', readonly=1),
        'active_sync_change_date': fields.datetime('Date of last active sync change', readonly=1),
        'soq_weight': fields.float(digits=(16,5), string='SoQ Weight'),
        'soq_volume': fields.float(digits=(16,5), string='SoQ Volume'),
        'soq_quantity': fields.float(digits=(16,2), string='SoQ Quantity', related_uom='uom_id', help="Standard Ordering Quantity. Quantity according to which the product should be ordered. The SoQ is usually determined by the typical packaging of the product."),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
        'nsl_merged': fields.function(_get_nsl_merged, method=True, type='boolean', string='UD / NSL merged'),
        'local_product_merged': fields.boolean('Local Merged', help='Local Product Merged with another Local Product', readonly=1),
        'replace_product_id': fields.many2one('product.product', string='Merged from', select=1),
        'replaced_by_product_id': fields.many2one('product.product', string='Merged to'),
        'allow_merge': fields.function(_get_allow_merge, type='boolean', method=True, string="UD Allow merge"),
        'uf_write_date': fields.datetime(_('Write date')),
        'uf_create_date': fields.datetime(_('Creation date')),
        'instance_level': fields.function(_get_product_instance_level, method=True, string='Instance Level', internal=1, type='char'),
        'show_ud': fields.function(_get_dummy, fnct_search=_search_show_ud, method=True, type='boolean', string='Search UD NSL or ST/NS', internal=1),
        'currency_fixed': fields.boolean('Currency Changed by US-8196'),
        'can_be_hq_merged': fields.function(_get_can_be_hq_merged, method=True, string='Can this product be merged to a kept product ?', type='boolean'),
        'kept_product_id': fields.many2one('product.product', string='Kept Product', select=1, readonly=1),
        'kept_initial_product_id': fields.many2one('product.product', string='1st Kept Product in case of chaining', select=1, readonly=1),
        'unidata_merged': fields.boolean('UniData Merged', readonly=1),
        'unidata_merge_date': fields.datetime('Date of UniData Merge', readonly=1, select=1),
        'is_kept_product': fields.boolean('Is a kept product', readonly=1),

        'oc_validation': fields.boolean('OC Validation', readonly=1),
        'oc_validation_date': fields.datetime('Validation Date', readonly=1), #lastValidationDate
        'oc_devalidation_date': fields.datetime('Devalidation Date', readonly=1), #lastDevalidationDate
        'oc_devalidation_reason': fields.text('Devalidation Reason', readonly=1), #devalidationReason
        'oc_comments': fields.text('Use Comments', readonly=1), # comments
        'oc_project_restrictions': fields.many2many('unidata.project', 'product_project_rel', 'product_id', 'unidata_project_id', 'UD Project Restrictions', readonly=1, order_by='code'),
        'oc_country_restrictions': fields.many2many('unidata.country', 'product_country_rel', 'product_id', 'unidata_country_id', 'UD Country Restrictions', readonly=1, order_by='name'),
        'oc_instance_restrictions': fields.function(_get_oc_coordo_restrictions, method=True, type='many2many', relation='msf.instance', string='Project Restrictions', multi='uf_restrictions'),
        'oc_coordo_restrictions': fields.function(_get_oc_coordo_restrictions, method=True, type='many2many', relation='msf.instance', string='Mission Restrictions', multi='uf_restrictions'),
        'msl_project_ids': fields.many2many('unifield.instance', 'product_msl_rel', 'product_id', 'unifield_instance_id', 'MSL List', readonly=1, order_by='instance_name', sql_rel_domain="product_msl_rel.creation_date is not null"),
        'restrictions_txt': fields.function(_get_restrictions_txt, method=True, type='text', string='Restrictions'),

        'mml_status': fields.function(tools.misc._get_std_mml_status, method=True, type='selection', selection=[('T', 'Yes'), ('F', 'No'), ('na', '')], string='MML', multi='mml'),
        'msl_status': fields.function(tools.misc._get_std_mml_status, method=True, type='selection', selection=[('T', 'Yes'), ('F', 'No'), ('na', '')], string='MSL', multi='mml'),


        'in_mml_instance': fields.function(tools.misc.get_fake, method=True, type='many2one', relation='msf.instance', string='MML Valid for instance', domain=[('state', '=', 'active'), ('level', '!=', 'section')]),
        'mml_restricted_instance': fields.function(tools.misc.get_fake, method=True, type='many2one', relation='msf.instance', string='MML Restricted to instance', domain=[('state', '=', 'active'), ('level', '!=', 'section')]),
        'in_msl_instance': fields.function(_get_valid_msl_instance, method=True, type='many2many', relation='unifield.instance', domain=[('uf_active', '=', True)], string='MSL Valid for instance'),

        'incompatible_oc_default_values': fields.function(tools.misc.get_fake, method=True, type='boolean', string='Incompatible OC default', fnct_search=_search_incompatible_oc_default_values),
    }


    def need_to_push(self, cr, uid, ids, touched_fields=None, field='sync_date', empty_ids=False, context=None):
        if touched_fields != ['active', 'local_from_hq', 'local_activation_from_merge', 'id']:
            return super(product_attributes, self).need_to_push(cr, uid, ids, touched_fields=touched_fields, field=field, empty_ids=empty_ids, context=context)

        if not empty_ids and not ids:
            return ids

        cr.execute("""
            SELECT id  FROM product_product
            WHERE
                ( active_sync_change_date IS NULL AND active_change_date IS NOT NULL ) OR active_change_date > active_sync_change_date
        """)
        return [row[0] for row in cr.fetchall()]


    def _get_default_sensitive_item(self, cr, uid, context=None):
        """
        Return the ID of the product.heat_sensitive item with 'No' value.
        :param cr: Cursor to the datase
        :param uid: ID of the res.users that calls the method
        :param context: Context of the call
        :return: The ID of the product.heat_sensitive item with 'No' value.
        """
        return self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'heat_no')[1]

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        res = super(product_attributes, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        if 'heat_sensitive_item' in fields or not fields:
            res['heat_sensitive_item'] = self._get_default_sensitive_item(cr, uid, context=context)

        return res

    _defaults = {
        'closed_article': 'no',
        'duplicate_ok': True,
        'perishable': False,
        'batch_management': False,
        'short_shelf_life': 'False',
        'narcotic': False,
        'composed_kit': False,
        'dangerous_goods': 'False',
        'controlled_substance': False,
        'restricted_country': False,
        'sterilized': 'no',
        'single_use': 'no',
        'standard_ok': 'non_standard',
        'currency_id': lambda obj, cr, uid, c: obj.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id,
        'field_currency_id': lambda obj, cr, uid, c: obj.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id,
        'vat_ok': lambda obj, cr, uid, c: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
        'oc_subscription': False,
        'mml_status': 'na',
        'msl_status': 'na',
    }

    def _check_uom_category(self, cr, uid, ids, context=None):
        '''
        Check the consistency of UoM category on product form
        '''
        move_obj = self.pool.get('stock.move')
        for product in self.browse(cr, uid, ids, context=context):
            uom_categ_id = product.uom_id.category_id.id
            uom_categ_name = product.uom_id.category_id.name
            move_ids = move_obj.search(cr, uid, [('product_id', '=', product.id)], context=context)
            if move_ids:
                uom_categ_id = move_obj.browse(cr, uid, move_ids[0], context=context).product_uom.category_id.id
                uom_categ_name = move_obj.browse(cr, uid, move_ids[0], context=context).product_uom.category_id.name

            if uom_categ_id != product.uom_id.category_id.id:
                raise osv.except_osv(_('Error'), _('There are some stock moves with this product on the system. So you should keep the same UoM category than these stock moves. UoM category used in stock moves : %s') % uom_categ_name)

        return True

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        Add a filter if the 'available_for_restriction' attribute is passed on context
        '''
        if context is None:
            context = {}

        res = super(product_attributes, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)

        if view_type == 'search' and context.get('display_batch_attr'):
            root = etree.fromstring(res['arch'])
            for field in root.xpath('//group[@name="batch_attr"]'):
                field.set('invisible', '0')
            res['arch'] = etree.tostring(root, encoding='unicode')

        if view_type == 'search' and context.get('display_active_filter'):
            root = etree.fromstring(res['arch'])
            for field in root.xpath('//group[@name="display_active_filter"]'):
                field.set('invisible', '0')
            res['arch'] = etree.tostring(root, encoding='unicode')

        if view_type == 'tree' and context.get('display_old_code'):
            root = etree.fromstring(res['arch'])
            for field in root.xpath('//field[@name="old_code"]'):
                field.set('invisible', '0')
            res['arch'] = etree.tostring(root, encoding='unicode')

        if view_type in ('tree', 'form', 'search') and self.pool.get('res.company')._get_instance_level(cr, uid) == 'section':
            root = etree.fromstring(res['arch'])
            found = False

            field_node = 'field'
            if view_type == 'search':
                field_node = 'group'
            for field in root.xpath('//%s[@name="golden_status"]' % field_node):
                field.set('invisible', '0')
                found = True
            if found:
                res['arch'] = etree.tostring(root, encoding='unicode')

        if view_type == 'form':
            esc_line = self.pool.get('unifield.setup.configuration').get_config(cr, uid, 'esc_line')
            if esc_line or uid == 1:
                root = etree.fromstring(res['arch'])
                if uid == 1:
                    for field in root.xpath('//button[@name="debug_ud"]'):
                        field.set('invisible', '0')
                if esc_line:
                    for field in root.xpath('//field[@name="finance_price"]|//field[@name="finance_price_currency_id"]'):
                        field.set('invisible', '0')
                res['arch'] = etree.tostring(root, encoding='unicode')

        if view_type == 'search' and context.get('available_for_restriction'):
            context.update({'search_default_not_restricted': 1})
            root = etree.fromstring(res['arch'])
            # xpath of fields to be modified
            xpath = '//filter[@name="service_with_reception"]'
            fields = root.xpath(xpath)

            if not fields:
                return res

            parent_node = fields[0].getparent()
            new_separator = """<separator orientation="vertical" />"""
            sep_form = etree.fromstring(new_separator)
            arg = context.get('available_for_restriction')
            if isinstance(arg, str):
                arg = '\'%s\'' % arg
            if 'add_multiple_lines' in context:
                # UFTP-15: parse 'available_for_restriction'
                # to implement it directly in product 'not_restricted' filter
                filter_domain = self._src_available_for_restriction(cr, uid,
                                                                    self, 'available_for_restriction',
                                                                    [('available_for_restriction','=', arg)],
                                                                    context=context)
            else:
                filter_domain = "[('available_for_restriction','=',%s)]" % arg
            new_filter = """<filter string="%s" name="not_restricted" icon="terp-accessories-archiver-minus" domain="%s" />""" % (_('Only permitted'), filter_domain)
            #generate new xml form$
            new_form = etree.fromstring(new_filter)
            # instert new form just after state index position
            state_index = parent_node.index(fields[0])
            parent_node.insert(state_index+1, new_form)
            parent_node.insert(state_index+1, sep_form)
            # generate xml back to string
            res['arch'] = etree.tostring(root, encoding='unicode')

        return res

    def _test_restriction_error(self, cr, uid, ids, vals=None, context=None):
        '''
        Builds and returns an error message according to the constraints
        '''
        if isinstance(ids, int):
            ids = [ids]

        if vals is None:
            vals = {}

        if context is None:
            context = {}

        if context.get('cancel_only'):
            return False, ''

        error = False
        error_msg = ''
        constraints = []
        partner_type = False
        sale_obj = vals.get('obj_type') == 'sale.order'

        # Compute the constraint if a partner is passed in vals
        if vals.get('partner_id'):
            partner_obj = self.pool.get('res.partner')
            partner_type = partner_obj.browse(cr, uid, vals.get('partner_id'), context=context).partner_type
            if partner_type == 'external':
                constraints.append('external')
            elif partner_type == 'esc':
                constraints.append('esc')
            elif partner_type in ('internal', 'intermission', 'section'):
                constraints.append('internal')

        # Compute the constraint if a location is passed in vals
        if vals.get('location_id'):
            location = self.pool.get('stock.location').browse(cr, uid, vals.get('location_id'), context=context)
            is_scrap_loc = location.destruction_location or location.quarantine_location
            if location.usage != 'inventory' and not is_scrap_loc:
                constraints.append('storage')

        # Compute the constraint if a destination location is passed in vals
        if vals.get('location_dest_id'):
            dest_location = self.pool.get('stock.location').browse(cr, uid, vals.get('location_dest_id'), context=context)
            if not dest_location.destruction_location and not dest_location.quarantine_location:
                if vals.get('move') and vals['move'].sale_line_id and not vals['move'].sale_line_id.order_id.procurement_request:
                    if (vals['move'].picking_id.shipment_id and vals['move'].picking_id.shipment_id.partner_id.partner_type != 'internal') or \
                            vals['move'].picking_id.partner_id.partner_type != 'internal':
                        constraints.append('cant_use')
                elif vals.get('move') and vals['move'].picking_id.type == 'internal' and vals['move'].picking_id.previous_chained_pick_id and vals['move'].picking_id.previous_chained_pick_id.partner_id.partner_type == 'internal':
                    constraints.append('from_internal_in')
                else:
                    constraints.append('cant_use')
            else:
                constraints.append('to_quarantine')

        # Compute constraints if constraints is passed in vals
        if vals.get('constraints'):
            if isinstance(vals.get('constraints'), list):
                constraints.extend(vals.get('constraints'))
            elif isinstance(vals.get('constraints'), str):
                constraints.append(vals.get('constraints'))

        for product in self.browse(cr, uid, ids, context=context):
            msg = ''
            st_cond = True

            if product.state.code == 'forbidden':
                if sale_obj and partner_type == 'internal':
                    continue
                if 'to_quarantine' in constraints or 'from_internal_in' in constraints:
                    continue
                if vals.get('obj_type') == 'in' and vals.get('partner_type') == 'internal':
                    continue
            if product.no_external and product.no_esc and product.no_internal and 'picking' in constraints:
                error = True
                msg = _('be exchanged')
                st_cond = product.state.no_external or product.state.no_esc or product.state.no_internal
            elif product.no_external and 'external' in constraints and \
                    (not sale_obj or (sale_obj and product.state and product.state.code != 'phase_out') or
                     (sale_obj and vals.get('sourcing_not_donation') and product.state and product.state.code == 'phase_out')):
                error = True
                msg = _('be %s externally') % (sale_obj and _('shipped') or _('purchased'))
                st_cond = product.state.no_external
            elif product.no_esc and 'esc' in constraints:
                error = True
                msg = _('be %s ESC') % (sale_obj and _('shipped to') or _('purchased at'))
                st_cond = product.state.no_esc
            elif product.no_internal and 'internal' in constraints:
                error = True
                msg = _('be supplied/exchanged internally')
                st_cond = product.state.no_internal
            elif product.no_consumption and 'consumption' in constraints:
                error = True
                msg = _('be consumed internally')
                st_cond = product.state.no_consumption
            elif product.no_storage and 'storage' in constraints:
                error = True
                msg = _('be stored anymore')
                st_cond = product.state.no_storage
            elif product.state.code == 'forbidden' and 'cant_use' in constraints:
                error = True
                msg = _('be moved')
                st_cond = product.state.no_consumption

            if error:
                # Build the error message
                st_type = st_cond and _('status') or _('product creator')
                st_name = st_cond and product.state.name or product.international_status.name

            if not error and vals.get('obj_type') == 'in' and not product.active:
                error = True
                st_type = _('status')
                st_name = _('Inactive')
                msg = _('be moved')

            if error:
                error_msg = ''
                if vals.get('move'):
                    error_msg = _('%s line %s: ') % (vals['move'].picking_id.name, vals['move'].line_number)
                error_msg += _('The product [%s] has the %s \'%s\' and consequently can\'t %s') \
                    % (product.default_code, st_type, st_name, msg)
        if context.get('noraise'):
            error = False

        return error, error_msg

    def _get_restriction_error(self, cr, uid, ids, vals=None, context=None):
        '''
        Raise an error if the product is not compatible with the order
        '''
        res, error_msg = self._test_restriction_error(cr, uid, ids, vals=vals, context=context)

        if res:
            raise osv.except_osv(_('Error'), error_msg)


    def change_soq_quantity(self, cr, uid, ids, soq, uom_id, context=None):
        """
        When the SoQ quantity is changed, check if the new quantity is consistent
        with rounding value of the product UoM
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of product.product on which the SoQ quantity is changed
        :param soq: New value for SoQ Quantity
        :param uom_id: ID of the product.uom linked to the product
        :param context: Context of the call
        :return: A dictionary that contains a warning message and the SoQ quantity
                 rounded with the UoM rounding value
        """
        uom_obj = self.pool.get('product.uom')

        if context is None:
            context = {}

        if not soq or not uom_id:
            return {}

        res = {}
        rd_soq = uom_obj._compute_qty(cr, uid, uom_id, soq, uom_id)
        if rd_soq != soq:
            res['warning'] = {
                'title': _('Warning'),
                'message': _('''SoQ quantity value (%s) is not consistent with UoM rounding value.
                The SoQ quantity has been automatically rounded to consistent value (%s)''') % (soq, rd_soq),
            }

        res['value'] = {'soq_quantity': rd_soq}
        return res

    def _on_change_restriction_error(self, cr, uid, ids, *args, **kwargs):
        '''
        Update the message on on_change of product
        '''
        field_name = kwargs.get('field_name')
        values = kwargs.get('values')
        vals = kwargs.get('vals')
        context = kwargs.get('context')

        res, error_msg = self._test_restriction_error(cr, uid, ids, vals=vals, context=context)

        result = values.copy()

        if res:
            result.setdefault('value', {})[field_name] = False
            result.setdefault('warning', {})['title'] = _('Warning')
            result.setdefault('warning', {})['message'] = error_msg

        return result, res

    def onchange_heat(self, cr, uid, ids, heat, context=None):
        """
        Set the value for the field 'show_cold_chain' according to
        selection Temperature sensitive value.
        If the returned value is True, the field Cold Chain will be displayed
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of product.product on which the field is computed
        :param heat: ID of the selected product.heat_sensitive
        :param context: Context of the call
        :return: True of False in the 'show_cold_chain' field
        """
        heat2_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'heat_no')[1]
        heat3_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'heat_no_know')[1]

        sensitive = heat and heat not in [heat2_id, heat3_id]

        values = {
            'show_cold_chain': sensitive
        }
        if not sensitive:
            values['cold_chain'] = False
        return {
            'value': values
        }

    def _check_gmdn_code(self, cr, uid, ids, context=None):
        int_pattern = re.compile(r'^\d*$')
        for product in self.browse(cr, uid, ids, fields_to_fetch=['gmdn_code'], context=context):
            if product.gmdn_code and not int_pattern.match(product.gmdn_code):
                return False
        return True

    def create(self, cr, uid, vals, context=None):
        """
        Ignore the leading whitespaces on the product default_code
        At product.product creation, create a standard.price.track.changes
        record with the standard price as new value and None as old value.
        :param cr: Cursor to the database
        :param uid: ID of the user that creates the record
        :param vals: Values of the new product.product to create
        :param context: Context of the call
        :return: The ID of the new product.template record
        """
        sptc_obj = self.pool.get('standard.price.track.changes')
        trans_obj = self.pool.get('ir.translation')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        self.clean_standard(cr, uid, vals, context)
        if context.get('sync_update_execution') and vals.get('local_from_hq'):
            vals['active'] = False


        def update_existing_translations(model, res_id, xmlid):
            # If we are in the creation of product by sync. engine, attach the already existing translations to this product
            if context.get('sync_update_execution'):
                trans_ids = trans_obj.search(cr, uid, [
                    ('res_id', '=', 0),
                    ('xml_id', '=', xmlid),
                    ('type', '=', 'model'),
                    ('name', '=like', '%s,%%' % model),
                ], context=context)
                if trans_ids:
                    trans_obj.write(cr, uid, trans_ids, {
                        'res_id': res_id,
                    }, context=context)

        if 'batch_management' in vals and 'perishable' in vals and context.get('from_import_menu'):
            if vals['batch_management'] and not vals['perishable']:
                raise osv.except_osv(
                    _('Error'),
                    _('Batch and Expiry attributes do not conform')
                )
        self.clean_bn_ed(cr, uid, vals, context)

        intstat_code = False
        if vals.get('international_status'):
            intstat_code = self.pool.get('product.international.status').browse(cr, uid, vals['international_status'],
                                                                                fields_to_fetch=['code'], context=context).code
        if 'default_code' in vals:
            if not context.get('sync_update_execution'):
                vals['default_code'] = vals['default_code'].strip()
                if ' ' in vals['default_code']:
                    raise osv.except_osv(
                        _('Error'),
                        _('White spaces are not allowed in product code'),
                    )
                if any(char.islower() for char in vals['default_code']):
                    vals['default_code'] = vals['default_code'].upper()
                if intstat_code and intstat_code == 'local' and 'Z' not in vals['default_code']:
                    raise osv.except_osv(
                        _('Error'),
                        _("Product Code %s must include a 'Z' character") % (vals['default_code'],),
                    )

        if vals.get('xmlid_code'):
            if not context.get('sync_update_execution') and ' ' in vals['xmlid_code']:
                raise osv.except_osv(
                    _('Error'),
                    _('White spaces are not allowed in XML ID code'),
                )
            if not context.get('sync_update_execution') and any(char.islower() for char in vals['xmlid_code']):
                vals['xmlid_code'] = vals['xmlid_code'].upper()

        if 'narcotic' in vals or 'controlled_substance' in vals:
            if vals.get('narcotic') == True or tools.ustr(vals.get('controlled_substance', '')) == 'True':
                vals['controlled_substance'] = 'True'

        if 'heat_sensitive_item' in vals:
            if not vals.get('heat_sensitive_item'):
                heat2_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'heat_no')[1]
                vals['heat_sensitive_item'] = heat2_id
            vals.update(self.onchange_heat(cr, uid, False, vals['heat_sensitive_item'], context=context).get('value', {}))

        if intstat_code:
            if 'oc_subscription' not in vals:
                vals['oc_subscription'] = intstat_code == 'unidata'

        if intstat_code == 'unidata':
            if not context.get('sync_update_execution'):
                if 'state_ud' in vals:
                    if self.mapping_ud.get(vals['state_ud']):
                        vals['state'] = \
                            self.pool.get('product.status').search(cr, uid, [('code', '=', self.mapping_ud.get(vals['state_ud']))],
                                                                   context=context)[0]
                        if vals['state_ud'] == 'archived':
                            vals['active'] = False
                if not vals['oc_subscription']:
                    vals['active'] = False
                elif vals.get('state_ud') != 'archived':
                    vals['active'] = True

        if 'cost_method' in vals and vals['cost_method'] != 'average':
            vals['cost_method'] = 'average'

        for f in ['sterilized', 'closed_article', 'single_use']:
            if f in vals and not vals.get(f):
                vals[f] = 'no'

        vals.update({
            'uf_create_date': vals.get('uf_create_date') or datetime.now(),
            'uf_write_date': vals.get('uf_write_date') or datetime.now(),
        })

        self.convert_price(cr, uid, vals, context)

        if not context.get('sync_update_execution') and vals.get('active') is False:
            # trigger sync update on state only if created as inactive (as active=True is the default)
            vals['active_change_date'] = datetime.now()

        res = super(product_attributes, self).create(cr, uid, vals, context=context)

        if context.get('sync_update_execution'):
            # Update existing translations for product.product and product.template
            product_tmpl_id = self.read(cr, uid, [res], ['product_tmpl_id'])[0]['product_tmpl_id'][0]
            prd_data_ids = data_obj.search(cr, uid, [
                ('res_id', '=', res),
                ('model', '=', 'product.product'),
            ], context=context)
            for prd_data in data_obj.browse(cr, uid, prd_data_ids, context=context):
                update_existing_translations('product.product', res, prd_data.name)
                update_existing_translations('product.template', product_tmpl_id, prd_data.name)
            # US-12147: Update existing translations before the ir_model_data for the product has been fully created
            if not prd_data_ids and context.get('product_sdref'):
                update_existing_translations('product.product', res, context['product_sdref'])
                update_existing_translations('product.template', product_tmpl_id, context['product_sdref'])

        sptc_obj.track_change(cr, uid, res, _('Product creation'), vals,
                              context=context)

        return res

    def convert_price(self, cr, uid, vals, context=None):
        """ on OCG_HQ UniDate creates products with EUR currency: convert prices to CHF """
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        converted = False

        if context is None:
            context = {}

        if not context.get('sync_update_execution') and company and company.instance_id and company.instance_id.instance == 'OCG_HQ':
            unidata_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_6')[1]
            if vals.get('international_status') == unidata_id and (vals.get('currency_id') or vals.get('field_currency_id')):
                curr_obj = self.pool.get('res.currency')
                if vals.get('standard_price') and vals.get('currency_id') != company.currency_id.id:
                    if vals['standard_price'] != 1:
                        vals['standard_price'] = round(curr_obj.compute(cr, 1, vals['currency_id'], company.currency_id.id, vals['standard_price'], round=False, context=context), 5)
                    vals['currency_id'] = company.currency_id.id
                    converted = True
                if vals.get('field_currency_id') != company.currency_id.id:
                    vals['field_currency_id'] = company.currency_id.id
                    converted = True

        return converted

    def fields_get(self, cr, uid, fields=None, context=None, with_uom_rounding=False):
        # to allow True / False in standard_ok for old sync updates

        fg = super(product_attributes, self).fields_get(cr, uid, fields=fields, context=context, with_uom_rounding=with_uom_rounding)
        if context and context.get('sync_update_execution') and  fg.get('standard_ok', {}).get('selection'):
            selection = fg['standard_ok']['selection'][:]
            selection += [('False', 'Non Standard (deprecated)'), ('True', 'Standard (deprecated)')]
            fg['standard_ok']['selection'] = selection
        return fg

    def clean_bn_ed(self, cr, uid, vals, context):
        if vals and vals.get('batch_management'):
            vals['perishable'] = True

    def clean_standard(self, cr, uid, vals, context):
        if vals and 'standard_ok' in vals:
            if vals['standard_ok'] == 'True':
                vals['standard_ok'] = 'standard'
            elif vals['standard_ok'] == 'False':
                vals['standard_ok'] = 'non_standard'

        if vals and 'state' in vals:
            # here to manage old sync updates
            st_obj = self.pool.get('product.status')
            if vals['state']:
                st = st_obj.browse(cr, uid, vals['state'], fields_to_fetch=['mapped_to'])
                if st and st.mapped_to:
                    vals['state'] = st.mapped_to.id
            else:
                vals['state'] = st_obj.search(cr, uid, [('code', '=', 'valid')], context=context)[0]

    def hq_cron_deactivate_ud_products(self, cr, uid, context=None):
        if self.pool.get('res.company')._get_instance_level(cr, uid) != 'section':
            return False

        ids = []
        products_used = set()

        ud_prod_ids = self.search(cr, uid, ['&', ('international_status', '=', 'UniData'), '|', '|', ('oc_subscription', '=', False), ('state_ud', '=', 'archived'), ('state', '=', 'Phase Out')], context=context)
        if ud_prod_ids:
            products_used = self.unidata_products_used(cr, uid, ud_prod_ids)
            ids = list(set(ud_prod_ids) - products_used)
            if ids:
                self.write(cr, uid, ids, {'active': False}, context=context)

        logging.getLogger('UD deactivation').info('%d products deactivated, %d kept as active' % (len(ids), len(products_used)))

        return True

    def unidata_products_used(self, cr, uid, ids):
        if not ids:
            return set()

        cr.execute('''
                    select
                        l.product_id
                    from
                        stock_mission_report r, msf_instance i, stock_mission_report_line l
                    where
                        i.id = r.instance_id and
                        i.state = 'active' and
                        l.mission_report_id = r.id and
                        l.product_id in %s and
                        r.full_view = 'f' and
                        ( l.internal_qty > 0 or l.in_pipe_qty > 0)
                    group by l.product_id
                ''' , (tuple(ids), ))
        ud_unable_to_inactive = set([x[0] for x in cr.fetchall()])

        cr.execute('select name from product_list_line where name in %s', (tuple(ids), ))
        ud_unable_to_inactive = ud_unable_to_inactive.union([x[0] for x in cr.fetchall()])
        return ud_unable_to_inactive

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        prod_status_obj = self.pool.get('product.status')
        int_stat_obj = self.pool.get('product.international.status')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        self.clean_standard(cr, uid, vals, context)
        self.clean_bn_ed(cr, uid, vals, context)

        if vals.get('active'):
            non_kept_ids = self.search(cr, uid, [('id', 'in', ids), ('active', 'in', ['t', 'f']), ('kept_product_id', '!=', False)], context=context)
            if non_kept_ids:
                raise osv.except_osv(
                    _('Error'),
                    _("Merged products cannot be activated: %s") % (', '.join([x['default_code'] for x in self.read(cr, uid, non_kept_ids, ['default_code'], context=context)]))
                )

        if 'batch_management' in vals:
            vals['track_production'] = vals['batch_management']
            vals['track_incoming'] = vals['batch_management']
            vals['track_outgoing'] = vals['batch_management']
            if vals['batch_management']:
                vals['perishable'] = True

        intstat_code = False
        unidata_product = False
        if 'international_status' in vals:
            intstat_code = ''
            if vals['international_status']:
                intstat_id = vals['international_status']
                if isinstance(intstat_id, int):
                    intstat_id = [intstat_id]
                intstat_code = int_stat_obj.read(cr, uid, intstat_id, ['code'], context=context)[0]['code']
                unidata_product = intstat_code == 'unidata'

        # Prevent Product Type change during sync if there is stock in the Stock Mission Report
        # or at Project Level if there is stock available
        if 'type' in vals and context.get('sync_update_execution'):
            ftf = ['default_code', 'type', 'international_status', 'company_id', 'qty_available']
            prod = self.browse(cr, uid, ids[0], fields_to_fetch=ftf, context=context)
            if vals['type'] != prod.type and prod.international_status.code in ['local', 'itc', 'esc', 'hq', 'unidata']:
                if self.check_exist_srml_stock(cr, uid, ids[0], context=context):
                    raise osv.except_osv(
                        _('Error'),
                        _('The Product Type of the %s Product %s can not be modified if it has stock in the Stock Mission Report')
                        % (prod.international_status.name, prod.default_code)
                    )
                if prod.company_id.instance_id.level == 'project' and prod.qty_available > 0:
                    raise osv.except_osv(
                        _('Error'), _('The Product Type of the %s Product %s can not be modified if it has stock available')
                        % (prod.international_status.name, prod.default_code)
                    )

        if 'default_code' in vals:
            if vals['default_code'] == 'XXX':
                vals['duplicate_ok'] = True
            else:
                vals['duplicate_ok'] = False
            if not context.get('sync_update_execution'):
                vals['default_code'] = vals['default_code'].strip()
                if ' ' in vals['default_code']:
                    # Check if the old code was 'XXX'
                    # in case there is, it mean it is a duplicate and spaces
                    # are not allowed.
                    if any(prd['default_code'] == 'XXX' for prd in self.read(cr, uid, ids, ['default_code'], context=context)):
                        raise osv.except_osv(
                            _('Error'),
                            _('White spaces are not allowed in product code'),
                        )
                if any(char.islower() for char in vals['default_code']):
                    vals['default_code'] = vals['default_code'].upper()
                # Look at current international status if none is given
                prod_instat_code = intstat_code
                if not prod_instat_code:
                    prod_instat_code = self.browse(cr, uid, ids[0], fields_to_fetch=['international_status'], context=context).international_status.code
                if prod_instat_code and prod_instat_code == 'local' and 'Z' not in vals['default_code']:
                    raise osv.except_osv(
                        _('Error'),
                        _("Product Code %s must include a 'Z' character") % (vals['default_code'],),
                    )

        if context.get('sync_update_execution') and vals.get('local_from_hq'):
            if vals.get('active'):
                del(vals['active'])

        if not intstat_code:
            unidata_product = self.search_exist(cr, uid, [('id', 'in', ids), ('international_status', '=', 'UniData'), ('active', 'in', ['t', 'f'])], context=context)

        check_reactivate = False
        reactivated_by_oc_subscription = False
        prod_state = ''

        if unidata_product and context.get('sync_update_execution'):
            if vals.get('level_source') == 'section':
                # remove fields managed by coordo
                for field in self.merged_fields_to_keep:
                    if field in vals:
                        del(vals[field])



        if unidata_product and not context.get('sync_update_execution'):
            if 'international_status' not in vals and 'oc_subscription' in vals:
                if self.search_exist(cr, uid, [('id', 'in', ids), ('international_status', '!=', 'UniData'), ('active', 'in', ['t', 'f'])], context=context):
                    raise osv.except_osv(_('Warning'), _("You can write the oc_subscription field on multiple products only if all products are UniData !"))

            if 'oc_subscription' in vals and not vals['oc_subscription']:
                # oc_subscription=False must preval on vals['state_ud']
                prod_state = 'archived'
            elif 'state_ud' in vals and self.mapping_ud.get(vals['state_ud']):
                prod_state = self.mapping_ud[vals['state_ud']]

            if prod_state:
                vals['state'] = prod_status_obj.search(cr, uid, [('code', '=', prod_state)], context=context)[0]

            if prod_state == 'archived':
                vals['active'] = False
            elif prod_state and 'oc_subscription' not in vals:
                # this will compute active
                check_reactivate = True
            elif vals.get('oc_subscription') and vals.get('golden_status', 'Golden') == 'Golden':
                vals['active'] = True
                if 'state' not in vals:
                    # only oc_subscription = True sent but no info on state / state_ud, we must recompute the mapping
                    reactivated_by_oc_subscription = True
        if not prod_state and 'state' in vals:
            if vals['state']:
                state_id = vals['state']
                if isinstance(state_id, int):
                    state_id = [state_id]
                prod_state = prod_status_obj.read(cr, uid, state_id, ['code'], context=context)[0]['code']


        product_uom_categ = []
        if 'uom_id' in vals or 'uom_po_id' in vals:
            if isinstance(ids, int):
                to_browse = [ids]
            else:
                to_browse = ids
            for product in self.browse(cr, uid, to_browse, fields_to_fetch=['uom_id'], context=context):
                category_id = product.uom_id.category_id.id
                if category_id not in product_uom_categ:
                    product_uom_categ.append(category_id)
        if 'heat_sensitive_item' in vals:
            if not vals.get('heat_sensitive_item'):
                heat2_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'heat_no')[1]
                vals['heat_sensitive_item'] = heat2_id
            vals.update(self.onchange_heat(cr, uid, ids, vals['heat_sensitive_item'], context=context).get('value', {}))

        if context.get('sync_update_execution') and not context.get('bypass_sync_update', False):
            if vals.get('active', None) is False:
                deactivate_result =  self.deactivate_product(cr, uid, ids, context=context, try_only=True)
                if not deactivate_result['ok']:
                    prod_code = self.read(cr, uid, ids[0], ['default_code'], context=context)
                    error_msg = []
                    wiz_error = self.pool.get('product.deactivation.error').browse(cr, uid, deactivate_result['error'], context=context)
                    if wiz_error.stock_exist:
                        error_msg.append('Stock exists (internal locations)')

                    doc_errors = []
                    for error in wiz_error.error_lines:
                        doc_errors.append("%s : %s" % (error.type or '', error.doc_ref or ''))

                    if doc_errors:
                        error_msg.append('Product is contained in opened documents :\n - %s'  % ' \n - '.join(doc_errors))
                    raise osv.except_osv('Warning', 'Product %s cannot be deactivated: \n * %s ' % (prod_code['default_code'], "\n * ".join(error_msg)))

                elif unidata_product:
                    # unidata product inactive must also be archived: 1st set as phase out by the update one
                    vals['state'] = prod_status_obj.search(cr, uid, [('code', '=', 'archived')], context=context)[0]

            if prod_state == 'archived' and unidata_product:
                # received archived: set as phase out, when the "active" update will be processed, it will set archive if inactivation is allowed
                # this must be done only if the product is not already inactive (US-7883)
                if vals.get('active') or self.search(cr, uid, [('id', 'in', ids), ('active', '=', True)]):
                    vals['state'] = prod_status_obj.search(cr, uid, [('code', '=', 'phase_out')], context=context)[0]

        ud_unable_to_inactive = []
        if 'active' in vals and not vals['active'] and not context.get('sync_update_execution') and unidata_product and not vals.get('kept_product_id'):
            ud_unable_to_inactive = self.unidata_products_used(cr, uid, ids)
            if not prod_state:
                vals['state'] = prod_status_obj.search(cr, uid, [('code', '=', 'archived')], context=context)[0]
            if ud_unable_to_inactive:
                ids = list(set(ids) - ud_unable_to_inactive)
                ud_unable_to_inactive = list(ud_unable_to_inactive)

        if ids and 'active' in vals and not vals.get('kept_product_id'):
            # to manage sync update generation on active field
            fields_to_update = ['active_change_date=%(now)s']
            if context.get('sync_update_execution') and not vals.get('from_hq_merge'):
                fields_to_update += ['active_sync_change_date=%(now)s']
            elif vals.get('from_hq_merge'):
                del(vals['from_hq_merge'])
            cr.execute('update product_product set '+', '.join(fields_to_update)+' where id in %(ids)s and active != %(active)s', {'now': fields.datetime.now(), 'ids': tuple(ids), 'active': vals['active']}) # not_a_user_entry

        if ids and unidata_product and not context.get('sync_update_execution') and vals.get('standard_ok') in ('standard', 'non_standard'):
            # active update must be trigger if product is active and was NSL (because created as inactive on lower instance)
            cr.execute("update product_product set active_change_date=%(now)s where id in %(ids)s and active = 't' and standard_ok='non_standard_local'", {'now': fields.datetime.now(), 'ids': tuple(ids)})

        if 'narcotic' in vals or 'controlled_substance' in vals:
            if vals.get('narcotic') == True or tools.ustr(vals.get('controlled_substance', '')) == 'True':
                vals['controlled_substance'] = 'True'

        if 'cost_method' in vals and vals['cost_method'] != 'average':
            vals['cost_method'] = 'average'

        for f in ['sterilized', 'closed_article', 'single_use']:
            if f in vals and not vals.get(f):
                vals[f] = 'no'

        vals['uf_write_date'] = vals.get('uf_write_date', datetime.now())

        self.convert_price(cr, uid, vals, context)
        if context.get('sync_update_execution') and 'batch_management' in vals and 'perishable' in vals:
            init_sync = not bool(self.pool.get('res.users').get_browse_user_instance(cr, uid))
            if not init_sync:
                if vals.get('batch_management'):
                    self.set_as_bned(cr, uid, ids, context=context)
                elif vals.get('perishable'):
                    self.set_as_edonly(cr, uid, ids, context=context)
                else:
                    self.set_as_nobn_noed(cr, uid, ids, context=context)

        res = super(product_attributes, self).write(cr, uid, ids, vals, context=context)
        if ud_unable_to_inactive:
            vals['active'] = True
            vals['state'] = prod_status_obj.search(cr, uid, [('code', '=', 'phase_out')], context=context)[0]
            super(product_attributes, self).write(cr, uid, ud_unable_to_inactive, vals, context=context)

        if product_uom_categ:
            uom_categ = 'uom_id' in vals and vals['uom_id'] and self.pool.get('product.uom').browse(cr, uid, vals['uom_id'], context=context).category_id.id or False
            uos_categ = 'uom_po_id' in vals and vals['uom_po_id'] and self.pool.get('product.uom').browse(cr, uid, vals['uom_po_id'], context=context).category_id.id or False

            if (uom_categ and uom_categ not in product_uom_categ) or (uos_categ and uos_categ not in product_uom_categ):
                raise osv.except_osv(_('Error'), _('You cannot choose an UoM which is not in the same UoM category of default UoM'))

        if ud_unable_to_inactive:
            ids = ids + ud_unable_to_inactive

        if reactivated_by_oc_subscription:
            self.set_state_from_state_ud(cr, uid, ids, context=context)

        if check_reactivate:
            # ud set only state_ud != archived, check if product must be reactivated
            set_as_active = self.search(cr, uid, [('active', '=', False), ('oc_subscription', '=', True), ('id', 'in', ids)], context=context)
            if set_as_active:
                self.write(cr, uid, set_as_active, {'active': True}, context=context)
        return res

    def set_state_from_state_ud(self, cr, uid, ids, context=None):
        for grp in self.read_group(cr, uid, [('id', 'in', ids)], fields=['state_ud'], groupby=['state_ud'], context=context):
            ids_to_w = self.search(cr, uid, grp['__domain'], context=context)
            if ids_to_w:
                self.write(cr, uid, ids_to_w, {'state_ud': grp['state_ud']},  context=context)
        return True

    def reactivate_product(self, cr, uid, ids, context=None):
        '''
        Re-activate product.
        '''
        data_obj = self.pool.get('ir.model.data')

        instance_level = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.level
        hq_status = data_obj.get_object_reference(cr, uid, 'product_attributes', 'int_3')[1]
        itc_status = data_obj.get_object_reference(cr, uid, 'product_attributes', 'int_1')[1]
        esc_status = data_obj.get_object_reference(cr, uid, 'product_attributes', 'int_2')[1]
        local_status = data_obj.get_object_reference(cr, uid, 'product_attributes', 'int_4')[1]
        for product in self.browse(cr, uid, ids, fields_to_fetch=['active', 'default_code', 'name', 'standard_ok', 'oc_subscription', 'international_status', 'state_ud'],context=context):
            vals = {'active': True}
            if product.active:
                raise osv.except_osv(_('Error'), _('The product [%s] %s is already active.') % (product.default_code, product.name))
            if product.standard_ok == 'non_standard_local':
                if not product.oc_subscription:
                    raise osv.except_osv(_('Error'), _('Product activation is not allowed on Non-Standard Local Products which are not OC Subscribed'))
                if instance_level == 'project':
                    raise osv.except_osv(_('Error'), _('%s activation is not allowed at project') % (product.default_code,))
            if (instance_level == 'section' and (product.international_status.id in (hq_status, itc_status, esc_status) or
                                                 (product.oc_subscription and product.state_ud in ('valid', 'outdated', 'discontinued')))) or \
                    (instance_level == 'coordo' and product.international_status.id == local_status):
                vals.update({'state': data_obj.get_object_reference(cr, uid, 'product_attributes', 'status_1')[1]})
            real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
            self.write(cr, real_uid, product.id, vals, context=context)

        return True

    def deactivate_product(self, cr, uid, ids, context=None, try_only=False, ignore_draft=True):
        '''
        De-activate product.
        Check if the product is not used in any document in Unifield
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        location_obj = self.pool.get('stock.location')
        po_line_obj = self.pool.get('purchase.order.line')
        tender_line_obj = self.pool.get('tender.line')
        fo_line_obj = self.pool.get('sale.order.line')
        move_obj = self.pool.get('stock.move')
        kit_obj = self.pool.get('composition.item')
        inv_obj = self.pool.get('stock.inventory.line')
        in_inv_obj = self.pool.get('initial.stock.inventory.line')
        invoice_obj = self.pool.get('account.invoice.line')

        prod_list_line_obj = self.pool.get('product.list.line')
        error_obj = self.pool.get('product.deactivation.error')
        error_line_obj = self.pool.get('product.deactivation.error.line')

        internal_loc = location_obj.search(cr, uid, [('usage', '=', 'internal')], context=context)

        ud_prod = []
        ud_nsl_prod = []
        other_prod = []
        for product in self.browse(cr, uid, ids, fields_to_fetch=['active', 'name', 'default_code', 'international_status', 'standard_ok'], context=context):
            # Raise an error if the product is already inactive
            if not product.active and not context.get('sync_update_execution'):
                raise osv.except_osv(_('Error'), _('The product [%s] %s is already inactive.') % (product.default_code, product.name))

            cr.execute('select distinct(list.id) from product_list list, product_list_line line where line.list_id = list.id and line.name = %s', (product.id,))
            has_product_list = [x[0] for x in cr.fetchall()]
            if context.get('sync_update_execution') and has_product_list:
                prod_list_line_ids = prod_list_line_obj.search(cr, uid, [('name', '=', product.id)], context=context)
                prod_list_line_obj.unlink(cr, uid, prod_list_line_ids, context=context, extra_comment='Product got deactivated')
                has_product_list = []


            states_to_ignore = ['done', 'cancel', 'cancel_r']
            if ignore_draft:
                states_to_ignore.append('draft')

            # Check if the product is in some purchase order lines or request for quotation lines
            cr.execute('''
                select
                    pol.id
                from
                    purchase_order po, purchase_order_line pol
                where
                    po.id = pol.order_id and
                    pol.state not in %s and
                    po.active = 't' and
                    pol.product_id = %s
            ''', (tuple(states_to_ignore), product.id, ))
            has_po_line = [x[0] for x in cr.fetchall()]

            # Check if the product is in some tender lines
            tender_line_domain = [('product_id', '=', product.id), ('line_state', 'not in', ['done', 'cancel'])]
            if ignore_draft:
                tender_line_domain = [
                    ('product_id', '=', product.id),
                    '|', ('line_state', 'not in', ['draft', 'done', 'cancel']),
                    '&', ('tender_id.state', '=', 'comparison'), ('line_state', '=', 'draft')
                ]
            has_tender_line = tender_line_obj.search(cr, uid, tender_line_domain, context=context)

            # Check if the product is in field order lines or in internal request lines
            states_to_ignore = ['done', 'cancel', 'cancel_r']
            if ignore_draft:
                states_to_ignore.append('draft')
            cr.execute('''
                select
                    sol.id
                from
                    sale_order so, sale_order_line sol
                where
                    so.id = sol.order_id and
                    sol.state not in %s and
                    so.active = 't' and
                    sol.product_id = %s
            ''', (tuple(states_to_ignore), product.id, ))
            has_fo_line = [x[0] for x in cr.fetchall()]

            # Check if the product is in stock picking
            # All stock moves in a stock.picking not draft/cancel/done/delivered or all stock moves in a shipment not delivered/done/cancel
            states_to_ignore = ['done', 'delivered', 'cancel']
            if ignore_draft:
                states_to_ignore.append('draft')

            cr.execute('''
                select
                    m.id
                from
                    stock_move m
                    inner join stock_picking p on m.picking_id = p.id
                    left join shipment ship on ship.id = p.shipment_id
                where
                    m.product_id = %s and
                    m.state not in ('done', 'cancel') and
                    ( p.state not in %s or p.shipment_id is not null and ship.state not in ('delivered', 'done', 'cancel') )
            ''', (product.id, tuple(states_to_ignore)))
            has_move_line = [x[0] for x in cr.fetchall()]

            states_to_ignore = ['done', 'cancel']
            if ignore_draft:
                states_to_ignore.append('draft')
            # Check if the product is in a stock inventory


            cr.execute('''
                select
                    l.id
                from
                    stock_inventory_line l, stock_inventory i
                where
                    l.inventory_id = i.id and
                    l.product_id = %s and
                    i.state not in %s
                ''', (product.id, tuple(states_to_ignore)))
            has_inventory_line = [x[0] for x in cr.fetchall()]

            # Check if the product is in an initial stock inventory
            cr.execute('''
                select
                    l.id
                from
                    initial_stock_inventory_line l, initial_stock_inventory i
                where
                    l.inventory_id = i.id and
                    l.product_id = %s and
                    i.state not in %s
                ''', (product.id, tuple(states_to_ignore)))
            has_initial_inv_line = [x[0] for x in cr.fetchall()]

            # Check if the product is in a real kit composition
            cr.execute('''
                select
                    i.id
                from
                    composition_item i, composition_kit k
                where
                    i.item_kit_id = k.id and
                    i.item_product_id = %s and
                    k.composition_type = 'real' and
                    k.state = 'completed'
                ''', (product.id, ))
            has_kit = [x[0] for x in cr.fetchall()]

            has_kit2 = self.pool.get('composition.kit').search(cr, uid, [('composition_product_id', '=', product.id),
                                                                         ('composition_type', '=', 'real'),
                                                                         ('state', '=', 'completed')], context=context)
            has_kit.extend(has_kit2)

            # Check if the product is in an invoice
            cr.execute('''
                select
                    l.id
                from
                    account_invoice_line l, account_invoice i, account_account a
                where
                    l.invoice_id = i.id and
                    i.account_id = a.id and
                    l.product_id = %s and
                    i.state not in ('paid', 'inv_close', 'done', 'proforma', 'proforma2', 'cancel') and
                    ( i.state != 'open' or coalesce(a.reconcile, 'f') != 'f' )
                ''', (product.id, ))
            has_invoice_line = [x[0] for x in cr.fetchall()]

            # Check if the product has stock in internal locations
            has_stock = self.pool.get('stock.mission.report.line.location').search_exists(cr, uid,
                                                                                          [('product_id', '=', product.id), ('location_id', 'in', internal_loc), ('quantity', '>', 0)])

            opened_object = has_kit or has_initial_inv_line or has_inventory_line or has_move_line or has_fo_line or has_tender_line or has_po_line or has_invoice_line or has_product_list
            if not has_stock and not opened_object:
                if product.international_status.code == 'unidata':
                    if product.standard_ok == 'non_standard_local':
                        ud_nsl_prod.append(product.id)
                    else:
                        ud_prod.append(product.id)
                else:
                    other_prod.append(product.id)
            else:
                # Create the error wizard
                wizard_id = error_obj.create(cr, uid, {'product_id': product.id,
                                                       'stock_exist': has_stock and True or False,
                                                       'opened_object': opened_object}, context=context)

                if has_product_list:
                    for prod_list in self.pool.get('product.list').read(cr, uid, has_product_list, ['name'], context=context):
                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': _('Product List'),
                                                        'internal_type': 'product.list',
                                                        'doc_ref': prod_list['name'],
                                                        'doc_id': prod_list['id']}, context=context)

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
                        # Customer Refund
                        if obj.doc_type == 'cr':
                            type_name = 'Customer Refund'
                        # Supplier Refund
                        elif obj.doc_type == 'sr':
                            type_name = 'Supplier Refund'
                        # Debit Note
                        elif obj.doc_type == 'dn':
                            type_name = 'Debit Note'
                        # Donation (in-kind donation)
                        elif obj.doc_type == 'donation':
                            type_name = 'Finance document In-kind Donation'
                        # Intermission voucher out
                        elif obj.doc_type == 'ivo':
                            type_name = 'Intermission Voucher Out'
                        # Intermission voucher in
                        elif obj.doc_type == 'ivi':
                            type_name = 'Intermission Voucher In'
                        # Stock Transfer Voucher
                        elif obj.doc_type == 'stv':
                            type_name = 'Stock Transfer Voucher'
                        # Supplier Invoice
                        elif obj.doc_type == 'si':
                            type_name = 'Supplier Invoice'
                        # Supplier Direct Invoice
                        elif obj.doc_type == 'di':
                            type_name = 'Supplier Direct Invoice'
                        # Stock Transfer Refund
                        elif obj.doc_type == 'str':
                            type_name = 'Stock Transfer Refund'
                        # Intersection Supplier Invoice
                        elif obj.doc_type == 'isi':
                            type_name = 'Intersection Supplier Invoice'
                        # Intersection Supplier Refund
                        elif obj.doc_type == 'isr':
                            type_name = 'Intersection Supplier Refund'

                        error_line_obj.create(cr, uid, {'error_id': wizard_id,
                                                        'type': type_name,
                                                        'internal_type': 'account.invoice',
                                                        'doc_ref': invoice.invoice_id.number or invoice.invoice_id.name or '',
                                                        'doc_id': invoice.invoice_id.id}, context=context)


                if try_only:
                    return {'ok': False, 'error': wizard_id}

                if context.get('sync_update_execution', False):
                    context['bypass_sync_update'] = True
                self.write(cr, uid, product.id, {
                    'active': True,
                }, context=context)

                return {'type': 'ir.actions.act_window',
                        'res_model': 'product.deactivation.error',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_id': wizard_id,
                        'target': 'new',
                        'context': context}

        if try_only:
            return {'ok': True, 'error': False}

        if context.get('sync_update_execution', False):
            context['bypass_sync_update'] = True

        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        if ud_nsl_prod:
            # reactivation of UD NSL prod must bypass UR : active allowed
            if self.pool.get('res.company')._get_instance_level(cr, uid) == 'coordo':
                real_uid = uid
            self.write(cr, real_uid, ud_nsl_prod, {'active': False}, context=context)
        if ud_prod:
            self.write(cr, real_uid, ud_prod, {'active': False}, context=context)
        if other_prod:
            phase_out_id = self.pool.get('product.status').search(cr, uid, [('code', '=', 'phase_out')], context=context)[0]
            self.write(cr, real_uid, other_prod, {'active': False, 'state': phase_out_id}, context=context)

        return True

    def change_bn_ed_mandatory(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if not ids:
            return True

        product = self.browse(cr, uid, ids[0], fields_to_fetch=['qty_available', 'batch_management', 'perishable', 'default_code'], context=context)

        cr.execute("""
            SELECT pm.id FROM product_merged pm LEFT JOIN product_product op ON pm.old_product_id = op.id 
            WHERE (pm.new_product_id = %s OR pm.old_product_id = %s) AND op.unidata_merged = 't'
        """, (ids[0], ids[0]))
        merged_ids = [x[0] for x in cr.fetchall()]
        if merged_ids and self.pool.get('product.merged').need_to_push(cr, 1, merged_ids, context=context):
            raise osv.except_osv(_('Error'), _('There is a UD merge products in the pipe, BN/ED attributes cannot be changed. Please try again after the following synchronization.'))


        change_target = context.get('change_target')
        if not change_target:
            raise osv.except_osv(_('Error'), _('Missing Target in context'))

        in_use_stock = product.qty_available > 0 or False
        if not in_use_stock:  # Check stock IN - stock OUT
            cr.execute("""
                SELECT (SELECT SUM(m.product_qty) FROM stock_move m, stock_location l 
                    WHERE l.id = m.location_dest_id AND m.product_id = %s AND m.state = 'done'
                        AND l.usage NOT IN ('customer', 'supplier', 'inventory')
                    GROUP BY m.product_id)
                -
                    (SELECT SUM(m.product_qty) FROM stock_move m, stock_location l 
                    WHERE l.id = m.location_id AND m.product_id = %s AND m.state = 'done'
                        AND l.usage NOT IN ('customer', 'supplier', 'inventory')
                    GROUP BY m.product_id)
            """, (product.id, product.id))
            for prod in cr.fetchall():
                if prod[0] and prod[0] > 0:
                    in_use_stock = True
                    break
        # Check for Available INs and for Available Moves of Picking Tickets with 0 qty and Processed Line State
        if not in_use_stock:
            cr.execute("""
                SELECT m.id FROM stock_move m, stock_picking p 
                LEFT JOIN stock_incoming_processor ip ON p.id = ip.picking_id
                WHERE m.picking_id = p.id AND m.product_id = %s 
                    AND (
                        (m.product_qty > 0 AND p.type = 'in' AND p.subtype = 'standard' 
                            AND (p.state = 'shipped' OR (ip.draft = 't' AND p.state = 'assigned'))) 
                        OR (m.state = 'assigned' AND m.product_qty = 0 AND p.type = 'out' AND p.line_state = 'processed')
                    )
                LIMIT 1
            """, (product.id,))
            if cr.rowcount:
                in_use_stock = True
        if not in_use_stock:  # Check for Stock Mission Report
            srml_domain = [
                ('product_id', '=', product.id),
                '|', '|', '|', '|', '|', '|', '|', '|', '|', '|',
                ('stock_qty', '>', 0), ('in_pipe_coor_qty', '>', 0), ('cross_qty', '>', 0), ('in_pipe_qty', '>', 0),
                ('cu_qty', '>', 0), ('wh_qty', '>', 0), ('secondary_qty', '>', 0), ('internal_qty', '>', 0),
                ('quarantine_qty', '>', 0), ('input_qty', '>', 0), ('opdd_qty', '>', 0)
            ]
            if self.pool.get('stock.mission.report.line').search(cr, uid, srml_domain, limit=1, context=context):
                in_use_stock = True

        if in_use_stock:
            context['prod_data'] = {'id': product.id, 'change_target': change_target}
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'change.bn.ed.mandatory.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context,
            }

        self._apply_change_bn_ed(cr, uid, ids, change_target, context)
        return True

    def _apply_change_bn_ed(self, cr, uid, ids, change_target, context=None):
        if change_target == 'edonly':
            self.set_as_edonly(cr, uid, ids, context=context)
        elif change_target == 'bn':
            self.set_as_bned(cr, uid, ids, context=context)
        elif change_target == 'nobn_noed':
            self.set_as_nobn_noed(cr, uid, ids, context=context)
        else:
            raise osv.except_osv(_('Error'), _('Unknown %s target') % (change_target, ))
        return True

    def copy(self, cr, uid, id, default=None, context=None):
        product_xxx = self.search(cr, uid, [('default_code', '=', 'XXX')])
        if product_xxx:
            raise osv.except_osv(_('Warning'), _('A product with a code "XXX" already exists please edit this product to change its Code.'))
        product2copy = self.read(cr, uid, [id], ['default_code', 'name'])[0]
        if default is None:
            default = {}

        to_reset_list = ['replace_product_id', 'replaced_by_product_id', 'currency_fixed', 'kept_product_id',
                         'kept_initial_product_id', 'unidata_merged', 'unidata_merge_date', 'local_merged_product']
        for to_reset in to_reset_list:
            if to_reset not in default:
                default[to_reset] = False

        temp_status = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_5')[1]

        copy_pattern = _("%s (copy)")
        copydef = dict(name=(copy_pattern % product2copy['name']),
                       default_code="XXX",
                       # we set international_status to "temp" so that it won't be synchronized with this status
                       international_status=temp_status,
                       # we do not duplicate the o2m objects
                       asset_ids=False,
                       prodlot_ids=False,
                       attribute_ids=False,
                       packaging=False,
                       uf_create_date=False,
                       uf_write_date=False,
                       kept_product_id=False,
                       kept_initial_product_id=False,
                       unidata_merged=False,
                       unidata_merge_date=False,
                       is_kept_product=False,
                       local_merged_product=False,
                       )
        copydef.update(default)
        return super(product_attributes, self).copy(cr, uid, id, copydef, context)

    def onchange_code(self, cr, uid, ids, default_code):
        '''
        Check if the code already exists
        '''
        res = {}
        if default_code:
            cr.execute("SELECT * FROM product_product pp where pp.default_code = %s", (default_code,))
            duplicate = cr.fetchall()
            if duplicate:
                res.update({'warning': {'title': 'Warning', 'message':'The Code already exists'}})
        return res

    def on_change_type(self, cr, uid, ids, type, context=None):
        '''
        Check if the type can be changed on Coordo or HQ
        If type is service_with_reception, procure_method is set to make_to_order
        '''
        if context is None:
            context = {}

        res = {}
        prods = self.browse(cr, uid, ids, fields_to_fetch=['company_id', 'type', 'international_status'], context=context)
        for prod in prods:
            inter_status = prod.international_status
            instance_level = prod.company_id.instance_id.level
            srml_stock_exist = self.check_exist_srml_stock(cr, uid, prod.id)
            if inter_status.code == 'local' and instance_level == 'coordo' and srml_stock_exist:
                res.update({'value': {'type': prod.type}, 'warning': {'title': _('Warning'),
                                                                      'message': _('In a Coordo instance, you can not change the Product Type of a Local Product if it has stock in the Mission Stock Report')}})
                type = prod.type
            elif inter_status.code in ['itc', 'esc', 'hq', 'unidata'] and instance_level == 'section' and srml_stock_exist:
                res.update({'value': {'type': prod.type}, 'warning': {'title': _('Warning'),
                                                                      'message': _('In a HQ instance, you can not change the Product Type of an ITC, ESC, HQ or Unidata Product if it has stock in the Mission Stock Report')}})
                type = prod.type

        if type in ('consu', 'service', 'service_recep'):
            res.update({'value': {'procure_method': 'make_to_order', 'supply_method': 'buy', }})
        return res

    fake_ed = '2999-12-31'
    fake_bn = 'TO-BE-REPLACED'

    def _update_bn_id_on_fk(self, cr, new_id, old_ids):
        # get all fk
        cr.execute("""
            SELECT tc.table_name, kcu.column_name, ref.delete_rule
            FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name
                JOIN information_schema.referential_constraints AS ref ON ref.constraint_name = tc.constraint_name
            WHERE
                tc.constraint_type = 'FOREIGN KEY' AND
                ccu.table_name='stock_production_lot' AND
                ccu.column_name='id'
        """)

        # following records have on delete casace and we want to delete them
        ignore = [ 'stock_production_lot_revision.lot_id', 'unconsistent_stock_report_line.prodlot_id']

        for table, column, const_type in cr.fetchall():
            if '%s.%s' % (table, column) in ignore:
                continue
            cr.execute("update "+table+" set "+column+"=%s where "+column+" in %s", (new_id, tuple(old_ids))) # not_a_user_entry

        return True


    def _remove_all_bned(self, cr, uid, product_ids, context=None):
        '''
            Reset BN
            Rest ED
        '''
        if not context.get('sync_update_execution'):
            prod_obj = self
        else:
            prod_obj = super(product_attributes, self)
        prod_obj.write(cr, uid, product_ids, {'perishable': False, 'batch_management': False}, context=context)

        cr.execute("update stock_move set hidden_batch_management_mandatory='f', hidden_perishable_mandatory='f', prodlot_id=NULL, expired_date=NULL, old_lot_info=(select name||'#'||life_date from stock_production_lot where id=stock_move.prodlot_id)||E'\n'||COALESCE(old_lot_info, '') where product_id in %s", (tuple(product_ids), ))
        cr.execute("delete from stock_production_lot where product_id in %s", (tuple(product_ids), ))

        # save as draft
        for table in ['internal_move_processor', 'outgoing_delivery_move_processor', 'stock_move_in_processor', 'stock_move_processor']:
            cr.execute("update "+ table + " set prodlot_id=NULL, expiry_date=NULL, lot_check='f', exp_check='f' where product_id in %s", (tuple(product_ids), )) # not_a_user_entry
        # ISI
        cr.execute("""update initial_stock_inventory_line set
            hidden_batch_management_mandatory='f', hidden_perishable_mandatory='f', expiry_date=NULL, prodlot_name=''
            where product_id in %s
        """, (tuple(product_ids), ))

        # Previous Inventory
        cr.execute("""update stock_inventory_line set
            hidden_batch_management_mandatory='f', hidden_perishable_mandatory='f', expiry_date=NULL
            where product_id in %s""", (tuple(product_ids), ))

        # Consump
        cr.execute("""update real_average_consumption_line set
            date_mandatory='f', batch_mandatory='f', expiry_date=NULL
            where product_id in %s""", (tuple(product_ids), ))

        #PI CS
        cr.execute("update physical_inventory_counting set batch_number='', expiry_date=NULL where product_id in %s", (tuple(product_ids), ))

        #PI Disc.
        cr.execute("update physical_inventory_discrepancy set batch_number='', expiry_date=NULL where product_id in %s", (tuple(product_ids), ))

    def switch_bn_to_no(self, cr, uid, ids, context=None):
        # i
        if context is None:
            context = {}
        prod_to_change = self.search(cr, uid, [('id', 'in', ids), ('batch_management', '=', True), ('perishable', '=', True)], context=context)
        if prod_to_change:
            self._remove_all_bned(cr, uid,  prod_to_change, context=context)
        return True

    def switch_no_to_bn(self, cr, uid, ids, context=None):
        # ii
        if context is None:
            context = {}
        lot_obj = self.pool.get('stock.production.lot')
        prod_to_change = self.search(cr, uid, [('id', 'in', ids), ('batch_management', '=', False), ('perishable', '=', False)], context=context)
        if prod_to_change:
            if not context.get('sync_update_execution'):
                prod_obj = self
            else:
                prod_obj = super(product_attributes, self)
            prod_obj.write(cr, uid, prod_to_change, {'perishable': True, 'batch_management': True}, context=context)
        for prod_id in prod_to_change:
            batch_id = lot_obj._get_or_create_lot(cr, uid, name=self.fake_bn, expiry_date=self.fake_ed, product_id=prod_id, context=context)
            cr.execute("update stock_move set hidden_batch_management_mandatory='t', hidden_perishable_mandatory='f', prodlot_id=%s, expired_date=%s where product_id=%s and state in ('done', 'cancel')", (batch_id, self.fake_ed, prod_id))
            count = cr.rowcount

            # all available move except IN
            cr.execute("update stock_move set hidden_batch_management_mandatory='t', hidden_perishable_mandatory='f', prodlot_id=%s, expired_date=%s where product_id=%s and state = 'assigned' and type!='in'", (batch_id, self.fake_ed, prod_id))
            count += cr.rowcount

            # Available Shipped or Available Updated IN
            cr.execute("update stock_move set hidden_batch_management_mandatory='t', hidden_perishable_mandatory='f' where product_id=%s and state = 'assigned' and type='in'", (prod_id, ))
            cr.execute("""update stock_move set hidden_batch_management_mandatory='t', hidden_perishable_mandatory='f', prodlot_id=%s, expired_date=%s where product_id=%s and state = 'assigned' and type='in'
                and picking_id in (select id from stock_picking where state in ('updated', 'shipped') and type='in') """, (batch_id, self.fake_ed, prod_id))
            count += cr.rowcount

            # save as draft
            for table in ['internal_move_processor', 'outgoing_delivery_move_processor', 'stock_move_in_processor', 'stock_move_processor']:
                cr.execute("update "+ table + " set prodlot_id=%s, expiry_date=%s, lot_check='t', exp_check='t' where product_id = %s and quantity>0", (batch_id, self.fake_ed, prod_id,)) # not_a_user_entry
                count += cr.rowcount

            # Previous Inventory
            cr.execute("""update stock_inventory_line set
                hidden_batch_management_mandatory='t', hidden_perishable_mandatory='t', prod_lot_id=%s, expiry_date=%s
                where product_id = %s""", (batch_id, self.fake_ed, prod_id ))
            count += cr.rowcount

            # Consump.
            cr.execute("update real_average_consumption_line set date_mandatory='t', batch_mandatory='t', prodlot_id=%s, expiry_date=%s where product_id = %s", (batch_id, self.fake_ed, prod_id))
            count += cr.rowcount

            if not count:
                if lot_obj.browse(cr, 1, batch_id, fields_to_fetch=['delete_ok'], context=context).delete_ok:
                    lot_obj.unlink(cr, 1, [batch_id], context=context)

        if prod_to_change:
            # save as draft
            for table in ['internal_move_processor', 'outgoing_delivery_move_processor', 'stock_move_in_processor', 'stock_move_processor']:
                cr.execute("update "+ table + " set lot_check='t', exp_check='t' where product_id in %s and quantity=0", (tuple(prod_to_change),)) # not_a_user_entry
            # ISI done
            cr.execute("""update initial_stock_inventory_line set
                hidden_batch_management_mandatory='t',  hidden_perishable_mandatory='t', prodlot_name=%s, expiry_date=%s
                where product_id in %s and inventory_id in
                    (select id from initial_stock_inventory where state = 'done')
            """, (self.fake_bn, self.fake_ed, tuple(prod_to_change) ))

            # ISI confirm /drart
            cr.execute("""update initial_stock_inventory_line set
                hidden_batch_management_mandatory='t',  hidden_perishable_mandatory='t'
                where product_id in %s and inventory_id in
                    (select id from initial_stock_inventory where state in ('confirm', 'draft'))
            """, (tuple(prod_to_change), ))

            #PI CS
            cr.execute("update physical_inventory_counting set batch_number=%s, expiry_date=%s where product_id in %s", (self.fake_bn, self.fake_ed, tuple(prod_to_change), ))

            #PI CS
            cr.execute("update physical_inventory_discrepancy set batch_number=%s, expiry_date=%s where product_id in %s", (self.fake_bn, self.fake_ed, tuple(prod_to_change), ))

        return len(prod_to_change)

    def switch_ed_to_no(self, cr, uid, ids, context=None):
        # iii
        if context is None:
            context = {}
        prod_to_change = self.search(cr, uid, [('id', 'in', ids), ('batch_management', '=', False), ('perishable', '=', True)], context=context)
        if prod_to_change:
            self._remove_all_bned(cr, uid, prod_to_change, context=context)
        return len(prod_to_change)

    def switch_bn_to_ed(self, cr, uid, ids, context=None):
        # iv
        if context is None:
            context = {}
        seq_obj = self.pool.get('ir.sequence')
        prod_to_change = self.search(cr, uid, [('id', 'in', ids), ('batch_management', '=', True), ('perishable', '=', True)], context=context)
        if prod_to_change:
            if not context.get('sync_update_execution'):
                prod_obj = self
            else:
                prod_obj = super(product_attributes, self)
            prod_obj.write(cr, uid, prod_to_change, {'batch_management': False}, context=context)

            # check if we should merge lot: i.e P1 BN1 EDA / P1 BN2 EDA : same EDA BN1+BN2 must be merged
            cr.execute("select min(id), array_agg(id) from stock_production_lot where product_id in %s group by product_id, life_date having count(*)>1", (tuple(prod_to_change),))
            for to_merge in cr.fetchall():
                to_keep = to_merge[0]
                merged = to_merge[1]
                merged.remove(to_keep)
                cr.execute("update stock_move set prodlot_id=%s, old_lot_info=(select name||'#'||life_date from stock_production_lot where id=stock_move.prodlot_id)||E'\n'||COALESCE(old_lot_info, '') where prodlot_id in %s",  (to_keep, tuple(merged)))
                self._update_bn_id_on_fk(cr, to_keep, merged)
                cr.execute("delete from stock_production_lot where id in %s", (tuple(merged), ))

            cr.execute("update stock_move set hidden_batch_management_mandatory='f', hidden_perishable_mandatory='t' where product_id in %s" , (tuple(prod_to_change),))
            # rename lot
            seq_obj = self.pool.get('ir.sequence')
            cr.execute("select id from stock_production_lot where type='standard' and product_id in %s order by life_date", (tuple(prod_to_change),))
            for bn_lot_to_internal in cr.fetchall():
                new_name = seq_obj.get(cr, uid, 'stock.lot.serial')
                cr.execute("update stock_production_lot set type='internal', name=%s where id=%s", (new_name, bn_lot_to_internal[0]))

            # save as draft
            for table in ['internal_move_processor', 'outgoing_delivery_move_processor', 'stock_move_in_processor', 'stock_move_processor']:
                cr.execute("update "+ table + " set lot_check='f', exp_check='t' where product_id in %s", (tuple(prod_to_change),)) # not_a_user_entry

            # ISI draft / confirm / done
            cr.execute("""update initial_stock_inventory_line set
                hidden_batch_management_mandatory='f', prodlot_name=''
                where product_id in %s
            """, (tuple(prod_to_change), ))

            # Previous Inventory
            cr.execute("""update stock_inventory_line set
                hidden_batch_management_mandatory='f', hidden_perishable_mandatory='t'
                where product_id in %s""", (tuple(prod_to_change), ))

            # Consump
            cr.execute("""update real_average_consumption_line set
                batch_mandatory='f'
                where product_id in %s""", (tuple(prod_to_change), ))
            #PI CS
            # untouch batch_number for dupliactes ED/prod id
            cr.execute("""update physical_inventory_counting set batch_number=NULL where product_id in %s""", (tuple(prod_to_change), ))

            #PI Disc.
            cr.execute("update physical_inventory_discrepancy set batch_number=NULL where product_id in %s", (tuple(prod_to_change), ))
            #cr.execute("""update physical_inventory_counting set batch_number='' where id in (
            #    select min(id) from physical_inventory_counting where product_id in %s group by inventory_id, product_id, expiry_date having count(*) < 2
            #    ) """, (tuple(prod_to_change), ))

        return len(prod_to_change)

    def switch_no_to_ed(self, cr, uid, ids, context=None):
        # vi
        if context is None:
            context = {}
        lot_obj = self.pool.get('stock.production.lot')
        prod_to_change = self.search(cr, uid, [('id', 'in', ids), ('batch_management', '=', False), ('perishable', '=', False)], context=context)
        if prod_to_change:
            if not context.get('sync_update_execution'):
                prod_obj = self
            else:
                prod_obj = super(product_attributes, self)
            prod_obj.write(cr, uid, prod_to_change, {'perishable': True}, context=context)

        for prod_id in prod_to_change:
            batch_id = lot_obj._get_or_create_lot(cr, uid, name=False, expiry_date=self.fake_ed, product_id=prod_id, context=context)
            cr.execute("update stock_move set hidden_batch_management_mandatory='f', hidden_perishable_mandatory='t', prodlot_id=%s, expired_date=%s where product_id=%s and state in ('done', 'cancel')", (batch_id, self.fake_ed, prod_id))
            count = cr.rowcount

            # Assigned except IN
            cr.execute("update stock_move set hidden_batch_management_mandatory='f', hidden_perishable_mandatory='t', prodlot_id=%s, expired_date=%s where product_id=%s and state = 'assigned' and type!='in'", (batch_id, self.fake_ed, prod_id))
            count += cr.rowcount

            # Available Shipped or Available Updated IN
            cr.execute("update stock_move set hidden_batch_management_mandatory='f', hidden_perishable_mandatory='t' where product_id=%s and state='assigned' and type='in'", (prod_id,))
            cr.execute("""update stock_move set hidden_batch_management_mandatory='f', hidden_perishable_mandatory='t', prodlot_id=%s, expired_date=%s where product_id=%s and state = 'assigned' and type='in'
                    and picking_id in (select id from stock_picking where state in ('updated', 'shipped') and type='in')""", (batch_id, self.fake_ed, prod_id))
            count += cr.rowcount

            # save as draft
            for table in ['internal_move_processor', 'outgoing_delivery_move_processor', 'stock_move_in_processor', 'stock_move_processor']:
                cr.execute("update "+ table + " set prodlot_id=%s, expiry_date=%s, lot_check='f', exp_check='t' where product_id in %s", (batch_id, self.fake_ed, tuple(prod_to_change),)) # not_a_user_entry
                count += cr.rowcount
            # Consump.
            cr.execute("update real_average_consumption_line set date_mandatory='t', batch_mandatory='f', prodlot_id=%s, expiry_date=%s where product_id = %s", (batch_id, self.fake_ed, prod_id))
            count += cr.rowcount

            # Previous Inventory
            cr.execute("""update stock_inventory_line set
                hidden_batch_management_mandatory='f', hidden_perishable_mandatory='t', prod_lot_id=%s, expiry_date=%s
                where product_id = %s""", (batch_id, self.fake_ed, prod_id))
            count += cr.rowcount

            if not count:
                if lot_obj.browse(cr, 1, batch_id, fields_to_fetch=['delete_ok'], context=context).delete_ok:
                    lot_obj.unlink(cr, 1, [batch_id], context=context)

        if prod_to_change:
            # ISI done
            cr.execute("""update initial_stock_inventory_line set
                hidden_batch_management_mandatory='f',  hidden_perishable_mandatory='t', prodlot_name=%s, expiry_date=%s
                where product_id in %s and inventory_id in
                    (select id from  initial_stock_inventory where state = 'done')
            """, (self.fake_bn, self.fake_ed, tuple(prod_to_change) ))

            # ISI confirm /draft
            cr.execute("""update initial_stock_inventory_line set
                hidden_batch_management_mandatory='t',  hidden_perishable_mandatory='t'
                where product_id in %s and inventory_id in
                    (select id from  initial_stock_inventory where state in ('confirm', 'draft'))
            """, (tuple(prod_to_change), ))

            #PI CS
            cr.execute("update physical_inventory_counting set batch_number='', expiry_date=%s where product_id in %s", (self.fake_ed, tuple(prod_to_change), ))
            #PI Disc
            cr.execute("update physical_inventory_discrepancy set batch_number='', expiry_date=%s where product_id in %s", (self.fake_ed, tuple(prod_to_change), ))

        return len(prod_to_change)

    def switch_ed_to_bn(self, cr, uid, ids, context=None):
        # v
        if context is None:
            context = {}
        prod_to_change = self.search(cr, uid, [('id', 'in', ids), ('batch_management', '=', False), ('perishable', '=', True)], context=context)
        if prod_to_change:
            if not context.get('sync_update_execution'):
                prod_obj = self
            else:
                prod_obj = super(product_attributes, self)
            prod_obj.write(cr, uid, prod_to_change, {'batch_management': True}, context=context)
            cr.execute("update stock_move set old_lot_info=(select name||'#'||life_date from stock_production_lot where id=stock_move.prodlot_id)||E'\n'||COALESCE(old_lot_info, '') where prodlot_id is not null and product_id in %s",  (tuple(prod_to_change), ))
            cr.execute("update stock_move set hidden_batch_management_mandatory='t', hidden_perishable_mandatory='f' where product_id in %s",  (tuple(prod_to_change), ))
            cr.execute("update stock_production_lot set name=%s, type='standard' where product_id in %s", (self.fake_bn, tuple(prod_to_change)))
            # save as draft
            for table in ['internal_move_processor', 'outgoing_delivery_move_processor', 'stock_move_in_processor', 'stock_move_processor']:
                cr.execute("update "+ table + " set prodlot_id=(select id from stock_production_lot where life_date="+table+".expiry_date and product_id="+table+".product_id), lot_check='t', exp_check='t' where product_id in %s and expiry_date is not null", (tuple(prod_to_change),)) # not_a_user_entry
                cr.execute("update "+ table + " set integrity_status='missing_lot' where product_id in %s and prodlot_id is null and expiry_date is not null", (tuple(prod_to_change),)) # not_a_user_entry
                cr.execute("update "+ table + " set lot_check='t', exp_check='t' where product_id in %s and prodlot_id is null and expiry_date is null", (tuple(prod_to_change),)) # not_a_user_entry

            # ISI
            cr.execute("""update initial_stock_inventory_line set
                hidden_batch_management_mandatory='t', prodlot_name=''
                where product_id in %s and inventory_id in
                    (select id from  initial_stock_inventory where state in ('confirm', 'draft'))
            """, (tuple(prod_to_change), ))
            cr.execute("""update initial_stock_inventory_line set
                hidden_batch_management_mandatory='t', prodlot_name=%s
                where product_id in %s and inventory_id in
                    (select id from  initial_stock_inventory where state ='done')
            """, (self.fake_bn, tuple(prod_to_change), ))

            # Previous Inventory
            cr.execute("""update stock_inventory_line set
                hidden_batch_management_mandatory='t', hidden_perishable_mandatory='t'
                where product_id in %s""", (tuple(prod_to_change), ))

            # Consumption Report
            cr.execute("""update real_average_consumption_line set
                date_mandatory='t', batch_mandatory='t'
                where product_id in %s""", (tuple(prod_to_change), ))

            #PI CS
            cr.execute("update physical_inventory_counting set batch_number=%s where product_id in %s", (self.fake_bn, tuple(prod_to_change), ))
            #PI Disc.
            cr.execute("update physical_inventory_discrepancy set batch_number=%s where product_id in %s", (self.fake_bn, tuple(prod_to_change), ))

        return len(prod_to_change)

    def set_as_edonly(self, cr, uid, ids, context=None):
        nb = self.switch_no_to_ed(cr, uid, ids, context)
        nb += self.switch_bn_to_ed(cr, uid, ids, context)
        return nb

    def set_as_bned(self, cr, uid, ids, context=None):
        nb = self.switch_no_to_bn(cr, uid, ids, context)
        nb += self.switch_ed_to_bn(cr, uid, ids, context)
        return nb

    def set_as_nobn_noed(self, cr, uid, ids, context=None):
        nb = self.switch_ed_to_no(cr, uid, ids, context)
        nb += self.switch_bn_to_no(cr, uid, ids, context)
        return nb

    def check_same_value(self, cr, uid, new_prod_id, old_prod_id, level, blocker=True, context=None):

        if level == 'coordo':
            if blocker:
                fields_to_check = [
                    'type', 'subtype', 'perishable', 'batch_management', 'uom_id', 'nomen_manda_0'
                ]
            else:
                fields_to_check = [
                    'nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'heat_sensitive_item', 'controlled_substance', 'dangerous_goods'
                ]
        else:
            if blocker:
                fields_to_check = [
                    'type', 'subtype', 'perishable', 'batch_management', 'uom_id', 'nomen_manda_0'
                ]
            else:
                fields_to_check = [
                    'nomen_manda_1', 'nomen_manda_2', 'heat_sensitive_item', 'controlled_substance', 'dangerous_goods'
                ]

        ftf = fields_to_check.copy()
        ftf.append('default_code')
        old_values = self.read(cr, uid, old_prod_id, ftf, context=context)
        new_values = self.read(cr, uid, new_prod_id, ftf, context=context)

        failed = []
        for f in fields_to_check:
            if old_values[f] != new_values[f]:
                failed.append(f)

        if failed:
            fields_data = self.fields_get(cr, uid, failed, context=context)
            values = {'attr': ', '.join([fields_data[x].get('string') for x in failed])}
            if blocker:
                values['product_old'] = old_values['default_code']
                values['product_new'] = new_values['default_code']
                if level == 'coordo':
                    return _('There is an inconsistency between the selected products: %(attr)s need to be the same. Please update your local product %(attr)s and then proceed with the merge. Products %(product_old)s and %(product_new)s') % values
                return _('There is an inconsistency between the selected products: %(attr)s need to be the same. Please update (one of) your UniData product\'s %(attr)s and then proceed with the merge. Products %(product_old)s and %(product_new)s') % values

            return _('There is an inconsistency between the selected products’ %(attr)s. Do you still want to proceed with the merge ?') % values

        return ''

    def open_merge_hq_product_wizard(self, cr, uid, prod_id, context=None):
        if self.pool.get('res.company')._get_instance_level(cr, uid) != 'section':
            raise osv.except_osv(_('Warning'), _('Merge products can only be done at HQ level.'))

        wiz_id = self.pool.get('product.merged.wizard').create(cr, uid, {'old_product_id': prod_id[0], 'level': 'section'}, context=context)

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'hq_product_merged_wizard_form_view')[1]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.merged.wizard',
            'res_id': wiz_id,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [view_id],
            'target': 'new',
            'context': context,
            'height': '400px',
            'width': '720px',
        }

    def open_merge_product_wizard(self, cr, uid, prod_id, context=None):
        if self.pool.get('res.company')._get_instance_level(cr, uid) != 'coordo':
            raise osv.except_osv(_('Warning'), _('Merge products can only be done at Coordo level.'))

        wiz_id = self.pool.get('product.merged.wizard').create(cr, uid, {'old_product_id': prod_id[0], 'level': 'coordo'}, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.merged.wizard',
            'res_id': wiz_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
            'height': '400px',
            'width': '720px',
        }

    def open_merge_local_product_wizard(self, cr, uid, prod_id, context=None):
        if self.pool.get('res.company')._get_instance_level(cr, uid) != 'coordo':
            raise osv.except_osv(_('Warning'), _('Merge products can only be done at Coordo level.'))

        wiz_vals = {'old_product_id': prod_id[0], 'level': 'coordo', 'local': True}
        wiz_id = self.pool.get('product.merged.wizard').create(cr, uid, wiz_vals, context=context)

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'local_product_merged_wizard_form_view')[1]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.merged.wizard',
            'res_id': wiz_id,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [view_id],
            'target': 'new',
            'context': context,
            'height': '400px',
            'width': '720px',
        }

    def _has_pipe(self, cr, uid, ids):
        if not ids:
            return False

        if isinstance(ids, int):
            ids = [ids]

        cr.execute('''
                    select
                        l.product_id, array_agg(i.code)
                    from
                        stock_mission_report r, msf_instance i, stock_mission_report_line l
                    where
                        i.id = r.instance_id and
                        i.state = 'active' and
                        l.mission_report_id = r.id and
                        l.product_id in %s and
                        r.full_view = 'f' and
                        ( l.internal_qty > 0 or l.in_pipe_qty > 0 or l.used_in_transaction='t')
                    group by l.product_id
                ''' , (tuple(ids), ))
        return [(x[0],', '.join(x[1])) for x in cr.fetchall()]

    def merge_hq_product(self, cr, uid, kept_id, old_prod_id, context=None):
        self._global_merge_product(cr, uid, kept_id, old_prod_id, 'section', False, context=context)

    def _global_merge_product(self, cr, uid, kept_id, old_prod_id, merge_type, local, context=None):
        """
        method used at HQ level to merge UD products, and executed at mission level by sync
        """
        if context is None:
            context = {}
        #  merged_fields_to_keep = ['procure_method', 'soq_quantity', 'description_sale', 'description_purchase', 'procure_delay'] # translations

        kept_context = context.copy()
        kept_context['lang'] = 'en_US'
        kept_data = self.read(cr, uid, kept_id, ['default_code','perishable', 'batch_management', 'old_code', 'product_tmpl_id', 'standard_price', 'qty_available', 'active', 'standard_ok', 'international_status', 'finance_price'], context=kept_context)

        old_fields_to_read = ['default_code', 'product_tmpl_id', 'standard_price', 'qty_available', 'active', 'can_be_hq_merged', 'international_status', 'standard_ok', 'finance_price']
        if merge_type != 'section':
            old_fields_to_read = list(set(old_fields_to_read).union(self.merged_fields_to_keep))

        old_prod_data = self.read(cr, uid, old_prod_id, old_fields_to_read, context=context)
        instance_level = self.pool.get('res.company')._get_instance_level(cr, uid)
        status_local_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_4')[1]

        errors = []
        if merge_type == 'section':
            if not context.get('sync_update_execution'):
                # checks on HQ only
                if not old_prod_data['can_be_hq_merged']:
                    errors.append(_('Product %s cannot be merged.') % (old_prod_data['default_code'],))
                if not old_prod_data['active']:
                    errors.append(_('Product %s must be active.') % (old_prod_data['default_code'],))
                if not kept_data['active']:
                    errors.append(_('Product %s must be active.') % (kept_data['default_code'],))
            else:
                # checks on mission
                if not old_prod_data['active'] and ((not local and old_prod_data['standard_ok'] != 'non_standard_local') or local):
                    errors.append(_('Product %s must be active.') % (old_prod_data['default_code'], ))
                if not kept_data['active'] and ((not local and kept_data['standard_ok'] != 'non_standard_local') or local):
                    errors.append(_('Product %s must be active.') % (kept_data['default_code'], ))

            if not local and (kept_data['international_status'] != old_prod_data['international_status'] or
                              kept_data['international_status'][1] != 'UniData'):
                errors.append(_('Products %s, %s must be UniData.') % (old_prod_data['default_code'], kept_data['default_code']))
            if local and (old_prod_data['international_status'][1] != status_local_id or
                          kept_data['international_status'][1] != status_local_id):
                errors.append(_('Products %s, %s must be Local.') % (old_prod_data['default_code'], kept_data['default_code']))


        if instance_level != 'project':
            block_msg = self.check_same_value( cr, uid,  kept_id, old_prod_id, level=merge_type, blocker=True, context=context)
            if block_msg:
                prod_data = self.read(cr, uid, [kept_id, old_prod_id], ['default_code'], context=context)
                errors.append(_('%s\nProducts: %s and %s') % (block_msg, prod_data[0]['default_code'], prod_data[1]['default_code']))

        if errors:
            raise osv.except_osv(_('Error'), "\n".join(errors))

        if merge_type == 'section':
            new_write_data = {'is_kept_product': True}
        else:
            new_write_data = {'active': True, 'replace_product_id': old_prod_id}

        if not kept_data['old_code']:
            new_write_data['old_code'] = old_prod_data['default_code']
        elif old_prod_data['default_code'] not in kept_data['old_code'].split(';'):
            new_write_data['old_code'] = '%s;%s' % (kept_data['old_code'], old_prod_data['default_code'])

        if old_prod_data['qty_available'] + kept_data['qty_available']:
            for price_field in ['standard_price', 'finance_price']:
                # ignore qty if price = 0
                if price_field == 'finance_price':
                    total_qty = 0
                    if old_prod_data[price_field]:
                        total_qty += old_prod_data['qty_available']
                    if kept_data[price_field]:
                        total_qty += kept_data['qty_available']
                else:
                    total_qty = old_prod_data['qty_available'] + kept_data['qty_available']

                if total_qty:
                    new_write_data[price_field] = (old_prod_data['qty_available'] * old_prod_data[price_field] + kept_data['qty_available'] * kept_data[price_field]) / float(total_qty)

            if abs(new_write_data['standard_price'] - kept_data['standard_price']) > 0.0001:
                self.pool.get('standard.price.track.changes').create(cr, uid, {
                    'old_standard_price': kept_data['standard_price'],
                    'new_standard_price': new_write_data['standard_price'],
                    'product_id': kept_id,
                    'transaction_name': 'Merge with %s: qty transferred: %s, avg cost: %s, resulting qty: %s' % (old_prod_data['default_code'], old_prod_data['qty_available'], old_prod_data['standard_price'], kept_data['qty_available']+old_prod_data['qty_available']),
                }, context=context)

        # kept is inactive NSL check at coordo if it must be activated
        if merge_type == 'section' and context.get('sync_update_execution'):
            if kept_data['standard_ok'] == 'non_standard_local' and not kept_data['active'] and old_prod_data['active']:
                if instance_level == 'coordo':
                    if not self.deactivate_product(cr, uid, old_prod_id, context=context, try_only=True, ignore_draft=False).get('ok') or \
                            self._has_pipe(cr, uid, old_prod_id):
                        # from_hq_merge used to trigger update from COO to activate prod at coo
                        new_write_data.update({'active': True, 'from_hq_merge': True})

        blacklist_table = {
            'product_template': [
                ('product_product', 'product_tmpl_id')
            ],
            'product_product': [
                ('stock_mission_report_line', 'product_id'),
                ('stock_mission_report_line_location', 'product_id'),
                ('prod_mass_update_product_rel', 'prod_mass_update_id'),
                ('product_mass_update_errors', 'product_id'),
                ('product_merged', 'new_product_id'),
                ('product_merged', 'old_product_id'),
                ('standard_price_track_changes', 'product_id'),
                ('product_product', 'kept_initial_product_id'),
            ]
        }

        # m2m tables have by standard a unique constraint, so we should delete old prod entry if the new one already exist
        m2m_relation = {}
        fields_obj = self.pool.get('ir.model.fields')
        m2m_ids = fields_obj.search(cr, uid, [('ttype', '=', 'many2many'), ('relation', '=', 'product.product'), ('state', '!=', 'deprecated')], context=context)
        if m2m_ids:
            for m2m_rel in fields_obj.browse(cr, uid, m2m_ids, fields_to_fetch=['model', 'name'], context=context):
                linked_obj = self.pool.get(m2m_rel.model)
                if linked_obj and not isinstance(linked_obj, osv.osv_memory):
                    m2m_field = linked_obj._columns.get(m2m_rel.name)
                    if not m2m_field or isinstance(m2m_field, fields.function):
                        continue
                    m2m_relation.setdefault(m2m_field._rel, []).append({'linked_field': m2m_field._id1, 'product_field': m2m_field._id2})

        default_code = kept_data['default_code']
        for table in ['product_product', 'product_template']:
            for x in cr.get_referenced(table):
                if (x[0], x[1]) in blacklist_table.get(table):
                    continue

                if table == 'product_product':
                    params = {'old_prod': old_prod_id, 'kept_id': kept_id}
                else:
                    params = {'old_prod': old_prod_data['product_tmpl_id'][0], 'kept_id': kept_data['product_tmpl_id'][0]}

                if x[0] == 'stock_production_lot':
                    # merge duplicates lot
                    if kept_data['batch_management'] or kept_data['perishable']:
                        if kept_data['batch_management']:
                            add_lot_query = 'and kept_lot.name = old_lot.name '
                        else:
                            add_lot_query = ''
                        cr.execute('''
                            select
                                kept_lot.id, old_lot.id
                            from
                                stock_production_lot kept_lot, stock_production_lot old_lot
                            where
                                kept_lot.product_id = %(kept_id)s and
                                old_lot.product_id = %(old_prod)s and
                                kept_lot.life_date = old_lot.life_date
                                ''' + add_lot_query + '''
                        ''', params) # not_a_user_entry

                        for kept_lot, old_lot in cr.fetchall():
                            for referenced in cr.get_referenced('stock_production_lot'):
                                cr.execute('update ' + referenced[0] + ' set ' + referenced[1] + '=%s where ' + referenced[1] + '=%s', (kept_lot, old_lot)) # not_a_user_entry
                            cr.execute('delete from stock_production_lot where id=%s', (old_lot, ))

                if cr.column_exists(x[0], 'default_code') and table != 'product_product':
                    params['default_code'] = default_code
                    add_query = ' , default_code=%(default_code)s '
                else:
                    add_query = ''

                if table == 'product_product' and x[0] in m2m_relation:
                    for m2m_rel in m2m_relation[x[0]]:
                        # delete duplicates on m2m
                        cr.execute("delete from "+x[0]+" where "+m2m_rel['product_field']+"=%(old_prod)s and "+m2m_rel['linked_field']+" in (select "+m2m_rel['linked_field']+" from "+x[0]+" where "+m2m_rel['product_field']+"=%(kept_id)s)", params) # not_a_user_entry
                cr.execute('update '+x[0]+' set '+x[1]+'=%(kept_id)s '+add_query+' where '+x[1]+'=%(old_prod)s', params) # not_a_user_entry

        write_context = context.copy()
        write_context['keep_standard_price'] = True # to allow to write standard_price field
        write_context['lang'] = 'en_US'
        if merge_type != 'section':
            if not context.get('sync_update_execution'):
                # copy fields from old product to kept prod
                for field in self.merged_fields_to_keep:
                    new_write_data[field] = old_prod_data[field]
            else:
                # project execute merge from coo
                new_write_data['procure_delay'] = old_prod_data['procure_delay']

        self.write(cr, uid, kept_id, new_write_data, context=write_context)
        if merge_type != 'section' and not context.get('sync_update_execution'):
            for lang in self.pool.get('res.lang').get_translatable_code(cr, uid):
                trans_data = self.read(cr, uid, old_prod_id, ['description_sale', 'description_purchase'], context={'lang': lang})
                for to_del in ['id', 'product_tmpl_id']:
                    try:
                        del(trans_data[to_del])
                    except:
                        pass
                self.write(cr, uid, kept_id, new_write_data, context={'lang': lang})

        if merge_type == 'section':
            old_prod_new_data = {'active': False, 'unidata_merged': True, 'unidata_merge_date': fields.datetime.now(), 'kept_product_id': kept_id, 'kept_initial_product_id': kept_id, 'new_code': kept_data['default_code']}
        else:
            old_prod_new_data = {'active': False, 'replaced_by_product_id': kept_id}
            if local:
                old_prod_new_data['local_product_merged'] = True
        self.write(cr, uid, old_prod_id, old_prod_new_data, context=context)

        # US-11877: To have those translations in the audittrail without putting mandatory lang at the creation
        # generate terms on translations export
        [_('Merge Product non-kept product'), _('Merge Product kept product')]


        if merge_type == 'section':
            _register_log(self, cr, uid, kept_id, self._name, 'Merge Product non-kept product', '', old_prod_data['default_code'], 'write', context)
            _register_log(self, cr, uid, old_prod_id, self._name, 'Merge Product kept product', '', kept_data['default_code'], 'write', context)
            if not context.get('sync_update_execution') or instance_level == 'coordo':
                merge_data = {'new_product_id': kept_id, 'old_product_id': old_prod_id, 'level': 'section'}
                new_ctx = context.copy()
                if instance_level == 'coordo':
                    merge_data['created_on_coo'] = True
                    if context.get('sync_update_execution'):
                        del(new_ctx['sync_update_execution'])  # otherwise product.merged record does not have an xmlid
                self.pool.get('product.merged').create(cr, 1, merge_data, context=new_ctx)
        else:
            if not context.get('sync_update_execution'):
                self.pool.get('product.merged').create(cr, 1, {'new_product_id': kept_id, 'old_product_id': old_prod_id}, context=context)

        # reset mission stock on nsl + old to 0, will be computed on next mission stock update
        instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)
        if instance_id:  # US-12845: To prevent issues during first synch when the instance has not been fully created
            mission_stock_fields_reset = [
                'stock_qty', 'stock_val',
                'in_pipe_coor_qty', 'in_pipe_coor_val', 'in_pipe_qty', 'in_pipe_val',
                'secondary_qty', 'secondary_val',
                'eprep_qty',
                'cu_qty', 'cu_val',
                'cross_qty', 'cross_val',
                'wh_qty', 'internal_qty',
                'quarantine_qty', 'input_qty', 'opdd_qty'
            ]
            cr.execute('''
                update stock_mission_report_line set ''' + ', '.join(['%s=%%(zero)s' % field for field in mission_stock_fields_reset]) + '''
                    where
                    mission_report_id in (select id from stock_mission_report where full_view='f' and instance_id=%(local_instance_id)s) and
                    product_id in %(product_ids)s
            ''', {'zero': 0, 'local_instance_id': instance_id,  'product_ids': (kept_id, old_prod_id)})  # not_a_user_entry
            cr.execute("update stock_move set included_in_mission_stock='f' where product_id=%s", (kept_id, ))

        return True

    def merge_product(self, cr, uid, new_prod_id, old_prod_id, local, context=None):
        """
        Method used at COO level to merge a local product to a UD product + executed by sync on project
        Or used at COO level to merge a local product to a local product + executed by sync on project
        """
        if context is None:
            context = {}

        if not local:
            new_data = self.read(cr, uid, new_prod_id, ['default_code','old_code', 'allow_merge', 'product_tmpl_id'], context=context)
            if not new_data['allow_merge']:
                raise osv.except_osv(_('Warning'), _('New product %s condition not met') % new_data['default_code'])

        old_prod_dom = [('id', '=', old_prod_id), ('international_status', '=', 'Local'), ('replaced_by_product_id', '=', False)]
        if not context.get('sync_update_execution'):
            old_prod_dom += [('active', '=', True)]
        else:
            old_prod_dom += [('active', 'in', ['t', 'f'])]

        if not self.search_exist(cr, uid, old_prod_dom, context=context):
            old_prod = self.read(cr, uid, old_prod_id, ['default_code'], context=context)
            raise osv.except_osv(_('Warning'), _('Old merged product %s: condition not met: active, local product') % old_prod['default_code'])


        self._global_merge_product(cr, uid, new_prod_id, old_prod_id, 'coo', local, context=context)
        return True

    def onchange_batch_management(self, cr, uid, ids, batch_management, context=None):
        '''
        batch management is modified -> modification of Expiry Date Mandatory (perishable)
        '''
        if batch_management:
            return {'value': {'perishable': True}}
        return {}

    def check_exist_srml_stock(self, cr, uid, product_id, context=None):
        '''
        Check if there is stock in the Stock Mission Report Lines for a specific product
        '''
        if context is None:
            context = {}

        if not product_id:
            raise osv.except_osv(_('Error'), _('Please specify which product to check'))
        srml_domain = [
            ('product_id', '=', product_id),
            '|', '|', '|', '|', '|', '|', '|', '|', '|', '|',
            ('stock_qty', '>', 0), ('in_pipe_coor_qty', '>', 0), ('cross_qty', '>', 0), ('in_pipe_qty', '>', 0),
            ('cu_qty', '>', 0), ('wh_qty', '>', 0), ('secondary_qty', '>', 0), ('internal_qty', '>', 0),
            ('quarantine_qty', '>', 0), ('input_qty', '>', 0), ('opdd_qty', '>', 0)
        ]
        return self.pool.get('stock.mission.report.line').search_exist(cr, uid, srml_domain, context=context)

    def debug_ud(self, cr, uid, ids, context=None):
        ud = unidata_sync.ud_sync(cr, uid, self.pool, logger=logging.getLogger('single-ud-sync'), max_retries=1,  hidden_records=True, context=context)
        for x in self.read(cr, uid, ids, ['msfid', 'default_code'], context=context):
            if x['msfid']:
                try:
                    p = ud.query(q_filter='msfIdentifier=%d'%x['msfid'])
                    wizard_obj = self.pool.get('physical.inventory.import.wizard')
                    return wizard_obj.message(cr, uid, title=_('API Result'), message=json.dumps(p, indent=2))
                except requests.exceptions.HTTPError as e:
                    raise osv.except_osv(_('Error'), _('Unidata error: %s, did you configure the UniData sync ?') % e.response)
            else:
                raise osv.except_osv(_('Error'), _('MSFID not set on product %s') % (x['default_code'], ))
        return True

    def pull_ud(self, cr, uid, ids, context=None):
        for x in self.read(cr, uid, ids, ['msfid'] , context=context):
            wiz_id = self.pool.get('product.pull_single_ud').create(cr, uid, {'msfid': x['msfid'] or False}, context=context)
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'product.pull_single_ud',
                'res_id': wiz_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context,
                'height': '190px',
                'width': '420px',
            }



    def open_mml_nonconform_report(self, cr, uid, ids, context=None):
        instance_level = self.pool.get('res.company')._get_instance_level(cr, uid)

        if instance_level == 'section':
            report = 'report.hq_product_mml_nonconform'
        else:
            report = 'report.product_mml_nonconform'

        wiz_id = self.pool.get('non.conform.inpipe').create(cr, uid, {'name': report}, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'non.conform.inpipe',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': [wiz_id],
            'context': context,
            'height': '200px',
            'width': '720px',
        }


    def open_msl_nonconform_report(self, cr, uid, ids, context=None):
        wiz_id = self.pool.get('non.conform.inpipe').create(cr, uid, {'name': 'report.product_msl_nonconform'}, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'non.conform.inpipe',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': [wiz_id],
            'context': context,
            'height': '200px',
            'width': '720px',
        }


    _constraints = [
        (_check_gmdn_code, 'Warning! GMDN code must be digits!', ['gmdn_code'])
    ]


product_attributes()


class product_merged(osv.osv):
    """
        Object mainly used to trigger sync update
    """

    _name = 'product.merged'
    _description = 'Products merged (NSL from Coo / UD from HQ / Local from Coo)'
    _rec_name = 'new_product_id'

    _columns = {
        'new_product_id': fields.many2one('product.product', 'UD NSL Product', required=1, select=1),
        'old_product_id': fields.many2one('product.product', 'Old local Product', required=1, select=1),
        'level': fields.char('Level', size=16),
        'created_on_coo': fields.boolean('Created on coo'),
    }

    _defaults = {
        'level': 'coordo',
    }

    def _auto_init(self, cr, context=None):
        res = super(product_merged, self)._auto_init(cr, context)
        cr.drop_constraint_if_exists('product_merged', 'product_merged_unique_new_product_id')
        return res

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        prod_obj = self.pool.get('product.product')

        new_id  = super(product_merged, self).create(cr, uid, vals, context=context)
        if context.get('sync_update_execution') and not vals.get('created_on_coo'):
            if vals.get('level') == 'section':
                prod_obj.merge_hq_product(cr, uid, vals['new_product_id'], vals['old_product_id'], context=context)
            else:
                status_local_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_4')[1]
                old_prod = prod_obj.read(cr, uid, vals['old_product_id'], ['international_status'], context=context)
                new_prod = prod_obj.read(cr, uid, vals['new_product_id'], ['international_status'], context=context)

                if old_prod['international_status'][0] == new_prod['international_status'][0] == status_local_id:
                    # For the merge of 2 local products
                    prod_obj.merge_product(cr, uid, vals['new_product_id'], vals['old_product_id'], True, context=context)
                else:
                    prod_obj.merge_product(cr, uid, vals['new_product_id'], vals['old_product_id'], False, context=context)

        return new_id

    _sql_constraints = [
        ('unique_old_product_id', 'unique(old_product_id, created_on_coo)', 'Local product already merged'),
    ]

product_merged()

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

    def return_to_product(self, cr, uid, ids, context=None):
        """
        When close the wizard view, reload the product view
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of product.deactivation.wizard
        :param context: Context of the call
        :return: A dictionary with parameters to reload the view
        """
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': self.browse(cr, uid, ids[0], context=context).product_id.id,
            'target': 'test',
            'context': context,
        }

product_deactivation_error()

class product_deactivation_error_line(osv.osv_memory):
    _name = 'product.deactivation.error.line'

    _columns = {
        'error_id': fields.many2one('product.deactivation.error', string='Error', readonly=True),
        'type': fields.char(size=64, string='Documents type'),
        'internal_type': fields.char(size=64, string='Internal document type'),
        'doc_ref': fields.char(size=128, string='Reference'),
        'doc_id': fields.integer(string='Internal Reference'),
        'view_id': fields.integer(string='Reference of the view to open'),
    }

    def open_doc(self, cr, uid, ids, context=None):
        '''
        Open the associated documents
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            if line.internal_type == 'stock.picking':
                pick_obj = self.pool.get('stock.picking')
                xmlid = pick_obj._hook_picking_get_view(cr, uid, [line.doc_id], context=context, pick=pick_obj.browse(cr, uid, line.doc_id))
                res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, xmlid, ['form', 'tree'],context=context)
                res['res_id'] = line.doc_id
                res['target'] = 'current'
                res['keep_open'] = True
                return res

            # Invoices
            if line.internal_type == 'account.invoice' and line.doc_id:
                inv_obj = self.pool.get('account.invoice')
                doc_type = inv_obj.read(cr, uid, line.doc_id, ['doc_type'], context=context)['doc_type']
                action_xmlid = inv_obj._invoice_action_act_window.get(doc_type)
                if not action_xmlid:
                    raise osv.except_osv(_('Warning'), _('Impossible to retrieve the view to display.'))
                res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, action_xmlid, ['form', 'tree'], context=context)
                res['res_id'] = line.doc_id
                res['target'] = 'current'
                res['keep_open'] = True
                return res

            view_id, context = self._get_view(cr, uid, line, context=context)
            return {'type': 'ir.actions.act_window',
                    'name': line.type,
                    'res_model': line.internal_type,
                    'res_id': line.doc_id,
                    'view_mode': 'form,tree',
                    'view_type': 'form',
                    'target': 'current',
                    'view_id': view_id,
                    'keep_open': True,
                    'context': context}

    def _get_view(self, cr, uid, line, context=None):
        '''
        Return the good view according to the type of the object
        '''
        if context is None:
            context = {}

        view_id = False
        obj = self.pool.get(line.internal_type).browse(cr, uid, line.doc_id)

        if line.internal_type == 'composition.kit':
            context.update({'composition_type': 'theoretical'})
            if obj.composition_type == 'real':
                context.update({'composition_type': 'real'})
        elif line.internal_type == 'stock.picking':
            view_id = self.pool.get('stock.picking')._hook_picking_get_view(cr, uid, [line.doc_id], context=context, pick=obj)
        elif line.internal_type == 'sale.order':
            context.update({'procurement_request': obj.procurement_request})
        elif line.internal_type == 'purchase.order':
            context.update({'rfq_ok': obj.rfq_ok})
        if view_id:
            view_id = [view_id[1]]

        return view_id, context

product_deactivation_error_line()


class pricelist_partnerinfo(osv.osv):
    _inherit = 'pricelist.partnerinfo'

    def onchange_uom_qty(self, cr, uid, ids, uom_id, min_quantity, min_order_qty):
        '''
        Check the rounding of the qty according to the rounding of the UoM
        '''
        res = {}

        if uom_id and min_quantity:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, min_quantity, 'min_quantity', res)

        if uom_id and min_order_qty:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, min_order_qty, 'min_order_qty', res)

        return res

pricelist_partnerinfo()


class product_uom(osv.osv):
    _inherit = 'product.uom'

    def _get_dummy(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for id in ids:
            res[id] = True

        return res


    def _get_compatible_uom(self, cr, uid, obj, name, args, context=None):
        res = []

        for arg in args:
            if arg[0] == 'compatible_product_id':
                if not arg[2]:
                    return []
                elif isinstance(arg[2], int):
                    product = self.pool.get('product.product').browse(cr, uid, arg[2], context=context)
                    return [('category_id', '=', product.uom_id.category_id.id)]

        return res

    _columns = {
        'compatible_product_id': fields.function(_get_dummy, fnct_search=_get_compatible_uom, method=True, type='boolean', string='Compatible UoM'),
    }

    def unlink(self, cr, uid, ids, context=None):
        """
        Check if the deleted product category is not a system one
        """
        data_obj = self.pool.get('ir.model.data')

        uom_data_id = [
            'uom_tbd',
        ]

        for data_id in uom_data_id:
            try:
                uom_id = data_obj.get_object_reference(
                    cr, uid, 'msf_doc_import', data_id)[1]
                if uom_id in ids:
                    uom_name = self.read(cr, uid, uom_id, ['name'])['name']
                    raise osv.except_osv(
                        _('Error'),
                        _("The UoM '%s' is an Unifield internal Uom, so you can't remove it" % uom_name),
                    )
            except ValueError:
                pass

        return super(product_uom, self).unlink(cr, uid, ids, context=context)


product_uom()


class change_bn_ed_mandatory_wizard(osv.osv_memory):
    _name = 'change.bn.ed.mandatory.wizard'

    _columns = {}

    def yes_change_bn_ed_mandatory(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if context.get('prod_data'):
            self.pool.get('product.product')._apply_change_bn_ed(cr, uid, [context['prod_data']['id']], context['prod_data']['change_target'], context=context)

        return {'type': 'ir.actions.act_window_close'}

    def no_change_bn_ed_mandatory(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if context.get('prod_data'):
            context.pop('prod_data')

        return {'type': 'ir.actions.act_window_close'}


change_bn_ed_mandatory_wizard()


class product_pull_single_ud(osv.osv_memory):
    _name = 'product.pull_single_ud'
    rec_name = 'msfid'
    _columns = {
        'msfid': fields.integer_null('MSFID'),
    }

    def pull_product(self, cr, uid, ids, context=None):
        session_obj = self.pool.get('unidata.sync.log')
        act_obj = self.pool.get('ir.actions.act_window')
        for x in self.read(cr, uid, ids, ['msfid'], context=context):
            if x['msfid']:
                session_id = session_obj.create(cr, uid, {'manual_single': True, 'server': 'ud', 'start_date': fields.datetime.now(), 'state': 'running', 'sync_type': 'single', 'msfid_min': x['msfid']}, context=context)
                ud = unidata_sync.ud_sync(cr, uid, self.pool, logger=logging.getLogger('single-ud-sync'), max_retries=1, hidden_records=True, context=context)
                try:
                    trash1, nb_prod, updated, total_nb_created, total_nb_errors = ud.update_products(q_filter='msfIdentifier=%d'%x['msfid'], record_date=False, session_id=session_id, create_missing_nomen=True)
                except requests.exceptions.HTTPError as e:
                    raise osv.except_osv(_('Error'), _('Unidata error: %s, did you configure the UniData sync ?') % e.response)
                except Exception:
                    raise
            else:
                raise osv.except_osv(_('Error'), _('Error: msfid is required'))

        session_obj.write(cr, uid, session_id, {'end_date': fields.datetime.now(), 'state': 'done', 'number_products_pulled': nb_prod, 'number_products_updated': updated, 'number_products_created': total_nb_created, 'number_products_errors': total_nb_errors}, context=context)

        p_ids = self.pool.get('product.product').search(cr, uid, [('msfid', '=', x['msfid'])], context=context)
        if p_ids:
            if len(p_ids) == 1:
                view = act_obj.open_view_from_xmlid(cr, uid, 'product.product_normal_action', ['form', 'tree'], context=context)
                view['res_id'] = p_ids[0]
            else:
                view = act_obj.open_view_from_xmlid(cr, uid, 'product.product_normal_action', context=context)
                view['domain'] = [('id','in', p_ids)]
        else:
            view = act_obj.open_view_from_xmlid(cr, uid, 'product_attributes.unidata_sync_log_action', ['form', 'tree'], new_tab=True, context=context)
            view['res_id'] = session_id
        return view

product_pull_single_ud()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
