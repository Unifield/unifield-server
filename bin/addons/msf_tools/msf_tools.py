# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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

import time
import tools
import re

from tools.translate import _
from datetime import datetime
from datetime import date
from decimal import Decimal, ROUND_UP
import math

import netsvc
from zipfile import ZipFile
from io import BytesIO
from base64 import b64encode
from tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import logging
import threading
import traceback
import pooler
from msf_doc_import.msf_import_export_conf import MODEL_DICT

class lang(osv.osv):
    '''
    define getter for date / time / datetime formats
    '''
    _inherit = 'res.lang'

    def _get_format(self, cr, uid, type, context=None):
        '''
        generic function
        '''
        if context is None:
            context = {}
        type = type + '_format'
        assert type in self._columns, 'Specified format field does not exist'
        user_obj = self.pool.get('res.users')
        # get user context lang
        user_lang = user_obj.read(cr, uid, uid, ['context_lang'], context=context)['context_lang']
        # get coresponding id
        lang_id = self.search(cr, uid, [('code','=',user_lang)])
        # return format value or from default function if not exists
        format = lang_id and self.read(cr, uid, lang_id[0], [type], context=context)[type] or getattr(self, '_get_default_%s'%type)(cr, uid, context=context)
        return format

    def _get_db_format(self, cr, uid, type, context=None):
        '''
        generic function - for now constant values
        '''
        if context is None:
            context = {}
        if type == 'date':
            return '%Y-%m-%d'
        if type == 'time':
            return '%H:%M:%S'
        # default value
        return '%Y-%m-%d'
lang()


class date_tools(osv.osv):
    '''
    date related tools for msf project
    '''
    _name = 'date.tools'

    def get_date_format(self, cr, uid, context=None):
        '''
        get the date format for the uid specified user

        from msf_order_date module
        '''
        lang_obj = self.pool.get('res.lang')
        return lang_obj._get_format(cr, uid, 'date', context=context)

    def get_db_date_format(self, cr, uid, context=None):
        '''
        return constant value
        '''
        lang_obj = self.pool.get('res.lang')
        return lang_obj._get_db_format(cr, uid, 'date', context=context)

    def get_time_format(self, cr, uid, context=None):
        '''
        get the time format for the uid specified user

        from msf_order_date module
        '''
        lang_obj = self.pool.get('res.lang')
        return lang_obj._get_format(cr, uid, 'time', context=context)

    def get_db_time_format(self, cr, uid, context=None):
        '''
        return constant value
        '''
        lang_obj = self.pool.get('res.lang')
        return lang_obj._get_db_format(cr, uid, 'time', context=context)

    def get_datetime_format(self, cr, uid, context=None):
        '''
        get the datetime format for the uid specified user
        '''
        return self.get_date_format(cr, uid, context=context) + ' ' + self.get_time_format(cr, uid, context=context)

    def get_db_datetime_format(self, cr, uid, context=None):
        '''
        return constant value
        '''
        return self.get_db_date_format(cr, uid, context=context) + ' ' + self.get_db_time_format(cr, uid, context=context)

    def get_date_formatted(self, cr, uid, d_type='date', datetime=None, context=None):
        '''
        Return the datetime in the format of the user
        @param d_type: 'date' or 'datetime' : determines which is the out format
        @param datetime: date to format
        '''
        assert d_type in ('date', 'datetime'), 'Give only \'date\' or \'datetime\' as type parameter'

        if not datetime:
            datetime = time.strftime('%Y-%m-%d')

        if d_type == 'date':
            d_format = self.get_date_format(cr, uid)
            date_to_format = time.strptime(datetime, '%Y-%m-%d')
            return time.strftime(d_format, date_to_format)
        elif d_type == 'datetime':
            d_format = self.get_datetime_format(cr, uid)
            date_to_format = time.strptime(datetime, '%Y-%m-%d %H:%M:%S')
            return time.strftime(d_format, date_to_format)

    def orm2date(self, dt):
        if isinstance(dt, str):
            st = time.strptime(dt, DEFAULT_SERVER_DATE_FORMAT)
            dt = date(st[0], st[1], st[2])
        return dt

    def date2orm(self, dt):
        return dt.strftime(DEFAULT_SERVER_DATE_FORMAT)

    def datetime2orm(self, dt):
        return dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    def orm2datetime(self, dt):
        if isinstance(dt, str):
            st = time.strptime(dt, DEFAULT_SERVER_DATETIME_FORMAT)
            dt = datetime(st[0], st[1], st[2], st[3], st[4], st[5])
        return dt

date_tools()


