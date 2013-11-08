from osv import osv, fields, orm
from osv.orm import browse_record, browse_record_list
import tools
from tools.safe_eval import safe_eval as eval
import logging
import functools
import types

from sync_common import MODELS_TO_IGNORE, xmlid_to_sdref


## Helpers ###################################################################

class DuplicateKey(KeyError):
    message_template = "Key \"%s\" already exist: \"%s\" -> \"%s\""
    message = ""
    key = None
    value = None

    def __init__(self, ddict, key, value):
        self.message = message_template % (key, ddict[key], value)
        self.key = key
        self.value = value

class RejectingDict(dict):
    def __setitem__(self, k, v):
        if k in self.keys():
            raise DuplicateKey(self, k, v)
        else:
            return super(RejectingDict, self).__setitem__(k, v)



class extended_orm(osv.osv):
    """Extend orm methods"""
    _auto = False
    _name = 'sync.client.orm_extended'
    _description = "Flag that certify presence of extended ORM methods"

extended_orm()



def orm_method_overload(fn):
    """
    Wrapper method to override orm.orm classic methods
    """
    original_method = getattr(orm.orm, fn.func_name)
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        if self.pool.get(extended_orm._name) is not None:
            return fn(self, original_method, *args, **kwargs)
        else:
            return original_method(self, *args, **kwargs)
    return wrapper

