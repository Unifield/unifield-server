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

import inspect

from tools.translate import _
from dateutil.relativedelta import relativedelta
from datetime import datetime

import netsvc

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
            date = time.strptime(datetime, '%Y-%m-%d')
            return time.strftime(d_format, date)
        elif d_type == 'datetime':
            d_format = self.get_datetime_format(cr, uid)
            date = time.strptime(datetime, '%Y-%m-%d %H:%M:%S')
            return time.strftime(d_format, date)
    
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
        # quarantine before scrap
        quarantine_scrap = obj_data.get_object_reference(cr, uid, 'stock_override', 'stock_location_quarantine_scrap')[1]
        context['common']['quarantine_scrap'] = quarantine_scrap
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

data_tools()


class sequence_tools(osv.osv):
    '''
    sequence tools
    '''
    _name = 'sequence.tools'
    
    def reset_next_number(self, cr, uid, seq_ids, value=1, context=None):
        '''
        reset the next number of the sequence to value, default value 1
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(seq_ids, (int, long)):
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
        if isinstance(ids, (int, long)):
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
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # objects
        pick_obj = self.pool.get('stock.picking')
        pick_obj.action_assign(cr, uid, ids, context)
        return True
    
    def force_assign(self, cr, uid, ids, context=None):
        '''
        force assign the picking
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
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
        if isinstance(ids, (int, long)):
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


def check_none(pos):
    '''
    if parameter at position pos is None, it is replaced by {}
    '''
    def decorator(fn):
        def wrapper(*args):
            if args[pos] is None:
                args = tuple([{} if x == pos else args[x] for x in range(len(args))])
            return fn(*args)
        return wrapper
    return decorator


def check_int_float(pos):
    '''
    if parameter at position pos is float or int, it is packed in a list
    '''
    def decorator(fn):
        def wrapper(*args):
            if isinstance(args[pos], (int, long)):
                args = tuple([[args[x]] if x == pos else args[x] for x in range(len(args))])
            return fn(*args)
        return wrapper
    return decorator


def check_both():
    '''
    decorator to replacing:
    - None 'context' by {}
    - int/float 'ids' packed in a list
    
    can only be used as first decorator... second decorator gets args as parameter name for the function...
    -> will do nothing if called after another decorator
    
    decorators are called in the following order
    
    @last to be called
    @second to be called
    @first to be called
    def function
    
    does not work -> def test(self, ids, context=None)
    if we call the function with self.test(1) -> we get an index out of bounds for args[pos]...
    '''
    def decorator(fn):
        def wrapper(*args):
            # first ids
            param = 'ids'
            print args
            # inspect method signature
            data = inspect.getargspec(fn)
            print data
            # if context exists and appears one time
            if param in data[0] and data[0].count(param) == 1:
                # get position of context parameter
                pos = data[0].index(param)
                if isinstance(args[pos], (int, long)):
                    args = tuple([[args[x]] if x == pos else args[x] for x in range(len(args))])
            print args
            # then context
            param = 'context'
            # if context exists and appears one time
            if param in data[0] and data[0].count(param) == 1:
                # get position of context parameter
                pos = data[0].index(param)
                if args[pos] is None:
                    args = tuple([{} if x == pos else args[x] for x in range(len(args))])
            print args
            return fn(*args)
        return wrapper
    return decorator

