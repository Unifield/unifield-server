from osv import osv, fields, orm
from osv.orm import browse_record
import tools
from tools.safe_eval import safe_eval as eval
import logging
import functools
import types

from sync_common import MODELS_TO_IGNORE, xmlid_to_sdref


## Debug method for development #############################################

## To use this, simply start the server in log_level DEBUG or lower
## and remove the logfile. Then call method debug() in RPC on any object

if not tools.config.options['logfile'] and tools.config.options['log_level'] <= logging.DEBUG:
    import ipdb

    def debug1(self, cr, uid, context=None):
        context = dict(context or {})
        logger = logging.getLogger('debugger')
        logger.debug("Welcome to ipdb!")

        entity = self.pool.get('sync.client.entity').get_entity(cr, uid, context=context)
        self.pool.get("sync.client.sync_server_connection").connect(cr, uid, context=context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        res = proxy.get_model_to_sync(entity.identifier)
        if not res[0]: raise Exception, res[1]
        newrules = res[1]
        rules = self.pool.get('sync.client.rule')
        old_rules_ids = set(rules.search(cr, uid, ['|',('active','=',True),('active','=',False)], context=context))
        rules.save(cr, uid, newrules, context=context)
        new_rules_ids = set(rules.search(cr, uid, ['|',('active','=',True),('active','=',False)], context=context))
        print old_rules_ids
        print new_rules_ids
        assert old_rules_ids & new_rules_ids == old_rules_ids, "Rules should never be deleted"

        obj = self.pool.get('res.country')
        rules = self.pool.get('sync.client.rule')
        ir_data = self.pool.get('ir.model.data')

        rec_id = obj.search(cr, uid, [], limit=1)[0]
        data_id = obj.get_sd_ref(cr, uid, rec_id, field='id')
        print ir_data.read(cr, uid, data_id, ['is_deleted'])

        ipdb.set_trace()

        try:
            ir_data.get(cr, uid, obj, rec_id)
        except DeprecationWarning, e:
            print "%s .. OK" % e.message

        obj.unlink(cr, uid, rec_id)
        print ir_data.read(cr, uid, data_id, ['is_deleted'])

        ids = obj.search_deleted(cr, uid)
        assert len(ids) > 0, "The record should be deleted"
        print "%s => %s" % (ids, obj.need_to_push(cr, uid, ids, []))

        #rule_id = rules.search(cr, uid, [('model.model','=',obj._name)], limit=1)[0]
        #rules.write(cr, uid, [rule_id], {'can_delete':True})
        # TODO broken: the server should know it's personal rule id
        rule_id = rules.create(cr, uid, {
            'model' : obj._name,
            'server_id' : 0, # wrong!
            'included_fields' : '[]',
            'can_delete' : True,
        })
        res = self.pool.get('sync.client.update_to_send').create_update(cr, uid, rule_id, 'SAMUS')
        assert res != (0, 0), "Nothing to do."
        #assert ir_data.search(cr, uid, [('model','=',obj._name),('res_id','=',rec_id)], count=True) == 0, "The xmlid should be deleted in case of purge"

        ipdb.set_trace()
        res = self.pool.get('sync.client.update_to_send').create_package(cr, uid, 'SAMUS', 2000)
        assert res is not False, "No update to send."
        update_ids, packet = res
        res = proxy.receive_package(entity.identifier, packet, context)
        if not res[0]: raise Exception, res[1]
        ipdb.set_trace()
        self.pool.get('sync.client.update_to_send').sync_finished(cr, uid, update_ids, context=context)
        logger.debug("Type 'c' to continue normal process")
        cr.rollback()
        return True

    orm.orm.debug1 = debug1

    def debug2(self, cr, uid, context=None):
        context = dict(context or {})
        logger = logging.getLogger('debugger')
        logger.debug("Welcome to ipdb!")

        entity = self.pool.get('sync.client.entity').get_entity(cr, uid, context=context)
        self.pool.get("sync.client.sync_server_connection").connect(cr, uid, context=context)
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")

        obj = self.pool.get('res.country')
        rules = self.pool.get('sync.client.rule')
        ir_data = self.pool.get('ir.model.data')

        res = proxy.get_update(entity.identifier, 998, 0, 2000, 999, True, context)
        assert res[0], res[1]
        assert res[1], "No more update"
        print self.pool.get('sync.client.update_received').unfold_package(cr, uid, res[1], context=context)
        ipdb.set_trace()
        res = self.pool.get('sync.client.update_received').execute_update(cr, uid, context=context)

        ipdb.set_trace()
        logger.debug("Type 'c' to continue normal process")
        cr.rollback()
        return True

    orm.orm.debug2 = debug2


## Helpers ###################################################################

class DuplicateKey(KeyError):
    message = "Key is already present"

class RejectingDict(dict):
    def __setitem__(self, k, v):
        if k in self.keys():
            raise DuplicateKey
        else:
            return super(RejectingDict, self).__setitem__(k, v)



def modif_o2m(self, cr, uid, ids, values, context=None):
    """record modification of m2o if the corresponding o2m is modified"""
    if not hasattr(ids, '__iter__'): ids = [ids]
    fields_ref = self.fields_get(cr, uid, context=context)
    for key in values.keys():
        if fields_ref.get(key) and fields_ref[key]['type'] == 'one2many' and values[key]:
            sub_model = fields_ref[key]['relation']
            for rec in self.browse(cr, uid, ids, context=context):
                sub_ids = [obj.id for obj in getattr(rec, key)]
                self.pool.get(sub_model).synchronize(cr, uid, sub_ids, context=context)



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

    def need_to_push(self, cr, uid, ids, context=None):
        """
        Check if records need to be pushed to the next synchronization process
        or not.

        One of those conditions needs to match: 
            - sync_date < last_modification
            - sync_date is not set

        Note: sync_date field can be changed to other field using parameter
        sync_field

        Return type:
            - If a list of ids is given, it returns a list of filtered ids.
            - If an id is given, it returns the id itself or False it the
              record doesn't need to be pushed.

        :param cr: database cursor
        :param uid: current user id
        :param ids: id or list of the ids of the records to read
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :return: list of ids that need to be pushed (or False for per record call)

        """
        result_iterable = hasattr(ids, '__iter__')
        if not result_iterable: ids = [ids]
        ids = filter(None, ids)
        if not ids: return ids if result_iterable else False
        # Optimization for not deleted records:
        # Filter data where sync_date < last_modification OR sync_date IS NULL
        cr.execute("""\
SELECT res_id
    FROM ir_model_data
    WHERE module = 'sd' AND
          model = %s AND
          res_id IN %s AND
          (sync_date < last_modification OR sync_date IS NULL)""",
[self._name, tuple(ids)])
        result = [row[0] for row in cr.fetchall()]
        return result if result_iterable else len(result) > 0

    def get_sd_ref(self, cr, uid, ids, field='name', synchronize=False, context=None):
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
        assert self._name != "ir.model.data", "Cannot create on xmlid on an ir.model.data object!"
        result_iterable = hasattr(ids, '__iter__')
        if not result_iterable: ids = [ids]
        model_data_obj = self.pool.get('ir.model.data')
        data_ids = model_data_obj.search(cr, uid, [('model','=',self._name),('res_id','in',ids),('module','=','sd')])
        try:
            result = RejectingDict((data.res_id, getattr(data, field)) for data in model_data_obj.browse(cr, uid, data_ids))
        except DuplicateKey:
            raise Exception("Duplicate definition of 'sd' xml_ids: model=%s, ids=%s. Too late for debugging, sorry!" % (self._name, ids))
        now = fields.datetime.now()
        identifier = self.pool.get('sync.client.entity').get_entity(cr, uid, context=context).identifier
        for res_id in (id for id in ids if id and not id in result):
            new_record = {
                'noupdate' : False, # don't set to True otherwise import won't work
                'module' : 'sd',
                'last_modification' : now,
                'model' : self._name,
                'res_id' : res_id,
                'version' : 1,
                'name' : self.get_unique_xml_name(cr, uid, identifier, self._table, res_id),
            }
            new_record['id'] = model_data_obj.create(cr, uid, new_record, context=context)
            result[res_id] = new_record.get(field)
        if synchronize and data_ids:
            model_data_obj.write(cr, uid, data_ids, {'last_modification' : now})
        return result if result_iterable else result.get(ids[0], False)

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

    def synchronize(self, cr, uid, ids, context=None):
        """
        Update the SD ref (or create one if it does'n exists) and mark it to be synchronize
        :param cr: database cursor
        :param uid: current user id
        :param ids: id or list of the ids of the records to read
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :return: dictionary with requested references

        """
        return self.get_sd_ref(cr, uid, ids, synchronize=True, context=context)

    def find_sd_ref(self, cr, uid, sdrefs, field='res_id', context=None):
        """
        Find the ids of records based on their SD reference. If called on a model, search SD refs for this model only. Otherwise, search any record.

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
        if self._name == "ir.model.data":
            cr.execute("""\
SELECT name, id FROM ir_model_data WHERE module = 'sd' AND name IN %s""", [sdrefs])
        else:
            cr.execute("""\
SELECT name, %s FROM ir_model_data WHERE module = 'sd' AND model = %%s AND name IN %%s""" \
% field, [self._name,sdrefs])
        try:
            result = RejectingDict(cr.fetchall())
        except DuplicateKey:
            raise Exception("Duplicate definition of 'sd' xml_ids: model=%s, sdrefs=%s. Too late for debugging, sorry!" % (self._name, sdrefs))
        return result if result_iterable else result.get(sdrefs[0], False)

    @orm_method_overload
    def create(self, original_create, cr, uid, values, context=None):
        id = original_create(self, cr, uid, values, context=context)
        if self._name not in MODELS_TO_IGNORE and (context is None or \
           (not context.get('sync_update_execution') and not context.get('sync_update_creation'))):
            global modif_o2m
            modif_o2m(self, cr, uid, id, values, context=context)
            self.synchronize(cr, uid, id, context=context)
        return id

    @orm_method_overload
    def write(self,original_write,cr,uid,ids,values,context=None):
        if self._name not in MODELS_TO_IGNORE and (context is None or \
           (not context.get('sync_update_execution') and not context.get('sync_update_creation'))):
            global modif_o2m
            if not isinstance(ids, (list, tuple)): ids = [ids]
            modif_o2m(self, cr, uid, ids, values, context=context)
            self.synchronize(cr, uid, ids, context=context)
        return original_write(self, cr, uid, ids, values,context=context)

    def message_unlink(self, cr, uid, source, unlink_info, context=None):
        model_name = unlink_info.model
        xml_id =  unlink_info.xml_id
        if model_name != self._name:
            return "Model not consistant"

        res_id = self.find_sd_ref(cr, uid, xmlid_to_sdref(xml_id), context=context)
        if not res_id:
            return "Object %s %s does not exist in destination" % (model_name, xml_id)

        return old_unlink(self, cr, uid, [res_id], context=context)

    def generate_message_for_destination(self, cr, uid, destination_name, xml_id, instance_name, send_to_parent_instances):
        instance_obj = self.pool.get('msf.instance')

        if not destination_name:
            return
        if destination_name != instance_name:
            message_data = {
                    'identifier' : 'delete_%s_to_%s' % (xml_id, destination_name),
                    'sent' : False,
                    'generate_message' : True,
                    'remote_call': self._name + ".message_unlink",
                    'arguments': "[{'model' :  '%s', 'xml_id' : '%s'}]" % (self._name, xml_id),
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
                    generate_message_for_destination(self, cr, uid, parent, xml_id, instance_name, send_to_parent_instances)

    @orm_method_overload
    def unlink(self, original_unlink, cr, uid, ids, context=None):
        if not ids: return True

        if hasattr(self, '_delete_owner_field'):
            if not hasattr(ids, '__iter__'): ids = [ids]
            instance_name = self.pool.get("sync.client.entity").get_entity(cr, 1, context=context).name
            xml_ids = self.pool.get('ir.model.data').get(cr, 1, self, ids, context=context)
            destination_names = self.get_destination_name(cr, 1, ids, self._delete_owner_field, context=context)
            for id, xml_id_record in zip(ids, self.pool.get('ir.model.data').browse(cr, 1, xml_ids, context=context)):
                xml_id = '%s.%s' % (xml_id_record.module, xml_id_record.name)
                self.generate_message_for_destination(cr, 1, destination_names[id], xml_id, instance_name, send_to_parent_instances=True)

        if self._name == 'ir.model.data' and (context is None or context.get('avoid_ir_data_deletion')):
            return True

        if self._name not in MODELS_TO_IGNORE and \
           (context is None or not context.get('sync_update_creation')):
            context = dict(context or {}, avoid_ir_data_deletion=True)
            if not context.get('sync_update_execution'):
                self.synchronize(cr, uid, ids, context=context)

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
        self.unlink(cr, uid, to_delete, context=None)
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
                        else: #TODO manage more case maybe selection or reference
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