class extended_orm_methods:

    def get_model_ids(self, cr, uid, context=None):
        """
        Return a list of ir.model ids that match the current model (include inheritance)
        """
        def recur_get_model(model, res):
            ids = self.pool.get('ir.model').search(cr, uid, [('model','=',model._name)])
            res.extend(ids)
            for parent in model._inherits.keys():
                recur_get_model(self.pool.get(parent), res)
            return res
        return recur_get_model(self, [])

    def need_to_push(self, cr, uid, ids, touched_fields=None, context=None):
        """
        Check if records need to be pushed to the next synchronization process
        or not.

        One of those conditions needs to match: 
            - sync_date < last_modification
            - sync_date is not set

        Plus, the result can be filtered to records that have changes in the
        fields given in touched_fields parameter.

        Note: sync_date field can be changed to other field using parameter
        sync_field

        Return type:
            - If a list of ids is given, it returns a list of filtered ids.
            - If an id is given, it returns the id itself or False it the
              record doesn't need to be pushed.

        :param cr: database cursor
        :param uid: current user id
        :param ids: id or list of the ids of the records to read
        :param touched_fields: reduce result to records that have fields
                               touched in touched_fields list.
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :return: list of ids that need to be pushed (or False for per record call)

        """
        result_iterable = hasattr(ids, '__iter__')
        if not result_iterable: ids = [ids]
        ids = filter(None, ids)
        if not ids: return ids if result_iterable else False
        if touched_fields is None:
            cr.execute("""\
SELECT res_id
    FROM ir_model_data
    WHERE module = 'sd' AND
          model = %s AND
          res_id IN %s AND
          (sync_date < last_modification OR sync_date IS NULL)""",
[self._name, tuple(ids)])
            result = [row[0] for row in cr.fetchall()]
        else:
            touched_fields = set(touched_fields)
            cr.execute("""\
SELECT res_id, touched
    FROM ir_model_data
    WHERE module = 'sd' AND
          model = %s AND
          res_id IN %s AND
          (sync_date < last_modification OR sync_date IS NULL)""",
[self._name, tuple(ids)])
            result = [row[0] for row in cr.fetchall()
                      if row[1] is None \
                          or touched_fields.intersection(eval(row[1]) if row[1] else [])]
        return result if result_iterable else len(result) > 0

    def get_sd_ref(self, cr, uid, ids, field='name', context=None):
        """
        Create or get the SD reference (replacement for link_with_ir_method).

        :param cr: database cursor
        :param uid: current user id
        :param ids: id or list of the ids of the records to read
        :param field: field to retrieve (normally 'name' by default)
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :return: dictionary with SD references

        """
        assert self._name != "ir.model.data", \
            "Cannot create xmlids on an ir.model.data object!"

        def get_fields(record):
            if hasattr(field, '__iter__'):
                return tuple(getattr(record, f, False) for f in field)
            else:
                return getattr(record, field, False)

        result_iterable = hasattr(ids, '__iter__')
        if not result_iterable: ids = [ids]
        if not ids: return {} if result_iterable else False

        model_data_obj = self.pool.get('ir.model.data')
        sdref_ids = model_data_obj.search(cr, uid, [('model','=',self._name),('res_id','in',ids),('module','=','sd')])
        try:
            result = RejectingDict((data.res_id, get_fields(data))
                for data in model_data_obj.browse(cr, uid, sdref_ids))
        except DuplicateKey, e:
            raise Exception("Duplicate definition of 'sd' xml_id: %d@ir.model.data" % e.key)
        missing_ids = filter(lambda id:id and not id in result, ids)
        if missing_ids:
            xmlids = dict(
                (data.res_id, "%(module)s_%(name)s" % data)
                for data in model_data_obj.browse(cr, uid,
                    model_data_obj.search(cr, uid,
                        [('model','=',self._name),('res_id','in',missing_ids),
                         '!',('module','in',['sd','__export__']),
                         '!','&',('module','=','base'),('name','=like','main_%')])))
            now = fields.datetime.now()
            identifier = self.pool.get('sync.client.entity')._get_entity(cr).identifier
            for res_id in missing_ids:
                name = xmlids.get(res_id, self.get_unique_xml_name(cr, uid, identifier, self._table, res_id))
                new_data_id = model_data_obj.create(cr, uid, {
                    'noupdate' : False, # don't set to True otherwise import won't work
                    'module' : 'sd',
                    'last_modification' : now,
                    'model' : self._name,
                    'res_id' : res_id,
                    'version' : 1,
                    'name' : name,
                }, context=context)
                result[res_id] = get_fields(model_data_obj.browse(cr, uid, new_data_id, context=context))
        return result if result_iterable else result[ids[0]]

    def version(self, cr, uid, ids, context=None):
        """
        Get the record version

        :param cr: database cursor
        :param uid: current user id
        :param ids: id or list of the ids of the records to read
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :return: dictionary with version per id

        """
        return self.get_sd_ref(cr, uid, ids, field='version', context=context)

    def get_touched_fields(self, cr, uid, ids, context=None):
        """
        For each id, get a list of fields that has been touch since the last
        synchronization

        :param cr: database cursor
        :param uid: current user id
        :param ids: id or list of the ids of the records to read
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :return: dictionary with list of touched fields per id

        """
        return dict(
            (id, (eval(touched) if touched else []))
            for id, touched_fields
            in self.get_sd_ref(cr, uid, ids, field='touched', context=context).items())

    def touch(self, cr, uid, ids, previous_values, synchronize,
            _previous_calls=None, context=None):
        """
        Touch the fields that has changed and/or mark the records to be
        synchronized. If previous_values is None, touch all the fields of every
        record. If synchronize is False, it doesn't mark the field has touched
        or mark the records for synchronize neither but call the 'on_change'
        method on the object if it exists.

        :param cr: database cursor
        :param uid: current user id
        :param ids: id or list of the ids of the records to read
        :param previous_values: dict or list of dict containing the result of a
                                read() call with ids given *before* the change
        :param synchronize: do we want to write the touched fields and update
                            last_modification date in ir.model.data
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :return:
        {
            id : {
                'field' : (previous_value, next_value),
                ...
            },
            ...
        }
        """
        assert not self._name == 'ir.model.data', \
            "Can not call this method on object ir.model.data!"
        assert hasattr(self, '_all_columns'), \
            "You are running an old version of OpenERP server. " \
            "Please update the server to the latest version."
        assert synchronize or previous_values is not None, \
            "This call is useless"

        _previous_calls = _previous_calls or []
        me = (self._name, ids)
        if me not in _previous_calls:
            _previous_calls.append(me)
        else:
            return {}

        result_iterable = hasattr(ids, '__iter__')
        if not result_iterable:
            ids = [ids]
            if previous_values is not None:
                previous_values = [previous_values]
        if not ids: return {}

        data = self.pool.get('ir.model.data')
        if isinstance(synchronize, dict):
            data_base_values = synchronize
        elif synchronize:
            data_base_values = {
                'last_modification' : fields.datetime.now(),
            }

        def touch(data_ids, touched_fields):
            if synchronize:
                data.write(cr, uid, data_ids, 
                    dict(data_base_values, touched=str(sorted(touched_fields))),
                    context=context)

        def filter_o2m(field_list):
            return [(f, self._all_columns[f].column)
                    for f in field_list
                    if isinstance(self._all_columns[f].column, fields.one2many)]

        # read current values
        whole_fields = self._all_columns.keys() \
            if previous_values is None \
            else previous_values[0].keys()
        try:
            whole_fields.remove('id')
        except ValueError:
            pass
        current_values = dict(
            (d['id'], d)
            for d in self.read(cr, uid, ids, whole_fields, context=context) )

        # touch things
        if previous_values is None:
            touch(
                self.get_sd_ref(cr, uid, ids, field='id',
                    context=context).values(),
                whole_fields)
            # handle one2many
            o2m_fields = filter_o2m(whole_fields)
            # handle one2many (because orm don't call write() on them)
            for field, column in o2m_fields:
                for next_rec in current_values.values():
                    if column._obj == self._name: continue
                    self.pool.get(column._obj).touch(
                        cr, uid, next_rec[field],
                        None, data_base_values,
                        _previous_calls=_previous_calls,
                        context=context)
        else:
            # convert previous_values to a mapping id -> dict_of_values
            previous_values = dict((d['id'], d) for d in previous_values)
            # check that the previous_values provided is correct
            assert set(ids) == set(previous_values.keys()), \
                "Missing previous values: %s got, %s expected" \
                % (previous_values.keys(), ids)
            for res_id, (data_id, touched) in self.get_sd_ref(cr, uid, ids, \
                    field=['id','touched'], context=context).items():
                prev_rec, next_rec = \
                    previous_values[res_id], current_values[res_id]
                modified = set(filter(
                    lambda field: next_rec[field] != prev_rec[field],
                    whole_fields))
                if modified:
                    touch([data_id], list(
                        modified.union(eval(touched) if touched else [])
                    ))
                # handle one2many (because orm don't call write() on them)
                for field, column in filter_o2m(whole_fields):
                    self.pool.get(column._obj).touch(
                        cr, uid, list(set(prev_rec[field] + next_rec[field])),
                        None, data_base_values,
                        _previous_calls=_previous_calls,
                        context=context)

        # store changes in the context
        if context is not None:
            if 'changes' not in context: context['changes'] = {}
            changes = context['changes'].setdefault(self._name, {})
        else:
            changes = {}
        if previous_values is not None:
            for res_id in ids:
                if res_id not in changes:
                    changes[res_id] = dict(
                        (field, (previous_values[res_id][field],
                                 current_values[res_id][field]))
                        for field in whole_fields
                        if not previous_values[res_id][field] == \
                            current_values[res_id][field] )
                else:
                    for field in whole_fields:
                        if previous_values[res_id][field] == \
                             current_values[res_id][field]:
                            continue
                        if field in changes[res_id]:
                            changes[res_id][field] = \
                                (changes[res_id][field][0],
                                 current_values[res_id][field])
                        else:
                            changes[res_id][field] = \
                                (previous_values[res_id][field],
                                 current_values[res_id][field])

        return changes

    def synchronize(self, cr, uid, ids, context=None):
        """
        Update the SD ref (or create one if it does'n exists) and mark it to be
        synchronize and mark all fields as touched.

        Doesn't returns anything interesting
        """
        self.touch(cr, uid, ids, None, True, context=context)
        return True

    def clear_synchronization(self, cr, uid, ids, context=None):
        data_ids = self.get_sd_ref(cr, uid, ids, field='id', context=context)
        return self.pool.get('ir.model.data').write(cr, uid, data_ids.values(),
            {'force_recreation':False,'touched':False}, context=context)

    def find_sd_ref(self, cr, uid, sdrefs, field=None, context=None):
        """
        Find the ids of records based on their SD reference. If called on a
        model, search SD refs for this model only. Otherwise, search any
        record.

        :param cr: database cursor
        :param uid: current user id
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :return: dictionary with requested references
        
        """
        result_iterable = hasattr(sdrefs, '__iter__')
        if not result_iterable: sdrefs = (sdrefs,)
        elif not isinstance(sdrefs, tuple): sdrefs = tuple(sdrefs)
        sdrefs = filter(None, sdrefs)
        if not sdrefs: return {} if result_iterable else False
        if field is None:
            field = 'id' if self._name == 'ir.model.data' else 'res_id'
        field, real_field = ('id' if field == 'is_deleted' else field), field
        if self._name == "ir.model.data":
            cr.execute("""\
SELECT name, %s FROM ir_model_data WHERE module = 'sd' AND name IN %%s""" % field, [sdrefs])
        else:
            cr.execute("""\
SELECT name, %s FROM ir_model_data WHERE module = 'sd' AND model = %%s AND name IN %%s""" \
% field, [self._name,sdrefs])
        try:
            result = RejectingDict(cr.fetchall())
        except DuplicateKey, e:
            # Should never happen if called on other object than ir.model.data
            raise Exception("Duplicate definition of 'sd' xml_id: %d@ir.model.data" % e.key)
        if field != real_field:
            read_result = self.pool.get('ir.model.data').read(cr, uid, result.values(), [real_field], context=context)
            read_result = dict((x['id'], x) for x in read_result)
            result = dict((sdref, read_result[id][real_field]) for sdref, id in result.items())
        return result if result_iterable else result.get(sdrefs[0], False)

    @orm_method_overload
    def create(self, original_create, cr, uid, values, context=None):
        if context is None: context = {}
        if 'changes' not in context: context['changes'] = {}
        id = original_create(self, cr, uid, values, context=context)
        to_be_synchronized = (
            self._name not in MODELS_TO_IGNORE and
            (not context.get('sync_update_execution') and
             not context.get('sync_update_creation')))
        if to_be_synchronized or hasattr(self, 'on_create'):
            self.touch(cr, uid, [id], None,
                to_be_synchronized, context=context)
            if hasattr(self, 'on_create'):
                self.on_create(cr, uid, id,
                    self.read(cr, uid, [id], values.keys(), context=context)[0],
                    context=context)
        return id

    @orm_method_overload
    def write(self, original_write, cr, uid, ids, values, context=None):
        if context is None: context = {}
        if 'changes' not in context: context['changes'] = {}
        previous_values = self.read(cr, uid, ids, values.keys(), context=context)
        result = original_write(self, cr, uid, ids, values,context=context)
        to_be_synchronized = (
            self._name not in MODELS_TO_IGNORE and
            (not context.get('sync_update_execution') and
             not context.get('sync_update_creation')))
        if to_be_synchronized or hasattr(self, 'on_change'):
            changes = self.touch(cr, uid, ids, previous_values,
                to_be_synchronized, context=context)
            if hasattr(self, 'on_change'):
                self.on_change(cr, uid, changes, context=context)
        return result

    def message_unlink(self, cr, uid, source, unlink_info, context=None):
        model_name = unlink_info.model
        xml_id =  unlink_info.xml_id
        if model_name != self._name:
            return "Model not consistant"

        res_id = self.find_sd_ref(cr, uid, xmlid_to_sdref(xml_id), context=context)
        if not res_id:
            return "Object %s %s does not exist in destination" % (model_name, xml_id)

        return self.unlink(cr, uid, [res_id], context=context)

    def generate_message_for_destination(self, cr, uid, destination_name, sdref, instance_name, send_to_parent_instances):
        instance_obj = self.pool.get('msf.instance')

        if not destination_name:
            return
        if destination_name != instance_name:
            message_data = {
                    'identifier' : 'delete_%s_to_%s' % (sdref, destination_name),
                    'sent' : False,
                    'generate_message' : True,
                    'remote_call': self._name + ".message_unlink",
                    'arguments': "[{'model' :  '%s', 'xml_id' : '%s'}]" % (self._name, sdref),
                    'destination_name': destination_name
            }
            self.pool.get("sync.client.message_to_send").create(cr, uid, message_data)

        if destination_name != instance_name or send_to_parent_instances:
            # generate message for parent instance
            instance_ids = instance_obj.search(cr, uid, [("instance", "=", destination_name)])
            if instance_ids:
                instance_record = instance_obj.browse(cr, uid, instance_ids[0])
                parent = instance_record.parent_id and instance_record.parent_id.instance or False
                if parent:
                    self.generate_message_for_destination(cr, uid, parent, sdref, instance_name, send_to_parent_instances)

    @orm_method_overload
    def unlink(self, original_unlink, cr, uid, ids, context=None):
        if not ids: return True
        context = context or {}

        if context.get('sync_message_execution'):
            return original_unlink(self, cr, uid, ids, context=context)

        if self._name == 'ir.model.data' \
           and context.get('avoid_sdref_deletion'):
            return original_unlink(self, cr, uid,
                [rec.id for rec
                    in self.browse(cr, uid, (ids if hasattr(ids, '__iter__') else [ids]), context=context)
                   if not rec.module == 'sd'],
                context=context)

        # In an update creation context, references are deleted normally
        # In an update execution context, references are kept, but no
        # synchronization is made.
        # Otherwise, references are kept and synchronization is triggered
        # ...see?
        if self._name not in MODELS_TO_IGNORE \
           and not context.get('sync_update_creation'):
            context = dict(context, avoid_sdref_deletion=True)
            to_be_synchronized = not context.get('sync_update_execution')
            self.touch(cr, uid, ids, None,
                to_be_synchronized, context=context)
            if hasattr(self, 'on_delete'):
                self.on_delete(cr, uid, ids, context=context)

        return original_unlink(self, cr, uid, ids, context=context)

    def purge(self, cr, uid, ids, context=None):
        """
        Just like unlink but remove the xmlid references also

        :param cr: database cursor
        :param uid: current user id
        :param ids: id or list of the ids of the records to read
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :return: id or list of ids of records matching the criteria and are deleted
        :raise AccessError: * if user tries to bypass access rules for read on the requested object.

        """
        if not ids: return True
        if not hasattr(ids, '__iter__'): ids = (ids,)
        elif not isinstance(ids, tuple): ids = tuple(ids)
        ids = filter(None, ids)
        if not ids: return True
        already_deleted = self.search_deleted(cr, uid, [('res_id','in',ids)], context=context)
        to_delete = list(set(ids) - set(already_deleted))
        self.unlink(cr, uid, to_delete, context=context)
        cr.execute("""\
DELETE FROM ir_model_data WHERE model = %s AND res_id IN %s
""", [self._name, ids])
        return True

    def search_deleted(self, cr, user, args=[], context=None):
        """
        Search for deleted entries in the table. It search for xmlids that are linked to not existing records. Beware that the domain applies to the ir.model.data

        :param cr: database cursor
        :param user: current user id
        :param args: list of tuples specifying the search domain [('field_name', 'operator', value), ...]. Pass an empty list to match all records.
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :return: id or list of ids of records matching the criteria and are deleted
        :raise AccessError: * if user tries to bypass access rules for read on the requested object.

        """
        ir_data = self.pool.get('ir.model.data')
        data_ids = ir_data.search(cr, user,
            args + [('model','=',self._name)], context=context)
        return list(set(data['res_id'] for data in ir_data.read(cr, user, data_ids, ['id','res_id','is_deleted'], context=context) if data['is_deleted']))

    def search_ext(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        """
        Make a search on the model with an extended domain (replacement to eval_poc_domain)

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

        """
        real_args = []
        for item in args:
            if isinstance(item, (tuple, list)):
                if len(item) != 3:
                    raise Exception("Malformed extended domain: %s" % tools.ustr(args))
                if isinstance(item[2], (tuple, list)) \
                   and len(item[2]) == 3 \
                   and isinstance(item[2][0], basestring) \
                   and isinstance(item[2][1], basestring) \
                   and isinstance(item[2][2], (tuple, list)):
                    model = item[2][0]
                    sub_domain = item[2][2]
                    field = item[2][1]
                    sub_obj = self.pool.get(model)
                    ids_list = sub_obj.search_ext(cr, user, sub_domain, context=context)
                    if ids_list:
                        new_ids = []
                        for data in sub_obj.read(cr, user, ids_list, [field], context=context):
                            if isinstance(data[field], (tuple, list)) \
                               and len(data[field]) == 2 \
                               and isinstance(data[field][0], (int, long)) \
                               and isinstance(data[field][1], basestring):
                                new_ids.append(data[field][0])
                            else:
                                new_ids.append(data[field])
                        ids_list = new_ids
                    real_args.append((item[0], item[1], ids_list))
                else:
                    real_args.append(item)
            else:
                real_args.append(item)

        return self.search(cr, user, real_args, offset=offset, limit=limit, context=context, count=count)

    def get_destination_name(self, cr, uid, ids, dest_field, context=None):
        """
            @param ids : ids of the record from which we need to find the destination
            @param dest_field : field of the record from where the name will be extract
            @return a dictionnary with ids : dest_fields
        """
        ids = ids if isinstance(ids, (tuple, list)) else [ids]
        result = dict.fromkeys(ids, False)

        if not dest_field:
            return result

        field = self.fields_get(cr, uid, context=context).get(dest_field)

        if field['type'] == 'many2one' and not field['relation'] == 'msf.instance':
            for rec in self.read(cr, uid, ids, [dest_field], context):
                if rec[dest_field]: result[rec['id']] = rec[dest_field][1]

        else:
            for rec in self.browse(cr, uid, ids, context=context):
                value = rec[dest_field]
                if value is False:
                    continue
                if field['type'] == 'many2one':
                    result[rec.id] = value.instance or False
                elif field['type'] in ('char','text'):
                    result[rec.id] = value
                else:
                    raise osv.except_osv(_('Error !'), _("%(method)s doesn't implement field of type %(type)s, please contact system administrator to upgrade.") % {'method':'get_destination_name()', 'type':field['type']})

        assert set(ids) == set(result.keys()), "The return value of get_destination_name is not consistent"
        return result

    def get_message_arguments(self, cr, uid, res_id, rule=None, context=None):
        """
            @param res_id: Id of the record from which we need to extract the args of the call
            @param rule: the message generating rule (browse record)
            @return a list : each element of the list will be an arg after uid
                If the call is create_po(self, cr, uid, arg1, arg2, context=None)
                the list should contains exactly 2 element

            The default method will extract object information from the rule and return a list with a single element
            the object information json serialized

        """
        fields = eval(rule.arguments)
        res =  self.export_data_json(cr, uid, [res_id], fields, context=context)
        return res['datas']

    def export_data_json(self, cr, uid, ids, fields_to_export, context=None):
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
            def __export_row_json(self, cr, uid, row, fields, json_data, context=None):
                    if not context:
                        context = {}

                    def get_name(row):
                        name_relation = self.pool.get(row._table_name)._rec_name
                        if isinstance(row[name_relation], browse_record):
                            row = row[name_relation]
                        row_name = self.pool.get(row._table_name).name_get(cr, uid, [row.id], context=context)
                        return row_name and row_name[0] and row_name[0][1] or ''

                    def export_list(field, record_list, json_list):
                        if not json_list: #if the list was not created before
                            json_list = [{} for i in record_list]

                        for i in xrange(0, len(record_list)):
                            if len(field) > 1:
                                if not record_list[i]:
                                    json_list[i] = {}
                                json_list[i] = export_field(field[1:], record_list[i], json_list[i])
                            else:
                                json_list[i] = get_name(record_list[i])

                        return json_list

                    def export_relation(field, record, json):
                        if len(field) > 1:
                            if not json: #if the list was not create before
                                json = {}
                            return export_field(field[1:], record, json)
                        else:
                            return get_name(record)

                    def export_field(field, row, json_data):
                        """
                            @param field: a list
                                size = 1 ['cost_price']
                                size > 1 ['partner_id', 'id']
                            @param row: the browse record for which field[0] is a valid field
                            @param json_data: json seralisation of row

                        """
                        if field[0] == 'id':
                            json_data[field[0]] = row.get_xml_id(cr, uid, [row.id]).get(row.id)
                        elif field[0] == '.id':
                            json_data[field[0]] = row.id
                        else:
                            r = row[field[0]]
                            if isinstance(r, (browse_record_list, list)):
                                json_data[field[0]] = export_list(field, r, json_data.get(field[0]))
                            elif isinstance(r, (browse_record)):
                                json_data[field[0]] = export_relation(field, r, json_data.get(field[0]))
                            elif not r:
                                json_data[field[0]] = False
                            else:
                                if len(field) > 1:
                                    raise ValueError('%s is not a relational field cannot use / to go deeper' % field[0])
                                json_data[field[0]] = r

                        return json_data

                    json_data = {}
                    for field in fields:
                        export_field(field, row, json_data)

                    return json_data

            def fsplit(x):
                if x=='.id': return [x]
                return x.replace(':id','/id').replace('.id','/.id').split('/')

            fields_to_export = map(fsplit, fields_to_export)
            datas = []
            for row in self.browse(cr, uid, ids, context):
                datas.append(__export_row_json(self, cr, uid, row, fields_to_export, context))
            return {'datas': datas}

    def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
        return uuid + '/' + table_name + '/' + str(res_id)

for symbol in filter(lambda sym: isinstance(sym, types.MethodType),
                     map(lambda label: getattr(extended_orm_methods, label),
                         dir(extended_orm_methods))):
    setattr(orm.orm, symbol.func_name, symbol.im_func)
