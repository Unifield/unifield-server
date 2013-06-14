from osv import osv, fields
from tools.translate import _

class usb_recovery(osv.osv_memory):
    _name = 'usb_recovery'
    
    def _get_entity(self, cr, uid, context):
        return self.pool.get('sync.client.entity').get_entity(cr, uid, context=context)
    
    def _get_usb_sync_step(self, cr, uid, context):
        return self._get_entity(cr, uid, context).usb_sync_step
    
    def _get_entity_last_push_file(self, cr, uid, ids=None, field_name=None, arg=None, context=None):
        return dict.fromkeys(ids, self._get_entity(cr, uid, context).usb_last_push_file)
    
    def _get_entity_last_push_file_name(self, cr, uid, ids=None, field_name=None, arg=None, context=None):
        last_push_date = self._get_entity(cr, uid, context).usb_last_push_date
        last_push_file_name = '%s.zip' % last_push_date
        return dict.fromkeys(ids, last_push_file_name)
    
    def _get_usb_instance_type(self, cr, uid, ids=None, field_name=None, arg=None, context=None):
        usb_instance_type = self._get_entity(cr, uid, context).usb_instance_type
        if isinstance(ids, (int, long, list)):
            return dict.fromkeys(ids, usb_instance_type)
        else:
            return usb_instance_type
        
    
    _columns = {
        # used for view state logic
        'push_file_ready' : fields.boolean('Push File Ready'),
        'usb_sync_step' : fields.char('USB Sync step', size=64),
        'usb_instance_type' : fields.function(_get_usb_instance_type, type='char', method=True, string="USB Instance Type"),
        
        # used to let user download pushed information
        'push_file' : fields.function(_get_entity_last_push_file, type='binary', method=True, string='Last Push File'),
        'push_file_name' : fields.function(_get_entity_last_push_file_name, type='char', method=True, string='Last Push File Name'),
    }
    
    _defaults = {
        'usb_sync_step': _get_usb_sync_step,
        'push_file': _get_entity_last_push_file,
        'push_file_name': _get_entity_last_push_file_name,
        'usb_instance_type': _get_usb_instance_type,
    }
    
    def _check_usb_instance_type(self, cr, uid, context):
        if not self._get_entity(cr, uid, context).usb_instance_type:
            raise osv.except_osv(_('Set USB Instance Type First'), _('You have not yet set a USB Instance Type for this instance. Please do this first by going to Synchronization > Registration > Setup USB Synchronisation'))
    
    def mark_first_sync(self, cr, uid, ids, context=None):
        self._check_usb_instance_type(cr, uid, context)
        entity = self._get_entity(cr, uid, context) 
        self.pool.get('sync.client.entity').write(cr, uid, entity.id, {'usb_sync_step' : 'first_sync'}, context=context)
        return self.write(cr, uid, ids, {'usb_sync_step': 'first_sync'})
    
    def get_last_push_file(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'push_file_ready': True})
        
usb_recovery()