class fields_tools(osv.osv):
    '''
    date related tools for msf project
    '''
    _name = 'fields.tools'

    def get_field_from_company(self, cr, uid, object=False, field=False, context=None):
        '''
        return the value for field from company for object
        '''
        # field is required for value
        if not field:
            return False
        # object
        company_obj = self.pool.get('res.company')
        # corresponding company
        company_id = company_obj._company_default_get(cr, uid, object, context=context)
        # get the value
        res = company_obj.read(cr, uid, [company_id], [field], context=context)[0][field]
        return res

    def get_selection_name(self, cr, uid, object=False, field=False, key=False, context=None):
        '''
        return the name from the key of selection field
        '''
        if not object or not field or not key:
            return False
        # get the selection values list
        if isinstance(object, str):
            object = self.pool.get(object)
        list = object._columns[field].selection
        name = [x[1] for x in list if x[0] == key][0]
        return name

    def get_ids_from_browse_list(self, cr, uid, browse_list=False, context=None):
        '''
        return the list of ids corresponding to browse list in parameter
        '''
        if not browse_list:
            return []

        result = [x.id for x in browse_list]
        return result

    def remove_sql_constraint(self, cr, table_name, field_name):
        """
        remove from field the constraint if it exists in current schema
        (orm does not remove _sql_constraint removed items)
        """
        # table name and constraint name (tablename_fieldname) params
        sql_params = (table_name, "%s_%s" % (table_name, field_name, ), )
        tpl_has_const = "select count(constraint_name) from" \
            " information_schema.constraint_column_usage where" \
            " table_name=%s and constraint_name=%s"
        cr.execute(tpl_has_const, sql_params)
        res_record = cr.fetchone()
        if res_record and res_record[0]:
            # drop existing constraint
            tpl_drop_const = "alter table %s drop constraint %s" % sql_params  # not_a_user_entry
            cr.execute(tpl_drop_const)

    def domain_get_field_index(self, domain, field_name):
        """
        get field tuple index in domain
        :return: index or < 0 if not found
        :rtype: int
        """
        index = 0
        if domain:
            for t in domain:
                if t[0] == field_name:
                    return index
                index += 1
        return -1

    def domain_remove_field(self, domain, field_names):
        """
        remove field(s) tuple(s) in domain
        :param field_names: field(s) to remove
        :type field_names: str/list/tuple
        :return: new domain
        """
        if not isinstance(field_names, (list, tuple )):
            field_names = [ field_names, ]
        res = []
        for t in domain:
            if t[0] not in field_names:
                res.append(t)
        return res

fields_tools()


