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
    
    def _check_usb_instance_type(self, cr, uid, context):
        if not self._get_entity(cr, uid, context).usb_instance_type:
            raise osv.except_osv(_('Set USB Instance Type First'), _('You have not yet set a USB Instance Type for this instance. Please do this first by going to Synchronization > Registration > Setup USB Synchronisation'))
    
    def pull(self, cr, uid, ids, context=None):
        
        self._check_usb_instance_type(cr, uid, context)
        
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
                pull_result += '\nSuccessfully ran %d update(s) and deletion(s)' % updates_ran
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
        
    def push(self, cr, uid, ids, context=None):
        """
        Triggered from the usb sync wizard.
        Checks usb_sync_step has correct status then triggers sync on entity, which in turn
        creates updates, messages, packages into zip and attaches to entity
        Then returns new values for wizard
        """
        # validation
        self._check_usb_instance_type(cr, uid, context)
        wizard = self.browse(cr, uid, ids[0])
        if wizard.usb_sync_step not in ['pull_performed', 'first_sync']:
            raise osv.except_osv(_('Cannot Push'), _('We cannot perform a Push until we have Validated the last Pull'))
        
        # start push
        updates, deletions, messages = self.pool.get('sync.client.entity').usb_push(cr, uid, context=context)
        
        # send results to wizard
        vals = {
            'usb_sync_step': self._get_usb_sync_step(cr, uid, context=context),
        }
        
        # update wizard to show results of push to user
        updates_result = updates and 'Successfully exported %s updates\n' % updates or 'No updates that need to be synchronised have been made so there were no updates to push\n'
        deletions_result = deletions and 'Successfully exported %s deletions\n' % deletions or 'No deletions that need to be synchronised have been made so there were no deletions to push\n'
        messages_result = messages and 'Successfully exported %s messages\n' % messages or 'No messages that need to be synchronised have been made so there were no messages to push\n'
        
        vals['push_result'] = updates_result + deletions_result + messages_result
        if updates or deletions or messages:
            vals['push_file_visible'] = True,
         
        return self.write(cr, uid, ids, vals, context=context)

usb_synchronisation()
