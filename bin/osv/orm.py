# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

#
# Object relationnal mapping to postgresql module
#    . Hierarchical structure
#    . Constraints consistency, validations
#    . Object meta Data depends on its status
#    . Optimised processing by complex query (multiple actions at once)
#    . Default fields value
#    . Permissions optimisation
#    . Persistant object: DB postgresql
#    . Datas conversions
#    . Multi-level caching system
#    . 2 different inheritancies
#    . Fields:
#         - classicals (varchar, integer, boolean, ...)
#         - relations (one2many, many2one, many2many)
#         - functions
#
#
import calendar
import copy
import datetime
import logging
import warnings
import operator
import pickle
import re
import time
import traceback
import types
import csv

import netsvc
from lxml import etree
from tools.config import config
from tools.translate import _

import fields
from query import Query
import tools
from tools.safe_eval import safe_eval as eval
import xmlid_no_delete
# List of etree._Element subclasses that we choose to ignore when parsing XML.
from tools import SKIPPED_ELEMENT_TYPES, cache

regex_order = re.compile('^(([a-z0-9_\.]+|"[a-z0-9_\.]+")( *desc| *asc)?( *, *|))+$', re.I)

POSTGRES_CONFDELTYPES = {
    'RESTRICT': 'r',
    'NO ACTION': 'a',
    'CASCADE': 'c',
    'SET NULL': 'n',
    'SET DEFAULT': 'd',
}

def last_day_of_current_month():
    today = datetime.date.today()
    last_day = str(calendar.monthrange(today.year, today.month)[1])
    return time.strftime('%Y-%m-' + last_day)

def intersect(la, lb):
    return filter(lambda x: x in lb, la)
    #return list(set(la).intersection(lb)) # this is less compatible, see US-867

class except_orm(Exception):
    def __init__(self, name, value, ir_rule_error=False):
        self.name = name
        self.value = value
        self.ir_rule_error = ir_rule_error
        self.args = (name, value)

class BrowseRecordError(Exception):
    pass

# Readonly python database object browser
class browse_null(object):

    def __init__(self):
        self.id = False

    def __getitem__(self, name):
        return None

    def __getattr__(self, name):
        return None  # XXX: return self ?

    def __int__(self):
        return False

    def __str__(self):
        return ''

    def __nonzero__(self):
        return False

    def __unicode__(self):
        return u''


#
# TODO: execute an object method on browse_record_list
#
class browse_record_list(list):

    def __init__(self, lst, context=None):
        if context is None:
            context = {}
        super(browse_record_list, self).__init__(lst)
        self.context = context

class browse_record(object):
    logger = netsvc.Logger()
    def __init__(self, cr, uid, id, table, cache, context=None,
                 list_class=None, fields_process=None, fields_to_fetch=None):
        '''
        table : the object (inherited from orm)
        context : dictionary with an optional context
        '''
        if fields_process is None:
            fields_process = {}
        if context is None:
            context = {}
        self._list_class = list_class or browse_record_list
        self._cr = cr
        self._uid = uid
        self._id = id
        self._table = table
        self._table_name = self._table._name
        self.__logger = logging.getLogger(
            'osv.browse_record.' + self._table_name)
        self._context = context
        self._fields_process = fields_process
        self._fields_to_fetch = fields_to_fetch

        cache.setdefault(table._name, {})
        self._data = cache[table._name]

        if not (id and isinstance(id, (int, long,))):
            raise BrowseRecordError(_('Wrong ID for the browse record, got %r, expected an integer.') % (id,))

        if id not in self._data:
            self._data[id] = {'id': id}

        self._cache = cache

    def __getitem__(self, name):
        if name == 'id':
            return self._id

        if name not in self._data[self._id]:
            # build the list of fields we will fetch

            # fetch the definition of the field which was asked for
            if name in self._table._columns:
                col = self._table._columns[name]
            elif name in self._table._inherit_fields:
                col = self._table._inherit_fields[name][2]
            elif hasattr(self._table, str(name)):
                attr = getattr(self._table, name)

                if isinstance(attr, (types.MethodType, types.LambdaType, types.FunctionType)):
                    return lambda *args, **argv: attr(self._cr, self._uid, [self._id], *args, **argv)
                else:
                    return attr
            else:
                self.logger.notifyChannel("browse_record", netsvc.LOG_WARNING,
                                          "Field '%s' does not exist in object '%s': \n%s" % (
                                              name, self, ''.join(traceback.format_exc())))
                raise KeyError("Field '%s' does not exist in object '%s'" % (
                    name, self))

            # if the field is a classic one or a many2one, we'll fetch all classic and many2one fields
            if col._prefetch:
                # gen the list of "local" (ie not inherited) fields which are classic or many2one
                fields_to_fetch = filter(lambda x: x[1]._classic_write and x[1]._prefetch, self._table._columns.items())
                # gen the list of inherited fields
                inherits = map(lambda x: (x[0], x[1][2]), self._table._inherit_fields.items())
                # complete the field list with the inherited fields which are classic or many2one
                fields_to_fetch += filter(lambda x: x[1]._classic_write and x[1]._prefetch, inherits)
            # otherwise we fetch only that field
            else:
                if self._name == 'replenishment.segment.line' and col._multi == 'merge_minmax':
                    # cache all rr_fmc values
                    fields_to_fetch = [x for x in self._table._columns.items() if x[1]._multi == 'merge_minmax']
                else:
                    fields_to_fetch = [(name, col)]
            ids = filter(lambda id: name not in self._data[id], self._data.keys())
            # read the results
            if self._fields_to_fetch:
                if name not in self._fields_to_fetch:
                    self.__logger.warn("fields_to_fetch has been defined in "
                                       "browse() for object %s, but field %s is not member "
                                       "of it %s" % (self, name, tools.misc.get_stack()))
                    self._fields_to_fetch.append(name)
                fields_to_fetch = [x for x in fields_to_fetch if x[0] in
                                   self._fields_to_fetch]
            field_names = [x[0] for x in fields_to_fetch]
            try:
                field_values = self._table.read(self._cr, self._uid, ids, field_names, context=self._context, load="_classic_write")
            except except_orm, e:
                if e.ir_rule_error:
                    # read more ids than asked, but this could raise an ir.rule error (read prev_reg_id on register but user is not allowed to read it)
                    field_values = self._table.read(self._cr, self._uid, [self._id], field_names, context=self._context, load="_classic_write")
                else:
                    raise

            # TODO: improve this, very slow for reports
            if self._fields_process:
                lang = self._context.get('lang', 'en_US') or 'en_US'
                if lang != 'en_US':
                    lang_obj_ids = self.pool.get('res.lang').search(self._cr, self._uid, [('code', '=', lang)])
                    if not lang_obj_ids:
                        raise Exception(_('Language with code "%s" is not defined in your system !\nDefine it through the Administration menu.') % (lang,))
                    lang_obj = self.pool.get('res.lang').browse(self._cr, self._uid, lang_obj_ids[0])

                    for field_name, field_column in fields_to_fetch:
                        if field_column._type in self._fields_process:
                            for result_line in field_values:
                                result_line[field_name] = self._fields_process[field_column._type](result_line[field_name])
                                if result_line[field_name] is not None and result_line[field_name] is not False:
                                    result_line[field_name].set_value(self._cr, self._uid, result_line[field_name], self, field_column, lang_obj, result_line['id'])

            if not field_values:
                # Where did those ids come from? Perhaps old entries in ir_model_dat?
                self.__logger.warn("No field_values found for ids %s in %s", ids, self)
                raise KeyError('Field %s not found in %s'%(name, self))
            # create browse records for 'remote' objects
            for result_line in field_values:
                new_data = {}
                for field_name, field_column in fields_to_fetch:
                    if field_column._type in ('many2one', 'one2one'):
                        if result_line[field_name]:
                            obj = self._table.pool.get(field_column._obj)
                            if isinstance(result_line[field_name], (list, tuple)):
                                value = result_line[field_name][0]
                            else:
                                value = result_line[field_name]
                            if value:
                                # FIXME: this happen when a _inherits object
                                #        overwrite a field of it parent. Need
                                #        testing to be sure we got the right
                                #        object and not the parent one.
                                if not isinstance(value, browse_record):
                                    if obj is None:
                                        # In some cases the target model is not available yet, so we must ignore it,
                                        # which is safe in most cases, this value will just be loaded later when needed.
                                        # This situation can be caused by custom fields that connect objects with m2o without
                                        # respecting module dependencies, causing relationships to be connected to soon when
                                        # the target is not loaded yet.
                                        continue
                                    new_data[field_name] = browse_record(self._cr,
                                                                         self._uid, value, obj, self._cache,
                                                                         context=self._context,
                                                                         list_class=self._list_class,
                                                                         fields_process=self._fields_process)
                                else:
                                    new_data[field_name] = value
                            else:
                                new_data[field_name] = browse_null()
                        else:
                            new_data[field_name] = browse_null()
                    elif field_column._type in ('one2many', 'many2many') and len(result_line[field_name]):
                        new_data[field_name] = self._list_class([browse_record(self._cr, self._uid,
                                                                               obj_id, self._table.pool.get(field_column._obj),
                                                                               self._cache, context=self._context,
                                                                               list_class=self._list_class,
                                                                               fields_process=self._fields_process) for obj_id in\
                                                                 result_line[field_name]], self._context)
                    elif field_column._type in ('reference'):
                        if result_line[field_name]:
                            if isinstance(result_line[field_name], browse_record):
                                new_data[field_name] = result_line[field_name]
                            else:
                                if isinstance(result_line[field_name], dict):
                                    ref_obj, ref_id = result_line[field_name].get('selection', ',').split(',')
                                else:
                                    ref_obj, ref_id = result_line[field_name].split(',')
                                if not ref_id:
                                    new_data[field_name] = browse_null()
                                    continue
                                ref_id = long(ref_id)
                                if ref_id:
                                    obj = self._table.pool.get(ref_obj)
                                    new_data[field_name] = browse_record(self._cr, self._uid, ref_id,
                                                                         obj, self._cache,
                                                                         context=self._context,
                                                                         list_class=self._list_class,
                                                                         fields_process=self._fields_process)
                                else:
                                    new_data[field_name] = browse_null()
                        else:
                            new_data[field_name] = browse_null()
                    else:
                        new_data[field_name] = result_line[field_name]
                self._data[result_line['id']].update(new_data)

        if not name in self._data[self._id]:
            # How did this happen? Could be a missing model due to custom fields used too soon, see above.
            self.logger.notifyChannel("browse_record", netsvc.LOG_ERROR,
                                      "Fields to fetch: %s, Field values: %s"%(field_names, field_values))
            self.logger.notifyChannel("browse_record", netsvc.LOG_ERROR,
                                      "Cached: %s, Table: %s"%(self._data[self._id], self._table))
            raise KeyError(_('Unknown attribute %s in %s ') % (name, self))
        return self._data[self._id][name]

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError, e:
            raise AttributeError(e)

    def __contains__(self, name):
        return (name in self._table._columns) or (name in self._table._inherit_fields) or hasattr(self._table, name)

    def __hasattr__(self, name):
        return name in self

    def __int__(self):
        return self._id

    def __str__(self):
        return "browse_record(%s, %d)" % (self._table_name, self._id)

    def __eq__(self, other):
        if not isinstance(other, browse_record):
            return False
        return (self._table_name, self._id) == (other._table_name, other._id)

    def __ne__(self, other):
        if not isinstance(other, browse_record):
            return True
        return (self._table_name, self._id) != (other._table_name, other._id)

    # we need to define __unicode__ even though we've already defined __str__
    # because we have overridden __getattr__
    def __unicode__(self):
        return unicode(str(self))

    def __hash__(self):
        return hash((self._table_name, self._id))

    __repr__ = __str__


def get_pg_type(f):
    '''
    returns a tuple
    (type returned by postgres when the column was created, type expression to create the column)
    '''

    type_dict = {
        fields.boolean: 'bool',
        fields.integer: 'int4',
        fields.integer_null: 'int4',
        fields.integer_big: 'int8',
        fields.text: 'text',
        fields.date: 'date',
        fields.time: 'time',
        fields.datetime: 'timestamp',
        fields.binary: 'bytea',
        fields.many2one: 'int4',
    }
    if type(f) in type_dict:
        f_type = (type_dict[type(f)], type_dict[type(f)])
    elif isinstance(f, fields.float):
        if f.digits:
            f_type = ('numeric', 'NUMERIC')
        else:
            f_type = ('float8', 'DOUBLE PRECISION')
    elif isinstance(f, (fields.char, fields.reference)):
        f_type = ('varchar', 'VARCHAR(%d)' % (f.size,))
    elif isinstance(f, fields.selection):
        if isinstance(f.selection, list) and isinstance(f.selection[0][0], (str, unicode)):
            f_size = reduce(lambda x, y: max(x, len(y[0])), f.selection, f.size or 16)
        elif isinstance(f.selection, list) and isinstance(f.selection[0][0], int):
            f_size = -1
        else:
            f_size = getattr(f, 'size', None) or 16

        if f_size == -1:
            f_type = ('int4', 'INTEGER')
        else:
            f_type = ('varchar', 'VARCHAR(%d)' % f_size)
    elif isinstance(f, fields.function) and eval('fields.'+(f._type), globals()) in type_dict:
        t = eval('fields.'+(f._type), globals())
        f_type = (type_dict[t], type_dict[t])
    elif isinstance(f, fields.function) and f._type == 'float':
        if f.digits:
            f_type = ('numeric', 'NUMERIC')
        else:
            f_type = ('float8', 'DOUBLE PRECISION')
    elif isinstance(f, fields.function) and f._type == 'selection':
        f_type = ('text', 'text')
    elif isinstance(f, fields.function) and f._type == 'char':
        f_type = ('varchar', 'VARCHAR(%d)' % (f.size))
    else:
        logger = netsvc.Logger()
        logger.notifyChannel("init", netsvc.LOG_WARNING, '%s type not supported!' % (type(f)))
        f_type = None
    return f_type


