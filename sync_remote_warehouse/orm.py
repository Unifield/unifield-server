from osv import osv, fields, orm

super_get_unique_xml_name = orm.orm.get_unique_xml_name
    
def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
    sd_ref = super_get_unique_xml_name(self, cr, uid, uuid, table_name, res_id)
    entity = self.pool.get('sync.client.entity').get_entity(cr, uid)
        
    # state checks
    if entity.usb_instance_type == 'remote_warehouse':
        sd_ref += "/RW"
    print 'new SD ref %s: %s' % (self._table, sd_ref)
    return sd_ref
    
orm.orm.get_unique_xml_name = get_unique_xml_name

def usb_need_to_push(self, cr, uid, ids, context=None):
        """
        
        Check if records need to be pushed to the next USB synchronization process
        or not.
        
        One of these conditions need to match:
            - Last modification > clone_date
            - sync_date > clone_date
        
        ~ AND ~
        
        One of these conditions needs to match: 
            - usb_sync_date < last_modification
            - usb_sync_date < sync_date
            - usb_sync_date is not set
            - record is deleted
            - watched fields are present in modified fields

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
        
        clone_date = self.pool.get('sync.client.entity').get_entity(cr, uid, context).clone_date
        
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
                  model = %%s AND
                  res_id IN %%s AND
                  (last_modification > '%(clone_date)s' OR sync_date > '%(clone_date)s') AND
                  (usb_sync_date < last_modification OR usb_sync_date < sync_date OR usb_sync_date IS NULL)""" % {'clone_date' : clone_date},
        [self._name, tuple(ids)])
        
        result = [row[0] for row in cr.fetchall()]
        return result if result_iterable else len(result) > 0

orm.orm.usb_need_to_push = usb_need_to_push


from workflow import workitem, instance, wkf_expr, wkf_logs
import pooler
import netsvc

old_wkf_workitem_create = workitem.create
def wkf_workitem_create(cr, act_datas, inst_id, ident, stack):
    new_ids = old_wkf_workitem_create(cr, act_datas, inst_id, ident, stack)
    pooler.get_pool(cr.dbname).get('workflow.workitem').get_sd_ref(cr, 1, new_ids)
    return new_ids
 
workitem.create = wkf_workitem_create   

old_wkf_instance_create = instance.create

def wkf_instance_create(cr, ident, wkf_id):
    id_new = old_wkf_instance_create(cr, ident, wkf_id)
    pooler.get_pool(cr.dbname).get('workflow.instance').get_sd_ref(cr, 1, [id_new])
    return id_new

instance.create = wkf_instance_create


class wkf_instance(osv.osv):
    """
    replace res_id with sdref for synchronization
    """
    
    _inherit = 'workflow.instance'
    
    _res_model_field = 'res_type'
    _res_id_field = 'res_id'
    
    def replace_res_id_by_xml_id(self, cr, uid, ids, fields, vals, context=None):
        def ids_per_model(values):
            res = {}
            for val in values:
                res.setdefault(val[self._res_model_field], []).append(val[self._res_id_field])
            return res
        
        def get_all_sd_ref(ids_per_model_dict):
            res = {}
            for model, ids in ids_per_model_dict.items():
                res.update(self.pool.get(model).get_sd_ref(cr, 1, ids, context=context))
            return res
                
        if not context or not context.get('sync_update_creation'): #May replace by offline_synchronization
            return vals

        is_list = True
        if not isinstance(vals, (tuple, list)):
            vals = [vals]
            is_list = False
            
        if fields and self._res_id_field in fields:
            assert (self._res_model_field in fields), \
                "When reading %s in object %s to during synchronization export, be sure to include field %s" % (self._res_id_field, self._name, self._res_model_field)
            
            all_sd_ref = get_all_sd_ref(ids_per_model(vals))
            for val in vals:
                val[self._res_id_field] = "sd." + all_sd_ref[val[self._res_id_field]]
        
        return is_list and vals or vals[0]
    
    def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
        vals = super(wkf_instance, self).read(cr, uid, ids, fields=fields, context=context, load=load)
        return self.replace_res_id_by_xml_id(cr, uid, ids, fields, vals, context)
    
    
wkf_instance()