class data_tools(osv.osv):
    '''
    data related tools for msf project
    '''
    _name = 'data.tools'

    def load_common_data(self, cr, uid, ids, context=None):
        '''
        load common data into context
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
        date = time.strftime(db_date_format)
        context['common']['date'] = date
        # default company id
        company_id = comp_obj._company_default_get(cr, uid, 'stock.picking', context=context)
        context['common']['company_id'] = company_id

        # stock location
        stock_id = obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
        context['common']['stock_id'] = stock_id
        # kitting location
        kitting_id = obj_data.get_object_reference(cr, uid, 'stock', 'location_production')[1]
        context['common']['kitting_id'] = kitting_id
        # input location
        input_id = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]
        context['common']['input_id'] = input_id
        # quarantine analyze
        quarantine_anal = obj_data.get_object_reference(cr, uid, 'stock_override', 'stock_location_quarantine_analyze')[1]
        context['common']['quarantine_anal'] = quarantine_anal
        # expired / damaged / for scrap
        exp_dam_scrap = obj_data.get_object_reference(cr, uid, 'stock_override', 'stock_location_quarantine_scrap')[1]
        context['common']['exp_dam_scrap'] = exp_dam_scrap
        # log
        log = obj_data.get_object_reference(cr, uid, 'stock_override', 'stock_location_logistic')[1]
        context['common']['log'] = log
        # cross docking
        cross_docking = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        context['common']['cross_docking'] = cross_docking

        # kit reason type
        reason_type_id = obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_kit')[1]
        context['common']['reason_type_id'] = reason_type_id
        # reason type goods return
        rt_goods_return = obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_goods_return')[1]
        context['common']['rt_goods_return'] = rt_goods_return
        # reason type goods replacement
        rt_goods_replacement = obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_goods_replacement')[1]
        context['common']['rt_goods_replacement'] = rt_goods_replacement
        # reason type internal supply
        rt_internal_supply = obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_supply')[1]
        context['common']['rt_internal_supply'] = rt_internal_supply

        return True

    def truncate_list(self, item_list, limit=300, separator=', '):
        """
        Returns a string corresponding to the list of items in parameter, separated by the "separator".
        If the string > "limit", cuts it and adds "..." at the end.
        """
        list_str = separator.join([item for item in item_list if item]) or ''
        if len(list_str) > limit:
            list_str = "%s%s" % (list_str[:limit-3], '...')
        return list_str

    def replace_line_breaks(self, string_to_format):
        """
        Modifies the string in parameter:
        - replaces the line breaks by spaces if they are in the middle of the string
        - replaces non-breakable spaces by ordinary spaces
        - removes the line breaks and the spaces at the beginning and at the end
        """
        return re.sub('[\r\n\xc2\xa0]', ' ', string_to_format or '').strip()

    def replace_line_breaks_from_vals(self, vals, fields, replace=None):
        """
        Updates the vals (dict) in param.
        For each of the fields (list) in param which is found in vals, applies "replace_line_breaks" to its value.
        If the value of a field listed in the "replace" list (usually a mandatory field) ends up empty, its empty value is replaced by "/".
        """
        if replace is None:
            replace = []
        default_char = '/'
        for field in fields:
            if vals.get(field):
                new_value = self.replace_line_breaks(vals[field])
                if not new_value and field in replace:
                    new_value = default_char
                vals.update({field: new_value})
            elif field in vals and field in replace:
                vals.update({field: default_char})
        return True


data_tools()


class sequence_tools(osv.osv):
    '''
    sequence tools
    '''
    _name = 'sequence.tools'

    def reorder_sequence_number(self, cr, uid, base_object, base_seq_field, dest_object, foreign_field, foreign_ids, seq_field, context=None):
        '''
        receive a browse list corresponding to one2many lines
        recompute numbering corresponding to specified field
        compute next number of sequence

        we must make sure we reorder in conservative way according to original order

        *not used presently*
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(foreign_ids, int):
            foreign_ids = [foreign_ids]

        # objects
        base_obj = self.pool.get(base_object)
        dest_obj = self.pool.get(dest_object)

        for foreign_id in foreign_ids:
            # will be ordered by default according to db id, it's what we want according to user sequence
            item_ids = dest_obj.search(cr, uid, [(foreign_field, '=', foreign_id)], context=context)
            if item_ids:
                # read line number and id from items
                item_data = dest_obj.read(cr, uid, item_ids, [seq_field], context=context)
                # check the line number: data are ordered according to db id, so line number must be equal to index+1
                for i in range(len(item_data)):
                    if item_data[i][seq_field] != i+1:
                        dest_obj.write(cr, uid, [item_data[i]['id']], {seq_field: i+1}, context=context)
                # reset sequence to length + 1 all time, checking if needed would take much time
                # get the sequence id
                seq_id = base_obj.read(cr, uid, foreign_id, [base_seq_field], context=context)[base_seq_field][0]
                # we reset the sequence to length+1
                self.reset_next_number(cr, uid, [seq_id], value=len(item_ids)+1, context=context)

        return True

    def reorder_sequence_number_from_unlink(self, cr, uid, ids, base_object, base_seq_field, dest_object, foreign_field, seq_field, context=None):
        '''
        receive a browse list corresponding to one2many lines
        recompute numbering corresponding to specified field
        compute next number of sequence

        for unlink, only items with id > min(deleted id) are resequenced + reset the sequence value

        we must make sure we reorder in conservative way according to original order

        this method is called from methods of **destination object**
        '''
        # Some verifications
        if context is None:
            context = {}
        # if no ids as parameter return Tru
        if not ids:
            return True

        # objects
        base_obj = self.pool.get(base_object)
        dest_obj = self.pool.get(dest_object)
        audit_obj = self.pool.get('audittrail.rule')

        to_trace = dest_obj.check_audit(cr, uid, 'write')

        # find the corresponding base ids
        base_ids = [x[foreign_field][0] for x in dest_obj.read(cr, uid, ids, [foreign_field], context=context) if x[foreign_field]]
        # simulate unique sql
        foreign_ids = set(base_ids)

        for foreign_id in foreign_ids:
            # will be ordered by default according to db id, it's what we want according to user sequence
            # reorder only ids bigger than min deleted + do not select deleted ones
            item_ids = dest_obj.search(cr, uid, [('id', '>', min(ids)), (foreign_field, '=', foreign_id), ('id', 'not in', ids)], context=context)
            # start numbering sequence
            start_num = 0
            # if deleted object is not the first one, we find the numbering value of previous one
            before_ids = dest_obj.search(cr, uid, [('id', '<', min(ids)), (foreign_field, '=', foreign_id)], context=context)
            if before_ids:
                # we read the numbering value of previous value (biggest id)
                start_num = dest_obj.read(cr, uid, max(before_ids), [seq_field], context=context)[seq_field]
            if item_ids:
                # read line number and id from items
                item_data = dest_obj.read(cr, uid, item_ids, [seq_field], context=context)
                # check the line number: data are ordered according to db id, so line number must be equal to index+1
                for i in range(len(item_data)):
                    # numbering value
                    start_num = start_num+1
                    if item_data[i][seq_field] != start_num:
                        # Create the audittrail log line if the object is traceable
                        if to_trace:
                            previous_values = dest_obj.read(cr, uid, [item_data[i]['id']], [seq_field], context=context)
                            audit_obj.audit_log(cr, uid, to_trace, dest_obj, [item_data[i]['id']], 'write', previous_values, {item_data[i]['id']: {seq_field: start_num}}, context=context)

                        cr.execute("update "+dest_obj._table+" set "+seq_field+"=%s where id=%s", (start_num, item_data[i]['id']))  # not_a_user_entry
                        #dest_obj.write(cr, uid, [item_data[i]['id']], {seq_field: start_num}, context=context)

            # reset sequence to start_num + 1 all time, checking if needed would take much time
            # get the sequence id
            seq_id = base_obj.read(cr, uid, foreign_id, [base_seq_field], context=context)[base_seq_field][0]
            # we reset the sequence to length+1, whether or not items
            self.reset_next_number(cr, uid, [seq_id], value=start_num+1, context=context)

        return True

    def reset_next_number(self, cr, uid, seq_ids, value=1, context=None):
        '''
        reset the next number of the sequence to value, default value 1
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(seq_ids, int):
            seq_ids = [seq_ids]

        # objects
        seq_obj = self.pool.get('ir.sequence')
        seq_obj.write(cr, uid, seq_ids, {'number_next': value}, context=context)
        return True

    def create_sequence(self, cr, uid, vals, name, code, prefix='', padding=0, context=None):
        '''
        create a new sequence
        '''
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        assert name, 'create sequence: missing name'
        assert code, 'create sequence: missing code'

        types = {'name': name,
                 'code': code
                 }
        seq_typ_pool.create(cr, uid, types)

        seq = {'name': name,
               'code': code,
               'prefix': prefix,
               'padding': padding,
               }
        return seq_pool.create(cr, uid, seq)

sequence_tools()


class picking_tools(osv.osv):
    '''
    picking related tools
    '''
    _name = 'picking.tools'

    def confirm(self, cr, uid, ids, context=None):
        '''
        confirm the picking
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # objects
        pick_obj = self.pool.get('stock.picking')
        pick_obj.draft_force_assign(cr, uid, ids, context)
        return True

    def check_assign(self, cr, uid, ids, context=None):
        '''
        check assign the picking
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # objects
        pick_obj = self.pool.get('stock.picking')
        pick_obj.action_assign(cr, uid, ids, context=context)
        return True

    def force_assign(self, cr, uid, ids, context=None):
        '''
        force assign the picking
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # objects
        pick_obj = self.pool.get('stock.picking')
        pick_obj.force_assign(cr, uid, ids, context)
        return True

    def validate(self, cr, uid, ids, context=None):
        '''
        validate the picking
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # objects
        pick_obj = self.pool.get('stock.picking')
        wf_service = netsvc.LocalService("workflow")
        # trigger standard workflow for validated picking ticket
        for id in ids:
            pick_obj.action_move(cr, uid, [id])
            wf_service.trg_validate(uid, 'stock.picking', id, 'button_done', cr)
        return True

    def all(self, cr, uid, ids, context=None):
        '''
        confirm - check - validate
        '''
        self.confirm(cr, uid, ids, context=context)
        self.check_assign(cr, uid, ids, context=context)
        self.validate(cr, uid, ids, context=context)
        return True

picking_tools()


class ir_translation(osv.osv):
    _name = 'ir.translation'
    _inherit = 'ir.translation'

    def tr_view(self, cr, name, context):
        if not context or not context.get('lang'):
            return name
        tr = self._get_source(cr, 1, False, 'view', context['lang'], name, True)
        if not tr:
            # sometimes de view name is empty and so the action name is used as view name
            tr2 = self._get_source(cr, 1, 'ir.actions.act_window,name', 'model', context['lang'], name)
            if tr2:
                return tr2
            return name
        return tr

    @tools.cache(skiparg=3, multi='ids')
    def _get_ids(self, cr, uid, name, tt, lang, ids):
        res = dict.fromkeys(ids, False)
        if ids:
            cr.execute('''SELECT res_id, value
                       FROM ir_translation
                       WHERE lang=%s
                       AND type=%s
                       AND name=%s
                       AND res_id IN %s''',
                       (lang, tt, name, tuple(ids)))
            for res_id, value in cr.fetchall():
                res[res_id] = value

            # US-394: If translation not found by res_id, search by xml_id
            for id in ids:
                if res[id] == False:
                    current_id = id
                    # Get the model name
                    if ',' in name:
                        model_name = name.split(",")[0]
                    else:
                        model_name = name
                    # product.template have not xml_id
                    if "product.template" in model_name:
                        model_name = 'product.product'
                        cr.execute('''SELECT id
                                   FROM product_product
                                   WHERE product_tmpl_id=%s''',
                                   ([current_id]))

                        for prod_id in cr.fetchall():
                            current_id = prod_id

                    # Search xml_id in ir_model_data
                    cr.execute('''SELECT name
                               FROM ir_model_data
                               WHERE module='sd' AND model=%s AND res_id=%s''',
                               (model_name, current_id))

                    for xml_id in cr.fetchall():
                        # Search in translation by xml_id
                        cr.execute('''SELECT value
                            FROM ir_translation
                            WHERE lang=%s
                            AND type=%s
                            AND name=%s
                            AND xml_id=%s''',
                                   (lang, tt, name, xml_id))
                        for value in cr.fetchall():
                            res[id] = value[0]
        return res

    def get_xml_id(self, cr, uid, vals, context=None):
        res = None

        if vals.get('name', False) and vals.get('res_id', False):
            name = vals['name']
            if ',' in name:
                model_name = name.split(",")[0]
            else:
                model_name = name

            if "ir.model.data" not in model_name:
                target_ids = vals['res_id']

                # product.template xml_id is not create, so we search the product.product xml_id
                if "product.template" in model_name:
                    target_ids = self.pool.get('product.product')\
                        .search(cr, uid, [('product_tmpl_id', '=', target_ids),
                                          ('active', 'in', ('t', 'f'))], context=context)
                    model_name = 'product.product'

                if isinstance(target_ids, int):
                    target_ids = [target_ids]
                target = self.pool.get(model_name)
                if target:
                    if hasattr(target, "get_sd_ref") and self.pool.get('sync.client.entity'):
                        res = list(target.get_sd_ref(cr, uid, target_ids).values())[0]
        return res

    def _get_res_id(self, cr, uid, name, sdref, context=None):
        tr_split = name.split(',')
        res_id = self.pool.get('ir.model.data').find_sd_ref(cr, 1, sdref, field='res_id', context=context)
        if res_id and tr_split[0] == 'product.template':
            prod = self.pool.get('product.product').read(cr, 1, [res_id], ['product_tmpl_id'], context=context)
            if prod and prod[0]['product_tmpl_id']:
                return prod[0]['product_tmpl_id'][0]
        return res_id

    def _audit_translatable_fields(self, cr, uid, ids, vals, context=None):
        """
        Fills in the Track Changes for translatable fields at synchro time,
        e.g. track the updates received on journal name in the Track Changes of the Journal object
        """
        fields = ['product.template,name', 'account.account,name', 'account.analytic.account,name',
                  'account.journal,name', 'account.analytic.journal,name']
        if context is None:
            context = {}
        if context.get('sync_update_execution') and vals.get('name') in fields and vals.get('lang'):
            if vals.get('name') == 'account.analytic.account,name' and vals.get('lang') == 'en_MF' and vals['value']:
                # translations removed on anaylitc account name, but still in (init) sync
                obj_id = False
                if vals.get('res_id'):
                    obj_id = vals['res_id']
                elif vals.get('xml_id'):
                    obj_id = self._get_res_id(cr, uid, vals['name'], vals['xml_id'], context=context)
                if obj_id:
                    self.pool.get('account.analytic.account').write(cr, uid, obj_id, {'name': vals['value']}, context=context)
                return True

            obj_name = vals['name'].split(',')[0]
            obj = self.pool.get(obj_name)
            audit_rule_ids = obj.check_audit(cr, uid, 'write')
            if audit_rule_ids:
                new_ctx = context.copy()
                new_ctx['lang'] = vals['lang']
                template_id = vals.get('res_id')
                if not template_id and ids:
                    template_id = self.browse(cr, uid, ids[0], fields_to_fetch=['res_id'], context=new_ctx).res_id
                if template_id:
                    previous = obj.read(cr, uid, [template_id], ['name'], context=new_ctx)[0]
                    audit_obj = self.pool.get('audittrail.rule')
                    audit_obj.audit_log(cr, uid, audit_rule_ids, obj, template_id, 'write', previous, {template_id: {'name': vals['value']}} , context=context)



    def write(self, cr, uid, ids, vals, clear=False, context=None):
        self._audit_translatable_fields(cr, uid, ids, vals, context=context)
        return super(ir_translation, self).write(cr, uid, ids, vals, clear=clear, context=context)


    # US_394: Remove duplicate lines for ir.translation
    def create(self, cr, uid, vals, clear=True, context=None):
        if context is None:
            context = {}
        domain = []
        # Search xml_id
        if context.get('sync_update_execution') and vals.get('xml_id') and vals.get('name') and not vals.get('res_id'):
            vals['res_id'] = self._get_res_id(cr, uid, vals['name'], vals['xml_id'], context=context)

        if not vals.get('xml_id', False):
            vals['xml_id'] = self.get_xml_id(cr, uid, vals, context=context)

        if vals.get('xml_id') or vals.get('res_id'):
            domain.append('&')
            domain.append('&')

            if vals.get('type') != 'model' and vals.get('src'):
                domain.append(('src', '=', vals['src']))
            if vals.get('lang'):
                domain.append(('lang', '=', vals['lang']))
            if vals.get('name'):
                domain.append(('name', '=', vals['name']))
            if vals.get('xml_id') and vals.get('res_id'):
                domain.append('|')
                domain.append(('xml_id', '=', vals['xml_id']))
                domain.append(('res_id', '=', vals['res_id']))
            elif vals.get('res_id'):
                domain.append(('res_id', '=', vals['res_id']))
            elif vals.get('xml_id'):
                domain.append(('xml_id', '=', vals['xml_id']))

            existing_ids = self.search(cr, uid, domain)
            if existing_ids:
                if len(existing_ids) > 1:
                    ids = existing_ids[0:1]
                    del_ids = existing_ids[1:]
                    self.unlink(cr, uid, del_ids, context=context)
                else:
                    ids = existing_ids
                self.write(cr, uid, ids, vals, context=context)
                return ids[0]

        if context.get('sync_update_execution') and vals.get('res_id') and vals.get('lang'):
            self._audit_translatable_fields(cr, uid, False, vals, context=context)

        return super(ir_translation, self).create(cr, uid, vals, clear=clear, context=context)

    # US_394: add xml_id for each lines
    def add_xml_ids(self, cr, uid, context=None):
        domain = [('type', '=', 'model'), ('xml_id', '=', False)]
        translation_ids = self.search(cr, uid, domain, context=context)
        translation_obj = self.browse(cr, uid, translation_ids, context=context)
        for translation in translation_obj:
            v = {'name': translation.name, 'res_id': translation.res_id}
            xml_id = self.get_xml_id(cr, uid, v, context=context)
            vals = {'xml_id': xml_id}
            self.write(cr, uid, translation['id'], vals, context=context)
        return

    # US_394: remove orphean ir.translation lines
    def clean_translation(self, cr, uid, context=None):
        unlink_ids = []
        domain = [('type', '=', 'model')]
        translation_ids = self.search(cr, uid, domain, context=context)
        translation_obj = self.browse(cr, uid, translation_ids, context=context)
        for translation in translation_obj:
            parent_name = translation.name.split(',')[0]

            obj = self.pool.get(parent_name)
            sql = "SELECT id FROM " + obj._table + " WHERE id=%s"  # not_a_user_entry
            cr.execute(sql, (translation.res_id,))
            res = cr.fetchall()
            if not res:
                unlink_ids.append(translation.id)
        if unlink_ids:
            if self.pool.get('sync.client.entity'):
                self.purge(cr, uid, unlink_ids, context=context)
            else:
                self.unlink(cr, uid, unlink_ids, context=context)
        return

ir_translation()


class uom_tools(osv.osv_memory):
    """
    This osv_memory class helps to check certain consistency related to the UOM.
    """
    _name = 'uom.tools'

    def check_uom(self, cr, uid, product_id, uom_id, context=None):
        """
        Check the consistency between the category of the UOM of a product and the category of a UOM.
        Return a boolean value (if false, it will raise an error).
        :param cr: database cursor
        :param product_id: takes the id of a product
        :param product_id: takes the id of a uom
        Note that this method is not consistent with the onchange method that returns a dictionary.
        """
        if context is None:
            context = {}
        if product_id and uom_id:
            if isinstance(product_id, int):
                product_id = [product_id]
            if isinstance(uom_id, int):
                uom_id = [uom_id]
            cr.execute(
                """
                SELECT COUNT(*)
                FROM product_uom AS uom,
                    product_template AS pt,
                    product_product AS pp,
                    product_uom AS uom2
                WHERE uom.id = pt.uom_id
                AND pt.id = pp.product_tmpl_id
                AND pp.id = %s
                AND uom2.category_id = uom.category_id
                AND uom2.id = %s""",
                (product_id[0], uom_id[0]))
            count = cr.fetchall()[0][0]
            return count > 0
        return True

uom_tools()


class product_uom(osv.osv):
    _inherit = 'product.uom'

    def _compute_round_up_qty(self, cr, uid, uom_id, qty, context=None):
        '''
        Round up the qty according to the UoM
        '''
        uom = self.browse(cr, uid, uom_id, context=context)
        rounding_value = Decimal(str(uom.rounding).rstrip('0'))

        return float(Decimal(str(qty)).quantize(rounding_value, rounding=ROUND_UP))

    def _change_round_up_qty(self, cr, uid, uom_id, qty, fields_q=[], result=None, context=None):
        '''
        Returns the error message and the rounded value
        '''
        if not result:
            result = {'value': {}, 'warning': {}}

        if isinstance(fields_q, str):
            fields_q = [fields_q]

        message = {'title': _('Bad rounding'),
                   'message': _('The quantity entered is not valid according to the rounding value of the UoM. The product quantity has been rounded to the highest good value.')}

        if uom_id and qty:
            new_qty = self._compute_round_up_qty(cr, uid, uom_id, qty, context=context)
            if qty != new_qty:
                for f in fields_q:
                    result.setdefault('value', {}).update({f: new_qty})
                result.setdefault('warning', {}).update(message)

        return result

product_uom()


class finance_tools(osv.osv):
    """
    finance tools
    """
    _name = 'finance.tools'

    def get_orm_date(self, day, month, year=False):
        """
        get date in ORM format
        :type day: int
        :type month: int
        :type year: int (current FY if not provided)
        """
        return "%04d-%02d-%02d" % (year or datetime.now().year, month, day, )

    def check_document_date(self, cr, uid, document_date, posting_date,
                            show_date=False, custom_msg=False, context=None):
        """
        Checks that posting date >= document date
        Depending on the config made in the Reconfigure Wizard, can also check that the document date is included
        in the same FY as the related posting date.

        :type document_date: orm date
        :type posting_date: orm date
        :param show_date: True to display dates in message
        :param custom_msg: str for custom basic message (will cancel show_date)
        :type custom_msg: bool/str
        """
        if not document_date or not posting_date:
            return
        if custom_msg:
            show_date = False

        if posting_date < document_date:
            if custom_msg:
                msg = custom_msg  # optional custom message
            else:
                if show_date:
                    msg = _('Posting date (%s) should be later than' \
                            ' Document Date (%s).') % (posting_date, document_date,)
                else:
                    msg = _(
                        'Posting date should be later than Document Date.')
            raise osv.except_osv(_('Error'), msg)

        # if the system doesn't allow doc dates from previous FY, check that this condition is met
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        if not setup or not setup.previous_fy_dates_allowed:
            # 01/01/FY <= document date <= 31/12/FY
            posting_date_obj = self.pool.get('date.tools').orm2date(posting_date)
            check_range_start = self.get_orm_date(1, 1, year=posting_date_obj.year)
            check_range_end = self.get_orm_date(31, 12, year=posting_date_obj.year)
            if not (check_range_start <= document_date <= check_range_end):
                if show_date:
                    msg = _('Document date (%s) should be in posting date FY') % (document_date, )
                else:
                    msg = _('Document date should be in posting date FY')
                raise osv.except_osv(_('Error'), msg)

    def check_correction_date_fy(self, original_date, correction_date, raise_error=True, context=None):
        """
        Checks that the correction entry is booked within the same Fiscal Year as the original entry.
        If they are in different FY, raises an error if raise_error is set to True (by default), else returns False.

        NOTE: the CONTEXT in parameter is not directly used in this method but enables the message translation.
        """
        res = True
        date_tools_obj = self.pool.get('date.tools')
        if original_date and correction_date:
            orig_date_obj = date_tools_obj.orm2date(original_date)
            corr_date_obj = date_tools_obj.orm2date(correction_date)
            if isinstance(orig_date_obj, date) and isinstance(corr_date_obj, date) and orig_date_obj.year != corr_date_obj.year:
                if raise_error:
                    raise osv.except_osv(_('Error'), _('The correction entry (posting date: %s) should be in the same fiscal year '
                                                       'as the original entry (posting date: %s).') % (correction_date, original_date))
                else:
                    res = False
        return res

    def truncate_amount(self, amount, digits):
        stepper = pow(10.0, digits)
        return math.trunc(stepper * amount) / stepper

finance_tools()


class user_rights_tools(osv.osv_memory):
    _name = 'user_rights.tools'
    _logger = logging.getLogger('UR import')
    def load_ur_zip(self, cr, uid, plain_zip, sync_server=False, logger=False, context=None):
        '''
            load UR from zip file
        plain_zip: content of the zip file as a string
        sync_server: method is executed from sync server: extra check needed else from client then UR not in files must be deleted
        logger: where to log progression of import
        '''

        if context is None:
            context = {}
        zp = BytesIO(plain_zip)
        ur = self.pool.get('user_rights.tools').unzip_file(cr, uid, zp, context=context)
        z = ZipFile(zp)


        uac_processor = self.pool.get('user.access.configurator')
        f = z.open(ur['UAC'])
        data = b64encode(f.read())
        f.close()
        if logger:
            log_line = 'Importing %s' % (ur['UAC'],)
            self._logger.info(log_line)
            logger.append(log_line)
            logger.write()

        wiz_id = uac_processor.create(cr, uid, {'file_to_import_uac': data})
        uac_processor.do_process_uac(cr, uid, [wiz_id])

        import_key = {}
        for x in MODEL_DICT:
            import_key[MODEL_DICT[x]['model']] = x

        context['from_synced_ur'] = True
        for model in ['msf_button_access_rights.button_access_rule', 'ir.model.access', 'ir.rule', 'ir.actions.act_window', 'msf_field_access_rights.field_access_rule', 'msf_field_access_rights.field_access_rule_line']:
            zip_to_import = ur[model]
            obj_to_import = self.pool.get(model)
            if not isinstance(zip_to_import, list):
                zip_to_import = [zip_to_import]

            if not sync_server and hasattr(obj_to_import, '_common_import') and obj_to_import._common_import:
                cr.execute("update %s set imported_flag='f'" % (obj_to_import._table)) # not_a_user_entry

            for zp_f in zip_to_import:
                if logger:
                    log_line = 'Importing %s' % (zp_f)
                    self._logger.info(log_line)
                    logger.append(log_line)
                    logger.write()

                file_d = z.open(zp_f, 'r')

                wiz_key = import_key[model]
                wiz = self.pool.get('msf.import.export').create(cr, uid, {'model_list_selection': wiz_key, 'import_file': b64encode(file_d.read())}, context=context)
                file_d.close()
                self.pool.get('msf.import.export').import_xml(cr, uid, [wiz], raise_on_error=True, context=context)
                if sync_server and model == 'msf_field_access_rights.field_access_rule_line':
                    cr.execute("""select coalesce(d.name, f.model || ' ' || f.name)  from msf_field_access_rights_field_access_rule_line line
                            left join ir_model_fields f on f.id = line.field
                            left join ir_model_data d on d.res_id = line.id and d.model='msf_field_access_rights.field_access_rule_line' and d.module!='sd'
                        where f.state='deprecated'
                        """)
                    error = [x[0] for x in cr.fetchall()]
                    if error:
                        raise osv.except_osv(_('Warning !'), _("FARL %s the following rules are on deprecated rows:\n - %s") % (zp_f, "\n - ".join(error)))


            if not sync_server and hasattr(obj_to_import, '_common_import') and obj_to_import._common_import:
                dom = [('imported_flag', '=', False)]
                if model == 'ir.model.access':
                    dom += [('from_system', '=', False)]
                to_del_ids = obj_to_import.search(cr, uid, dom, context=context)
                if to_del_ids:
                    if model == 'msf_button_access_rights.button_access_rule':
                        obj_to_import.write(cr, uid, to_del_ids, {'group_ids': [(6, 0, [])]}, context=context)
                    else:
                        obj_to_import.unlink(cr, uid, to_del_ids, context=context)
                    self._logger.info("User Rigths model %s, %d records deleted" % (model, len(to_del_ids)))
        return True

    def unzip_file(self, cr, uid, zfile, raise_error=False, context=None):
        ur = {
            'UAC': False,
            'msf_button_access_rights.button_access_rule': [],
            'ir.model.access': False,
            'msf_field_access_rights.field_access_rule': False,
            'msf_field_access_rights.field_access_rule_line': False,
            'ir.rule': False,
            'ir.actions.act_window': False,
        }

        expected_files = 7
        z = ZipFile(zfile)
        nb = 0
        for f in z.infolist():
            if f.filename.endswith('/'):
                continue
            nb += 1
            if 'button_access' in f.filename.lower():
                ur['msf_button_access_rights.button_access_rule'].append(f.filename)
            elif 'access_control' in f.filename.lower():
                ur['ir.model.access'] = f.filename
            elif 'record_rules' in f.filename.lower():
                ur['ir.rule'] = f.filename
            elif 'window' in f.filename.lower():
                ur['ir.actions.act_window'] = f.filename
            elif 'user_access' in f.filename.lower():
                ur['UAC'] = f.filename
            elif 'rule_lines' in f.filename.lower():
                ur['msf_field_access_rights.field_access_rule_line'] = f.filename
            elif 'field_access_rules' in f.filename.lower():
                ur['msf_field_access_rights.field_access_rule'] = f.filename
            elif raise_error:
                raise osv.except_osv(_('Warning !'), _('Extra file "%s" found in zip !') % (f.filename))

        if raise_error:
            if nb != expected_files:
                raise osv.except_osv(_('Warning !'), _("%s files found, %s expected.") % (nb, expected_files))

        z.close()

        return ur

user_rights_tools()

class job_in_progress(osv.osv_memory):
    _name = 'job.in_progress'
    _columns = {
        'res_id': fields.integer('Db Id'),
        'model': fields.char('Object', size=256),
        'name': fields.char('Name', size=256),
        'total': fields.integer('Total to process'),
        'nb_processed': fields.integer('Total processed'),
        'state': fields.selection([('in-progress', 'In Progress'), ('done', 'Done'), ('error', 'Error')], 'State'),
        'target_link': fields.text('Target'),
        'error': fields.text('Error'),
        'read': fields.boolean('Msg read by user'),
        'src_name': fields.char('Src Name', size=256),
        'target_name': fields.char('Target Name', size=256),
    }

    _defaults = {
        'read': False,
        'state': 'in-progress',
    }

    # force uid=1 to by pass osv_memory domain
    def read(self, cr, uid, *a, **b):
        return super(job_in_progress, self).read(cr, 1, *a, **b)

    def search(self, cr, uid, *a, **b):
        return super(job_in_progress, self).search(cr, 1, *a, **b)

    def write(self, cr, uid, *a, **b):
        return super(job_in_progress, self).write(cr, 1, *a, **b)

    def _prepare_run_bg_job(self, cr, uid, src_ids, model, method_to_call, nb_lines, name, return_success=True, main_object_id=False, context=None):
        assert len(src_ids) == 1, 'Can only process 1 object'

        if not nb_lines:
            raise osv.except_osv(_('Warning'), _('No line to process'))


        object_id = src_ids[0]
        if main_object_id:
            object_id = main_object_id

        if self.search(cr, 1, [('state', '=', 'in-progress'), ('model', '=', model), ('res_id', '=', object_id)]):
            return True

        src_name = self.pool.get(model).read(cr, uid, object_id, ['name']).get('name')

        job_id = self.create(cr, uid, {'res_id': object_id, 'model': model, 'name': name, 'total': nb_lines, 'src_name': src_name})
        th = threading.Thread(
            target=self._run_bg_job,
            args=(cr.dbname, uid, job_id,  method_to_call),
            kwargs={'src_ids': src_ids, 'context': context}
        )
        th.start()
        th.join(3)
        if not th.is_alive():
            job_data = self.pool.get('job.in_progress').read(cr, uid, job_id, ['target_link', 'state', 'error'])
            self.unlink(cr, uid, [job_id])
            if job_data['state'] == 'done':
                return job_data.get('target_link') or return_success
            else:
                raise osv.except_osv(_('Warning'), job_data['error'])

        return return_success


    def _run_bg_job(self, crname, uid, job_id, method, src_ids, context=None):

        new_cr = pooler.get_db(crname).cursor()
        try:
            res = False
            process_error = False
            res = method(new_cr, uid, src_ids, context, job_id=job_id)
        except osv.except_osv as er:
            new_cr.rollback()
            if job_id:
                process_error = True
                self.pool.get('job.in_progress').write(new_cr, uid, [job_id], {'state': 'error', 'error': tools.ustr(er.value)})
            raise

        except Exception:
            new_cr.rollback()
            if job_id:
                process_error = True
                self.pool.get('job.in_progress').write(new_cr, uid, [job_id], {'state': 'error', 'error': tools.ustr(traceback.format_exc())})
            raise

        finally:
            if job_id:
                if not process_error:
                    target_name = False
                    if isinstance(res, bool):
                        # if target is not a dict, do not display button
                        res = False
                    if res and res.get('res_id') and res.get('res_model'):
                        target_name = self.pool.get(res['res_model']).read(new_cr, uid, res['res_id'], ['name']).get('name')

                    self.pool.get('job.in_progress').write(new_cr, uid, [job_id], {'state': 'done', 'target_link': res, 'target_name': target_name})
                new_cr.commit()
                new_cr.close(True)
job_in_progress()