class orm_template(object):
    _name = None
    _trace = False
    _columns = {}
    _constraints = []
    _defaults = {}
    _rec_name = 'name'
    _parent_name = 'parent_id'
    _parent_store = False
    _parent_order = False
    _date_name = 'date'
    _order = 'id'
    _sequence = None
    _description = None
    _inherits = {}
    _table = None
    _invalids = set()
    _log_create = False
    # Dict with fields to replace as key and replacing fields as value like this
    # {'product_id': [
    #         (['product_code', 'Product Code'], 10),
    #         (['product_name', 'Product Name'], 20),
    #     ]
    # }
    _replace_exported_fields = {}

    CONCURRENCY_CHECK_FIELD = '__last_update'
    def log(self, cr, uid, id, message, secondary=False, action_xmlid=False, context=None, read=False):
        return self.pool.get('res.log').create(cr, uid,
                                               {
                                                   'name': message,
                                                   'res_model': self._name,
                                                   'secondary': secondary,
                                                   'res_id': id,
                                                   'action_xmlid': action_xmlid,
                                                   'read': read,
                                               },
                                               context=context
                                               )

    def view_init(self, cr, uid, fields_list, context=None):
        """Override this method to do specific things when a view on the object is opened."""
        pass

    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, count=False):
        raise NotImplementedError(_('The read_group method is not implemented on this object !'))

    def _field_create(self, cr, context=None):
        if context is None:
            context = {}
        cr.execute("SELECT id FROM ir_model WHERE model=%s", (self._name,))
        if not cr.rowcount:
            cr.execute('SELECT nextval(%s)', ('ir_model_id_seq',))
            model_id = cr.fetchone()[0]
            cr.execute("INSERT INTO ir_model (id,model, name, info,state) VALUES (%s, %s, %s, %s, %s)", (model_id, self._name, self._description, self.__doc__, 'base'))
        else:
            model_id = cr.fetchone()[0]
        if 'module' in context:
            name_id = 'model_'+self._name.replace('.', '_')
            cr.execute('select * from ir_model_data where name=%s and module=%s', (name_id, context['module']))
            if not cr.rowcount:
                cr.execute("INSERT INTO ir_model_data (name,date_init,date_update,module,model,res_id) VALUES (%s, now(), now(), %s, %s, %s)", \
                           (name_id, context['module'], 'ir.model', model_id)
                           )

        cr.commit()

        cr.execute("SELECT * FROM ir_model_fields WHERE model=%s", (self._name,))
        cols = {}
        for rec in cr.dictfetchall():
            cols[rec['name']] = rec

        for (k, f) in self._columns.items():
            vals = {
                'model_id': model_id,
                'model': self._name,
                'name': k,
                'field_description': f.string.replace("'", " "),
                'ttype': f._type,
                'relation': f._obj or u'',
                'view_load': (f.view_load and True) or False,
                'select_level': tools.ustr(f.select or 0),
                'readonly': (f.readonly and True) or False,
                'required': (f.required and True) or False,
                'selectable': (f.selectable and True) or False,
                'translate': (f.translate and True) or False,
                'relation_field': (f._type=='one2many' and isinstance(f, fields.one2many)) and f._fields_id or '',
                'state': 'base',
            }

            # When its a custom field,it does not contain f.select
            if context.get('field_state', 'base') == 'manual':
                if context.get('field_name', '') == k:
                    vals['select_level'] = context.get('select', '0')
                #setting value to let the problem NOT occur next time
                elif k in cols:
                    vals['select_level'] = cols[k]['select_level']

            if k not in cols:
                cr.execute('select nextval(%s)', ('ir_model_fields_id_seq',))
                id = cr.fetchone()[0]
                vals['id'] = id
                cr.execute("""INSERT INTO ir_model_fields (
                    id, model_id, model, name, field_description, ttype,
                    relation,view_load,state,select_level,relation_field, translate
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                )""", (
                    id, vals['model_id'], vals['model'], vals['name'], vals['field_description'], vals['ttype'],
                    vals['relation'], bool(vals['view_load']), 'base',
                    vals['select_level'], vals['relation_field'], bool(vals['translate'])
                ))
                if 'module' in context:
                    name1 = 'field_' + self._table + '_' + k
                    cr.execute("select name from ir_model_data where name=%s", (name1,))
                    if cr.fetchone():
                        name1 = name1 + "_" + str(id)
                    cr.execute("INSERT INTO ir_model_data (name,date_init,date_update,module,model,res_id) VALUES (%s, now(), now(), %s, %s, %s)", \
                               (name1, context['module'], 'ir.model.fields', id)
                               )
            else:
                for key, val in vals.items():
                    if cols[k][key] != vals[key]:
                        cr.execute("""UPDATE ir_model_fields SET
                            model_id=%s, field_description=%s, ttype=%s, relation=%s,
                            view_load=%s, select_level=%s, readonly=%s ,required=%s, selectable=%s, relation_field=%s, translate=%s, state='base'
                        WHERE
                            model=%s AND name=%s""", (
                            vals['model_id'], vals['field_description'], vals['ttype'],
                            vals['relation'], bool(vals['view_load']),
                            vals['select_level'], bool(vals['readonly']), bool(vals['required']), bool(vals['selectable']), vals['relation_field'], bool(vals['translate']), vals['model'], vals['name']
                        ))
                        break
        cr.commit()

    def _auto_init(self, cr, context=None):
        self._field_create(cr, context=context)

    def __init__(self, cr):
        if not self._name and not hasattr(self, '_inherit'):
            name = type(self).__name__.split('.')[0]
            msg = "The class %s has to have a _name attribute" % name

            logger = netsvc.Logger()
            logger.notifyChannel('orm', netsvc.LOG_ERROR, msg)
            raise except_orm('ValueError', msg)

        if not self._description:
            self._description = self._name
        if not self._table:
            self._table = self._name.replace('.', '_')

    def browse(self, cr, uid, select, context=None, list_class=None,
               fields_process=None, fields_to_fetch=None):
        """Fetch records as objects allowing to use dot notation to browse fields and relations

        :param cr: database cursor
        :param user: current user id
        :param select: id or list of ids
        :param context: context arguments, like lang, time zone
        :rtype: object or list of objects requested

        """
        self._list_class = list_class or browse_record_list
        bcache = {}
        # need to accepts ints and longs because ids coming from a method
        # launched by button in the interface have a type long...
        if isinstance(select, (int, long)):
            return browse_record(cr, uid, select, self, bcache, context=context,
                                 list_class=self._list_class, fields_process=fields_process,
                                 fields_to_fetch=fields_to_fetch)
        elif isinstance(select, list):
            return self._list_class([browse_record(cr, uid, id, self, bcache,
                                                   context=context, list_class=self._list_class,
                                                   fields_process=fields_process, fields_to_fetch=fields_to_fetch) for id in select], context=context)
        else:
            return browse_null()

    def __export_row(self, cr, uid, row, fields, context=None):
        if context is None:
            context = {}
        sync_context = context.get('sync_update_creation')

        def check_type(field_type):
            if field_type == 'float':
                return '0.0'
            elif field_type == 'integer':
                return '0'
            elif field_type == 'boolean':
                return 'False'
            return ''

        def selection_field(in_field):
            col_obj = self.pool.get(in_field.keys()[0])
            if f[i] in col_obj._columns.keys():
                return  col_obj._columns[f[i]]
            elif f[i] in col_obj._inherits.keys():
                selection_field(col_obj._inherits)
            else:
                return False

        def _get_xml_id(self, cr, uid, r):
            model_data = self.pool.get('ir.model.data')
            is_sync = context.get('sync_update_creation') or context.get('sync_update_creation')
            data_ids = []
            dom = [('model', '=', r._table_name), ('res_id', '=', r['id'])]
            if is_sync:
                data_ids = model_data.search(cr, uid, dom+[('module', '=', 'sd')])
            if not data_ids:
                data_ids = model_data.search(cr, uid, dom)
            if len(data_ids):
                d = model_data.read(cr, uid, data_ids, ['name', 'module'])[0]
                if d['module']:
                    r = '%s.%s' % (d['module'], d['name'])
                else:
                    r = d['name']
            else:
                postfix = 0
                while True:
                    n = self._table+'_'+str(r['id']) + (postfix and ('_'+str(postfix)) or '' )
                    if not model_data.search(cr, uid, [('name', '=', n)],
                                             limit=1, order='NO_ORDER'):
                        break
                    postfix += 1
                model_data.create(cr, uid, {
                    'name': n,
                    'model': self._name,
                    'res_id': r['id'],
                    'module': '__export__',
                })
                r = '__export__.'+n
            return r

        lines = []
        data = map(lambda x: '', range(len(fields)))
        done = []
        for fpos in xrange(len(fields)):
            f = fields[fpos]
            if f:
                r = row
                i = 0
                while i < len(f):
                    if f[i] == '.id':
                        r = r['id']
                    elif f[i] == 'id':
                        model_data = self.pool.get('ir.model.data')
                        dom_search = [('model', '=', r._table_name), ('res_id', '=', r['id'])]
                        data_ids = model_data.search(cr, uid, dom_search+[('module', '=', 'sd')])
                        if not data_ids:
                            data_ids = model_data.search(cr, uid, dom_search)
                        if len(data_ids):
                            d = model_data.read(cr, uid, data_ids[0], ['name', 'module'])
                            if d['module']:
                                r = '%s.%s' % (d['module'], d['name'])
                            else:
                                r = d['name']
                        else:
                            break
                    else:
                        if isinstance(r, browse_record):
                            obj = self.pool.get(r._table_name)
                        else:
                            obj = self
                        r = r[f[i]]
                        # To display external name of selection field when its exported
                        cols = False
                        if f[i] in obj._columns.keys():
                            cols = obj._columns[f[i]]
                        elif f[i] in obj._inherit_fields.keys():
                            cols = selection_field(obj._inherits)
                        if cols and cols._type == 'selection' and not sync_context:
                            # if requested, translate the fields.selection values
                            translated_selection = False
                            if context.get('translate_selection_field', False) and r and f:
                                fields_get_res = obj.fields_get(cr, uid, f, context=context)
                                if f[0] in fields_get_res and 'selection' in fields_get_res[f[0]]:
                                    r = dict(fields_get_res[f[0]]['selection'])[r]
                                    translated_selection = True
                            if not translated_selection:
                                sel_list = cols.selection
                                if r and type(sel_list) == type([]):
                                    r = [x[1] for x in sel_list if r==x[0]]
                                    r = r and r[0] or False
                    if not r:
                        if f[i] in self._columns:
                            r = check_type(self._columns[f[i]]._type)
                        elif f[i] in self._inherit_fields:
                            r = check_type(self._inherit_fields[f[i]][2]._type)
                        data[fpos] = r or False
                        break
                    if isinstance(r, (browse_record_list, list)):
                        first = True
                        fields2 = map(lambda x: (x[:i+1]==f[:i+1] and x[i+1:]) \
                                      or [], fields)
                        if fields2 in done:
                            if [x for x in fields2 if x]:
                                break
                        done.append(fields2)

                        if sync_context and cols and cols._type in ('many2many', 'one2many') and len(fields[fpos])>(i+1) and (fields[fpos][i+1]=='id'):
                            data[fpos] = ','.join([_get_xml_id(self, cr, uid, x) for x in r])
                            break

                        for row2 in r:
                            lines2 = self.__export_row(cr, uid, row2, fields2,
                                                       context)
                            if first:
                                # Make a check to see if there is data in at least one column
                                # because before this test, only the first line is exported
                                # if there is no data in the first column
                                no_data = True
                                for fpos2 in range(len(fields)):
                                    if lines2 and lines2[0][fpos2]:
                                        no_data = False
                                        data[fpos2] = lines2[0][fpos2]

                                if no_data:
                                    dt = ''
                                    rel_table_name = r[0]._table_name
                                    name_relation = self.pool.get(rel_table_name)._rec_name
                                    if isinstance(r[0][name_relation], browse_record):
                                        rel = True
                                        rel_table_name = r[0][name_relation]._table_name
                                        all_rr = [rr[name_relation].id for rr in r]
                                    else:
                                        rel = False
                                        all_rr = [rr.id for rr in r]
                                    all_name_get = dict(self.pool.get(rel_table_name).name_get(cr, uid, all_rr, context=context))
                                    for rr in r:
                                        if not rel:
                                            rr_name = all_name_get.get(rr.id, '')
                                        else:
                                            rr_name = all_name_get.get(rr[name_relation].id, '')
                                        dt += tools.ustr(rr_name or '') + ','
                                    data[fpos] = dt[:-1]
                                    break
                                lines += lines2[1:]
                                first = False
                            else:
                                lines += lines2
                        break
                    i += 1
                if i == len(f):
                    if isinstance(r, browse_record):

                        # add support for reference fields
                        if cols and cols._type == 'reference' and (sync_context or context.get('import_comp')):
                            row_id = r.id
                            model = r._name
                            xml_id = r._get_xml_ids(cr, uid, [row_id]).get(row_id, '')
                            module = ''
                            if xml_id:
                                module, xml_id = xml_id[0].split('.',1)
                            r = module and model and xml_id and (module, model, xml_id) or ''

                        else:
                            r = self.pool.get(r._table_name).name_get(cr, uid, [r.id], context=context)
                            r = r and r[0] and r[0][1] or ''

                    data[fpos] = tools.ustr(r or '')
        return [data] + lines

    def export_data(self, cr, uid, ids, fields_to_export, context=None):
        """
        Export fields for selected objects

        :param cr: database cursor
        :param uid: current user id
        :param ids: list of ids
        :param fields_to_export: list of fields
        :param context: context arguments, like lang, time zone
        :rtype: dictionary with a *datas* matrix

        This method is used when exporting data via client menu

        """
        if context is None:
            context = {}
        cols = self._columns.copy()
        for f in self._inherit_fields:
            cols.update({f: self._inherit_fields[f][2]})
        def fsplit(x):
            if x=='.id': return [x]
            return x.replace(':id','/id').replace('.id','/.id').split('/')
        fields_to_export = [fsplit(x) for x in fields_to_export]
        datas = []
        for row in self.browse(cr, uid, ids, context,
                               fields_to_fetch=[x[0] for x in fields_to_export]):
            datas += self.__export_row(cr, uid, row, fields_to_export, context)
        return {'datas': datas}

    def import_data_with_wizard(self, cr, uid, csv_file, quotechar="'", delimiter=",", context=None):
        import base64

        import_obj = self.pool.get('import_data')
        import_id = import_obj.create(cr, uid, {
            'ignore': 1,
            'file': base64.encodestring(open(csv_file, 'r').read()),
            'object': self._name,
            'import_mode': 'create',
        })
        processed, rejected, headers = import_obj._import(cr, uid, import_id, use_new_cursor=False, auto_import=True)
        return processed, rejected, headers

    def import_data_from_csv(self, cr, uid, csv_file, quotechar='"', delimiter=',', context=None, with_commit=True):
        headers = []
        list_data = []
        with open(csv_file, 'r') as fcsv:
            reader = csv.reader(fcsv, quotechar=quotechar, delimiter=delimiter)
            for row in reader:
                if not headers:
                    headers = row
                else:
                    list_data.append(row)

        rejected = []
        processed = []
        i = 1
        for d in list_data:
            i += 1
            try:
                res = self.import_data(cr, uid, headers, [d], has_header=True)
                if res[0] == -1:
                    rejected.append((i, d, res[2]))
                else:
                    processed.append((i, d))
                if with_commit:
                    cr.commit()
            except Exception as e:
                rejected.append((i, d, tools.ustr(e)))
                if with_commit:
                    cr.commit()

        return processed, rejected, headers

    def import_data_web(self, cr, uid, fields, datas, mode='init',
                        current_module='', noupdate=False, context=None, filename=None,
                        display_all_errors=False, has_header=False):
        if context is None:
            context = {}
        context['import_from_web_interface'] = True
        return self.import_data(cr, uid, fields, datas, mode=mode, current_module=current_module, noupdate=noupdate, context=context, filename=filename, display_all_errors=display_all_errors, has_header=has_header)

    def import_data(self, cr, uid, fields, datas, mode='init',
                    current_module='', noupdate=False, context=None, filename=None,
                    display_all_errors=False, has_header=False):
        """
        Import given data in given module

        :param cr: database cursor
        :param uid: current user id
        :param fields: list of fields
        :param data: data to import
        :param mode: 'init' or 'update' for record creation
        :param current_module: module name
        :param noupdate: flag for record creation
        :param context: context arguments, like lang, time zone,
        :param filename: optional file to store partial import state for recovery
        :param display_all_errors: display only the first error by default
        :param has_header: flag to add 1 to the total line in error message
        :rtype: tuple

        This method is used when importing data via client menu.

        Example of fields to import for a sale.order::

            .id,                         (=database_id)
            partner_id,                  (=name_search)
            order_line/.id,              (=database_id)
            order_line/name,
            order_line/product_id/id,    (=xml id)
            order_line/price_unit,
            order_line/product_uom_qty,
            order_line/product_uom/id    (=xml_id)
        """
        if context is None:
            context = {}
        def _replace_field(x):
            x = re.sub('([a-z0-9A-Z_])\\.id$', '\\1/.id', x)
            return x.replace(':id','/id').split('/')
        fields = map(_replace_field, fields)
        logger = netsvc.Logger()
        ir_model_data_obj = self.pool.get('ir.model.data')

        # mode: id (XML id) or .id (database id) or False for name_get
        def _get_id(model_name, id, current_module=False, mode='id', context=None):
            if mode=='.id':
                id = int(id)
                obj_model = self.pool.get(model_name)
                ids = obj_model.search(cr, uid, [('id', '=', int(id))],
                                       limit=1, order='NO_ORDER')
                if not ids:
                    raise Exception(_("Database ID doesn't exist: %s : %s") %(model_name, id))
            elif mode=='id':
                if '.' in id:
                    module, xml_id = id.rsplit('.', 1)
                else:
                    module, xml_id = current_module, id
                record_id = ir_model_data_obj._get_id(cr, uid, module, xml_id)
                ir_model_data = ir_model_data_obj.read(cr, uid, [record_id], ['res_id'])
                if not ir_model_data:
                    raise ValueError('No references to %s.%s' % (module, xml_id))
                id = ir_model_data[0]['res_id']
            else:
                obj_model = self.pool.get(model_name)
                ids = obj_model.name_search(cr, uid, id, operator='=', context=context)
                if not ids:
                    if context.get('sync_update_execution'):
                        newctx = context.copy()
                        newctx['active_test'] = False
                        ids = obj_model.name_search(cr, uid, id, operator='=', context=newctx)

                    if not ids:
                        raise ValueError('No record found for %s' % (id,))
                id = ids[0][0]
            return id

        # IN:
        #   datas: a list of records, each record is defined by a list of values
        #   prefix: a list of prefix fields ['line_ids']
        #   position: the line to process, skip is False if it's the first line of the current record
        # OUT:
        #   (res, position, warning, res_id) with
        #     res: the record for the next line to process (including it's one2many)
        #     position: the new position for the next line
        #     res_id: the ID of the record if it's a modification
        def process_liness(self, datas, prefix, current_module, model_name, fields_def, position=0, skip=0):
            line = datas[position]
            row = {}
            warning = []
            data_res_id = False
            xml_id = False
            nbrmax = position+1
            done = {}

            for i in xrange(len(fields)):
                value = line[i]
                res = False
                #if not value:
                #    continue
                if i >= len(line):
                    raise Exception(_('Please check that all your lines have %d columns.') % (len(fields),))

                field = fields[i]
                if field[:len(prefix)] <> prefix:
                    if value and skip:
                        return False
                    continue

                # ID of the record using a XML ID
                if field[len(prefix)]=='id':
                    try:
                        data_res_id = value and _get_id(model_name, value, current_module, 'id')
                    except ValueError:
                        pass
                    xml_id = value
                    continue

                # ID of the record using a database ID
                elif field[len(prefix)]=='.id':
                    data_res_id = value and _get_id(model_name, value, current_module, '.id')
                    continue

                # recursive call for getting children and returning [(0,0,{})] or [(1,ID,{})]
                field_type = fields_def[field[len(prefix)]]['type']
                with_null = fields_def[field[len(prefix)]].get('with_null')
                if field_type not in ('one2many', 'many2one', 'many2many',
                                      'integer', 'boolean', 'float', 'selection',
                                      'reference'):
                    if not context.get('sync_update_execution', False) and field_type == 'char' and isinstance(value, basestring) \
                            and len(value.splitlines()) > 1 and (field[len(prefix)]!='name' or model_name != 'res.partner'):
                        # US-2661 do not allowed newline character in char fields
                        res = False
                        warning += [_("New line characters in the field '%s' not allowed. Please fix entry :\n'%s'") % (field[len(prefix)], tools.ustr(value))]
                    else:
                        res = value
                elif field_type == 'one2many':
                    if field[len(prefix)] in done:
                        continue
                    done[field[len(prefix)]] = True
                    relation = fields_def[field[len(prefix)]]['relation']
                    relation_obj = self.pool.get(relation)
                    newfd = relation_obj.fields_get( cr, uid, context=context )
                    pos = position
                    res = []
                    first = 0
                    if context.get('sync_update_execution'):
                        res2 = []
                        if len(field) == len(prefix)+1:
                            mode = False
                        else:
                            mode = field[len(prefix)+1]
                        if value:
                            for db_id in value.split(config.get('csv_internal_sep')) or []:
                                res2.append( _get_id(relation, db_id, current_module, mode, context=context))
                        res = [(6, 0, res2)]
                    else:
                        while pos < len(datas):
                            res2 = process_liness(self, datas, prefix + [field[len(prefix)]], current_module, relation_obj._name, newfd, pos, first)
                            if not res2:
                                break
                            (newrow, pos, w2, data_res_id2, xml_id2) = res2
                            nbrmax = max(nbrmax, pos)
                            warning += w2
                            first += 1
                            if (not newrow) or not reduce(lambda x, y: x or y, newrow.values(), 0):
                                break
                            res.append( (data_res_id2 and 1 or 0, data_res_id2 or 0, newrow) )

                elif field_type=='many2one':
                    relation = fields_def[field[len(prefix)]]['relation']
                    if len(field) == len(prefix)+1:
                        mode = False
                    else:
                        mode = field[len(prefix)+1]
                    res = value and _get_id(relation, value, current_module, mode, context=context)

                elif field_type=='many2many':
                    relation = fields_def[field[len(prefix)]]['relation']
                    if len(field) == len(prefix)+1:
                        mode = False
                    else:
                        mode = field[len(prefix)+1]

                    # TODO: improve this by using csv.csv_reader
                    res = []
                    if value:
                        for db_id in value.split(config.get('csv_internal_sep')) or []:
                            res.append( _get_id(relation, db_id, current_module, mode, context=context) )
                    res = [(6,0,res)]

                elif field_type == 'integer':
                    res = value and int(value) or 0
                elif field_type == 'boolean':
                    res = value and value.lower() not in ('0', 'false', 'off') or False
                elif field_type == 'float':
                    res = value and float(value.replace(',','.')) or 0.0
                elif field_type == 'selection':
                    for key, val in fields_def[field[len(prefix)]]['selection']:
                        if value in [tools.ustr(key), tools.ustr(val)] or \
                           tools.ustr(value) in [tools.ustr(key), tools.ustr(val)]:
                            res = key
                            break
                    if not value:
                        res = False
                    if value and not res:
                        model_obj = self.pool.get(model_name)
                        if model_obj:
                            # get the selection from the field.selection definition
                            sel_list = getattr(getattr(model_obj._all_columns.get(field[len(prefix)], object), 'column', object), 'selection', False)
                            if isinstance(sel_list, list):
                                for key, val in sel_list:
                                    if value == val:
                                        res = key
                                        break
                    if value and not res:
                        logger.notifyChannel("import", netsvc.LOG_WARNING,
                                             _("key '%s' not found in selection field '%s'") % \
                                             (value, field[len(prefix)]))
                        warning += [_("Key/value '%s' not found in selection field '%s'") % (value, field[len(prefix)])]
                elif field_type == 'reference':
                    # support importing of reference fields
                    field_value = value and eval(value)
                    if isinstance(field_value, tuple):
                        (module, model, ref_xml_id) = (field_value[0], field_value[1], field_value[2])
                        ir_model_data_obj = self.pool.get('ir.model.data')
                        try:
                            ir_model_data_id = ir_model_data_obj._get_id(cr, 1, module, ref_xml_id)
                            ref_db_id = ir_model_data_obj.read(cr, uid,
                                                               ir_model_data_id, ['res_id'])
                        except:
                            ref_db_id = None
                        res = model and ref_db_id and '%s,%s' % (str(model), str(ref_db_id['res_id'])) or ''
                    else:
                        res = 0

                if with_null and not res and res is not None and res is not False:
                    row[field[len(prefix)]] = res
                else:
                    row[field[len(prefix)]] = res or False

            result = (row, nbrmax, warning, data_res_id, xml_id)
            return result

        fields_def = self.fields_get(cr, uid, context=context)

        from osv import except_osv
        position = 0
        error_list = []
        while position<len(datas):
            res = {}
            try:
                (res, position, warning, res_id, xml_id) = \
                    process_liness(self, datas, [], current_module, self._name, fields_def, position=position)
            except Exception as e:
                if display_all_errors:
                    res = None
                    position += 1
                    warning = [tools.ustr(e)]
                    res_id = False
                    xml_id = False
                else:
                    raise
            if len(warning):
                if display_all_errors:
                    error_list.append(_('Line %s: %s') % (str(position + (has_header and 1 or 0)),
                                                          '\n'.join(warning)))
                    cr.rollback()
                    continue
                else:
                    cr.rollback()
                    return (-1, res, 'Line ' + str(position + (has_header and 1 or 0)) +' : ' + '!\n'.join(warning), '')

            try:
                context.update({'from_import_data': True})
                ir_model_data_obj._update(cr, uid, self._name,
                                          current_module, res, mode=mode, xml_id=xml_id,
                                          noupdate=noupdate, res_id=res_id, context=context)
            except except_osv, e:
                if display_all_errors:
                    error_list.append(_('Line %s: %s') % (str(position + (has_header and 1 or 0)),
                                                          tools.ustr(e.value)))
                    cr.rollback()
                    continue
                else:
                    cr.rollback()
                    return (-1, res, 'Line ' + str(position + (has_header and 1 or 0)) +' : ' + tools.ustr(e.value), '')
            except Exception, e:
                #US-88: If this from an import account analytic, and there is sql error, AND not sync context, then just clear the cache
                if 'account.analytic.account' in self._name and not context.get('sync_update_execution', False):
                    cache.clean_caches_for_db(cr.dbname)
                if display_all_errors:
                    error_list.append(_('Line %s: %s') % (str(position + (has_header and 1 or 0)),
                                                          tools.ustr(e) + "\n" +
                                                          tools.ustr(traceback.format_exc())))
                    cr.rollback()
                    continue
                else:
                    return (-1, res, 'Line ' + str(position + (has_header and 1 or 0)) +' : ' + tools.ustr(e) + "\n" + tools.ustr(traceback.format_exc()), '')

            if not error_list and config.get('import_partial', False) and filename and (not (position%100)):
                data = pickle.load(file(config.get('import_partial')))
                data[filename] = position
                pickle.dump(data, file(config.get('import_partial'), 'wb'))
                if context.get('defer_parent_store_computation'):
                    self._parent_store_compute(cr)
                cr.commit()

        if error_list:
            return (-1, {}, '\n'.join(error_list), '')

        if context.get('defer_parent_store_computation'):
            self._parent_store_compute(cr)
        return (position, 0, 0, 0)

    def read_web(self, cr, user, ids, fields=None, context=None, load='_classic_read'):
        return self.read(cr, user, ids, fields, context=context, load=load)

    def read(self, cr, user, ids, fields=None, context=None, load='_classic_read'):
        """
        Read records with given ids with the given fields

        :param cr: database cursor
        :param user: current user id
        :param ids: id or list of the ids of the records to read
        :param fields: optional list of field names to return (default: all fields would be returned)
        :type fields: list (example ['field_name_1', ...])
        :param context: optional context dictionary - it may contains keys for specifying certain options
                        like ``context_lang``, ``context_tz`` to alter the results of the call.
                        A special ``bin_size`` boolean flag may also be passed in the context to request the
                        value of all fields.binary columns to be returned as the size of the binary instead of its
                        contents. This can also be selectively overriden by passing a field-specific flag
                        in the form ``bin_size_XXX: True/False`` where ``XXX`` is the name of the field.
                        Note: The ``bin_size_XXX`` form is new in OpenERP v6.0.
        :return: list of dictionaries((dictionary per record asked)) with requested field values
        :rtype: [{‘name_of_the_field’: value, ...}, ...]
        :raise AccessError: * if user has no read rights on the requested object
                            * if user tries to bypass access rules for read on the requested object

        """
        raise NotImplementedError(_('The read method is not implemented on this object !'))

    def get_invalid_fields(self, cr, uid):
        return list(self._invalids)

    def _validate(self, cr, uid, ids, context=None):
        context = context or {}
        lng = context and context.get('lang', False) or 'en_US'
        trans = self.pool.get('ir.translation')
        error_msgs = []
        for constraint in self._constraints:
            fun, msg, fields = constraint
            if not fun(self, cr, uid, ids):
                # Check presence of __call__ directly instead of using
                # callable() because it will be deprecated as of Python 3.0
                if hasattr(msg, '__call__'):
                    tmp_msg = msg(self, cr, uid, ids, context=context)
                    if isinstance(tmp_msg, tuple):
                        tmp_msg, params = tmp_msg
                        translated_msg = tmp_msg % params
                    else:
                        translated_msg = tmp_msg
                else:
                    translated_msg = trans._get_source(cr, uid, self._name, 'constraint', lng, source=msg) or msg
                error_msgs.append(
                    _("Error at data validation: %s") % translated_msg
                )
                self._invalids.update(fields)
        if error_msgs:
            cr.rollback()
            raise except_orm('ValidateError', '\n'.join(error_msgs))
        else:
            self._invalids.clear()

    def default_get(self, cr, uid, fields_list, context=None, from_web=False):
        """
        Returns default values for the fields in fields_list.

        :param fields_list: list of fields to get the default values for (example ['field1', 'field2',])
        :type fields_list: list
        :param context: optional context dictionary - it may contains keys for specifying certain options
                        like ``context_lang`` (language) or ``context_tz`` (timezone) to alter the results of the call.
                        It may contain keys in the form ``default_XXX`` (where XXX is a field name), to set
                        or override a default value for a field.
                        A special ``bin_size`` boolean flag may also be passed in the context to request the
                        value of all fields.binary columns to be returned as the size of the binary instead of its
                        contents. This can also be selectively overriden by passing a field-specific flag
                        in the form ``bin_size_XXX: True/False`` where ``XXX`` is the name of the field.
                        Note: The ``bin_size_XXX`` form is new in OpenERP v6.0.
        :return: dictionary of the default values (set on the object model class, through user preferences, or in the context)
        """
        # trigger view init hook
        self.view_init(cr, uid, fields_list, context)

        if context is None:
            context = {}
        defaults = {}

        # get the default values for the inherited fields
        for t in self._inherits.keys():
            defaults.update(self.pool.get(t).default_get(cr, uid, fields_list,
                                                         context, from_web=from_web))

        # get the default values defined in the object
        for f in fields_list:
            if f in self._defaults:
                if callable(self._defaults[f]):
                    defaults[f] = self._defaults[f](self, cr, uid, context)
                else:
                    defaults[f] = self._defaults[f]

            fld_def = ((f in self._columns) and self._columns[f]) \
                or ((f in self._inherit_fields) and self._inherit_fields[f][2]) \
                or False

            if isinstance(fld_def, fields.property):
                property_obj = self.pool.get('ir.property')
                prop_value = property_obj.get(cr, uid, f, self._name, context=context)
                if prop_value:
                    if isinstance(prop_value, (browse_record, browse_null)):
                        defaults[f] = prop_value.id
                    else:
                        defaults[f] = prop_value
                else:
                    if f not in defaults:
                        defaults[f] = False

        # get the default values set by the user and override the default
        # values defined in the object
        ir_values_obj = self.pool.get('ir.values')
        meta = False
        if from_web:
            meta = 'web'
        res = ir_values_obj.get(cr, uid, 'default', False, [self._name], meta=meta, context=context)
        for id, field, field_value in res:
            if field in fields_list:
                fld_def = (field in self._columns) and self._columns[field] or self._inherit_fields[field][2]
                if fld_def._type in ('many2one', 'one2one'):
                    obj = self.pool.get(fld_def._obj)
                    if not obj.search(cr, uid, [('id', '=', field_value or
                                                 False)], limit=1, order='NO_ORDER'):
                        continue
                if fld_def._type in ('many2many'):
                    obj = self.pool.get(fld_def._obj)
                    field_value2 = []
                    for i in range(len(field_value)):
                        if not obj.search(cr, uid, [('id', '=',
                                                     field_value[i])], limit=1, order='NO_ORDER'):
                            continue
                        field_value2.append(field_value[i])
                    field_value = field_value2
                if fld_def._type in ('one2many'):
                    obj = self.pool.get(fld_def._obj)
                    field_value2 = []
                    for i in range(len(field_value)):
                        field_value2.append({})
                        for field2 in field_value[i]:
                            if field2 in obj._columns.keys() and obj._columns[field2]._type in ('many2one', 'one2one'):
                                obj2 = self.pool.get(obj._columns[field2]._obj)
                                if not obj2.search(cr, uid,
                                                   [('id', '=', field_value[i][field2])],
                                                   limit=1, order='NO_ORDER'):
                                    continue
                            elif field2 in obj._inherit_fields.keys() and obj._inherit_fields[field2][2]._type in ('many2one', 'one2one'):
                                obj2 = self.pool.get(obj._inherit_fields[field2][2]._obj)
                                if not obj2.search(cr, uid,
                                                   [('id', '=', field_value[i][field2])],
                                                   limit=1, order='NO_ORDER'):
                                    continue
                            # TODO add test for many2many and one2many
                            field_value2[i][field2] = field_value[i][field2]
                    field_value = field_value2
                defaults[field] = field_value

        # get the default values from the context
        for key in context or {}:
            if key.startswith('default_') and (key[8:] in fields_list):
                defaults[key[8:]] = context[key]
        return defaults


    def perm_read(self, cr, user, ids, context=None, details=True):
        raise NotImplementedError(_('The perm_read method is not implemented on this object !'))

    def unlink(self, cr, uid, ids, context=None):
        raise NotImplementedError(_('The unlink method is not implemented on this object !'))

    def write(self, cr, user, ids, vals, context=None):
        raise NotImplementedError(_('The write method is not implemented on this object !'))

    def write_web(self, cr, user, ids, vals, context=None):
        """
        Method called by the Web on write
        """
        return self.write(cr, user, ids, vals, context=context)


    def create(self, cr, user, vals, context=None):
        raise NotImplementedError(_('The create method is not implemented on this object !'))

    def fields_get_keys(self, cr, user, context=None):
        res = self._columns.keys()
        for parent in self._inherits:
            res.extend(self.pool.get(parent).fields_get_keys(cr, user, context))
        return res

    # returns the definition of each field in the object
    # the optional fields parameter can limit the result to some fields
    def fields_get(self, cr, user, allfields=None, context=None, write_access=True, with_uom_rounding=False):
        if context is None:
            context = {}
        res = {}
        translation_obj = self.pool.get('ir.translation')
        for parent in self._inherits:
            res.update(self.pool.get(parent).fields_get(cr, user, allfields, context))

        uom_rounding = False
        if self._columns.keys():
            for f in self._columns.keys():
                field_col = self._columns[f]
                if allfields and f not in allfields:
                    continue
                res[f] = {'type': field_col._type}
                if hasattr(field_col, '_with_null') and field_col._with_null:
                    res[f]['with_null'] = True
                if hasattr(field_col, 'null_value') and field_col.null_value:
                    res[f]['null_value'] = field_col.null_value
                # This additional attributes for M2M and function field is added
                # because we need to display tooltip with this additional information
                # when client is started in debug mode.
                if isinstance(field_col, fields.function):
                    res[f]['function'] = field_col._fnct and field_col._fnct.func_name or False
                    res[f]['store'] = field_col.store
                    if isinstance(field_col.store, dict):
                        res[f]['store'] = str(field_col.store)
                    res[f]['fnct_search'] = field_col._fnct_search and field_col._fnct_search.func_name or False
                    res[f]['fnct_inv'] = field_col._fnct_inv and field_col._fnct_inv.func_name or False
                    res[f]['fnct_inv_arg'] = field_col._fnct_inv_arg or False
                    res[f]['func_obj'] = field_col._obj or False
                    res[f]['func_method'] = field_col._method
                if isinstance(field_col, fields.many2many):
                    res[f]['related_columns'] = list((field_col._id1, field_col._id2))
                    res[f]['third_table'] = field_col._rel
                for arg in ('string', 'readonly', 'states', 'size', 'required', 'group_operator',
                            'change_default', 'translate', 'help', 'select',
                            'selectable', 'internal', 'hide_default_menu', 'sort_column'):
                    if getattr(field_col, arg):
                        res[f][arg] = getattr(field_col, arg)
                if not write_access:
                    res[f]['readonly'] = True
                    res[f]['states'] = {}
                    res[f]['no_write_access'] = True
                for arg in ('digits', 'invisible', 'filters', 'computation', 'related_uom'):
                    if getattr(field_col, arg, None):
                        res[f][arg] = getattr(field_col, arg)

                if with_uom_rounding and res[f].get('related_uom'):
                    if not uom_rounding:
                        uom_rounding = self.pool.get('product.uom').get_rounding(cr, 1)
                    res[f]['uom_rounding'] = uom_rounding

                context_lang = context and context.get('lang', False) or 'en_US'
                if field_col.string and context_lang != 'en_US':
                    res_trans = translation_obj._get_source(cr, user,
                                                            self._name + ',' + f, 'field', context_lang)
                    if res_trans:
                        res[f]['string'] = res_trans
                if field_col._type == 'float' and context_lang == 'en_MF' and hasattr(field_col, 'en_thousand_sep'):
                    if not field_col.en_thousand_sep:
                        res[f]['en_thousand_sep'] = False

                if field_col.help and context_lang != 'en_US':
                    help_trans = translation_obj._get_source(cr, user,
                                                             self._name + ',' + f, 'help', context_lang)
                    if help_trans:
                        res[f]['help'] = help_trans

                if hasattr(field_col, 'selection'):
                    if isinstance(field_col.selection, (tuple, list)):
                        sel = field_col.selection
                    else:
                        # call the 'dynamic selection' function
                        sel = field_col.selection(self, cr, user, context)
                    # translate each selection option
                    sel2 = []
                    sel2_append = sel2.append
                    if context_lang != 'en_US':
                        for (key, val) in sel:
                            val2 = None
                            if val:
                                val2 = translation_obj._get_source(cr, user,
                                                                   self._name + ',' + f, 'selection',
                                                                   context_lang, val)
                            sel2_append((key, val2 or val))
                    sel = sel2 or sel
                    if getattr(field_col, 'add_empty', None):
                        res[f]['add_empty'] = getattr(field_col, 'add_empty')
                    res[f]['selection'] = sel
                if res[f]['type'] in ('one2many', 'many2many', 'many2one', 'one2one'):
                    res[f]['relation'] = field_col._obj
                    res[f]['domain'] = field_col._domain
                    res[f]['context'] = field_col._context
        else:
            #TODO : read the fields from the database
            pass

        if allfields:
            # filter out fields which aren't in the fields list
            for r in res.keys():
                if r not in allfields:
                    del res[r]
        return res

    #
    # Overload this method if you need a window title which depends on the context
    #
    def view_header_get(self, cr, user, view_id=None, view_type='form', context=None):
        return False

    def __view_look_dom(self, cr, user, node, view_id, context=None):
        if context is None:
            context = {}
        result = False
        fields = {}
        children = True

        def encode(s):
            if isinstance(s, unicode):
                return s.encode('utf8')
            return s

        # return True if node can be displayed to current user
        def check_group(node):
            if node.get('groups'):
                groups = node.get('groups').split(',')
                access_pool = self.pool.get('ir.model.access')
                can_see = any(access_pool.check_groups(cr, user, group) for group in groups)
                if not can_see:
                    node.set('invisible', '1')
                    if 'attrs' in node.attrib:
                        del(node.attrib['attrs']) #avoid making field visible later
                del(node.attrib['groups'])
                return can_see
            else:
                return True

        if node.tag in ('field', 'node', 'arrow'):
            if node.get('object'):
                attrs = {}
                views = {}
                xml = "<form>"
                for f in node:
                    if f.tag in ('field'):
                        xml += etree.tostring(f, encoding="utf-8")
                xml += "</form>"
                new_xml = etree.fromstring(encode(xml))
                ctx = context.copy()
                ctx['base_model_name'] = self._name
                xarch, xfields = self.pool.get(node.get('object')).__view_look_dom_arch(cr, user, new_xml, view_id, ctx)
                views['form'] = {
                    'arch': xarch,
                    'fields': xfields
                }
                attrs = {'views': views}
                fields = xfields
            if node.get('name'):
                attrs = {}
                try:
                    if node.get('name') in self._columns:
                        column = self._columns[node.get('name')]
                    else:
                        column = self._inherit_fields[node.get('name')][2]
                except Exception:
                    column = False

                if column:
                    relation = self.pool.get(column._obj)

                    children = False
                    views = {}
                    for f in node:
                        if f.tag in ('form', 'tree', 'graph'):
                            node.remove(f)
                            ctx = context.copy()
                            ctx['base_model_name'] = self._name
                            xarch, xfields = relation.__view_look_dom_arch(cr, user, f, view_id, ctx)
                            views[str(f.tag)] = {
                                'arch': xarch,
                                'fields': xfields
                            }
                    attrs = {'views': views}
                    if node.get('widget') and node.get('widget') == 'selection' and not node.get('get_selection'):
                        # Prepare the cached selection list for the client. This needs to be
                        # done even when the field is invisible to the current user, because
                        # other events could need to change its value to any of the selectable ones
                        # (such as on_change events, refreshes, etc.)

                        # If domain and context are strings, we keep them for client-side, otherwise
                        # we evaluate them server-side to consider them when generating the list of
                        # possible values
                        # TODO: find a way to remove this hack, by allow dynamic domains
                        dom = []
                        if column._domain and not isinstance(column._domain, basestring):
                            dom = column._domain
                        dom += eval(node.get('domain', '[]'), {'uid': user, 'time': time})
                        search_context = dict(context)
                        if column._context and not isinstance(column._context, basestring):
                            search_context.update(column._context)
                        attrs['selection'] = relation._name_search(cr, user, '', dom, context=search_context, limit=None, name_get_uid=1)
                        if (node.get('required') and not int(node.get('required'))) or not column.required:
                            attrs['selection'].append((False, ''))
                fields[node.get('name')] = attrs

        elif node.tag in ('form', 'tree'):
            result = self.view_header_get(cr, user, False, node.tag, context)
            if result:
                node.set('string', result)

        elif node.tag == 'calendar':
            for additional_field in ('date_start', 'date_delay', 'date_stop', 'color'):
                if node.get(additional_field):
                    fields[node.get(additional_field)] = {}

        if 'groups' in node.attrib:
            check_group(node)

        # translate view
        if ('lang' in context) and not result:
            translation_obj = self.pool.get('ir.translation')
            if node.get('sum'):
                trans = translation_obj._get_source(cr, user, self._name, 'view', context['lang'], node.get('sum'))
                if trans:
                    node.set('sum', trans)
            if node.get('confirm'):
                trans = translation_obj._get_source(cr, user, self._name, 'view', context['lang'], node.get('confirm'))
                if trans:
                    node.set('confirm', trans)
            if node.get('help'):
                trans = translation_obj._get_source(cr, user, self._name, 'view', context['lang'], node.get('help'))
                if trans:
                    node.set('help', trans)
            if node.get('required_error_msg'):
                trans = translation_obj._get_source(cr, user, self._name, 'view', context['lang'], node.get('required_error_msg'))
                if trans:
                    node.set('required_error_msg', trans)
            if node.get('string'):
                trans = translation_obj._get_source(cr, user, self._name, 'view', context['lang'], node.get('string'))
                if trans == node.get('string') and ('base_model_name' in context):
                    # If translation is same as source, perhaps we'd have more luck with the alternative model name
                    # (in case we are in a mixed situation, such as an inherited view where parent_view.model != model
                    trans = translation_obj._get_source(cr, user, context['base_model_name'], 'view', context['lang'], node.get('string'))
                if trans:
                    node.set('string', trans)
            if node.get('filter_selector'):
                try:
                    filter_eval = eval(node.get('filter_selector'))
                    if filter_eval and isinstance(filter_eval, list):
                        trans_filter_eval = []
                        for x in filter_eval:
                            trans_x = translation_obj._get_source(cr, user, self._name, 'view', context['lang'], x[0])
                            trans_filter_eval.append((trans_x, x[1]))
                        node.set('filter_selector', '%s'%trans_filter_eval)
                except:
                    logger = netsvc.Logger()
                    logger.notifyChannel("translate.view", netsvc.LOG_WARNING, "Unable to translate %s" % node.get('filter_selector'))

            if node.tag == 'translate':
                parent = node.getparent()
                source = node.text
                for child in node.getchildren():
                    source += etree.tostring(child)
                trans = translation_obj._get_source(cr, user, self._name,
                                                    'view', context['lang'], source)
                parent.remove(node)
                parent.text = parent.text and parent.text + trans or trans

        for f in node:
            if children or (node.tag == 'field' and f.tag in ('filter', 'separator')):
                fields.update(self.__view_look_dom(cr, user, f, view_id, context))

        return fields

    def _disable_workflow_buttons(self, cr, user, node):
        if user == 1:
            # admin user can always activate workflow buttons
            return node

        # TODO handle the case of more than one workflow for a model or multiple
        # transitions with different groups and same signal
        usersobj = self.pool.get('res.users')
        buttons = (n for n in node.getiterator('button') if n.get('type') != 'object')
        for button in buttons:
            user_groups = usersobj.read(cr, user, [user], ['groups_id'])[0]['groups_id']
            cr.execute("""SELECT DISTINCT t.group_id
                        FROM wkf
                  INNER JOIN wkf_activity a ON a.wkf_id = wkf.id
                  INNER JOIN wkf_transition t ON (t.act_to = a.id)
                       WHERE wkf.osv = %s
                         AND t.signal = %s
                         AND t.group_id is NOT NULL
                   """, (self._name, button.get('name')))
            group_ids = [x[0] for x in cr.fetchall() if x[0]]
            can_click = not group_ids or bool(set(user_groups).intersection(group_ids))
            button.set('readonly', str(int(not can_click)))
        return node

    def __view_look_dom_arch(self, cr, user, node, view_id, context=None):
        fields_def = self.__view_look_dom(cr, user, node, view_id, context=context)
        node = self._disable_workflow_buttons(cr, user, node)
        arch = etree.tostring(node, encoding="utf-8").replace('\t', '')
        fields = {}
        if node.tag == 'diagram':
            if node.getchildren()[0].tag == 'node':
                node_fields = self.pool.get(node.getchildren()[0].get('object')).fields_get(cr, user, fields_def.keys(), context)
            if node.getchildren()[1].tag == 'arrow':
                arrow_fields = self.pool.get(node.getchildren()[1].get('object')).fields_get(cr, user, fields_def.keys(), context)
            for key, value in node_fields.items():
                fields[key] = value
            for key, value in arrow_fields.items():
                fields[key] = value
        else:
            fields = self.fields_get(cr, user, fields_def.keys(), context)
        for field in fields_def:
            if field == 'id':
                # sometime, the view may contain the (invisible) field 'id' needed for a domain (when 2 objects have cross references)
                fields['id'] = {'readonly': True, 'type': 'integer', 'string': 'ID'}
            elif field in fields:
                fields[field].update(fields_def[field])
            else:
                cr.execute('select name, model from ir_ui_view where (id=%s or inherit_id=%s) and arch like %s', (view_id, view_id, '%%%s%%' % field))
                res = cr.fetchall()[:]
                model = res[0][1]
                res.insert(0, ("Can't find field '%s' in the following view parts composing the view of object model '%s':" % (field, model), None))
                msg = "\n * ".join([r[0] for r in res])
                msg += "\n\nEither you wrongly customized this view, or some modules bringing those views are not compatible with your current data model"
                netsvc.Logger().notifyChannel('orm', netsvc.LOG_ERROR, msg)
                raise except_orm('View error', msg)
        return arch, fields

    def __get_default_calendar_view(self):
        """Generate a default calendar view (For internal use only).
        """

        arch = ('<?xml version="1.0" encoding="utf-8"?>\n'
                '<calendar string="%s"') % (self._description)

        if (self._date_name not in self._columns):
            date_found = False
            for dt in ['date', 'date_start', 'x_date', 'x_date_start']:
                if dt in self._columns:
                    self._date_name = dt
                    date_found = True
                    break

            if not date_found:
                raise except_orm(_('Invalid Object Architecture!'), _("Insufficient fields for Calendar View!"))

        if self._date_name:
            arch += ' date_start="%s"' % (self._date_name)

        for color in ["user_id", "partner_id", "x_user_id", "x_partner_id"]:
            if color in self._columns:
                arch += ' color="' + color + '"'
                break

        dt_stop_flag = False

        for dt_stop in ["date_stop", "date_end", "x_date_stop", "x_date_end"]:
            if dt_stop in self._columns:
                arch += ' date_stop="' + dt_stop + '"'
                dt_stop_flag = True
                break

        if not dt_stop_flag:
            for dt_delay in ["date_delay", "planned_hours", "x_date_delay", "x_planned_hours"]:
                if dt_delay in self._columns:
                    arch += ' date_delay="' + dt_delay + '"'
                    break

        arch += ('>\n'
                 '  <field name="%s"/>\n'
                 '</calendar>') % (self._rec_name)

        return arch

    def __get_default_search_view(self, cr, uid, context=None):
        form_view = self.fields_view_get(cr, uid, False, 'form', context=context)
        tree_view = self.fields_view_get(cr, uid, False, 'tree', context=context)

        fields_to_search = set()
        fields = self.fields_get(cr, uid, context=context)
        for field in fields:
            if fields[field].get('select'):
                fields_to_search.add(field)
        for view in (form_view, tree_view):
            view_root = etree.fromstring(view['arch'])
            # Only care about select=1 in xpath below, because select=2 is covered
            # by the custom advanced search in clients
            fields_to_search = fields_to_search.union(view_root.xpath("//field[@select=1]/@name"))

        tree_view_root = view_root # as provided by loop above
        search_view = etree.Element("search", attrib={'string': tree_view_root.get("string", "")})
        field_group = etree.Element("group")
        search_view.append(field_group)

        for field_name in fields_to_search:
            field_group.append(etree.Element("field", attrib={'name': field_name}))

        return etree.tostring(search_view, encoding="utf-8").replace('\t', '')

    #
    # if view_id, view_type is not required
    #
    def fields_view_get(self, cr, user, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Get the detailed composition of the requested view like fields, model, view architecture

        :param cr: database cursor
        :param user: current user id
        :param view_id: id of the view or None
        :param view_type: type of the view to return if view_id is None ('form', tree', ...)
        :param context: context arguments, like lang, time zone
        :param toolbar: true to include contextual actions
        :param submenu: example (portal_project module)
        :return: dictionary describing the composition of the requested view (including inherited views and extensions)
        :raise AttributeError:
                            * if the inherited view has unknown position to work with other than 'before', 'after', 'inside', 'replace'
                            * if some tag other than 'position' is found in parent view
        :raise Invalid ArchitectureError: if there is view type other than form, tree, calendar, search etc defined on the structure

        """
        if context is None:
            context = {}

        view_id_orig = view_id
        def encode(s):
            if isinstance(s, unicode):
                return s.encode('utf8')
            return s

        def raise_view_error(error_msg, child_view_id):
            view, child_view = self.pool.get('ir.ui.view').browse(cr, user, [view_id, child_view_id], context)
            raise AttributeError(("View definition error for inherited view '%(xml_id)s' on '%(model)s' model: " + error_msg)
                                 %  { 'xml_id': child_view.xml_id,
                                      'parent_xml_id': view.xml_id,
                                      'model': self._name, })

        def _inherit_apply(src, inherit, inherit_id=None):
            def _find(node, node2):
                if node2.tag == 'xpath':
                    res = node.xpath(node2.get('expr'))
                    if res:
                        return res[0]
                    else:
                        return None
                else:
                    for n in node.getiterator(node2.tag):
                        res = True
                        if node2.tag == 'field':
                            # only compare field names, a field can be only once in a given view
                            # at a given level (and for multilevel expressions, we should use xpath
                            # inheritance spec anyway)
                            if node2.get('name') == n.get('name'):
                                return n
                            else:
                                continue
                        for attr in node2.attrib:
                            if attr == 'position':
                                continue
                            if n.get(attr):
                                if n.get(attr) == node2.get(attr):
                                    continue
                            res = False
                        if res:
                            return n
                return None

            # End: _find(node, node2)

            doc_dest = etree.fromstring(encode(inherit))
            toparse = [doc_dest]

            while len(toparse):
                node2 = toparse.pop(0)
                if isinstance(node2, SKIPPED_ELEMENT_TYPES):
                    continue
                if node2.tag == 'data':
                    toparse += [ c for c in doc_dest ]
                    continue
                node = _find(src, node2)
                if node is not None:
                    pos = 'inside'
                    if node2.get('position'):
                        pos = node2.get('position')
                    if pos == 'replace':
                        parent = node.getparent()
                        if parent is None:
                            src = copy.deepcopy(node2[0])
                        else:
                            for child in node2:
                                node.addprevious(child)
                            node.getparent().remove(node)
                    elif pos == 'attributes':
                        for child in node2.getiterator('attribute'):
                            attribute = (child.get('name'), child.text and child.text.encode('utf8') or None)
                            if attribute[1]:
                                node.set(attribute[0], attribute[1])
                            else:
                                del(node.attrib[attribute[0]])
                    else:
                        sib = node.getnext()
                        for child in node2:
                            if pos == 'inside':
                                node.append(child)
                            elif pos == 'after':
                                if sib is None:
                                    node.addnext(child)
                                    node = child
                                else:
                                    sib.addprevious(child)
                            elif pos == 'before':
                                node.addprevious(child)
                            else:
                                raise_view_error("Invalid position value: '%s'" % pos, inherit_id)
                else:
                    attrs = ''.join([
                        ' %s="%s"' % (attr, node2.get(attr))
                        for attr in node2.attrib
                        if attr != 'position'
                    ])
                    tag = "<%s%s>" % (node2.tag, attrs)
                    raise_view_error("Element '%s' not found in parent view '%%(parent_xml_id)s'" % tag, inherit_id)
            return src
        # End: _inherit_apply(src, inherit)

        result = {'type': view_type, 'model': self._name}

        model = True
        is_inherited_view = True
        sql_res = False
        parent_view_model = None
        view_id_kept = False
        while is_inherited_view:
            view_ref = context.get(view_type + '_view_ref', False)
            if view_ref and not view_id:
                if '.' in view_ref:
                    module, view_ref = view_ref.split('.', 1)
                    cr.execute("SELECT res_id FROM ir_model_data WHERE model='ir.ui.view' AND module=%s AND name=%s", (module, view_ref))
                    view_ref_res = cr.fetchone()
                    if view_ref_res:
                        view_id = view_ref_res[0]

            if view_id:
                query = "SELECT arch,name,field_parent,id,type,inherit_id,model, duplicate_view_id, title_field FROM ir_ui_view WHERE id=%s"
                params = (view_id,)
                if model:
                    query += " AND model = %s"
                    params += (self._name,)
                cr.execute(query, params)
            else:
                cr.execute('''SELECT
                        arch,name,field_parent,id,type,inherit_id,model, 'f', title_field
                    FROM
                        ir_ui_view
                    WHERE
                        model = %s AND
                        type=%s AND
                        inherit_id IS NULL
                    ORDER BY priority''', (self._name, view_type))
            sql_res = cr.fetchone()
            if not sql_res:
                break

            is_inherited_view = sql_res[5]
            view_id = is_inherited_view or sql_res[3]
            model = False
            parent_view_model = sql_res[6]
            if sql_res[7] and view_id_orig:
                view_id_kept = view_id_orig
                is_inherited_view = True
                view_id = sql_res[7]
            # use view_id_orig only on 1st loop
            view_id_orig = False

        # if a view was found
        if sql_res:
            result['type'] = sql_res[4]
            result['view_id'] = view_id_kept or sql_res[3]
            result['arch'] = sql_res[0]
            result['title_field'] = sql_res[8]

            # Reverse the search on models to apply view inheritance in a good way
            def _inherit_apply_rec(result, inherit_id):
                # get all views which inherit from (ie modify) this view
                cr.execute('select arch, id from ir_ui_view where inherit_id=%s and model = %s order by priority', (inherit_id, self._name))
                sql_inherit = cr.fetchall()
                for (inherit, id) in sql_inherit:
                    result = _inherit_apply(result, inherit, id)
                    result = _inherit_apply_rec(result, id)
                return result

            inherit_result = etree.fromstring(encode(result['arch']))
            result['arch'] = _inherit_apply_rec(inherit_result, sql_res[3])
            if view_id_kept:
                result['arch'] = _inherit_apply_rec(result['arch'], view_id_kept)
            result['name'] = sql_res[1]
            result['field_parent'] = sql_res[2] or False
        else:
            # otherwise, build some kind of default view
            if view_type == 'form':
                res = self.fields_get(cr, user, context=context)
                xml = '<?xml version="1.0" encoding="utf-8"?> ' \
                    '<form string="%s">' % (self._description,)
                for x in res:
                    if res[x]['type'] not in ('one2many', 'many2many'):
                        xml += '<field name="%s"/>' % (x,)
                        if res[x]['type'] == 'text':
                            xml += "<newline/>"
                xml += "</form>"

            elif view_type == 'tree':
                _rec_name = self._rec_name
                if _rec_name not in self._columns:
                    _rec_name = self._columns.keys()[0]
                xml = '<?xml version="1.0" encoding="utf-8"?>' \
                    '<tree string="%s"><field name="%s"/></tree>' \
                    % (self._description, self._rec_name)

            elif view_type == 'calendar':
                xml = self.__get_default_calendar_view()

            elif view_type == 'search':
                xml = self.__get_default_search_view(cr, user, context)

            else:
                xml = '<?xml version="1.0"?>' # what happens here, graph case?
                raise except_orm(_('Invalid Architecture!'), _("There is no view of type '%s' defined for the structure!") % view_type)
            result['arch'] = etree.fromstring(encode(xml))
            result['name'] = 'default'
            result['field_parent'] = False
            result['view_id'] = 0

        if parent_view_model != self._name:
            ctx = context.copy()
            ctx['base_model_name'] = parent_view_model
        else:
            ctx = context
        xarch, xfields = self.__view_look_dom_arch(cr, user, result['arch'], view_id, context=ctx)
        result['arch'] = xarch
        result['fields'] = xfields


        result['uom_rounding'] = {}
        uom_obj = self.pool.get('product.uom')
        if uom_obj:
            result['uom_rounding'] = uom_obj.get_rounding(cr, user)
        if submenu:
            if context and context.get('active_id', False):
                data_menu = self.pool.get('ir.ui.menu').browse(cr, user, context['active_id'], context).action
                if data_menu:
                    act_id = data_menu.id
                    if act_id and data_menu._name == 'ir.actions.act_window':
                        data_action = self.pool.get('ir.actions.act_window').browse(cr, user, [act_id], context)[0]
                        result['submenu'] = getattr(data_action, 'menus', False)
        if toolbar:
            def clean(x):
                x = x[2]
                for key in ('report_sxw_content', 'report_rml_content',
                            'report_sxw', 'report_rml',
                            'report_sxw_content_data', 'report_rml_content_data'):
                    if key in x:
                        del x[key]
                return x
            ir_values_obj = self.pool.get('ir.values')
            resprint = ir_values_obj.get(cr, user, 'action',
                                         'client_print_multi', [(self._name, False)], False,
                                         context, view_id=view_id_kept or view_id)
            resaction = ir_values_obj.get(cr, user, 'action',
                                          'client_action_multi', [(self._name, False)], False,
                                          context, view_id=view_id_kept or view_id)

            resrelate = ir_values_obj.get(cr, user, 'action',
                                          'client_action_relate', [(self._name, False)], False,
                                          context, view_id=view_id_kept or view_id)
            resprint = map(clean, resprint)
            resaction = map(clean, resaction)
            resaction = filter(lambda x: not x.get('multi', False), resaction)
            resprint = filter(lambda x: not x.get('multi', False), resprint)
            resrelate = map(lambda x: x[2], resrelate)

            for x in resprint + resaction + resrelate:
                x['string'] = x['name']

            result['toolbar'] = {
                'print': resprint,
                'action': resaction,
                'relate': resrelate
            }
        return result

    _view_look_dom_arch = __view_look_dom_arch

    def approximate_search_count(self, cr, user, args, context=None):
        """
        search_count can be very slow on big tables as it need to parse all
        elements one by one. This method is very fast but not very accurate.
        In case there is less than 100000 elements, the exact result will be
        returned (search_count), else an aproximate one.
        In addition a boolean is also returned to know if the result is exact
        or approximate.
        :return: (count, boolean) boolean is True in case of approximation
        """
        if not args or \
                (self._table in ['account_move_line', 'account_move'] and args in ([('period_id.number', '!=', 0)], [('period_id.number', '!=', 0), ('move_id.state', '=', 'posted')])) or \
                (self._table == 'account_analytic_line' and args == [('account_id.category', '=', 'FUNDING')]):
            cr.execute("""
                SELECT reltuples::BIGINT AS approximate_row_count
                FROM pg_class WHERE relname = '%s'
            """ % self._table)  # not_a_user_entry
            approximative_result = cr.fetchall()
            approximative_result = approximative_result and approximative_result[0][0] or 0
            # check if approximative is big
            if approximative_result > 100000:
                exclude = 0
                if self._table in ['account_move_line', 'account_move']:
                    exclude = self.search_count(cr, user, [('period_id.number', '=', 0)], context={'show_period_0': 1})
                if self._table == 'account_move_line' and args == [('period_id.number', '!=', 0), ('move_id.state', '=', 'posted')]:
                    exclude += self.search_count(cr, user, [('move_id.state', '=', 'draft')], context=context)
                if self._table == 'account_analytic_line':
                    exclude = self.search_count(cr, user, [('account_id.category', '!=', 'FUNDING')], context=context)
                return int(approximative_result) - exclude, True
        return self.search_count(cr, user, args, context=context), False


    def search_count(self, cr, user, args, context=None):
        if context is None:
            context = {}
        res = self.search(cr, user, args, context=context, count=True)
        if isinstance(res, list):
            return len(res)
        return res

    def has_index(self,cr, column_name):
        '''
            check if column_name have an index in the database
        '''
        indexname = '%s_%s_index' % (self._table, column_name)
        cr.execute("SELECT indexname FROM pg_indexes WHERE indexname = %s and tablename = %s", (indexname, self._table))
        res = cr.dictfetchall()
        if res:
            return True
        return False

    def exact_search_web(self, cr, uid, args=None, offset=0, limit=None, order=None, context=None, count=False):
        '''
            If the domain exists, check that it contains at least one exact search.
            And exact search contain at least one '=' in its subdomain
            and this subdomain have a corresponding index in the databse
        '''
        if args:
            exact_search = False
            exact_search_with_no_index = []
            for sub_domain in args:
                if len(sub_domain) > 1 and sub_domain[1] in ('=', '<=', '>='):
                    # check this column have an index, if not this doesn't
                    # count as an exact search
                    if self.has_index(cr, sub_domain[0]):
                        exact_search = True
                        break
                    exact_search_with_no_index.append(_(self._columns[sub_domain[0]].string))

            if not exact_search:
                if exact_search_with_no_index:
                    raise except_orm(_("Error!"), _("Sorry, the field(s) '%s' can not be searched alone with '='. Use '=' with others search fields.") % ', '.join(exact_search_with_no_index))
                raise except_orm(_("Error!"), _("You can't search on this object without using at least one exact search term (precede your search with the character '=')."))

        return self.search(cr, uid, args, offset, limit,
                           order, context=context, count=count)

    def search_web(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        '''
        by default search_web do the same thing than search. If you need a
        special treatment, you need to redifine it in the class you wan't
        (in which you can call exact_search_web() for example if you want to
        force for exact search
        '''
        return self.search(cr, user, args, offset, limit, order, context, count)

    def search_exists(self, cr, user, args, context=None):
        """
        return True if there is at least one element matching the criterions,
        False otherwise.
        """
        return bool(self.search(cr, user, args, context=context,
                                limit=1, order='NO_ORDER'))

    def search_exist(self, cr, user, args, context=None):
        return self.search_exists(cr, user, args, context=context)

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        """
        Search for records based on a search domain.

        :param cr: database cursor
        :param user: current user id
        :param args: list of tuples specifying the search domain [('field_name', 'operator', value), ...]. Pass an empty list to match all records.
        :param offset: optional number of results to skip in the returned values (default: 0)
        :param limit: optional max number of records to return (default: **None**)
        :param order: optional columns to sort by (default: self._order=id )
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :param count: optional (default: **False**), if **True**, returns only the number of records matching the criteria, not their ids
        :return: id or list of ids of records matching the criteria
        :rtype: integer or list of integers
        :raise AccessError: * if user tries to bypass access rules for read on the requested object.

        **Expressing a search domain (args)**

        Each tuple in the search domain needs to have 3 elements, in the form: **('field_name', 'operator', value)**, where:

            * **field_name** must be a valid name of field of the object model, possibly following many-to-one relationships using dot-notation, e.g 'street' or 'partner_id.country' are valid values.
            * **operator** must be a string with a valid comparison operator from this list: ``=, !=, >, >=, <, <=, like, ilike, in, not in, child_of, parent_left, parent_right``
              The semantics of most of these operators are obvious.
              The ``child_of`` operator will look for records who are children or grand-children of a given record,
              according to the semantics of this model (i.e following the relationship field named by
              ``self._parent_name``, by default ``parent_id``.
            * **value** must be a valid value to compare with the values of **field_name**, depending on its type.

        Domain criteria can be combined using 3 logical operators than can be added between tuples:  '**&**' (logical AND, default), '**|**' (logical OR), '**!**' (logical NOT).
        These are **prefix** operators and the arity of the '**&**' and '**|**' operator is 2, while the arity of the '**!**' is just 1.
        Be very careful about this when you combine them the first time.

        Here is an example of searching for Partners named *ABC* from Belgium and Germany whose language is not english ::

            [('name','=','ABC'),'!',('language.code','=','en_US'),'|',('country_id.code','=','be'),('country_id.code','=','de'))

        The '&' is omitted as it is the default, and of course we could have used '!=' for the language, but what this domain really represents is::

            (name is 'ABC' AND (language is NOT english) AND (country is Belgium OR Germany))

        """
        return self._search(cr, user, args, offset=offset, limit=limit, order=order, context=context, count=count)

    def _search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False, access_rights_uid=None):
        """
        Private implementation of search() method, allowing specifying the uid to use for the access right check.
        This is useful for example when filling in the selection list for a drop-down and avoiding access rights errors,
        by specifying ``access_rights_uid=1`` to bypass access rights check, but not ir.rules!

        :param access_rights_uid: optional user ID to use when checking access rights
                                  (not for ir.rules, this is only for ir.model.access)
        """
        raise NotImplementedError(_('The search method is not implemented on this object !'))

    def name_get(self, cr, user, ids, context=None):
        """

        :param cr: database cursor
        :param user: current user id
        :type user: integer
        :param ids: list of ids
        :param context: context arguments, like lang, time zone
        :type context: dictionary
        :return: tuples with the text representation of requested objects for to-many relationships

        """
        if context is None:
            context = {}
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        return [(r['id'], tools.ustr(r[self._rec_name])) for r in self.read(cr, user, ids,
                                                                            [self._rec_name], context, load='_classic_write')]

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        """
        Search for records and their display names according to a search domain.

        :param cr: database cursor
        :param user: current user id
        :param name: object name to search
        :param args: list of tuples specifying search criteria [('field_name', 'operator', 'value'), ...]
        :param operator: operator for search criterion
        :param context: context arguments, like lang, time zone
        :type context: dictionary
        :param limit: optional max number of records to return
        :return: list of object names matching the search criteria, used to provide completion for to-many relationships

        This method is equivalent of :py:meth:`~osv.osv.osv.search` on **name** + :py:meth:`~osv.osv.osv.name_get` on the result.
        See :py:meth:`~osv.osv.osv.search` for an explanation of the possible values for the search domain specified in **args**.

        """
        return self._name_search(cr, user, name, args, operator, context, limit)

    # private implementation of name_search, allows passing a dedicated user for the name_get part to
    # solve some access rights issues
    def _name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100, name_get_uid=None):
        if args is None:
            args = []
        if context is None:
            context = {}
        args = args[:]
        if name:
            args += [(self._rec_name, operator, name)]
        access_rights_uid = name_get_uid or user
        ids = self._search(cr, user, args, limit=limit, context=context,
                           access_rights_uid=access_rights_uid)
        res = self.name_get(cr, access_rights_uid, ids, context)
        return res

    def copy(self, cr, uid, id, default=None, context=None):
        raise NotImplementedError(_('The copy method is not implemented on this object !'))

    def exists(self, cr, uid, id, context=None):
        raise NotImplementedError(_('The exists method is not implemented on this object !'))

    def read_string(self, cr, uid, id, langs, fields=None, context=None):
        res = {}
        res2 = {}
        self.pool.get('ir.model.access').check(cr, uid, 'ir.translation', 'read', context=context)
        if not fields:
            fields = self._columns.keys() + self._inherit_fields.keys()
        #FIXME: collect all calls to _get_source into one SQL call.
        for lang in langs:
            res[lang] = {'code': lang}
            for f in fields:
                if f in self._columns:
                    res_trans = self.pool.get('ir.translation')._get_source(cr, uid, self._name+','+f, 'field', lang)
                    if res_trans:
                        res[lang][f] = res_trans
                    else:
                        res[lang][f] = self._columns[f].string
        for table in self._inherits:
            cols = intersect(self._inherit_fields.keys(), fields)
            res2 = self.pool.get(table).read_string(cr, uid, id, langs, cols, context)
        for lang in res2:
            if lang in res:
                res[lang]['code'] = lang
            for f in res2[lang]:
                res[lang][f] = res2[lang][f]
        return res

    def write_string(self, cr, uid, id, langs, vals, context=None):
        self.pool.get('ir.model.access').check(cr, uid, 'ir.translation', 'write', context=context)
        #FIXME: try to only call the translation in one SQL
        for lang in langs:
            if lang == 'en_US':
                continue
            for field in vals:
                if field in self._columns:
                    src = self._columns[field].string
                    self.pool.get('ir.translation')._set_ids(cr, uid, self._name+','+field, 'field', lang, [0], vals[field], src)
        for table in self._inherits:
            cols = intersect(self._inherit_fields.keys(), vals)
            if cols:
                self.pool.get(table).write_string(cr, uid, id, langs, vals, context)
        return True

    def _check_removed_columns(self, cr, log=False):
        raise NotImplementedError()

    def _add_missing_default_values(self, cr, uid, values, context=None):
        missing_defaults = []
        avoid_tables = [] # avoid overriding inherited values when parent is set
        for tables, parent_field in self._inherits.items():
            if parent_field in values:
                avoid_tables.append(tables)
        for field in self._columns.keys():
            if not field in values:
                missing_defaults.append(field)
        for field in self._inherit_fields.keys():
            if (field not in values) and (self._inherit_fields[field][0] not in avoid_tables):
                missing_defaults.append(field)

        if len(missing_defaults):
            # override defaults with the provided values, never allow the other way around
            defaults = self.default_get(cr, uid, missing_defaults, context, from_web=False)
            for dv in defaults:
                if ((dv in self._columns and self._columns[dv]._type == 'many2many') \
                        or (dv in self._inherit_fields and self._inherit_fields[dv][2]._type == 'many2many')) \
                        and defaults[dv] and isinstance(defaults[dv][0], (int, long)):
                    defaults[dv] = [(6, 0, defaults[dv])]
                elif (dv in self._columns and self._columns[dv]._type == 'one2many' \
                        or (dv in self._inherit_fields and self._inherit_fields[dv][2]._type == 'one2many')) \
                        and isinstance(defaults[dv], (list, tuple)) and\
                        defaults[dv] and isinstance(defaults[dv][0], dict):
                    defaults[dv] = [(0, 0, x) for x in defaults[dv]]
            defaults.update(values)
            values = defaults
        return values

    def update_exported_fields(self, cr, uid, fields):
        """
        Override this method if you would like to change the exported
        fields on the object.
        """
        for fld, rpl_flds in self._replace_exported_fields.iteritems():
            fld_index = None
            fld_val = None
            fld_to_rm = []
            for f in fields:
                if f[0] == fld:
                    fld_index = fields.index(f)
                    fld_val = f
                else:
                    for rpl_fld in rpl_flds:
                        if f[0] == rpl_fld[0][0]:
                            fld_to_rm.append(f)

            if fld_index is not None:
                for frm in fld_to_rm:
                    if frm[0] not in self._replace_exported_fields.keys():
                        fields.remove(frm)

                sorted_rpl_flds = reversed(sorted(rpl_flds, key=lambda x: x[1]))
                for rpl_fld in sorted_rpl_flds:
                    fields.insert(fld_index, rpl_fld[0])

                fields.remove(fld_val)

        return fields

    def filter_export_data_result(self, cr, uid, result, fields):
        """
        Override this method if you would like to filter the result of
        export_data method of the object.
        """
        fld_indexes = []

        for fld in self._replace_exported_fields.keys():
            if fld in fields:
                fld_indexes.append(fields.index(fld))

        if fld_indexes:
            fld_indexes.sort(reverse=True)
            for r in result:
                for fld_index in fld_indexes:
                    del r[fld_index]

            for fld_index in fld_indexes:
                del fields[fld_index]

        return result, fields


class orm_memory(orm_template):

    _protected = ['read', 'write', 'create', 'default_get', 'perm_read', 'unlink', 'fields_get', 'fields_view_get', 'search', 'name_get', 'distinct_field_get', 'name_search', 'copy', 'import_data', 'search_count', 'exists']
    _inherit_fields = {}
    _max_count = config.get('osv_memory_count_limit')
    _max_hours = config.get('osv_memory_age_limit')
    _check_time = 20

    def __init__(self, cr):
        super(orm_memory, self).__init__(cr)
        self.datas = {}
        self.next_id = 0
        self.check_id = 0
        cr.execute('delete from wkf_instance where res_type=%s', (self._name,))
        for x in self._columns:
            if self._columns[x]._type == 'many2many':
                self._columns[x].setup_m2m(self)

    def _check_access(self, cr, uid, object_id, mode):
        user_obj = self.pool.get('res.users')
        if uid != 1 and uid != user_obj._get_sync_user_id(cr) and self.datas[object_id]['internal.create_uid'] != uid:
            raise except_orm(_('AccessError'), '%s access is only allowed on your own records for osv_memory objects except for the super-user' % mode.capitalize())

    def vaccum(self, cr, uid, force=False):
        """Run the vaccuum cleaning system, expiring and removing old records from the
        virtual osv_memory tables if the "max count" or "max age" conditions are enabled
        and have been reached. This method can be called very often (e.g. everytime a record
        is created), but will only actually trigger the cleanup process once out of
        "_check_time" times (by default once out of 20 calls)."""
        self.check_id += 1
        if (not force) and (self.check_id % self._check_time):
            return True
        tounlink = []

        logger = logging.getLogger('memory.vacuum')
        # Age-based expiration
        if self._max_hours:
            max = time.time() - self._max_hours * 60 * 60
            for k,v in self.datas.iteritems():
                if v['internal.date_access'] < max:
                    tounlink.append(k)
            self.unlink(cr, 1, tounlink)
            if tounlink:
                logger.info('delete %d %s based on age' % (len(tounlink), self._name))

        # Count-based expiration
        if self._max_count and len(self.datas) > self._max_count:
            # sort by access time to remove only the first/oldest ones in LRU fashion
            records = self.datas.items()
            records.sort(key=lambda x:x[1]['internal.date_access'])
            tounlink = [x[0] for x in records[:len(self.datas)-self._max_count]]
            self.unlink(cr, 1, tounlink)
            if tounlink:
                logger.info('delete %d %s based on count' % (len(tounlink), self._name))

        return True

    def read(self, cr, user, ids, fields_to_read=None, context=None, load='_classic_read'):
        if context is None:
            context = {}
        if not fields_to_read:
            fields_to_read = self._columns.keys()
        result = []
        if self.datas:
            ids_orig = ids
            if isinstance(ids, (int, long)):
                ids = [ids]

            # order ids by _parent_order or _order
            order_by = self._parent_order or self._order
            ids_set = set(ids)
            data = self._in_memory_sorted_items(cr, user, order_by, context=context, sort_raw_id=True)
            ids = [ id for id, values in data if id in ids_set ]
            for id in ids:
                r = {'id': id}
                for f in fields_to_read:
                    record = self.datas.get(id)
                    if record:
                        self._check_access(cr, user, id, 'read')
                        r[f] = record.get(f, False)
                        if r[f] and isinstance(self._columns[f], fields.binary) and context.get('bin_size', False):
                            r[f] = len(r[f])
                result.append(r)
                if id in self.datas:
                    self.datas[id]['internal.date_access'] = time.time()

            # all non inherited fields for which the attribute whose name is in load is False
            fields_post = filter(lambda x: x in self._columns and not getattr(self._columns[x], load), fields_to_read)

            # Compute POST fields
            todo = {}
            for f in fields_post:
                todo.setdefault(self._columns[f]._multi, [])
                todo[self._columns[f]._multi].append(f)
            for key, val in todo.items():
                if key:
                    res2 = self._columns[val[0]].get_memory(cr, self, ids, val, user, context=context, values=result)
                    for pos in val:
                        for record in result:
                            if isinstance(res2[record['id']], str): res2[record['id']] = eval(res2[record['id']]) #TOCHECK : why got string instend of dict in python2.6
                            multi_fields = res2.get(record['id'],{})
                            if multi_fields:
                                record[pos] = multi_fields.get(pos,[])
                else:
                    for f in val:
                        res2 = self._columns[f].get_memory(cr, self, ids, f, user, context=context, values=result)
                        for record in result:
                            if res2:
                                record[f] = res2[record['id']]
                            else:
                                record[f] = []

            if isinstance(ids_orig, (int, long)):
                return result[0]
        return result

    def copy_translations(self, cr, uid, old_id, new_id, context=None):
        pass

    def write(self, cr, user, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        vals2 = {}
        upd_todo = []
        for field in vals:
            if self._columns[field]._classic_write:
                vals2[field] = vals[field]
            else:
                upd_todo.append(field)
        for object_id in ids:
            self._check_access(cr, user, object_id, mode='write')
            try:
                self.datas[object_id].update(vals2)
            except KeyError:
                error_message = _('Object id \'%s\' not found in \'%s\'. You may try to access a deleted temporary object (ie. wizard)')
                error_message = error_message % (object_id, self._name)
                raise except_orm(_('Error'), error_message)
            self.datas[object_id]['internal.date_access'] = time.time()
            for field in upd_todo:
                self._columns[field].set_memory(cr, self, object_id, field, vals[field], user, context)
        self._validate(cr, user, [object_id], context)
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_write(user, self._name, object_id, cr)
        return object_id

    def create(self, cr, user, vals, context=None):
        self.vaccum(cr, user)
        self.next_id += 1
        id_new = self.next_id

        vals = self._add_missing_default_values(cr, user, vals, context)

        vals2 = {}
        upd_todo = []
        for field in vals:
            if self._columns[field]._classic_write:
                vals2[field] = vals[field]
            else:
                upd_todo.append(field)
        self.datas[id_new] = vals2
        self.datas[id_new]['internal.date_access'] = time.time()
        self.datas[id_new]['internal.create_uid'] = user

        for field in upd_todo:
            self._columns[field].set_memory(cr, self, id_new, field, vals[field], user, context)
        self._validate(cr, user, [id_new], context)
        if self._log_create and not (context and context.get('no_store_function', False)):
            message = self._description + \
                " '" + \
                self.name_get(cr, user, [id_new], context=context)[0][1] + \
                "' "+ _("created.")
            self.log(cr, user, id_new, message, True, context=context)
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_create(user, self._name, id_new, cr)
        return id_new

    def _where_calc(self, cr, user, args, active_test=True, context=None):
        if context is None:
            context = {}
        args = args[:]
        res = []
        # if the object has a field named 'active', filter out all inactive
        # records unless they were explicitely asked for
        if 'active' in self._columns and (active_test and context.get('active_test', True)):
            if args:
                active_in_args = False
                for a in args:
                    if a[0] == 'active':
                        active_in_args = True
                if not active_in_args:
                    args.insert(0, ('active', '=', 1))
            else:
                args = [('active', '=', 1)]
        if args:
            import expression
            e = expression.expression(args)
            e.parse(cr, user, self, context)
            res = e.exp
        return res or []

    def _in_memory_sorted_items(self, cr, user, order_spec, context=None, sort_raw_id=False):
        """ sort internal orm_memory data by requestd order
        :param cr: database cursor
        :param uid: current user id
        :param order_spec: ``order by`` specification, for overriding the natural
                      sort ordering of the groups, see also :py:meth:`~osv.orm.orm_memory.search`
                      (supported only for many2one fields currently)
        :param context: context arguments, like lang, time zone
        :param sort_raw_id: if True, relationnal field (i.e many2one) will be sorted by their 'id'
                            and no based on order specification of the related object. Not active
                            by default
        :return: list of tuple containing the row id and row valud => [(id1, {values...}), (id2, {values...}), ...]
        """
        if context is None:
            context = {}
        data = self.datas.items()
        if order_spec:

            if not regex_order.match(order_spec):
                raise except_orm(_('AccessError'), _('Invalid "order" specified. A valid "order" specification is a comma-separated list of valid field names (optionnaly followed by asc/desc for the direction)'))

            order_context = {'lang': context.get('lang')}
            order_parts_getters = []
            order_info = {}
            for order_part in order_spec.split(','):
                order_split = order_part.strip().split(' ')
                order_field = order_split[0].strip()
                order_direction = order_split[1].strip().lower() if len(order_split) == 2 else 'asc'
                if order_field == 'id':
                    getter = lambda d, i, o_field: d[0]
                elif order_field in self._columns:
                    order_column = self._columns[order_field]
                    # OEB-79: Patch provided by Xavier
                    if hasattr(order_column, 'store'):
                        # explicitly skip function field (stored or not) as for osv_memory we do not have raw data
                        # in 'self.datas' available for sorting
                        continue

                    if order_column._classic_read:
                        getter = lambda d, i, o_field: len(d) > 1 and d[1].get(o_field) or False
                    elif order_column._type == 'many2one':
                        if sort_raw_id:
                            # uppon read, many2one sorting is done directly on 'id'
                            getter = lambda d, i, o_field: len(d) > 1 and d[1].get(o_field) or False
                        else:
                            # use the fact the read follow object standard _parent_order/_order to get many2one ordered
                            dest_model = self.pool.get(order_column._obj)
                            dest_ids = set([ (d.get(order_field) or False) for k, d in data ])
                            dest_ids_has_false = False in dest_ids
                            if dest_ids_has_false:
                                dest_ids.remove(False)
                            ordered_ids = [ x['id'] for x in dest_model.read(cr, 1, list(dest_ids), ['id'], context=order_context) ]
                            if dest_ids_has_false:
                                ordered_ids.insert(0, False) # false is always first
                            order_info[order_field] = ordered_ids
                            getter = lambda d, i, o_field: i.get(o_field) and len(d) > 1 and d[1].get(o_field) and i.get(o_field).index(d[1].get(o_field)) or False
                else:
                    raise NotImplementedError()
                order_parts_getters.append((getter, order_direction, order_field))
            # create an inline sort method that fullfill 'cmp' specification
            def in_memory_sort(x, y):
                i = order_info
                for (getter, direction, o_field) in order_parts_getters:
                    if direction == 'asc': # normal sort order
                        v = cmp(getter(x, i, o_field), getter(y, i, o_field))
                    elif direction == 'desc':
                        v = cmp(getter(y, i, o_field), getter(x, i, o_field))
                    if v == 0:
                        # at this level item equals,
                        # continue to next order field
                        continue
                    return v
                return 0
            data.sort(cmp=in_memory_sort)
        return data

    def _search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False, access_rights_uid=None):
        if context is None:
            context = {}

        if order == 'NO_ORDER':
            order = ''

        # implicit filter on current user except for superuser
        if user != 1:
            if not args:
                args = []
            args.insert(0, ('internal.create_uid', '=', user))

        result = self._where_calc(cr, user, args, context=context)
        if result == []:
            return [ k for k, v in self._in_memory_sorted_items(cr, user, order, context=context) ]

        res = []
        #Find the value of dict
        f = False
        if result:
            for id, data in self._in_memory_sorted_items(cr, user, order, context=context):
                data['id'] = id

                f = True
                for arg in result:
                    if arg[1] == '=':
                        val = eval('data[arg[0]]'+'==' +' arg[2]', locals())
                    elif arg[1] in ['<', '>', 'in', 'not in', '<=', '>=', '<>']:
                        val = eval('data[arg[0]]'+arg[1] +' arg[2]', locals())
                    elif arg[1] in ['ilike']:
                        val = (str(data[arg[0]]).find(str(arg[2]))!=-1)

                    f = f and val

                if f:
                    res.append(id)

        if count:
            return len(res)

        if offset and limit:
            return res[offset:limit+offset]
        if offset:
            return res[offset:]
        if limit:
            return res[0:limit]

        return res or []

    def unlink(self, cr, uid, ids, context=None):
        for id in ids:
            self._check_access(cr, uid, id, 'unlink')
            self.datas.pop(id, None)
        if len(ids):
            cr.execute('delete from wkf_instance where res_type=%s and res_id IN %s', (self._name, tuple(ids)))
        return True

    def perm_read(self, cr, user, ids, context=None, details=True):
        result = []
        credentials = self.pool.get('res.users').name_get(cr, user, [user])[0]
        create_date = time.strftime('%Y-%m-%d %H:%M:%S')
        for id in ids:
            self._check_access(cr, user, id, 'read')
            result.append({
                'create_uid': credentials,
                'create_date': create_date,
                'write_uid': False,
                'write_date': False,
                'id': id,
                'xmlid' : False,
            })
        return result

    def _check_removed_columns(self, cr, log=False):
        # nothing to check in memory...
        pass

    def exists(self, cr, uid, ids, context=None):
        if isinstance(ids, (long,int)):
            ids = [ids]
        return [id for id in ids if id in self.datas]

class orm(orm_template):
    _sql_constraints = []
    _table = None
    _all_columns = {}
    _protected = ['read', 'write', 'create', 'default_get', 'perm_read', 'unlink', 'fields_get', 'fields_view_get', 'search', 'name_get', 'distinct_field_get', 'name_search', 'copy', 'import_data', 'search_count', 'exists']
    __logger = logging.getLogger('orm')
    __schema = logging.getLogger('orm.schema')
    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, count=False):
        """
        Get the list of records in list view grouped by the given ``groupby`` fields

        :param cr: database cursor
        :param uid: current user id
        :param domain: list specifying search criteria [['field_name', 'operator', 'value'], ...]
        :param fields: list of fields present in the list view specified on the object
        :param groupby: list of fields on which to groupby the records
        :type fields_list: list (example ['field_name_1', ...])
        :param offset: optional number of records to skip
        :param limit: optional max number of records to return
        :param context: context arguments, like lang, time zone
        :param order: optional ``order by`` specification, for overriding the natural
                      sort ordering of the groups, see also :py:meth:`~osv.osv.osv.search`
                      (supported only for many2one fields currently)
        :return: list of dictionaries(one dictionary for each record) containing:

                    * the values of fields grouped by the fields in ``groupby`` argument
                    * __domain: list of tuples specifying the search criteria
                    * __context: dictionary with argument like ``groupby``
        :rtype: [{'field_name_1': value, ...]
        :raise AccessError: * if user has no read rights on the requested object
                            * if user tries to bypass access rules for read on the requested object

        """
        context = context or {}
        self.pool.get('ir.model.access').check(cr, uid, self._name, 'read', context=context)
        if not fields:
            fields = self._columns.keys()

        query = self._where_calc(cr, uid, domain, context=context)
        self._apply_ir_rules(cr, uid, query, 'read', context=context)

        # Take care of adding join(s) if groupby is an '_inherits'ed field
        groupby_list = groupby
        qualified_groupby_field = groupby
        if groupby:
            if isinstance(groupby, list):
                groupby = groupby[0]
            qualified_groupby_field = self._inherits_join_calc(groupby, query)

        if groupby:
            assert not groupby or groupby in fields, "Fields in 'groupby' must appear in the list of fields to read (perhaps it's missing in the list view?)"
            groupby_def = self._columns.get(groupby) or (self._inherit_fields.get(groupby) and self._inherit_fields.get(groupby)[2])
            assert groupby_def and groupby_def._classic_write, "Fields in 'groupby' must be regular database-persisted fields (no function or related fields), or function fields with store=True"

        fget = self.fields_get(cr, uid, fields)
        float_int_fields = filter(lambda x: fget[x]['type'] in ('float', 'integer') or fget[x].get('group_operator'), fields)
        flist = ''
        group_count = group_by = groupby
        if groupby:
            if fget.get(groupby):
                if fget[groupby]['type'] in ('date', 'datetime'):
                    flist = "to_char(%s,'yyyy-mm') as %s " % (qualified_groupby_field, groupby)
                    groupby = "to_char(%s,'yyyy-mm')" % (qualified_groupby_field)
                    qualified_groupby_field = groupby
                else:
                    flist = qualified_groupby_field
            else:
                # Don't allow arbitrary values, as this would be a SQL injection vector!
                raise except_orm(_('Invalid group_by'),
                                 _('Invalid group_by specification: "%s".\nA group_by specification must be a list of valid fields.')%(groupby,))


        fields_pre = [f for f in float_int_fields if
                      f == self.CONCURRENCY_CHECK_FIELD
                      or (f in self._columns and getattr(self._columns[f], '_classic_write'))]
        rounding_uom = set(self._columns[f].related_uom for f in fields_pre if f in self._columns and hasattr(self._columns[f], 'related_uom') and self._columns[f].related_uom)
        for f in fields_pre + list(rounding_uom):
            if f not in ['id', 'sequence']:
                if f in rounding_uom:
                    group_operator = fget[f].get('group_operator', 'max')
                else:
                    group_operator = fget[f].get('group_operator', 'sum')
                if group_operator == 'no_group':
                    continue
                if flist:
                    flist += ', '
                qualified_field = '"%s"."%s"' % (self._table, f)
                flist += "%s(%s) AS %s" % (group_operator, qualified_field, f)

        gb = groupby and (' GROUP BY ' + qualified_groupby_field) or ''

        from_clause, where_clause, where_clause_params = query.get_sql()
        where_clause = where_clause and ' WHERE ' + where_clause
        if count:
            cr.execute('SELECT count(%s) ' % (qualified_groupby_field,) + ' FROM ' + from_clause + where_clause, where_clause_params)  # not_a_user_entry
            return cr.fetchone()[0]

        limited_groupby = self._name == 'replenishment.product.list'

        if limited_groupby and not limit:
            limit = 20

        limit_str = limit and ' limit %d' % limit or ''
        offset_str = offset and ' offset %d' % offset or ''
        if len(groupby_list) < 2 and context.get('group_by_no_leaf'):
            group_count = '_'

        query_orderby = ''
        if limited_groupby:
            if gb:
                gb += ',default_code'
            if orderby:
                split_orderby = orderby.split(' ')
                query_orderby = ' order by default_code '
                if len(split_orderby) == 2 and split_orderby[1].strip().lower() in ['asc', 'desc']:
                    query_orderby = '%s %s ' % (query_orderby, split_orderby[1])
            else:
                query_orderby = ' order by default_code '

        cr.execute('SELECT min(%s.id) AS id, count(%s.id) AS %s_count' % (self._table, self._table, group_count) + (flist and ',') + flist + ' FROM ' + from_clause + where_clause + gb + query_orderby + limit_str + offset_str, where_clause_params)  # not_a_user_entry
        alldata = {}
        groupby = group_by
        for r in cr.dictfetchall():
            for fld, val in r.items():
                if val == None: r[fld] = False
            alldata[r['id']] = r
            del r['id']

        data_ids = self.search(cr, uid, [('id', 'in', alldata.keys())], order=orderby or groupby, context=context)
        # the IDS of records that have groupby field value = False or '' should be sorted too
        data_ids += filter(lambda x:x not in data_ids, alldata.keys())
        data = self.read(cr, uid, data_ids, groupby and [groupby] or ['id'], context=context)
        # restore order of the search as read() uses the default _order (this is only for groups, so the size of data_read shoud be small):
        data.sort(lambda x,y: cmp(data_ids.index(x['id']), data_ids.index(y['id'])))

        for d in data:
            if groupby:
                d['__domain'] = [(groupby, '=', alldata[d['id']][groupby] or False)] + domain
                if not isinstance(groupby_list, (str, unicode)):
                    if groupby or not context.get('group_by_no_leaf', False):
                        d['__context'] = {'group_by': groupby_list[1:]}
            if groupby and groupby in fget:
                if d[groupby] and fget[groupby]['type'] in ('date', 'datetime'):
                    dt = datetime.datetime.strptime(alldata[d['id']][groupby][:7], '%Y-%m')
                    days = calendar.monthrange(dt.year, dt.month)[1]

                    d[groupby] = datetime.datetime.strptime(d[groupby][:10], '%Y-%m-%d').strftime('%B %Y')
                    d['__domain'] = [(groupby, '>=', alldata[d['id']][groupby] and datetime.datetime.strptime(alldata[d['id']][groupby][:7] + '-01', '%Y-%m-%d').strftime('%Y-%m-%d') or False),\
                                     (groupby, '<=', alldata[d['id']][groupby] and datetime.datetime.strptime(alldata[d['id']][groupby][:7] + '-' + str(days), '%Y-%m-%d').strftime('%Y-%m-%d') or False)] + domain
                del alldata[d['id']][groupby]
            d.update(alldata[d['id']])
            del d['id']
        return data

    def _inherits_join_add(self, parent_model_name, query):
        """
        Add missing table SELECT and JOIN clause to ``query`` for reaching the parent table (no duplicates)

        :param parent_model_name: name of the parent model for which the clauses should be added
        :param query: query object on which the JOIN should be added
        """
        inherits_field = self._inherits[parent_model_name]
        parent_model = self.pool.get(parent_model_name)
        parent_table_name = parent_model._table
        quoted_parent_table_name = '"%s"' % parent_table_name
        if quoted_parent_table_name not in query.tables:
            query.join([self._table, parent_table_name, inherits_field, 'id'], outer=True)
            # Use query.join() instead of just put new table and new where clause elements because
            # to be able to sort on translated values, we need JOIN between tables

    def _inherits_join_calc(self, field, query):
        """
        Adds missing table select and join clause(s) to ``query`` for reaching
        the field coming from an '_inherits' parent table (no duplicates).

        :param field: name of inherited field to reach
        :param query: query object on which the JOIN should be added
        :return: qualified name of field, to be used in SELECT clause
        """
        current_table = self
        while field in current_table._inherit_fields and not field in current_table._columns:
            parent_model_name = current_table._inherit_fields[field][0]
            parent_table = self.pool.get(parent_model_name)
            current_table._inherits_join_add(parent_model_name, query)
            current_table = parent_table
        return '"%s".%s' % (current_table._table, field)

    def _parent_store_compute(self, cr):
        if not self._parent_store:
            return
        logger = netsvc.Logger()
        logger.notifyChannel('data', netsvc.LOG_INFO, 'Computing parent left and right for table %s...' % (self._table, ))
        def browse_rec(root, pos=0):
            # TODO: set order
            where = self._parent_name+'='+str(root)
            if not root:
                where = self._parent_name+' IS NULL'
            if self._parent_order:
                where += ' order by '+self._parent_order
            cr.execute('SELECT id FROM '+self._table+' WHERE '+where)  # not_a_user_entry
            pos2 = pos + 1
            for id in cr.fetchall():
                pos2 = browse_rec(id[0], pos2)
            query = ''.join(('UPDATE ', self._table, ' SET parent_left=%s, parent_right=%s WHERE id=%s'))
            cr.execute(query, (pos, pos2, root))
            return pos2 + 1
        query = ''.join(('SELECT id FROM ', self._table, ' WHERE ',
                         self._parent_name, ' IS NULL'))
        if self._parent_order:
            query = ''.join((query, ' ORDER BY ', self._parent_order))
        pos = 0
        cr.execute(query)
        for (root,) in cr.fetchall():
            pos = browse_rec(root, pos)
        return True

    def _update_store(self, cr, f, k):
        logger = netsvc.Logger()
        logger.notifyChannel('data', netsvc.LOG_INFO, "storing computed values of fields.function '%s'" % (k,))
        ss = self._columns[k]._symbol_set
        update_query = 'UPDATE "%s" SET "%s"=%s WHERE id=%%s' % (self._table, k, ss[0])  # not_a_user_entry
        cr.execute('SELECT id FROM '+self._table)  # not_a_user_entry
        ids_lst = map(lambda x: x[0], cr.fetchall())

        migrate = False
        if self._columns[k]._fnct_migrate:
            migrate = self._columns[k].migrate(cr, ids_lst)

        while ids_lst and migrate == False:
            iids = ids_lst[:40]
            ids_lst = ids_lst[40:]
            res = f.get(cr, self, iids, k, 1, {})
            for key, val in res.items():
                if f._multi:
                    val = val[k]
                # if val is a many2one, just write the ID
                if type(val) == tuple:
                    val = val[0]
                if (val<>False) or (type(val)<>bool):
                    cr.execute(update_query, (ss[1](val), key))

    def _check_selection_field_value(self, cr, uid, field, value, context=None):
        """Raise except_orm if value is not among the valid values for the selection field"""
        if self._columns[field]._type == 'reference':
            val_model, val_id_str = value.split(',', 1)
            val_id = False
            try:
                val_id = long(val_id_str)
            except ValueError:
                pass
            if not val_id:
                raise except_orm(_('ValidateError'),
                                 _('Invalid value for reference field "%s" (last part must be a non-zero integer): "%s"') % (field, value))
            val = val_model
        else:
            val = value
        if isinstance(self._columns[field].selection, (tuple, list)):
            if val in dict(self._columns[field].selection):
                return
        elif val in dict(self._columns[field].selection(self, cr, uid, context=context)):
            return
        raise except_orm(_('ValidateError'),
                         _('The value "%s" for the field "%s" is not in the selection') % (value, field))

    def _check_removed_columns(self, cr, log=False):
        # iterate on the database columns to drop the NOT NULL constraints
        # of fields which were required but have been removed (or will be added by another module)
        columns = [c for c in self._columns if not (isinstance(self._columns[c], fields.function) and not self._columns[c].store)]
        columns += ('id', 'write_uid', 'write_date', 'create_uid', 'create_date') # openerp access columns
        cr.execute("SELECT a.attname, a.attnotnull"
                   "  FROM pg_class c, pg_attribute a"
                   " WHERE c.relname=%s"
                   "   AND c.oid=a.attrelid"
                   "   AND a.attisdropped=%s"
                   "   AND pg_catalog.format_type(a.atttypid, a.atttypmod) NOT IN ('cid', 'tid', 'oid', 'xid')"
                   "   AND a.attname NOT IN %s", (self._table, False, tuple(columns))),

        for column in cr.dictfetchall():
            if log:
                self.__logger.debug("column %s is in the table %s but not in the corresponding object %s",
                                    column['attname'], self._table, self._name)
            if column['attnotnull']:
                cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" DROP NOT NULL' % (self._table, column['attname']))  # not_a_user_entry
                self.__schema.debug("Table '%s': column '%s': dropped NOT NULL constraint",
                                    self._table, column['attname'])

    def execute_migration(self, cr, moved_column, new_column):
        """
        On change type of column, make a migration of data. The old values
        are moved to a new column suffixed by _movedX.
        This method must be overriden on needed objects.
        :param cr: Cursor to the database
        :param moved_column: The renamed old column
        :param new_column: The column with the new type
        :return: Nothing
        """
        pass

    def _clean_cache(self, dbname):
        '''
        This method is called everytime a cache based on
         this object has to be cleaned because data has been updated.

        The default behaviour is to do nothing.
        '''
        pass

    def _create_fk(self, cr, col_name, field_def, update=False):
        try:
            ref = self.pool.get(field_def._obj)._table
        except:
            print field_def._obj
            raise
        # ir_actions is inherited so foreign key doesn't work on it
        if ref != 'ir_actions':
            to_create = True
            if update:
                to_create = False
                # check if fk already exist on should be changed
                cr.execute('SELECT confdeltype, conname FROM pg_constraint as con, pg_class as cl1, pg_class as cl2, '
                           'pg_attribute as att1, pg_attribute as att2 '
                           'WHERE con.conrelid = cl1.oid '
                           'AND cl1.relname = %s '
                           'AND con.confrelid = cl2.oid '
                           'AND cl2.relname = %s '
                           'AND array_lower(con.conkey, 1) = 1 '
                           'AND con.conkey[1] = att1.attnum '
                           'AND att1.attrelid = cl1.oid '
                           'AND att1.attname = %s '
                           'AND array_lower(con.confkey, 1) = 1 '
                           'AND con.confkey[1] = att2.attnum '
                           'AND att2.attrelid = cl2.oid '
                           'AND att2.attname = %s '
                           "AND con.contype = 'f'", (self._table, ref, col_name, 'id'))
                res2 = cr.dictfetchall()
                if res2:
                    if res2[0]['confdeltype'] != POSTGRES_CONFDELTYPES.get(field_def.ondelete.upper(), 'a'):
                        cr.execute('ALTER TABLE "' + self._table + '" DROP CONSTRAINT "' + res2[0]['conname'] + '"') # not_a_user_entry
                        to_create = True

            if to_create:
                cr.execute('ALTER TABLE "%s" ADD FOREIGN KEY ("%s") REFERENCES "%s" ON DELETE %s' % (self._table, col_name, ref, field_def.ondelete)) # not_a_user_entry
                self.__schema.debug("Table '%s': added foreign key '%s' with definition=REFERENCES \"%s\" ON DELETE %s",
                                    self._table, col_name, ref, field_def.ondelete)
                cr.commit()

    def _create_m2m_table(self, cr, f):
        f.setup_m2m(self)

        cr.execute("SELECT relname, relhasoids FROM pg_class WHERE relkind IN ('r','v') AND relname=%s", (f._rel,))
        x = cr.dictfetchall()
        if not x:
            if not self.pool.get(f._obj):
                raise except_orm('Programming Error', ('There is no reference available for %s') % (f._obj,))
            ref = self.pool.get(f._obj)._table
            cr.execute('CREATE TABLE "%s" ("%s" INTEGER NOT NULL REFERENCES "%s" ON DELETE CASCADE, "%s" INTEGER NOT NULL REFERENCES "%s" ON DELETE CASCADE, UNIQUE("%s","%s"))' % (f._rel, f._id1, self._table, f._id2, ref, f._id1, f._id2)) # not_a_user_entry
            cr.execute('CREATE INDEX "%s_%s_index" ON "%s" ("%s")' % (f._rel, f._id1, f._rel, f._id1)) # not_a_user_entry
            cr.execute('CREATE INDEX "%s_%s_index" ON "%s" ("%s")' % (f._rel, f._id2, f._rel, f._id2)) # not_a_user_entry
            cr.execute("COMMENT ON TABLE \"%s\" IS 'RELATION BETWEEN %s AND %s'" % (f._rel, self._table, ref)) # not_a_user_entry
            cr.commit()
            self.__schema.debug("Create table '%s': relation between '%s' and '%s'",
                                f._rel, self._table, ref)
        elif x[0].get('relhasoids'):
            cr.execute('ALTER TABLE "%s" SET WITHOUT OIDS' % (f._rel, )) # not_a_user_entry
            cr.commit()


    def _auto_init(self, cr, context=None):
        if context is None:
            context = {}
        store_compute = False
        create = False
        todo_end = []
        self._field_create(cr, context=context)
        to_migrate = []
        missing_fk = {}
        missing_m2m = {}
        if getattr(self, '_auto', True):
            cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname=%s", (self._table,))
            if not cr.rowcount:
                cr.execute('CREATE TABLE "%s" (id SERIAL NOT NULL, PRIMARY KEY(id))' % (self._table,))  # not_a_user_entry
                cr.execute("COMMENT ON TABLE \"%s\" IS '%s'" % (self._table, self._description.replace("'", "''")))  # not_a_user_entry
                create = True
                self.__schema.debug("Table '%s': created", self._table)

            cr.commit()
            if self._parent_store:
                cr.execute("""SELECT c.relname
                    FROM pg_class c, pg_attribute a
                    WHERE c.relname=%s AND a.attname=%s AND c.oid=a.attrelid
                    """, (self._table, 'parent_left'))
                if not cr.rowcount:
                    cr.execute('ALTER TABLE "%s" ADD COLUMN "parent_left" INTEGER' % (self._table,))  # not_a_user_entry
                    cr.execute('ALTER TABLE "%s" ADD COLUMN "parent_right" INTEGER' % (self._table,))  # not_a_user_entry
                    if 'parent_left' not in self._columns:
                        self.__logger.error('create a column parent_left on object %s: fields.integer(\'Left Parent\', select=1)',
                                            self._table)
                        self.__schema.debug("Table '%s': added column '%s' with definition=%s",
                                            self._table, 'parent_left', 'INTEGER')
                    elif not self._columns['parent_left'].select:
                        self.__logger.error('parent_left column on object %s must be indexed! Add select=1 to the field definition)',
                                            self._table)
                    if 'parent_right' not in self._columns:
                        self.__logger.error('create a column parent_right on object %s: fields.integer(\'Right Parent\', select=1)',
                                            self._table)
                        self.__schema.debug("Table '%s': added column '%s' with definition=%s",
                                            self._table, 'parent_right', 'INTEGER')
                    elif not self._columns['parent_right'].select:
                        self.__logger.error('parent_right column on object %s must be indexed! Add select=1 to the field definition)',
                                            self._table)
                    if self._columns[self._parent_name].ondelete != 'cascade':
                        self.__logger.error("The column %s on object %s must be set as ondelete='cascade'",
                                            self._parent_name, self._name)

                    cr.commit()
                    store_compute = True

            if self._log_access:
                logs = {
                    'create_uid': 'INTEGER REFERENCES res_users ON DELETE SET NULL',
                    'create_date': 'TIMESTAMP',
                    'write_uid': 'INTEGER REFERENCES res_users ON DELETE SET NULL',
                    'write_date': 'TIMESTAMP'
                }
                for k in logs:
                    cr.execute("""
                        SELECT c.relname
                          FROM pg_class c, pg_attribute a
                         WHERE c.relname=%s AND a.attname=%s AND c.oid=a.attrelid
                        """, (self._table, k))
                    if not cr.rowcount:
                        cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (self._table, k, logs[k]))  # not_a_user_entry
                        cr.commit()
                        self.__schema.debug("Table '%s': added column '%s' with definition=%s",
                                            self._table, k, logs[k])

            self._check_removed_columns(cr, log=False)

            # iterate on the "object columns"
            todo_update_store = []
            update_custom_fields = context.get('update_custom_fields', False)

            cr.execute("SELECT c.relname,a.attname,a.attlen,a.atttypmod,a.attnotnull,a.atthasdef,t.typname,CASE WHEN a.attlen=-1 THEN a.atttypmod-4 ELSE a.attlen END as size " \
                       "FROM pg_class c,pg_attribute a,pg_type t " \
                       "WHERE c.relname=%s " \
                       "AND c.oid=a.attrelid " \
                       "AND a.atttypid=t.oid", (self._table,))
            col_data = dict(map(lambda x: (x['attname'], x),cr.dictfetchall()))


            for k in self._columns:
                if k in ('id', 'write_uid', 'write_date', 'create_uid', 'create_date'):
                    continue
                #Not Updating Custom fields
                if k.startswith('x_') and not update_custom_fields:
                    continue

                f = self._columns[k]

                if isinstance(f, fields.one2many):
                    cr.execute("SELECT relname FROM pg_class WHERE relkind='r' AND relname=%s", (f._obj,))

                    if self.pool.get(f._obj):
                        if f._fields_id not in self.pool.get(f._obj)._columns.keys():
                            if not self.pool.get(f._obj)._inherits or (f._fields_id not in self.pool.get(f._obj)._inherit_fields.keys()):
                                raise except_orm('Programming Error', ("There is no reference field '%s' found for '%s'") % (f._fields_id, f._obj,))

                    if cr.fetchone():
                        cr.execute("SELECT count(1) as c FROM pg_class c,pg_attribute a WHERE c.relname=%s AND a.attname=%s AND c.oid=a.attrelid", (f._obj, f._fields_id))
                        res = cr.fetchone()[0]
                        if not res:
                            cr.execute('ALTER TABLE "%s" ADD FOREIGN KEY (%s) REFERENCES "%s" ON DELETE SET NULL' % (self._obj, f._fields_id, f._table))  # not_a_user_entry
                            self.__schema.debug("Table '%s': added foreign key '%s' with definition=REFERENCES \"%s\" ON DELETE SET NULL",
                                                self._obj, f._fields_id, f._table)
                elif isinstance(f, fields.many2many):
                    if not self.pool.get(f._obj):
                        missing_m2m.setdefault(f._obj, [])
                        missing_m2m[f._obj].append((self, f))
                    else:
                        self._create_m2m_table(cr, f)
                else:
                    res = col_data.get(k, [])
                    res = res and [res] or []
                    if not res and hasattr(f, 'oldname'):
                        cr.execute("SELECT c.relname,a.attname,a.attlen,a.atttypmod,a.attnotnull,a.atthasdef,t.typname,CASE WHEN a.attlen=-1 THEN a.atttypmod-4 ELSE a.attlen END as size " \
                                   "FROM pg_class c,pg_attribute a,pg_type t " \
                                   "WHERE c.relname=%s " \
                                   "AND a.attname=%s " \
                                   "AND c.oid=a.attrelid " \
                                   "AND a.atttypid=t.oid", (self._table, f.oldname))
                        res_old = cr.dictfetchall()
                        if res_old and len(res_old) == 1:
                            cr.execute('ALTER TABLE "%s" RENAME "%s" TO "%s"' % (self._table, f.oldname, k))  # not_a_user_entry
                            res = res_old
                            res[0]['attname'] = k
                            self.__schema.debug("Table '%s': renamed column '%s' to '%s'",
                                                self._table, f.oldname, k)

                    if len(res) == 1:
                        f_pg_def = res[0]
                        f_pg_type = f_pg_def['typname']
                        f_pg_size = f_pg_def['size']
                        f_pg_notnull = f_pg_def['attnotnull']
                        if isinstance(f, fields.function) and not f.store and\
                                not getattr(f, 'nodrop', False):
                            self.__logger.info('column %s (%s) in table %s removed: converted to a function !\n',
                                               k, f.string, self._table)
                            cr.execute('ALTER TABLE "%s" DROP COLUMN "%s" CASCADE' % (self._table, k))  # not_a_user_entry
                            cr.commit()
                            self.__schema.debug("Table '%s': dropped column '%s' with cascade",
                                                self._table, k)
                            f_obj_type = None
                        else:
                            f_obj_type = get_pg_type(f) and get_pg_type(f)[0]

                        if f_obj_type:
                            ok = False
                            casts = [
                                ('text', 'char', 'VARCHAR(%d)' % (f.size or 0,), '::VARCHAR(%d)'%(f.size or 0,)),
                                ('varchar', 'text', 'TEXT', ''),
                                ('int4', 'float', get_pg_type(f)[1], '::'+get_pg_type(f)[1]),
                                ('date', 'datetime', 'TIMESTAMP', '::TIMESTAMP'),
                                ('timestamp', 'date', 'date', '::date'),
                                ('numeric', 'float', get_pg_type(f)[1], '::'+get_pg_type(f)[1]),
                                ('float8', 'float', get_pg_type(f)[1], '::'+get_pg_type(f)[1]),
                                ('int4', 'integer_big', get_pg_type(f)[1], '::'+get_pg_type(f)[1]),
                            ]

                            if f_pg_type == 'varchar' and f._type in ('char', 'selection') and f_pg_size < f.size:
                                cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO temp_change_size' % (self._table, k))  # not_a_user_entry
                                cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" VARCHAR(%d)' % (self._table, k, f.size))  # not_a_user_entry
                                cr.execute('UPDATE "%s" SET "%s"=temp_change_size::VARCHAR(%d)' % (self._table, k, f.size))  # not_a_user_entry
                                cr.execute('ALTER TABLE "%s" DROP COLUMN temp_change_size CASCADE' % (self._table,))  # not_a_user_entry
                                cr.commit()
                                self.__schema.warn("Table '%s': column '%s' (type varchar) changed size from %s to %s",
                                                   self._table, k, f_pg_size, f.size)
                            for c in casts:
                                if (f_pg_type==c[0]) and (f._type==c[1]):
                                    if f_pg_type != f_obj_type:
                                        ok = True
                                        cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO temp_change_size' % (self._table, k))  # not_a_user_entry
                                        cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (self._table, k, c[2]))  # not_a_user_entry
                                        cr.execute(('UPDATE "%s" SET "%s"=temp_change_size'+c[3]) % (self._table, k))  # not_a_user_entry
                                        cr.execute('ALTER TABLE "%s" DROP COLUMN temp_change_size CASCADE' % (self._table,))  # not_a_user_entry
                                        cr.commit()
                                        self.__schema.warn("Table '%s': column '%s' changed type from %s to %s",
                                                           self._table, k, c[0], c[1])
                                    break

                            if f_pg_type != f_obj_type:
                                if not ok:
                                    i = 0
                                    while True:
                                        newname = k + '_moved' + str(i)
                                        cr.execute("SELECT count(1) FROM pg_class c,pg_attribute a " \
                                                   "WHERE c.relname=%s " \
                                                   "AND a.attname=%s " \
                                                   "AND c.oid=a.attrelid ", (self._table, newname))
                                        if not cr.fetchone()[0]:
                                            break
                                        i += 1
                                    if f_pg_notnull:
                                        cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" DROP NOT NULL' % (self._table, k))  # not_a_user_entry
                                    cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"' % (self._table, k, newname))  # not_a_user_entry
                                    cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (self._table, k, get_pg_type(f)[1]))  # not_a_user_entry
                                    cr.execute("COMMENT ON COLUMN %s.%s IS '%s'" % (self._table, k, f.string.replace("'", "''")))  # not_a_user_entry
                                    self.__schema.warn("Table '%s': column '%s' has changed type (DB=%s, def=%s), data moved to column %s !",
                                                       self._table, k, f_pg_type, f._type, newname)
                                    to_migrate.append((newname, k))

                            # if the field is required and hasn't got a NOT NULL constraint
                            if f.required and f_pg_notnull == 0:
                                # set the field to the default value if any
                                if k in self._defaults:
                                    if callable(self._defaults[k]):
                                        default = self._defaults[k](self, cr, 1, context)
                                    else:
                                        default = self._defaults[k]

                                    if default is not None:
                                        ss = self._columns[k]._symbol_set
                                        query = 'UPDATE "%s" SET "%s"=%s WHERE "%s" is NULL' % (self._table, k, ss[0], k)  # not_a_user_entry
                                        cr.execute(query, (ss[1](default),))
                                # add the NOT NULL constraint
                                cr.commit()
                                try:
                                    cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" SET NOT NULL' % (self._table, k), log_exceptions=False)  # not_a_user_entry
                                    cr.commit()
                                    self.__schema.debug("Table '%s': column '%s': added NOT NULL constraint",
                                                        self._table, k)
                                except Exception:
                                    msg = "Table '%s': unable to set a NOT NULL constraint on column '%s' !\n"\
                                        "If you want to have it, you should update the records and execute manually:\n"\
                                        "ALTER TABLE %s ALTER COLUMN %s SET NOT NULL"
                                    self.__schema.warn(msg, self._table, k, self._table, k)
                                cr.commit()
                            elif not f.required and f_pg_notnull == 1:
                                cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" DROP NOT NULL' % (self._table, k))  # not_a_user_entry
                                cr.commit()
                                self.__schema.debug("Table '%s': column '%s': dropped NOT NULL constraint",
                                                    self._table, k)
                            # Verify index
                            indexname = '%s_%s_index' % (self._table, k)
                            cr.execute("SELECT indexname FROM pg_indexes WHERE indexname = %s and tablename = %s", (indexname, self._table))
                            res2 = cr.dictfetchall()
                            if not res2 and f.select:
                                cr.execute('CREATE INDEX "%s_%s_index" ON "%s" ("%s")' % (self._table, k, self._table, k))  # not_a_user_entry
                                cr.commit()
                                if f._type == 'text':
                                    # FIXME: for fields.text columns we should try creating GIN indexes instead (seems most suitable for an ERP context)
                                    msg = "Table '%s': Adding (b-tree) index for text column '%s'."\
                                        "This is probably useless (does not work for fulltext search) and prevents INSERTs of long texts"\
                                        " because there is a length limit for indexable btree values!\n"\
                                        "Use a search view instead if you simply want to make the field searchable."
                                    self.__schema.warn(msg, self._table, k, f._type)
                            if res2 and not f.select:
                                cr.execute('DROP INDEX "%s_%s_index"' % (self._table, k))  # not_a_user_entry
                                cr.commit()
                                msg = "Table '%s': dropping index for column '%s' of type '%s' as it is not required anymore"
                                self.__schema.debug(msg, self._table, k, f._type)

                            if isinstance(f, fields.many2one):
                                if self.pool.get(f._obj):
                                    self._create_fk(cr, k, f, True)
                                else:
                                    missing_fk.setdefault(f._obj, [])
                                    missing_fk[f._obj].append((self, k, f, True))
                    elif len(res) > 1:
                        netsvc.Logger().notifyChannel('orm', netsvc.LOG_ERROR, "Programming error, column %s->%s has multiple instances !" % (self._table, k))
                    else:
                        if not isinstance(f, fields.function) or f.store:
                            # add the missing field
                            cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (self._table, k, get_pg_type(f)[1]))  # not_a_user_entry
                            cr.execute("COMMENT ON COLUMN %s.%s IS '%s'" % (self._table, k, f.string.replace("'", "''")))  # not_a_user_entry
                            self.__schema.debug("Table '%s': added column '%s' with definition=%s",
                                                self._table, k, get_pg_type(f)[1])

                            # initialize it
                            if not create and k in self._defaults:
                                if callable(self._defaults[k]):
                                    default = self._defaults[k](self, cr, 1, context)
                                else:
                                    default = self._defaults[k]

                                ss = self._columns[k]._symbol_set
                                query = 'UPDATE "%s" SET "%s"=%s' % (self._table, k, ss[0])  # not_a_user_entry
                                cr.execute(query, (ss[1](default),))
                                cr.commit()
                                netsvc.Logger().notifyChannel('data', netsvc.LOG_DEBUG, "Table '%s': setting default value of new column %s" % (self._table, k))

                            if isinstance(f, fields.function):
                                order = 10
                                if f.store is not True:
                                    store_info = f.store[f.store.keys()[0]]
                                    if isinstance(store_info, list):
                                        order = store_info[0][2]
                                    else:
                                        order = store_info[2]
                                else:
                                    todo_update_store.append((order, f, k))

                            # and add constraints if needed
                            elif isinstance(f, fields.many2one):
                                if not self.pool.get(f._obj) or not cr.table_exists(self.pool.get(f._obj)._table):
                                    missing_fk.setdefault(f._obj, [])
                                    missing_fk[f._obj].append((self, k, f, False))
                                else:
                                    self._create_fk(cr, k, f, False)

                            if f.select:
                                cr.execute('CREATE INDEX "%s_%s_index" ON "%s" ("%s")' % (self._table, k, self._table, k))  # not_a_user_entry
                            if f.required:
                                try:
                                    cr.commit()
                                    cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" SET NOT NULL' % (self._table, k), log_exceptions=False)  # not_a_user_entry
                                    self.__schema.debug("Table '%s': column '%s': added a NOT NULL constraint",
                                                        self._table, k)
                                except Exception:
                                    msg = "WARNING: unable to set column %s of table %s not null !\n"\
                                        "Try to re-run: openerp-server.py --update=module\n"\
                                        "If it doesn't work, update records and execute manually:\n"\
                                        "ALTER TABLE %s ALTER COLUMN %s SET NOT NULL"
                                    self.__logger.warn(msg, k, self._table, self._table, k)
                            cr.commit()
            todo_end_append = todo_end.append
            for order, f, k in todo_update_store:
                todo_end_append((order, self._update_store, (f, k)))

        else:
            cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname=%s", (self._table,))
            create = not bool(cr.fetchone())

        for t in to_migrate:
            self.execute_migration(cr, t[0], t[1])

        cr.commit()     # start a new transaction

        for (key, con, null) in self._sql_constraints:
            if not con:
                continue
            conname = '%s_%s' % (self._table, key)

            cr.execute("SELECT conname, pg_catalog.pg_get_constraintdef(oid, true) as condef FROM pg_constraint where conname=%s", (conname,))
            existing_constraints = cr.dictfetchall()

            sql_actions = {
                'drop': {
                    'execute': False,
                    'query': 'ALTER TABLE "%s" DROP CONSTRAINT "%s"' % (self._table, conname, ),
                    'msg_ok': "Table '%s': dropped constraint '%s'. Reason: its definition changed from '%%s' to '%s'" % (
                        self._table, conname, con),
                    'msg_err': "Table '%s': unable to drop \'%s\' constraint !" % (self._table, con),
                    'order': 1,
                },
                'add': {
                    'execute': False,
                    'query': 'ALTER TABLE "%s" ADD CONSTRAINT "%s" %s' % (self._table, conname, con,),
                    'msg_ok': "Table '%s': added constraint '%s' with definition=%s" % (self._table, conname, con),
                    'msg_err': "Table '%s': unable to add \'%s\' constraint !\n If you want to have it, you should update the records and execute manually:\n%%s" % (
                        self._table, con),
                    'order': 2,
                },
            }

            if not existing_constraints:
                # constraint does not exists:
                sql_actions['add']['execute'] = True
                sql_actions['add']['msg_err'] = sql_actions['add']['msg_err'] % (sql_actions['add']['query'], )
            elif con.lower() not in [item['condef'].lower() for item in existing_constraints]:
                # constraint exists but its definition has changed:
                sql_actions['drop']['execute'] = True
                sql_actions['drop']['msg_ok'] = sql_actions['drop']['msg_ok'] % (existing_constraints[0]['condef'].lower(), )
                sql_actions['add']['execute'] = True
                sql_actions['add']['msg_err'] = sql_actions['add']['msg_err'] % (sql_actions['add']['query'], )

            # we need to add the constraint:
            sql_actions = [item for item in sql_actions.values()]
            sql_actions.sort(key=lambda x: x['order'])
            for sql_action in [action for action in sql_actions if action['execute']]:
                try:
                    cr.execute(sql_action['query'])
                    cr.commit()
                    self.__schema.debug(sql_action['msg_ok'])
                except:
                    self.__schema.warn(sql_action['msg_err'])
                    cr.rollback()

        if create:
            if hasattr(self, "_sql"):
                for line in self._sql.split(';'):
                    line2 = line.replace('\n', '').strip()
                    if line2:
                        cr.execute(line2)
                        cr.commit()
        if store_compute:
            self._parent_store_compute(cr)
            cr.commit()
        return todo_end, missing_fk, missing_m2m

    def __init__(self, cr):
        super(orm, self).__init__(cr)

        if not hasattr(self, '_log_access'):
            # if not access is not specify, it is the same value as _auto
            self._log_access = getattr(self, "_auto", True)

        self._columns = self._columns.copy()
        for store_field in self._columns:
            f = self._columns[store_field]
            if hasattr(f, 'digits_change'):
                f.digits_change(cr)
            if not isinstance(f, fields.function):
                continue
            if not f.store:
                continue
            if self._columns[store_field].store is True:
                sm = {self._name: (lambda self, cr, uid, ids, c={}: ids, None, 10, None)}
            else:
                sm = self._columns[store_field].store
            for object, aa_list in sm.items():
                if isinstance(aa_list, tuple):
                    aa_list = [aa_list]
                for aa in aa_list:
                    if len(aa) == 4:
                        (fnct, fields2, order, length) = aa
                    elif len(aa) == 3:
                        (fnct, fields2, order) = aa
                        length = None
                    else:
                        raise except_orm('Error',
                                         ('Invalid function definition %s in object %s !\nYou must use the definition: store={object:(fnct, fields, priority, time length)}.' % (store_field, self._name)))
                    self.pool._store_function.setdefault(object, [])
                    ok = True
                    for x, y, z, e, f, l in self.pool._store_function[object]:
                        if (x==self._name) and (y==store_field) and (e==fields2):
                            if f == order:
                                ok = False
                                break
                    if ok:
                        self.pool._store_function[object].append( (self._name, store_field, fnct, fields2, order, length))
                        self.pool._store_function[object].sort(lambda x, y: cmp(x[4], y[4]))

        for (key, null, msg) in self._sql_constraints:
            self.pool._sql_error[self._table+'_'+key] = msg

        # Load manual fields

        cr.execute("SELECT id FROM ir_model_fields WHERE name=%s AND model=%s", ('state', 'ir.model.fields'))
        if cr.fetchone():
            cr.execute('SELECT * FROM ir_model_fields WHERE model=%s AND state=%s', (self._name, 'manual'))
            for field in cr.dictfetchall():
                if field['name'] in self._columns:
                    continue
                attrs = {
                    'string': field['field_description'],
                    'required': bool(field['required']),
                    'readonly': bool(field['readonly']),
                    'domain': eval(field['domain']) if field['domain'] else None,
                    'size': field['size'],
                    'ondelete': field['on_delete'],
                    'translate': (field['translate']),
                    'manual': True,
                    #'select': int(field['select_level'])
                }

                if field['ttype'] == 'selection':
                    self._columns[field['name']] = getattr(fields, field['ttype'])(eval(field['selection']), **attrs)
                elif field['ttype'] == 'reference':
                    self._columns[field['name']] = getattr(fields, field['ttype'])(selection=eval(field['selection']), **attrs)
                elif field['ttype'] == 'many2one':
                    self._columns[field['name']] = getattr(fields, field['ttype'])(field['relation'], **attrs)
                elif field['ttype'] == 'one2many':
                    self._columns[field['name']] = getattr(fields, field['ttype'])(field['relation'], field['relation_field'], **attrs)
                elif field['ttype'] == 'many2many':
                    _rel1 = field['relation'].replace('.', '_')
                    _rel2 = field['model'].replace('.', '_')
                    _rel_name = 'x_%s_%s_%s_rel' % (_rel1, _rel2, field['name'])
                    self._columns[field['name']] = getattr(fields, field['ttype'])(field['relation'], _rel_name, 'id1', 'id2', **attrs)
                else:
                    self._columns[field['name']] = getattr(fields, field['ttype'])(**attrs)
        self._inherits_check()
        self._inherits_reload()
        if not self._sequence:
            self._sequence = self._table + '_id_seq'
        for k in self._defaults:
            assert (k in self._columns) or (k in self._inherit_fields), 'Default function defined in %s but field %s does not exist !' % (self._name, k,)
        for f in self._columns:
            self._columns[f].restart()

    #
    # Update objects that uses this one to update their _inherits fields
    #

    def _inherits_reload_src(self):
        for obj in self.pool.obj_pool.values():
            if self._name in obj._inherits:
                obj._inherits_reload()

    def _inherits_reload(self):
        res = {}
        for table in self._inherits:
            res.update(self.pool.get(table)._inherit_fields)
            for col in self.pool.get(table)._columns.keys():
                res[col] = (table, self._inherits[table], self.pool.get(table)._columns[col], table)
            for col in self.pool.get(table)._inherit_fields.keys():
                res[col] = (table, self._inherits[table], self.pool.get(table)._inherit_fields[col][2], self.pool.get(table)._inherit_fields[col][3])
        self._inherit_fields = res
        self._all_columns = self._get_column_infos()
        self._inherits_reload_src()

    def _get_column_infos(self):
        """Returns a dict mapping all fields names (direct fields and
           inherited field via _inherits) to a ``column_info`` struct
           giving detailed columns """
        result = {}
        for k, (parent, m2o, col, original_parent) in self._inherit_fields.iteritems():
            result[k] = fields.column_info(k, col, parent, m2o, original_parent)
        for k, col in self._columns.iteritems():
            result[k] = fields.column_info(k, col)
        return result

    def _inherits_check(self):
        for table, field_name in self._inherits.items():
            if field_name not in self._columns:
                logging.getLogger('init').info('Missing many2one field definition for _inherits reference "%s" in "%s", using default one.' % (field_name, self._name))
                self._columns[field_name] = fields.many2one(table, string="Automatically created field to link to parent %s" % table,
                                                            required=True, ondelete="cascade")
            elif not self._columns[field_name].required or self._columns[field_name].ondelete.lower() != "cascade":
                logging.getLogger('init').warning('Field definition for _inherits reference "%s" in "%s" must be marked as "required" with ondelete="cascade", forcing it.' % (field_name, self._name))
                self._columns[field_name].required = True
                self._columns[field_name].ondelete = "cascade"

    #def __getattr__(self, name):
    #    """
    #    Proxies attribute accesses to the `inherits` parent so we can call methods defined on the inherited parent
    #    (though inherits doesn't use Python inheritance).
    #    Handles translating between local ids and remote ids.
    #    Known issue: doesn't work correctly when using python's own super(), don't involve inherit-based inheritance
    #                 when you have inherits.
    #    """
    #    for model, field in self._inherits.iteritems():
    #        proxy = self.pool.get(model)
    #        if hasattr(proxy, name):
    #            attribute = getattr(proxy, name)
    #            if not hasattr(attribute, '__call__'):
    #                return attribute
    #            break
    #    else:
    #        return super(orm, self).__getattr__(name)

    #    def _proxy(cr, uid, ids, *args, **kwargs):
    #        objects = self.browse(cr, uid, ids, kwargs.get('context', None))
    #        lst = [obj[field].id for obj in objects if obj[field]]
    #        return getattr(proxy, name)(cr, uid, lst, *args, **kwargs)

    #    return _proxy


    def fields_get(self, cr, user, fields=None, context=None, with_uom_rounding=False):
        """
        Get the description of list of fields

        :param cr: database cursor
        :param user: current user id
        :param fields: list of fields
        :param context: context arguments, like lang, time zone
        :return: dictionary of field dictionaries, each one describing a field of the business object
        :raise AccessError: * if user has no create/write rights on the requested object

        """
        ira = self.pool.get('ir.model.access')
        write_access = ira.check(cr, user, self._name, 'write', raise_exception=False, context=context) or \
            ira.check(cr, user, self._name, 'create', raise_exception=False, context=context)
        return super(orm, self).fields_get(cr, user, fields, context, write_access, with_uom_rounding=with_uom_rounding)

    def read(self, cr, user, ids, fields=None, context=None, load='_classic_read'):
        if not ids:
            return []
        if context is None:
            context = {}
        self.pool.get('ir.model.access').check(cr, user, self._name, 'read', context=context)
        if not fields:
            fields = list(set(self._columns.keys() + self._inherit_fields.keys()))
        if isinstance(ids, (int, long)):
            select = [ids]
        else:
            select = ids
        select = [isinstance(x, dict) and x['id'] or x for x in select]
        result = self._read_flat(cr, user, select, fields, context, load)

        for r in result:
            for key, v in r.items():
                if v is None:
                    r[key] = False

        if isinstance(ids, (int, long, dict)):
            return result and result[0] or False
        return result

    def _read_flat(self, cr, user, ids, fields_to_read, context=None, load='_classic_read'):
        if not ids:
            return []
        if context is None:
            context = {}
        if fields_to_read == None:
            fields_to_read = self._columns.keys()

        # Construct a clause for the security rules.
        # 'tables' hold the list of tables necessary for the SELECT including the ir.rule clauses,
        # or will at least contain self._table.
        rule_clause, rule_params, tables = self.pool.get('ir.rule').domain_get(cr, user, self._name, 'read', context=context)

        # all inherited fields + all non inherited fields for which the attribute whose name is in load is True
        fields_pre = [f for f in fields_to_read if
                      f == self.CONCURRENCY_CHECK_FIELD
                      or (f in self._columns and getattr(self._columns[f], '_classic_write'))
                      ] + self._inherits.values()

        res = []
        if fields_pre:
            def convert_field(f):
                f_qual = "%s.%s" % (self._table, f) # need fully-qualified references in case len(tables) > 1
                if f in ('create_date', 'write_date'):
                    return "date_trunc('second', %s) as %s" % (f_qual, f)
                if f == self.CONCURRENCY_CHECK_FIELD:
                    if self._log_access:
                        return "COALESCE(%s.write_date, %s.create_date, now())::timestamp AS %s" % (self._table, self._table, f,)
                    return "now()::timestamp AS %s" % (f,)
                if isinstance(self._columns[f], fields.binary) and context.get('bin_size', False):
                    if self._name == 'ir.attachment' and 'size' in self._columns:
                        return 'size as "%s"' % f
                    return 'length(%s) as "%s"' % (f_qual, f)
                return f_qual

            fields_pre2 = map(convert_field, fields_pre)
            order_by = self._parent_order or self._order
            select_fields = ','.join(fields_pre2 + [self._table + '.id'])
            query = 'SELECT %s FROM %s WHERE %s.id IN %%s' % (select_fields,  # ignore_sql_check
                                                              ','.join(tables), self._table)
            if rule_clause:
                query = ''.join((query, ' AND ', ' OR '.join(rule_clause)))

            def execute_request(res, query, rule_clause, local_ids):
                if rule_clause:
                    cr.execute(query, [tuple(local_ids)] + rule_params)
                    if cr.rowcount != len(local_ids):
                        raise except_orm(_('AccessError'),
                                         _('Operation prohibited by access rules, or performed on an already deleted document (Operation: read, Document type: %s).')
                                         % (self._description,),
                                         ir_rule_error=True)
                else:
                    cr.execute(query, (tuple(local_ids),))
                res.extend(cr.dictfetchall())

            if len(ids) == 1:
                # ~ 70% of the requests are done with only one id (20/05/2016)
                execute_request(res, query, rule_clause, ids)
            else:
                # order only when there is more than one id in ids
                query = ''.join((query, ' ORDER BY ', order_by))
                max_split = None
                # number of C/S lines is big and using split breaks default order_by
                if self._name == 'physical.inventory.counting':
                    max_split = 3000
                for sub_ids in cr.split_for_in_conditions(ids, max_split):
                    execute_request(res, query, rule_clause, sub_ids)

            context_lang = context and context.get('lang', False) or 'en_US'
            if context_lang != 'en_US':
                translation_obj = self.pool.get('ir.translation')
                for f in fields_pre:
                    if f == self.CONCURRENCY_CHECK_FIELD:
                        continue
                    if self._columns[f].translate:
                        ids = [x['id'] for x in res]
                        res_trans = translation_obj._get_ids(cr,
                                                             user, self._name+','+f, 'model', context_lang, ids)
                        for r in res:
                            r[f] = res_trans.get(r['id'], False) or r[f]
        else:
            res = [{'id':x} for x in ids]

        for table in self._inherits:
            cols = [x for x in intersect(self._inherit_fields.keys(), fields_to_read) if x not in self._columns.keys()]
            if not cols:
                continue
            col = self._inherits[table]
            res2 = self.pool.get(table).read(cr, user, [x[col] for x in res], cols, context, load)

            res3 = {}
            for r in res2:
                res3[r['id']] = r
                del r['id']

            for record in res:
                if not record[col]: # if the record is deleted from _inherits table?
                    continue
                record.update(res3[record[col]])
                if col not in fields_to_read:
                    del record[col]

        # all fields which need to be post-processed by a simple function (symbol_get)
        fields_post = filter(lambda x: x in self._columns and self._columns[x]._symbol_get, fields_to_read)
        if fields_post:
            for r in res:
                for f in fields_post:
                    r[f] = self._columns[f]._symbol_get(r[f])
        ids = [x['id'] for x in res]

        # all non inherited fields for which the attribute whose name is in load is False
        fields_post = filter(lambda x: x in self._columns and not getattr(self._columns[x], load), fields_to_read)

        # Compute POST fields
        todo = {}
        for f in fields_post:
            todo.setdefault(self._columns[f]._multi, [])
            todo[self._columns[f]._multi].append(f)
        for key, val in todo.items():
            if key:
                res2 = self._columns[val[0]].get(cr, self, ids, val, user, context=context, values=res)
                for pos in val:
                    for record in res:
                        if not record['id'] in res2:
                            raise Exception("Could not process key %s" % key)
                        if isinstance(res2[record['id']], str): res2[record['id']] = eval(res2[record['id']]) #TOCHECK : why got string instend of dict in python2.6
                        multi_fields = res2.get(record['id'],{})
                        if multi_fields:
                            record[pos] = multi_fields.get(pos,[])
            else:
                for f in val:
                    res2 = self._columns[f].get(cr, self, ids, f, user, context=context, values=res)
                    for record in res:
                        if res2:
                            try:
                                record[f] = res2[record['id']]
                            except:
                                self.__logger.error('Read %s field %s, record not found' % (self._name, f), exc_info=True)
                                raise
                        else:
                            record[f] = []
        readonly = None
        for vals in res:
            for field in vals.copy():
                fobj = None
                if field in self._columns:
                    fobj = self._columns[field]

                if not fobj:
                    continue
                groups = fobj.read
                if groups:
                    edit = False
                    for group in groups:
                        module = group.split(".")[0]
                        grp = group.split(".")[1]
                        cr.execute("select count(*) from res_groups_users_rel where gid IN (select res_id from ir_model_data where name=%s and module=%s and model=%s) and uid=%s",  \
                                   (grp, module, 'res.groups', user))
                        readonly = cr.fetchall()
                        if readonly[0][0] >= 1:
                            edit = True
                            break
                        elif readonly[0][0] == 0:
                            edit = False
                        else:
                            edit = False

                    if not edit:
                        if type(vals[field]) == type([]):
                            vals[field] = []
                        elif type(vals[field]) == type(0.0):
                            vals[field] = 0
                        elif type(vals[field]) == type(''):
                            vals[field] = '=No Permission='
                        else:
                            vals[field] = False
        return res

    def perm_read(self, cr, user, ids, context=None, details=True):
        """
        Returns some metadata about the given records.

        :param details: if True, \*_uid fields are replaced with the name of the user
        :return: list of ownership dictionaries for each requested record
        :rtype: list of dictionaries with the following keys:

                    * id: object id
                    * create_uid: user who created the record
                    * create_date: date when the record was created
                    * write_uid: last user who changed the record
                    * write_date: date of the last change to the record
                    * xmlid: XML ID to use to refer to this record (if there is one), in format ``module.name``
        """
        if context is None:
            context = {}
        if not ids:
            return []
        fields = ''
        uniq = isinstance(ids, (int, long))
        if uniq:
            ids = [ids]
        fields = ['id']
        if self._log_access:
            fields += ['create_uid', 'create_date', 'write_uid', 'write_date']
        quoted_table = '"%s"' % self._table
        fields_str = ",".join('%s.%s'%(quoted_table, field) for field in fields)
        query = '''SELECT %s, __imd.module, __imd.name
                   FROM %s LEFT JOIN ir_model_data __imd
                       ON (__imd.model = %%s and __imd.res_id = %s.id)
                   WHERE %s.id IN %%s''' % (fields_str, quoted_table, quoted_table, quoted_table)  # not_a_user_entry
        cr.execute(query, (self._name, tuple(ids)))
        res = cr.dictfetchall()
        for r in res:
            for key in r:
                r[key] = r[key] or False
                if details and key in ('write_uid', 'create_uid') and r[key]:
                    try:
                        r[key] = self.pool.get('res.users').name_get(cr, user, [r[key]])[0]
                    except Exception:
                        pass # Leave the numeric uid there
            r['xmlid'] = ("%(module)s.%(name)s" % r) if r['name'] else False
            del r['name'], r['module']
        if uniq:
            return res[ids[0]]
        return res

    def _check_concurrency(self, cr, ids, context):
        if not context:
            return
        if not (context.get(self.CONCURRENCY_CHECK_FIELD) and self._log_access):
            return
        check_clause = "(id = %s AND %s < COALESCE(write_date, create_date, now())::timestamp)"
        for sub_ids in cr.split_for_in_conditions(ids):
            ids_to_check = []
            for id in sub_ids:
                id_ref = "%s,%s" % (self._name, id)
                update_date = context[self.CONCURRENCY_CHECK_FIELD].pop(id_ref, None)
                if update_date:
                    ids_to_check.extend([id, update_date])
            if not ids_to_check:
                continue
            cr.execute("SELECT id FROM %s WHERE %s" % (self._table, " OR ".join([check_clause]*(len(ids_to_check)/2))), tuple(ids_to_check))  # not_a_user_entry
            res = cr.fetchone()
            if res:
                # mention the first one only to keep the error message readable
                raise except_orm('ConcurrencyException', _('A document was modified since you last viewed it (%s:%d)') % (self._description, res[0]))

    def check_access_rule(self, cr, uid, ids, operation, context=None):
        """Verifies that the operation given by ``operation`` is allowed for the user
           according to ir.rules.

           :param operation: one of ``write``, ``unlink``
           :raise except_orm: * if current ir.rules do not permit this operation.
           :return: None if the operation is allowed
        """
        where_clause, where_params, tables = self.pool.get('ir.rule').domain_get(cr, uid, self._name, operation, context=context)
        if where_clause:
            where_clause = ''.join((' AND ', ' AND '.join(where_clause)))
            for sub_ids in cr.split_for_in_conditions(ids):
                query = ''.join(('SELECT ', self._table, '.id FROM ',
                                 ','.join(tables), ' WHERE ', self._table, '.id IN %s',
                                 where_clause))
                cr.execute(query, [sub_ids] + where_params)
                if cr.rowcount != len(sub_ids):
                    raise except_orm(_('AccessError'),
                                     _('Operation prohibited by access rules, or performed on an already deleted document (Operation: %s, Document type: %s).')
                                     % (operation, self._description))

    def unlink_web(self, cr, uid, ids, context=None):
        return self.unlink(cr, uid, ids, context=context)

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete records with given ids

        :param cr: database cursor
        :param uid: current user id
        :param ids: id or list of ids
        :param context: (optional) context arguments, like lang, time zone
        :return: True
        :raise AccessError: * if user has no unlink rights on the requested object
                            * if user tries to bypass access rules for unlink on the requested object
        :raise UserError: if the record is default property for other records

        """
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]

        result_store = self._store_get_values(cr, uid, ids, None, context)

        self._check_concurrency(cr, ids, context)

        self.pool.get('ir.model.access').check(cr, uid, self._name, 'unlink', context=context)

        properties = self.pool.get('ir.property')
        domain = [('res_id', '=', False),
                  ('value_reference', 'in', ['%s,%s' % (self._name, i) for i in ids]),
                  ]
        if properties.search(cr, uid, domain, limit=1, order='NO_ORDER',
                             context=context):
            raise except_orm(_('Error'), _('Unable to delete this document because it is used as a default property'))

        wf_service = netsvc.LocalService("workflow")
        for oid in ids:
            wf_service.trg_delete(uid, self._name, oid, cr)


        self.check_access_rule(cr, uid, ids, 'unlink', context=context)
        pool_model_data = self.pool.get('ir.model.data')
        pool_ir_values = self.pool.get('ir.values')
        for sub_ids in cr.split_for_in_conditions(ids):
            # delete the related attachements
            cr.execute('DELETE FROM ir_attachment WHERE res_id IN %s AND res_model = %s',
                       (sub_ids, self._name))

            cr.execute('DELETE FROM ' + self._table + ' WHERE id IN %s', (sub_ids,))  # not_a_user_entry

            # Removing the ir_model_data reference if the record being deleted is a record created by xml/csv file,
            # as these are not connected with real database foreign keys, and would be dangling references.
            # Step 1. Calling unlink of ir_model_data only for the affected IDS.
            referenced_ids = pool_model_data.search(cr, uid,
                                                    [('res_id','in',list(sub_ids)),('model','=',self._name)],
                                                    order='NO_ORDER', context=context)

            if referenced_ids and self._name in xmlid_no_delete.prevent_deletion:
                cr.execute('''select module, name from ir_model_data
                        where
                            (module, name) in %s and
                            id in %s
                        limit 1
                ''', (tuple(xmlid_no_delete.prevent_deletion[self._name]), tuple(referenced_ids)))
                no_delete = cr.fetchone()
                if no_delete:
                    raise except_orm(_('Error'), _('Unable to delete this record defined as Master Data: object: %s, xmlid: %s.%s') % (self._name, no_delete[0], no_delete[1]))

            # Step 2. Marching towards the real deletion of referenced records
            pool_model_data.unlink(cr, uid, referenced_ids, context=context)


            if context.get('avoid_sdref_deletion') and hasattr(self, '_unlink_sdref') and self._unlink_sdref:
                cr.execute("DELETE FROM ir_model_data WHERE model=%s AND res_id in %s AND module='sd'", (self._name, sub_ids))

            # For the same reason, removing the record relevant to ir_values
            ir_value_ids = pool_ir_values.search(cr, uid,
                                                 ['|',('value','in',['%s,%s' % (self._name, sid) for sid in sub_ids]),'&',('res_id','in',list(sub_ids)),('model','=',self._name)],
                                                 order='NO_ORDER', context=context)
            if ir_value_ids:
                pool_ir_values.unlink(cr, uid, ir_value_ids, context=context)

        for order, current_obj, store_ids, field_list in result_store:
            if current_obj != self._name:
                obj = self.pool.get(current_obj)
                cr.execute('SELECT id from '+obj._table+' WHERE id IN %s', (tuple(store_ids),))  # not_a_user_entry
                rids = map(lambda x: x[0], cr.fetchall())
                if rids:
                    obj._store_set_values(cr, uid, rids, field_list, context)

        self._clean_cache(cr.dbname)
        return True

    #
    # TODO: Validate
    #
    def write(self, cr, user, ids, vals, context=None):
        """
        Update records with given ids with the given field values

        :param cr: database cursor
        :param user: current user id
        :type user: integer
        :param ids: object id or list of object ids to update according to **vals**
        :param vals: field values to update, e.g {'field_name': new_field_value, ...}
        :type vals: dictionary
        :param context: (optional) context arguments, e.g. {'lang': 'en_us', 'tz': 'UTC', ...}
        :type context: dictionary
        :return: True
        :raise AccessError: * if user has no write rights on the requested object
                            * if user tries to bypass access rules for write on the requested object
        :raise ValidateError: if user tries to enter invalid value for a field that is not in selection
        :raise UserError: if a loop would be created in a hierarchy of objects a result of the operation (such as setting an object as its own parent)

        **Note**: The type of field values to pass in ``vals`` for relationship fields is specific:

            + For a many2many field, a list of tuples is expected.
              Here is the list of tuple that are accepted, with the corresponding semantics ::

                 (0, 0,  { values })    link to a new record that needs to be created with the given values dictionary
                 (1, ID, { values })    update the linked record with id = ID (write *values* on it)
                 (2, ID)                remove and delete the linked record with id = ID (calls unlink on ID, that will delete the object completely, and the link to it as well)
                 (3, ID)                cut the link to the linked record with id = ID (delete the relationship between the two objects but does not delete the target object itself)
                 (4, ID)                link to existing record with id = ID (adds a relationship)
                 (5)                    unlink all (like using (3,ID) for all linked records)
                 (6, 0, [IDs])          replace the list of linked IDs (like using (5) then (4,ID) for each ID in the list of IDs)

                 Example:
                    [(6, 0, [8, 5, 6, 4])] sets the many2many to ids [8, 5, 6, 4]

            + For a one2many field, a lits of tuples is expected.
              Here is the list of tuple that are accepted, with the corresponding semantics ::

                 (0, 0,  { values })    link to a new record that needs to be created with the given values dictionary
                 (1, ID, { values })    update the linked record with id = ID (write *values* on it)
                 (2, ID)                remove and delete the linked record with id = ID (calls unlink on ID, that will delete the object completely, and the link to it as well)

                 Example:
                    [(0, 0, {'field_name':field_value_record1, ...}), (0, 0, {'field_name':field_value_record2, ...})]

            + For a many2one field, simply use the ID of target record, which must already exist, or ``False`` to remove the link.
            + For a reference field, use a string with the model name, a comma, and the target object id (example: ``'product.product, 5'``)

        """
        if not ids:
            return True
        assert isinstance(vals, dict), "orm.write() expects a dictionnary as 4th argument!"
        readonly = None
        for field in vals.copy():
            fobj = None
            if field in self._columns:
                fobj = self._columns[field]
            elif field in self._inherit_fields:
                fobj = self._inherit_fields[field][2]
            if not fobj:
                continue
            groups = fobj.write

            if groups:
                edit = False
                for group in groups:
                    module = group.split(".")[0]
                    grp = group.split(".")[1]
                    cr.execute("select count(*) from res_groups_users_rel where gid IN (select res_id from ir_model_data where name=%s and module=%s and model=%s) and uid=%s", \
                               (grp, module, 'res.groups', user))
                    readonly = cr.fetchall()
                    if readonly[0][0] >= 1:
                        edit = True
                        break
                    elif readonly[0][0] == 0:
                        edit = False
                    else:
                        edit = False

                if not edit:
                    vals.pop(field)

        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self._check_concurrency(cr, ids, context)
        self.pool.get('ir.model.access').check(cr, user, self._name, 'write', context=context)

        #result = self._store_get_values(cr, user, ids, vals.keys(), context) or []
        result = []

        # No direct update of parent_left/right
        vals.pop('parent_left', None)
        vals.pop('parent_right', None)

        parents_changed = []
        if self._parent_store and (self._parent_name in vals):
            # The parent_left/right computation may take up to
            # 5 seconds. No need to recompute the values if the
            # parent is the same. Get the current value of the parent
            parent_val = vals[self._parent_name]
            if parent_val:
                query = "SELECT id FROM %s WHERE id IN %%s AND (%s != %%s OR %s IS NULL)" % \
                    (self._table, self._parent_name, self._parent_name)
                cr.execute(query, (tuple(ids), parent_val))
            else:
                query = "SELECT id FROM %s WHERE id IN %%s AND (%s IS NOT NULL)" % (self._table, self._parent_name)  # not_a_user_entry
                cr.execute(query, (tuple(ids),))
            parents_changed = map(operator.itemgetter(0), cr.fetchall())

        upd0 = []
        upd0_append = upd0.append
        upd1 = []
        upd1_append = upd1.append
        upd_todo = []
        upd_todo_append = upd_todo.append
        updend = []
        updend_append = updend.append
        direct = []
        direct_append = direct.append
        to_translate = context and context.get('lang', False) and (context['lang'] != 'en_US')
        for field in vals:
            if field in self._columns:
                if self._columns[field]._classic_write and not (hasattr(self._columns[field], '_fnct_inv')):
                    if (not to_translate) or not self._columns[field].translate:
                        upd0_append('"'+field+'"='+self._columns[field]._symbol_set[0])
                        upd1_append(self._columns[field]._symbol_set[1](vals[field]))
                    direct_append(field)
                else:
                    upd_todo_append(field)
            else:
                updend_append(field)
            if field in self._columns \
                    and hasattr(self._columns[field], 'selection') \
                    and vals[field]:
                self._check_selection_field_value(cr, user, field, vals[field], context=context)

        if self._log_access and not context.get('no_write_access'):
            upd0_append('write_uid=%s')
            upd0_append('write_date=now()')

            # if user is fakeUid object, use realId, otherwise use user
            upd1_append(hasattr(user, 'realUid') and user.realUid or user)

        if len(upd0):
            self.check_access_rule(cr, user, ids, 'write', context=context)
            for sub_ids in cr.split_for_in_conditions(ids):
                query = ''.join(('UPDATE ', self._table, ' SET ',
                                 ','.join(upd0), ' WHERE id IN %s'))
                cr.execute(query, upd1 + [sub_ids])
                if cr.rowcount != len(sub_ids):
                    raise except_orm(_('AccessError'),
                                     _('One of the records you are trying to modify has already been deleted (Document type: %s).') % self._description)
            if to_translate:
                sync_context = context.get('sync_type', False)
                # do not clear cache in case of synchronization. It will be
                # done at the end of the sync in _get_reset_cache_at_sync().
                clear_cache = not sync_context
                fields_to_translate = [f for f in direct if\
                                       self._columns[f].translate]
                if fields_to_translate:
                    field_translated_dict = dict([(key, vals[key]) for key in
                                                  fields_to_translate])
                    original_values = self.read(cr, user, ids, fields_to_translate, context=context)[0]

                    # remove elements which have the same value than the
                    # orginal one
                    field_translated_dict = dict((key, value) for key, value in\
                                                 field_translated_dict.items() if field_translated_dict[key]!=original_values[key])
                    field_to_write_dict = {}

                    for field_name, new_value in field_translated_dict.items():
                        src_trans = original_values.get(field_name, None)
                        if not src_trans or not vals.get(field_name, None):
                            src_trans = vals.get(field_name, None)
                            field_to_write_dict[field_name]=vals[field_name]
                        self.pool.get('ir.translation')._set_ids(cr, user,
                                                                 self._name+','+field_name, 'model', context['lang'],
                                                                 ids, new_value, src=src_trans, clear=clear_cache, context=context)
                    if field_to_write_dict:
                        self.write(cr, user, ids, field_to_write_dict)


        if upd_todo:
            upd_todo.sort(lambda x, y: self._columns[x].priority-self._columns[y].priority)
            # default element in context must be removed when call a one2many or many2many
            rel_context = context.copy()
            for c in context.items():
                if c[0].startswith('default_'):
                    del rel_context[c[0]]

            for field in upd_todo:
                for current_id in ids:
                    # call the 'set' method of fields which are not classic_write
                    result += self._columns[field].set(cr, self, current_id, field, vals[field], user, context=rel_context) or []

        for table in self._inherits:
            col = self._inherits[table]
            nids = []
            for sub_ids in cr.split_for_in_conditions(ids):
                query = ''.join(('SELECT DISTINCT "', col, '" FROM "',
                                 self._table, '" WHERE id IN %s'))
                cr.execute(query, (sub_ids,))
                nids.extend([x[0] for x in cr.fetchall()])

            v = {}
            for val in updend:
                if self._inherit_fields[val][0] == table:
                    v[val] = vals[val]
            if v:
                self.pool.get(table).write(cr, user, nids, v, context)

        self._validate(cr, user, ids, context)

        # TODO: use _order to set dest at the right position and not first node of parent
        # We can't defer parent_store computation because the stored function
        # fields that are computer may refer (directly or indirectly) to
        # parent_left/right (via a child_of domain)
        if parents_changed:
            if self.pool._init:
                self.pool._init_parent[self._name] = True
            else:
                order = self._parent_order or self._order
                parent_val = vals[self._parent_name]
                if parent_val:
                    clause, params = '%s=%%s' % (self._parent_name,), (parent_val,)
                else:
                    clause, params = '%s IS NULL' % (self._parent_name,), ()

                for current_id in parents_changed:
                    cr.execute('SELECT parent_left, parent_right FROM %s WHERE id=%%s' % (self._table,), (current_id,))  # not_a_user_entry
                    pleft, pright = cr.fetchone()
                    distance = pright - pleft + 1

                    # Positions of current siblings, to locate proper insertion point;
                    # this can _not_ be fetched outside the loop, as it needs to be refreshed
                    # after each update, in case several nodes are sequentially inserted one
                    # next to the other (i.e computed incrementally)
                    cr.execute('SELECT parent_right, id FROM %s WHERE %s ORDER BY %s' % (self._table, clause, order), params)  # not_a_user_entry
                    parents = cr.fetchall()

                    # Find Position of the element
                    position = None
                    for (parent_pright, parent_id) in parents:
                        if parent_id == current_id:
                            break
                        position = parent_pright + 1

                    # It's the first node of the parent
                    if not position:
                        if not parent_val:
                            position = 1
                        else:
                            query = ''.join(('SELECT parent_left FROM ',
                                             self._table, ' WHERE id=%s'))
                            cr.execute(query, (parent_val,))
                            position = cr.fetchone()[0] + 1

                    if pleft < position <= pright:
                        raise except_orm(_('UserError'), _('Recursivity Detected.'))

                    query = ''.join(('UPDATE ', self._table,
                                     ' SET parent_left=parent_left+%s WHERE parent_left>=%s',))
                    cr.execute(query, (distance, position))
                    query = ''.join(('UPDATE ', self._table,
                                     ' SET parent_right=parent_right+%s WHERE parent_right>=%s',))
                    cr.execute(query, (distance, position))
                    if pleft < position:
                        query = ''.join(('UPDATE ', self._table,
                                         ' SET parent_left=parent_left+%s, parent_right=parent_right+%s WHERE parent_left>=%s AND parent_left<%s'))
                        cr.execute(query, (position-pleft, position-pleft, pleft, pright))
                    else:
                        query = ''.join(('UPDATE ', self._table,
                                         ' SET parent_left=parent_left-%s, parent_right=parent_right-%s WHERE parent_left>=%s AND parent_left<%s'))
                        cr.execute(query, (pleft-position+distance, pleft-position+distance, pleft+distance, pright+distance))


        if not context.get('no_store_function', False) or isinstance(context['no_store_function'], list) and self._name not in context['no_store_function']:
            self._call_store_function(cr, user, ids, keys=vals.keys(), result=result, context=context)

        wf_service = netsvc.LocalService("workflow")
        for current_id in ids:
            wf_service.trg_write(user, self._name, current_id, cr)
        self._clean_cache(cr.dbname)
        return True

    def _call_store_function(self, cr, uid, ids, keys=None, result=None, bypass=True, context=None):
        if result is None:
            result = []
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        done = []
        done_append = done.append

        result += self._store_get_values(cr, uid, ids, keys, context)
        result.sort()
        for order, object, ids, fields2 in result:
            if bypass and context.get('bypass_store_function') and (object, fields2) in context['bypass_store_function']:
                continue
            if not (object, ids, fields2) in done:
                self.pool.get(object)._store_set_values(cr, uid, ids, fields2, context)
                done_append((object, ids, fields2))
        return True
    #
    # TODO: Should set perm to user.xxx
    #
    def create(self, cr, user, vals, context=None):
        """
        Create new record with specified value

        :param cr: database cursor
        :param user: current user id
        :type user: integer
        :param vals: field values for new record, e.g {'field_name': field_value, ...}
        :type vals: dictionary
        :param context: optional context arguments, e.g. {'lang': 'en_us', 'tz': 'UTC', ...}
        :type context: dictionary
        :return: id of new record created
        :raise AccessError: * if user has no create rights on the requested object
                            * if user tries to bypass access rules for create on the requested object
        :raise ValidateError: if user tries to enter invalid value for a field that is not in selection
        :raise UserError: if a loop would be created in a hierarchy of objects a result of the operation (such as setting an object as its own parent)

        **Note**: The type of field values to pass in ``vals`` for relationship fields is specific.
        Please see the description of the :py:meth:`~osv.osv.osv.write` method for details about the possible values and how
        to specify them.

        """
        if context is None:
            context = {}
        self.pool.get('ir.model.access').check(cr, user, self._name, 'create', context=context)

        vals = self._add_missing_default_values(cr, user, vals, context)

        tocreate = {}
        for v in self._inherits:
            if self._inherits[v] not in vals:
                tocreate[v] = {}
            else:
                tocreate[v] = {'id': vals[self._inherits[v]]}
        (upd0, upd1, upd2) = ('', '', [])
        upd_todo = []
        upd2_append = upd2.append
        upd_todo_append = upd_todo.append
        for v in vals.keys():
            if v in self._inherit_fields:
                (table, col, col_detail, original_parent) = self._inherit_fields[v]
                tocreate[table][v] = vals[v]
                del vals[v]
            elif v not in self._columns:
                del vals[v]

        # Try-except added to filter the creation of those records whose fields are readonly.
        # Example : any dashboard which has all the fields readonly.(due to Views(database views))
        try:
            cr.execute("SELECT nextval('"+self._sequence+"')")  # not_a_user_entry
        except:
            raise except_orm(_('UserError'),
                             _('You cannot perform this operation. New Record Creation is not allowed for this object as this object is for reporting purpose.'))

        id_new = cr.fetchone()[0]
        for table in tocreate:
            if self._inherits[table] in vals:
                del vals[self._inherits[table]]

            record_id = tocreate[table].pop('id', None)

            inherit_obj = self.pool.get(table)
            if record_id is None or not record_id:
                if hasattr(inherit_obj, '_record_source') and inherit_obj._record_source:
                    tocreate[table]['signature_res_model'] = self._name
                    tocreate[table]['signature_res_id'] = id_new
                record_id = inherit_obj.create(cr, user, tocreate[table], context=context)
            elif tocreate[table]:
                inherit_obj.write(cr, user, [record_id], tocreate[table], context=context)

            upd0 += ',' + self._inherits[table]
            upd1 += ',%s'
            upd2_append(record_id)

        #Start : Set bool fields to be False if they are not touched(to make search more powerful)
        bool_fields = [x for x in self._columns.keys() if self._columns[x]._type=='boolean']

        for bool_field in bool_fields:
            if bool_field not in vals:
                vals[bool_field] = False
        #End
        for field in vals.copy():
            fobj = None
            if field in self._columns:
                fobj = self._columns[field]
            else:
                fobj = self._inherit_fields[field][2]
            if not fobj:
                continue
            groups = fobj.write
            if groups:
                edit = False
                for group in groups:
                    module = group.split(".")[0]
                    grp = group.split(".")[1]
                    cr.execute("select count(*) from res_groups_users_rel where gid IN (select res_id from ir_model_data where name='%s' and module='%s' and model='%s') and uid=%s" % (grp, module, 'res.groups', user))   # not_a_user_entry
                    readonly = cr.fetchall()
                    if readonly[0][0] >= 1:
                        edit = True
                        break
                if not edit:
                    vals.pop(field)
        for field in vals:
            if self._columns[field]._classic_write:
                upd0 = upd0 + ',"' + field + '"'
                upd1 = upd1 + ',' + self._columns[field]._symbol_set[0]
                upd2_append(self._columns[field]._symbol_set[1](vals[field]))
            else:
                if not isinstance(self._columns[field], fields.related):
                    upd_todo_append(field)
            if field in self._columns \
                    and hasattr(self._columns[field], 'selection') \
                    and vals[field]:
                self._check_selection_field_value(cr, user, field, vals[field], context=context)
        if self._log_access:
            upd0 += ',create_uid,create_date'
            upd1 += ',%s,now()'
            # if user is fakeUid object, use realId, otherwise use user
            upd2_append(hasattr(user, 'realUid') and user.realUid or user)

        query = ''.join(('INSERT INTO "', self._table, '" (id', upd0,') values (', str(id_new), upd1, ')'))
        cr.execute(query, tuple(upd2))
        self.check_access_rule(cr, user, [id_new], 'create', context=context)

        if self._parent_store and not context.get('defer_parent_store_computation'):
            if self.pool._init:
                self.pool._init_parent[self._name] = True
            else:
                parent = vals.get(self._parent_name, False)
                if parent:
                    query = ''.join(('SELECT parent_right from ', self._table,
                                     ' WHERE ', self._parent_name, '=%s ORDER BY ',
                                     (self._parent_order or self._order)))
                    cr.execute(query, (parent,))
                    pleft_old = None
                    result_p = cr.fetchall()
                    for (pleft,) in result_p:
                        if not pleft:
                            break
                        pleft_old = pleft
                    if not pleft_old:
                        cr.execute('select parent_left from '+self._table+' where id=%s', (parent,))  # not_a_user_entry
                        pleft_old = cr.fetchone()[0]
                    pleft = pleft_old
                else:
                    cr.execute('select max(parent_right) from '+self._table)  # not_a_user_entry
                    pleft = cr.fetchone()[0] or 0
                cr.execute('update '+self._table+' set parent_left=parent_left+2 where parent_left>%s', (pleft,))  # not_a_user_entry
                cr.execute('update '+self._table+' set parent_right=parent_right+2 where parent_right>%s', (pleft,))  # not_a_user_entry
                cr.execute('update '+self._table+' set parent_left=%s,parent_right=%s where id=%s', (pleft+1, pleft+2, id_new))  # not_a_user_entry

        # default element in context must be remove when call a one2many or many2many
        result = []
        if upd_todo:
            upd_todo.sort(lambda x, y: self._columns[x].priority-self._columns[y].priority)
            rel_context = context.copy()
            for c in context.items():
                if c[0].startswith('default_'):
                    del rel_context[c[0]]

            for field in upd_todo:
                result += self._columns[field].set(cr, self, id_new, field, vals[field], user, rel_context) or []
        self._validate(cr, user, [id_new], context)

        if not context.get('no_store_function', False) or isinstance(context['no_store_function'], list) and self._name not in context['no_store_function']:
            self._call_store_function(cr, user, id_new, keys=vals.keys(), result=result, context=context)

        if self._log_create and not (context and context.get('no_store_function', False)):
            message = self._description + \
                " '" + \
                self.name_get(cr, user, [id_new], context=context)[0][1] + \
                "' " + _("created.")
            self.log(cr, user, id_new, message, True, context=context)
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_create(user, self._name, id_new, cr)
        self._clean_cache(cr.dbname)
        return id_new

    def _store_get_values(self, cr, uid, ids, fields, context=None):
        """Returns an ordered list of fields.functions to call due to
           an update operation on ``fields`` of records with ``ids``,
           obtained by calling the 'store' functions of these fields,
           as setup by their 'store' attribute.

           :return: [(priority, model_name, [record_ids,], [function_fields,])]
        """
        if context is None:
            context = {}
        # FIXME: rewrite, cleanup, use real variable names
        # e.g.: http://pastie.org/1222060
        result = {}
        fncts = self.pool._store_function.get(self._name, [])

        for fnct in range(len(fncts)):
            if fncts[fnct][3]:
                ok = False
                if not fields:
                    ok = True
                for f in (fields or []):
                    if f in fncts[fnct][3]:
                        ok = True
                        break
                if not ok:
                    continue

            result.setdefault(fncts[fnct][0], {})

            # uid == 1 for accessing objects having rules defined on store fields
            ids2 = list(set((fncts[fnct][2](self, cr, 1, ids, context))))
            for id in filter(None, ids2):
                result[fncts[fnct][0]].setdefault(id, [])
                result[fncts[fnct][0]][id].append(fnct)
        function_dict = {}
        for object in result:
            k2 = {}
            for id, fnct in result[object].items():
                k2.setdefault(tuple(fnct), [])
                k2[tuple(fnct)].append(id)
            for fnct, id in k2.items():
                function_dict.setdefault(fncts[fnct[0]][4], [])
                function_dict[fncts[fnct[0]][4]].append((fncts[fnct[0]][4], object, id, map(lambda x: fncts[x][1], fnct)))
        result2 = []
        tmp = function_dict.keys()
        tmp.sort()
        for k in tmp:
            result2 += function_dict[k]
        return result2

    def _store_set_values(self, cr, uid, ids, fields, context):
        """Calls the fields.function's "implementation function" for all ``fields``, on records with ``ids`` (taking care of
           respecting ``multi`` attributes), and stores the resulting values in the database directly."""
        if not ids:
            return True
        field_flag = False
        field_dict = {}
        if self._log_access:
            cr.execute('select id,write_date from '+self._table+' where id IN %s', (tuple(ids),))  # not_a_user_entry
            res = cr.fetchall()
            for r in res:
                if r[1]:
                    field_dict.setdefault(r[0], [])
                    res_date = time.strptime((r[1])[:19], '%Y-%m-%d %H:%M:%S')
                    write_date = datetime.datetime.fromtimestamp(time.mktime(res_date))
                    for i in self.pool._store_function.get(self._name, []):
                        if i[5]:
                            up_write_date = write_date + datetime.timedelta(hours=i[5])
                            if datetime.datetime.now() < up_write_date:
                                if i[1] in fields:
                                    field_dict[r[0]].append(i[1])
                                    if not field_flag:
                                        field_flag = True
        todo = {}
        keys = []
        keys_append = keys.append
        for f in fields:
            key = self._columns[f]._multi
            if key not in keys:
                keys_append(key)
        todo = dict((k, []) for k in keys)
        for f in fields:
            key = self._columns[f]._multi
            todo[key].append(f)

        for key in keys:
            val = todo[key]
            if key:
                # uid == 1 for accessing objects having rules defined on store fields
                if hasattr(uid, 'realUid'):
                    context['computed_for_uid'] = uid.realUid
                else:
                    context['computed_for_uid'] = uid
                result = self._columns[val[0]].get(cr, self, ids, val, 1, context=context)
                try:
                    del context['computed_for_uid']
                except KeyError:
                    pass
                for id, value in result.items():
                    if field_flag:
                        for f in value.keys():
                            if f in field_dict[id]:
                                value.pop(f)
                    upd0 = []
                    upd1 = []
                    for v in value:
                        if v not in val:
                            continue
                        if self._columns[v]._type in ('many2one', 'one2one'):
                            try:
                                value[v] = value[v][0]
                            except:
                                pass
                        upd0.append('"'+v+'"='+self._columns[v]._symbol_set[0])
                        upd1.append(self._columns[v]._symbol_set[1](value[v]))
                    upd1.append(id)
                    if upd0 and upd1:
                        query = ''.join(('UPDATE "', self._table, '" SET ',
                                         ','.join(upd0), ' WHERE id = %s'))
                        cr.execute(query, upd1)

            else:
                id_param_dict = {}
                for f in val:
                    # uid == 1 for accessing objects having rules defined on store fields
                    result = self._columns[f].get(cr, self, ids, f, 1, context=context)
                    if field_flag:
                        for r in result.keys():
                            if r in field_dict.keys():
                                if f in field_dict[r]:
                                    result.pop(r)
                    if result:
                        current_value = '"%s"=%s' % (f, self._columns[f]._symbol_set[0])
                        column_type = self._columns[f]._type
                        for id, value in result.items():
                            if column_type in ('many2one', 'one2one'):
                                try:
                                    value = value[0]
                                except:
                                    pass
                            id_param_dict.setdefault(id, {})
                            param_list = id_param_dict[id].setdefault('param_list', [])
                            param_list.append((self._columns[f]._symbol_set[1](value)))
                            update_list = id_param_dict[id].setdefault('update_list', [])
                            update_list.append(current_value)

                # do only one update request per object
                for id, param_dict in id_param_dict.items():
                    current_query = ['UPDATE "%s" SET' % self._table]
                    current_query.append(', '.join(param_dict['update_list']))
                    current_query.append('WHERE id = %s')
                    param_dict['param_list'].append(id)
                    final_query = ' '.join(current_query)
                    cr.execute(final_query, tuple(param_dict['param_list']))
        return True

    #
    # TODO: Validate
    #
    def perm_write(self, cr, user, ids, fields, context=None):
        raise NotImplementedError(_('This method does not exist anymore'))

    # TODO: ameliorer avec NULL
    def _where_calc(self, cr, user, domain, active_test=True, context=None):
        """Computes the WHERE clause needed to implement an OpenERP domain.
        :param domain: the domain to compute
        :type domain: list
        :param active_test: whether the default filtering of records with ``active``
                            field set to ``False`` should be applied.
        :return: the query expressing the given domain as provided in domain
        :rtype: osv.query.Query
        """
        if context is None:
            context = {}
        domain = domain[:]
        # if the object has a field named 'active', filter out all inactive
        # records unless they were explicitely asked for
        if 'active' in self._columns and (active_test and context.get('active_test', True)):
            if domain:
                active_in_args = False
                for a in domain:
                    if a[0] == 'active':
                        active_in_args = True
                if not active_in_args:
                    domain.insert(0, ('active', '=', 1))
            else:
                domain = [('active', '=', 1)]

        if domain:
            import expression
            e = expression.expression(domain)
            e.parse(cr, user, self, context)
            tables = e.get_tables()
            where_clause, where_params = e.to_sql()
            where_clause = where_clause and [where_clause] or []
        else:
            where_clause, where_params, tables = [], [], ['"%s"' % self._table]

        return Query(tables, where_clause, where_params)

    def _check_qorder(self, word):
        if not regex_order.match(word):
            raise except_orm(_('AccessError'), _('Invalid "order" specified. A valid "order" specification is a comma-separated list of valid field names (optionally followed by asc/desc for the direction)'))
        return True

    def _apply_ir_rules(self, cr, uid, query, mode='read', context=None):
        """Add what's missing in ``query`` to implement all appropriate ir.rules
          (using the ``model_name``'s rules or the current model's rules if ``model_name`` is None)

           :param query: the current query object
        """
        def apply_rule(added_clause, added_params, added_tables, parent_model=None, child_object=None):
            if added_clause:
                if parent_model and child_object:
                    # as inherited rules are being applied, we need to add the missing JOIN
                    # to reach the parent table (if it was not JOINed yet in the query)
                    child_object._inherits_join_add(parent_model, query)
                query.where_clause += added_clause
                query.where_clause_params += added_params
                for table in added_tables:
                    if table not in query.tables:
                        query.tables.append(table)
                return True
            return False

        # apply main rules on the object
        rule_obj = self.pool.get('ir.rule')
        apply_rule(*rule_obj.domain_get(cr, uid, self._name, mode, context=context))

        # apply ir.rules from the parents (through _inherits)
        for inherited_model in self._inherits:
            kwargs = dict(parent_model=inherited_model, child_object=self) #workaround for python2.5
            apply_rule(*rule_obj.domain_get(cr, uid, inherited_model, mode, context=context), **kwargs)

    def _generate_m2o_order_by(self, order_field, query, subfield=False):
        """
        Add possibly missing JOIN to ``query`` and generate the ORDER BY clause for m2o fields,
        either native m2o fields or function/related fields that are stored, including
        intermediate JOINs for inheritance if required.

        :return: the qualified field name to use in an ORDER BY clause to sort by ``order_field``
        """
        if order_field not in self._columns and order_field in self._inherit_fields:
            # also add missing joins for reaching the table containing the m2o field
            qualified_field = self._inherits_join_calc(order_field, query)
            order_field_column = self._inherit_fields[order_field][2]
        else:
            qualified_field = '"%s"."%s"' % (self._table, order_field)
            order_field_column = self._columns[order_field]

        assert order_field_column._type == 'many2one', 'Invalid field passed to _generate_m2o_order_by()'
        if not order_field_column._classic_write and not getattr(order_field_column, 'store', False):
            logging.getLogger('orm.search').debug("Many2one function/related fields must be stored " \
                                                  "to be used as ordering fields! Ignoring sorting for %s.%s",
                                                  self._name, order_field)
            return

        # figure out the applicable order_by for the m2o
        dest_model = self.pool.get(order_field_column._obj)
        if subfield:
            src_table, src_field = qualified_field.replace('"','').split('.', 1)
            query.join((src_table, dest_model._table, src_field, 'id'), outer=True)
            m2o_order = subfield
            model = dest_model._table

            if subfield in dest_model._inherit_fields:
                src_table, src_field = dest_model._inherits_join_calc(subfield, query).replace('"','').split('.', 1)
                query.join((src_table, dest_model._table, src_field, 'id'), outer=True)
                model = src_table
            qualify = lambda field: '"%s"."%s"' % (model, field)
            return map(qualify, m2o_order) if isinstance(m2o_order, list) else qualify(m2o_order)
        elif order_field_column.m2o_order:
            m2o_order = order_field_column.m2o_order
        else:
            m2o_order = dest_model._order
        if not regex_order.match(m2o_order):
            # _order is complex, can't use it here, so we default to _rec_name
            m2o_order = dest_model._rec_name
        else:
            # extract the field names, to be able to qualify them and add desc/asc
            m2o_order_list = []
            for order_part in m2o_order.split(","):
                m2o_order_list.append(order_part.strip().split(" ",1)[0].strip())
            m2o_order = m2o_order_list
            if m2o_order == ['id']:
                # default order on m2o table is "id", not need to join table
                return qualified_field


        # Join the dest m2o table if it's not joined yet. We use [LEFT] OUTER join here
        # as we don't want to exclude results that have NULL values for the m2o
        src_table, src_field = qualified_field.replace('"','').split('.', 1)
        query.join((src_table, dest_model._table, src_field, 'id'), outer=True)
        qualify = lambda field: '"%s"."%s"' % (dest_model._table, field)
        return map(qualify, m2o_order) if isinstance(m2o_order, list) else qualify(m2o_order)


    def _generate_order_by(self, order_spec, query, context=None):
        """
        Attempt to consruct an appropriate ORDER BY clause based on order_spec, which must be
        a comma-separated list of valid field names, optionally followed by an ASC or DESC direction.

        :raise" except_orm in case order_spec is malformed
        """
        if context is None:
            context = {}
        order_by_clause = self._order

        if not order_spec:
            order_spec = self._order

        from_order_clause = []
        translation = 0
        if order_spec:
            order_by_elements = []
            order_by_elements_nodir = []
            self._check_qorder(order_spec)
            for order_part in order_spec.split(','):
                translatable = False
                order_split = order_part.strip().split(' ')
                order_field = order_split[0].strip()
                subfield = False
                if '.' in order_field:
                    order_field, subfield = order_field.split('.', 1)
                order_direction = order_split[1].strip() if len(order_split) == 2 else ''
                inner_clause = None
                end_inner_clause = []
                if order_field == 'id':
                    end_inner_clause = '"%s"."%s"' % (self._table, order_field)
                elif order_field in self._columns:
                    order_column = self._columns[order_field]
                    translatable = order_column.translate
                    trans_table = self._table
                    trans_obj_name = self._name
                    trans_classic_read = order_column._classic_read

                    if order_column._classic_read:
                        inner_clause = '"%s"."%s"' % (self._table, order_field)
                    elif order_column._type == 'many2one':
                        inner_clause = self._generate_m2o_order_by(order_field, query, subfield)
                        if subfield:
                            pool_sub_obj = self.pool.get(order_column._obj)
                            order_field = subfield

                            if pool_sub_obj._columns.get(subfield):
                                translatable =  pool_sub_obj._columns[subfield].translate
                                trans_classic_read = pool_sub_obj._columns[subfield]._classic_read
                                if translatable:
                                    trans_table = pool_sub_obj._columns[subfield]._table
                                    trans_obj_name = pool_sub_obj._name
                            elif pool_sub_obj._inherit_fields.get(subfield):
                                translatable =  pool_sub_obj._inherit_fields[subfield][2].translate
                                trans_classic_read = pool_sub_obj._inherit_fields[subfield][2]._classic_read
                                if translatable:
                                    trans_table = self.pool.get(pool_sub_obj._inherit_fields[subfield][0])._table
                                    trans_obj_name = pool_sub_obj._inherit_fields[subfield][0]
                    else:
                        continue # ignore non-readable or "non-joinable" fields

                    if translatable and trans_classic_read:
                        translation += 1
                        trans_name = '"ir_translation%s"' % translation
                        init_field = '"%s"."%s"' % (self._table, order_field)
                        order_by_elements.append('COALESCE(%s."value", %s) %s' % (trans_name, init_field, order_direction))
                        if query.having:
                            order_by_elements_nodir.append('COALESCE(%s."value", %s)' % (trans_name, init_field))
                        left_join_clause = 'LEFT JOIN "ir_translation" %s' % trans_name
                        on_clause = 'ON %s.res_id = "%s".id AND %s.name = \'%s,%s\' AND %s.type = \'model\' AND %s.lang = \'%s\'' % (
                            trans_name, trans_table, trans_name, trans_obj_name, order_field, trans_name, trans_name, context.get('lang', 'en_US'))
                        from_order_clause.append('%s %s' % (left_join_clause, on_clause))

                elif order_field in self._inherit_fields:
                    parent_obj = self.pool.get(self._inherit_fields[order_field][3])
                    order_column = parent_obj._columns[order_field]
                    translatable = order_column.translate
                    if translatable and order_column._classic_read:
                        translation += 1
                        trans_name = '"ir_translation%s"' % translation

                        init_field = self._inherits_join_calc(order_field, query)
                        order_by_elements.append('COALESCE(%s."value", %s) %s' % (trans_name, init_field, order_direction))
                        if query.having:
                            order_by_elements_nodir.append('COALESCE(%s."value", %s)' % (trans_name, init_field))
                        left_join_clause = 'LEFT JOIN "ir_translation" %s' % trans_name
                        on_clause = 'ON %s.res_id = "%s".id AND %s.name = \'%s,%s\' AND %s.type = \'model\' AND %s.lang = \'%s\'' % (
                            trans_name, parent_obj._table, trans_name, parent_obj._name, order_field, trans_name, trans_name, context.get('lang', 'en_US'))
                        from_order_clause.append('%s %s' % (left_join_clause, on_clause))
                    elif order_column._classic_read:
                        inner_clause = self._inherits_join_calc(order_field, query)
                    elif order_column._type == 'many2one':
                        inner_clause = self._generate_m2o_order_by(order_field, query)
                    else:
                        continue # ignore non-readable or "non-joinable" fields

                if isinstance(inner_clause, list):
                    end_inner_clause.extend(inner_clause)
                elif inner_clause:
                    end_inner_clause.append(inner_clause)
                if end_inner_clause:
                    if isinstance(end_inner_clause, list):
                        for clause in end_inner_clause:
                            order_by_elements.append("%s %s" % (clause, order_direction))
                            if query.having:
                                order_by_elements_nodir.append(clause)
                    else:
                        order_by_elements.append("%s %s" % (end_inner_clause, order_direction))
                        if query.having:
                            order_by_elements_nodir.append(end_inner_clause)
            if order_by_elements:
                order_by_clause = ",".join(order_by_elements)

        if order_by_elements_nodir:
            query.having_group_by = '%s, %s' % (query.having_group_by, ','.join(order_by_elements_nodir))

        return order_by_clause and (' ORDER BY %s ' % order_by_clause) or '', from_order_clause

    def _search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False, access_rights_uid=None):
        """
        Private implementation of search() method, allowing specifying the uid to use for the access right check.
        This is useful for example when filling in the selection list for a drop-down and avoiding access rights errors,
        by specifying ``access_rights_uid=1`` to bypass access rights check, but not ir.rules!
        This is ok at the security level because this method is private and not callable through XML-RPC.

        :param access_rights_uid: optional user ID to use when checking access rights
                                  (not for ir.rules, this is only for ir.model.access)
        """
        if context is None:
            context = {}
        self.pool.get('ir.model.access').check(cr, access_rights_uid or user, self._name, 'read', context=context)

        query = self._where_calc(cr, user, args, context=context)
        self._apply_ir_rules(cr, user, query, 'read', context=context)
        if order == 'NO_ORDER' or count:
            order_by=''
            from_order_clause = []
        else:
            order_by, from_order_clause = self._generate_order_by(order, query,
                                                                  context=context)

        from_clause, where_clause, where_clause_params = query.get_sql()
        from_clause = from_clause + ' '.join(from_order_clause)

        limit_str = limit and ' LIMIT %d' % limit or ''
        offset_str = offset and ' OFFSET %d' % offset or ''
        where_str = where_clause and (" WHERE %s" % where_clause) or ''

        if count:
            if not query.having:
                count_query = ''.join(('SELECT COUNT("%s".id) FROM ' % self._table,
                                       from_clause, where_str, limit_str, offset_str))
                cr.execute(count_query, where_clause_params)
                res = cr.fetchall()
                return res[0][0]
            else:
                count_query = ''.join(('SELECT "%s".id FROM ' % self._table,
                                       from_clause, where_str, query.having_group_by, query.having, limit_str, offset_str))
                cr.execute(count_query, where_clause_params)
                return cr.rowcount

        select_query = ''.join(('SELECT "%s".id FROM ' % self._table,
                                from_clause, where_str, query.having_group_by, query.having, order_by,limit_str, offset_str))
        cr.execute(select_query, where_clause_params)
        res = cr.fetchall()
        return [x[0] for x in res]

    # returns the different values ever entered for one field
    # this is used, for example, in the client when the user hits enter on
    # a char field
    def distinct_field_get(self, cr, uid, field, value, args=None, offset=0, limit=None):
        if not args:
            args = []
        if field in self._inherit_fields:
            return self.pool.get(self._inherit_fields[field][0]).distinct_field_get(cr, uid, field, value, args, offset, limit)
        else:
            return self._columns[field].search(cr, self, args, field, value, offset, limit, uid)

    def copy_data(self, cr, uid, id, default=None, context=None):
        """
        Copy given record's data with all its fields values

        :param cr: database cursor
        :param user: current user id
        :param id: id of the record to copy
        :param default: field values to override in the original values of the copied record
        :type default: dictionary
        :param context: context arguments, like lang, time zone
        :type context: dictionary
        :return: dictionary containing all the field values
        """

        if context is None:
            context = {}

        # avoid recursion through already copied records in case of circular relationship
        seen_map = context.setdefault('__copy_data_seen',{})
        if id in seen_map.setdefault(self._name,[]):
            return
        seen_map[self._name].append(id)

        if default is None:
            default = {}
        if 'state' not in default:
            if 'state' in self._defaults:
                if callable(self._defaults['state']):
                    default['state'] = self._defaults['state'](self, cr, uid, context)
                else:
                    default['state'] = self._defaults['state']

        context_wo_lang = context.copy()
        if 'lang' in context:
            del context_wo_lang['lang']

        fields = self.fields_get(cr, uid, context=context)
        to_read = []
        for f in fields:
            if 'function' not in fields[f]:
                to_read.append(f)
        data = self.read(cr, uid, [id,], to_read, context=context_wo_lang)
        if data:
            data = data[0]
        else:
            raise IndexError( _("Record #%d of %s not found, cannot copy!") %( id, self._name))

        for f in fields:
            ftype = fields[f]['type']

            if self._log_access and f in ('create_date', 'create_uid', 'write_date', 'write_uid'):
                del data[f]

            if f in default:
                data[f] = default[f]
            elif 'function' in fields[f]:
                if f in data:
                    del data[f]
            elif ftype == 'many2one':
                try:
                    data[f] = data[f] and data[f][0]
                except:
                    pass
            elif ftype in ('one2many', 'one2one'):
                res = []
                rel = self.pool.get(fields[f]['relation'])
                if data[f]:
                    # duplicate following the order of the ids
                    # because we'll rely on it later for copying
                    # translations in copy_translation()!
                    data[f].sort()
                    for rel_id in data[f]:
                        # the lines are first duplicated using the wrong (old)
                        # parent but then are reassigned to the correct one thanks
                        # to the (0, 0, ...)
                        d = rel.copy_data(cr, uid, rel_id, context=context)
                        if d:
                            res.append((0, 0, d))
                data[f] = res
            elif ftype == 'many2many':
                data[f] = [(6, 0, data[f])]

        del data['id']

        # make sure we don't break the current parent_store structure and
        # force a clean recompute!
        for parent_column in ['parent_left', 'parent_right']:
            data.pop(parent_column, None)

        # remove _inherits field's from data recursively, missing parents will
        # be created by create() (so that copy() copy everything).
        def remove_ids(inherits_dict):
            for parent_table in inherits_dict:
                del data[inherits_dict[parent_table]]
                remove_ids(self.pool.get(parent_table)._inherits)
        remove_ids(self._inherits)
        return data

    def copy_translations(self, cr, uid, old_id, new_id, context=None):
        if context is None:
            context = {}

        # avoid recursion through already copied records in case of circular relationship
        seen_map = context.setdefault('__copy_translations_seen',{})
        if old_id in seen_map.setdefault(self._name,[]):
            return
        seen_map[self._name].append(old_id)

        trans_obj = self.pool.get('ir.translation')
        fields = self.fields_get(cr, uid, context=context)

        translation_records = []
        for field_name, field_def in fields.items():
            # we must recursively copy the translations for o2o and o2m
            if field_def['type'] in ('one2one', 'one2many'):
                target_obj = self.pool.get(field_def['relation'])
                old_record, new_record = self.read(cr, uid, [old_id, new_id], [field_name], context=context)
                # here we rely on the order of the ids to match the translations
                # as foreseen in copy_data()
                old_children = sorted(old_record[field_name])
                new_children = sorted(new_record[field_name])
                for (old_child, new_child) in zip(old_children, new_children):
                    target_obj.copy_translations(cr, uid, old_child, new_child, context=context)
            # and for translatable fields we keep them for copy
            elif field_def.get('translate'):
                trans_name = ''
                if field_name in self._columns:
                    trans_name = self._name + "," + field_name
                elif field_name in self._inherit_fields:
                    trans_name = self._inherit_fields[field_name][0] + "," + field_name
                if trans_name:
                    trans_ids = trans_obj.search(cr, uid, [
                        ('name', '=', trans_name),
                        ('res_id', '=', old_id)
                    ], order='NO_ORDER')
                    translation_records.extend(trans_obj.read(cr, uid, trans_ids, context=context))

        for record in translation_records:
            del record['id']
            del record['xml_id']
            record['res_id'] = new_id
            trans_obj.create(cr, uid, record, context=context)


    def copy_web(self, cr, uid, id, default=None, context=None):
        return self.copy(cr, uid, id, default, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        """
        Duplicate record with given id updating it with default values

        :param cr: database cursor
        :param uid: current user id
        :param id: id of the record to copy
        :param default: dictionary of field values to override in the original values of the copied record, e.g: ``{'field_name': overriden_value, ...}``
        :type default: dictionary
        :param context: context arguments, like lang, time zone
        :type context: dictionary
        :return: True

        """
        if context is None:
            context = {}
        context = context.copy()
        data = self.copy_data(cr, uid, id, default, context)
        new_id = self.create(cr, uid, data, context)
        self.copy_translations(cr, uid, id, new_id, context)
        return new_id

    def exists(self, cr, uid, ids, context=None):
        if type(ids) in (int, long):
            ids = [ids]
        query = 'SELECT count(1) FROM "%s"' % (self._table)
        cr.execute(query + "WHERE ID IN %s", (tuple(ids),))  # not_a_user_entry
        return cr.fetchone()[0] == len(ids)

    def check_recursion(self, cr, uid, ids, context=None, parent=None):
        warnings.warn("You are using deprecated %s.check_recursion(). Please use the '_check_recursion()' instead!" % \
                      self._name, DeprecationWarning, stacklevel=3)
        assert parent is None or parent in self._columns or parent in self._inherit_fields,\
            "The 'parent' parameter passed to check_recursion() must be None or a valid field name"
        return self._check_recursion(cr, uid, ids, context, parent)

    def _check_recursion(self, cr, uid, ids, context=None, parent=None):
        """
        Verifies that there is no loop in a hierarchical structure of records,
        by following the parent relationship using the **parent** field until a loop
        is detected or until a top-level record is found.

        :param cr: database cursor
        :param uid: current user id
        :param ids: list of ids of records to check
        :param parent: optional parent field name (default: ``self._parent_name = parent_id``)
        :return: **True** if the operation can proceed safely, or **False** if an infinite loop is detected.
        """

        if not parent:
            parent = self._parent_name
        ids_parent = ids[:]
        query = 'SELECT distinct "%s" FROM "%s" WHERE id IN %%s' % (parent, self._table)  # not_a_user_entry
        while ids_parent:
            ids_parent2 = []
            for i in range(0, len(ids), cr.IN_MAX):
                sub_ids_parent = ids_parent[i:i+cr.IN_MAX]
                cr.execute(query, (tuple(sub_ids_parent),))
                ids_parent2.extend(filter(None, map(lambda x: x[0], cr.fetchall())))
            ids_parent = ids_parent2
            for i in ids_parent:
                if i in ids:
                    return False
        return True

    def _get_xml_ids(self, cr, uid, ids, *args, **kwargs):
        """Find out the XML ID(s) of any database record.

        **Synopsis**: ``_get_xml_ids(cr, uid, ids) -> { 'id': ['module.xml_id'] }``

        :return: map of ids to the list of their fully qualified XML IDs
                 (empty list when there's none).
        """
        model_data_obj = self.pool.get('ir.model.data')
        data_ids = model_data_obj.search(cr, uid, [('model', '=', self._name), ('res_id', 'in', ids)])
        data_results = model_data_obj.read(cr, uid, data_ids, ['module', 'name', 'res_id'])
        result = {}
        for id in ids:
            # can't use dict.fromkeys() as the list would be shared!
            result[id] = []
        for record in data_results:
            if record['module'] == 'sd':
                result[record['res_id']].insert(0, '%(module)s.%(name)s' % record)
            else:
                result[record['res_id']].append('%(module)s.%(name)s' % record)
        return result

    def get_xml_id(self, cr, uid, ids, *args, **kwargs):
        """Find out the XML ID of any database record, if there
        is one. This method works as a possible implementation
        for a function field, to be able to add it to any
        model object easily, referencing it as ``osv.osv.get_xml_id``.

        When multiple XML IDs exist for a record, only one
        of them is returned (randomly).

        **Synopsis**: ``get_xml_id(cr, uid, ids) -> { 'id': 'module.xml_id' }``

        :return: map of ids to their fully qualified XML ID,
                 defaulting to an empty string when there's none
                 (to be usable as a function field).
        """
        results = self._get_xml_ids(cr, uid, ids)
        for k, v in results.items():
            if results[k]:
                results[k] = v[0]
            else:
                results[k] = ''
        return results

    def is_linked(self, cr, uid, ids):
        if not ids:
            return False

        if isinstance(ids, (int, long)):
            ids = [ids]

        # get fk constaint names that point to self._table
        cr.execute("""
            SELECT ccu.constraint_name
            FROM information_schema.constraint_column_usage ccu
            WHERE ccu.table_name = %s AND ccu.table_catalog = %s""", (self._table, cr.dbname))
        constraints = cr.fetchall()

        # get table and column names
        cr.execute("""
            SELECT kcu.column_name, kcu.table_name
            FROM information_schema.key_column_usage kcu
            WHERE kcu.table_catalog = %s AND kcu.constraint_name IN %s""", (cr.dbname, tuple([x[0] for x in constraints])))
        for column, table in cr.fetchall():
            if table == self._table:
                continue
            cr.execute("""SELECT count(id) FROM %s WHERE %s IN %%s""" % (table, column), (tuple(ids),))  # not_a_user_entry
            res = cr.fetchall()
            if res[0][0]:
                return True

        return False

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

