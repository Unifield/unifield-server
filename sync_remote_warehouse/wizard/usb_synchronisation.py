from osv import osv, fields
import zipfile
from tools.translate import _

class usb_synchronisation(osv.osv_memory):
    _name = 'usb_synchronisation'
    
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
    
    _columns = {
        # used to store pulled and pushed data, and to show results in the UI
        'pull_data' : fields.binary('Pull Data', filters='*.zip'),
        'pull_result' : fields.text('Pull Results', readonly=True),
        'push_result' : fields.text('Push Results', readonly=True),
        
        # used for view state logic
        'usb_sync_step' : fields.char('USB Sync step', size=64),
        
        # used to let user download pushed information
        'push_file' : fields.function(_get_entity_last_push_file, type='binary', method=True, string='Last Push File'),
        'push_file_name' : fields.function(_get_entity_last_push_file_name, type='char', method=True, string='Last Push File Name'),
        'push_file_visible': fields.boolean('Push File Visible'),
    }
    
    _defaults = {
        'usb_sync_step': _get_usb_sync_step,
        'push_file_name': _get_entity_last_push_file_name,
        'push_file_visible': False,
    }
    
    def pull(self, cr, uid, ids, context=None):
        
        context = context or {}
        context.update({'offline_synchronization' : True})
        
        wizard = self.browse(cr, uid, ids[0])
        
        if not wizard.pull_data:
            raise osv.except_osv(_('No Data to Pull'), _('You have not specified a file that contains the data you want to Pull'))
        
        import_count, import_error = 0, False
        try:
            import_count, import_error, updates_ran, run_error = self.pool.get('sync.client.entity').usb_pull_update(cr, uid, wizard.pull_data, context=context)
        except zipfile.BadZipfile:
            raise osv.except_osv(_('Not a Zip File'), _('The file you uploaded was not a .zip file'))
        
        # handle returned values
        pull_result = ''
        if not import_error:
            pull_result = 'Successfully Pulled %d update(s) and deletion(s)' % import_count
            if not run_error:
                pull_result += '\nSuccessfully ran %d update(s) and deletion(s)' % import_count
            else:
                pull_result += '\nError while executing the updates: %s' % run_error
        else:
            pull_result = 'Got an error while pulling %d update(s) and deletion(s): %s' % (import_count, import_error)
        
        # write results to wizard object to update ui
        vals = {
            'pull_result': pull_result,
            'usb_sync_step': self._get_usb_sync_step(cr, uid, context=context),
            'push_file_visible': False,
        }
        
        return self.write(cr, uid, ids, vals, context=context)
        
    def validate(self, cr, uid, ids, context=None):
        
        context = context or {}
        context.update({'offline_synchronization' : True})
        
        wizard = self.browse(cr, uid, ids[0])
        if wizard.usb_sync_step != 'pull_performed':
            raise osv.except_osv(_('Cannot Validated'), _('We cannot Validate the last Pull until we have performed a Pull'))
        
        self.pool.get('sync.client.entity').usb_validate_pull(cr, uid, wizard.pull_data, context=context)
                
        vals = {
            'usb_sync_step': self._get_usb_sync_step(cr, uid, context=context),
            'push_file_visible': False,
        }
        
        return self.write(cr, uid, ids, vals, context=context)
        
    def push(self, cr, uid, ids, context=None):
        
        context = context or {}
        context.update({'offline_synchronization' : True})
        
        wizard = self.browse(cr, uid, ids[0])
        if wizard.usb_sync_step not in ['pull_validated', 'first_sync']:
            raise osv.except_osv(_('Cannot Push'), _('We cannot perform a Push until we have Validated the last Pull'))
        
        push_result = self.pool.get('sync.client.entity').usb_push_update(cr, uid, wizard.pull_data, context=context)
        
        vals = {
            'usb_sync_step': self._get_usb_sync_step(cr, uid, context=context),
        }
        
        if push_result == 0:
            vals['push_result'] = _('No changes that need to be synchronized have been made so there is nothing to Push')
        else:
            vals['push_result'] = _('Push successfully exported %s update(s) and %s deletion(s)' % (push_result[0], push_result[1]))
            vals['push_file_visible'] = True,
         
        return self.write(cr, uid, ids, vals, context=context)

usb_synchronisation()
