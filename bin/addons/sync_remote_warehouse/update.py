from osv import osv, fields
import tools

class UpdateReceived(osv.osv):
    _inherit = 'sync.client.update_received'
    _name = 'sync_remote_warehouse.update_received'
    _sync_field = 'usb_sync_field'
    
    def _conflict(self, cr, uid, sdref, next_version, context=None):
        ir_data = self.pool.get('ir.model.data')
        data_id = ir_data.find_sd_ref(cr, uid, sdref, context=context)
        # no data => no record => no conflict
        if not data_id: return False
        data_rec = ir_data.browse(cr, uid, data_id, context=context)
        return (not data_rec.is_deleted                                           # record doesn't exists => no conflict
                and (not data_rec.sync_date and not data_rec.usb_sync_date        # never synced => conflict
                     or (data_rec.last_modification and data_rec.sync_date        # if last_modification and sync date exist,
                         and data_rec.sync_date < data_rec.last_modification)     # modification after synchro => conflict
                     or (data_rec.last_modification and data_rec.usb_sync_date    # if last_modification and usb sync date exist,
                         and data_rec.usb_sync_date < data_rec.last_modification) # modification after synchro => conflict
                     or next_version < data_rec.version))                         # next version is lower than current version

UpdateReceived()

class UpdateToSend(osv.osv):
    _inherit = 'sync.client.update_to_send'
    _name = 'sync_remote_warehouse.update_to_send'
    
    def sync_finished(self, cr, uid, update_ids, sync_field='sync_date', context=None):
        return super(UpdateToSend, self).sync_finished(cr, uid, update_ids, sync_field="usb_sync_date", context=context)
    
    def create_update(self, cr, uid, rule_id, session_id, context=None):
        rule = self.pool.get('sync.client.rule').browse(cr, uid, rule_id, context=context)
        update = self
        
        def create_normal_update(self, rule, context):
            domain = eval(rule.domain or '[]')
            included_fields = eval(rule.included_fields or '[]') 
            if not 'id' in included_fields: 
                included_fields.append('id')

            ids_need_to_push = self.usb_need_to_push(cr, uid, context=context)
            if not ids_need_to_push:
                return 0
            domain.append(('id', 'in', ids_need_to_push))
            ids_to_compute = self.search_ext(cr, uid, domain, context=context)
            if not ids_to_compute:
                return 0

            owners = self.get_destination_name(cr, uid, ids_to_compute, rule.owner_field, context)
            datas = self.export_data(cr, uid, ids_to_compute, included_fields, context=context)['datas']
            sdrefs = self.get_sd_ref(cr, uid, ids_to_compute, context=context)
            versions = self.version(cr, uid, ids_to_compute, context=context)
            ustr_included_fields = tools.ustr(included_fields)
            for (id, row) in zip(ids_to_compute, datas):
                for owner in (owners[id] if hasattr(owners[id], '__iter__') else [owners[id]]):
                    update_id = update.create(cr, uid, {
                        'session_id' : session_id,
                        'values' : tools.ustr(row),
                        'model' : self._name,
                        'version' : versions[id] + 1,
                        'rule_id' : rule.id,
                        'sdref' : sdrefs[id],
                        'fields' : ustr_included_fields,
                        'owner' : owner,
                    }, context=context)
                    update._logger.debug("Created 'normal' update model=%s id=%d (rule sequence=%d)" % (self._name, update_id, rule.id))

            return len(ids_to_compute)

        def create_delete_update(self, rule, context):
            if not rule.can_delete:
                return 0

            ids_to_delete = self.need_to_push(cr, uid,
                self.search_deleted(cr, uid, module='sd', context=context), context=context)

            if not ids_to_delete:
                return 0

            sdrefs = self.get_sd_ref(cr, uid, ids_to_delete, context=context)
            for id in ids_to_delete:
                update_id = update.create(cr, uid, {
                    'session_id' : session_id,
                    'model' : self._name,
                    'rule_id' : rule.id,
                    'sdref' : sdrefs[id],
                    'is_deleted' : True,
                }, context=context)
                update._logger.debug("Created 'delete' update: model=%s id=%d (rule sequence=%d)" % (self._name, update_id, rule.id))

            self.purge(cr, uid, ids_to_delete, context=context)
            return len(ids_to_delete)

        update_context = dict(context or {}, sync_update_creation=True)
        obj = self.pool.get(rule.model)
        assert obj, "Cannot find model %s of rule id=%d!" % (rule.model, rule.id)
        return (create_normal_update(obj, rule, update_context), create_delete_update(obj, rule, update_context))

UpdateToSend()
