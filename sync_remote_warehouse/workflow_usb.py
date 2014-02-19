from osv import osv, fields, orm
from workflow import workitem, instance, wkf_expr, wkf_logs
import pooler
import netsvc

# trigger creation of SD ref automatically
old_wkf_workitem_create = workitem.create

def wkf_workitem_create(cr, act_datas, inst_id, ident, stack):
    new_ids = old_wkf_workitem_create(cr, act_datas, inst_id, ident, stack)
    pooler.get_pool(cr.dbname).get('workflow.workitem').get_sd_ref(cr, 1, new_ids)
    return new_ids
 
workitem.create = wkf_workitem_create   

# trigger creation of SD ref automatically
old_wkf_instance_create = instance.create

def wkf_instance_create(cr, ident, wkf_id):
    id_new = old_wkf_instance_create(cr, ident, wkf_id)
    pooler.get_pool(cr.dbname).get('workflow.instance').get_sd_ref(cr, 1, [id_new])
    return id_new

instance.create = wkf_instance_create


class wkf_instance(osv.osv):
    """
    If synchronising, convert res_id from int to SD ref on export, and sd ref to int on import 
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
                res.setdefault(model, {})
                for i in ids:
                    res[model][i] = self.pool.get(model).get_sd_ref(cr, 1, i, context=context)
            return res
                
        if not context or not context.get('sync_update_creation'): #May replace by offline_synchronization
            return vals

        is_list = True
        if not isinstance(vals, (tuple, list)):
            vals = [vals]
            is_list = False
            
        if fields and self._res_id_field in fields:
            assert (self._res_model_field in fields), \
                "When reading %s in object %s during synchronization export, be sure to include field %s" % (self._res_id_field, self._name, self._res_model_field)
            
            all_sd_ref = get_all_sd_ref(ids_per_model(vals))
            for val in vals:
                val[self._res_id_field] = "sd." + all_sd_ref[val[self._res_model_field]][val[self._res_id_field]]
        
        return is_list and vals or vals[0]
    
    def is_int(self, obj):
        try:
            int(obj)
            return True
        except ValueError:
            return False
    
    def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
        """ Convert int to SD ref for res_id field """
        vals = super(wkf_instance, self).read(cr, uid, ids, fields=fields, context=context, load=load)
        return self.replace_res_id_by_xml_id(cr, uid, ids, fields, vals, context)
    
    def import_data(self, cr, uid, fields, datas, mode='init', current_module='', noupdate=False, context=None, filename=None):
        """ Convert SD ref to id for res_id field """
        if not isinstance(context, dict) or not context.get('sync_update_execution'): #May replace by offline_synchronization
            return super(wkf_instance, self).import_data(cr, uid, fields, datas, mode=mode, current_module=current_module, noupdate=noupdate, context=context, filename=filename)
        
        index = fields.index('res_id')
        for data in datas:
            if not self.is_int(data[index]):
                sd_ref = '.' in data[index] and data[index].split('.', 1)[1] or data[index]
                cr.execute("select res_id from ir_model_data where name = '%s' and module = 'sd'" % sd_ref)
                res_id = cr.fetchone()
                data[index] = res_id and res_id[0] or 0
        return super(wkf_instance, self).import_data(cr, uid, fields, datas, mode=mode, current_module=current_module, noupdate=noupdate, context=context, filename=filename)
    
wkf_instance()

