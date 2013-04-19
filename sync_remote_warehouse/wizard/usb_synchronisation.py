from osv import osv, fields
from .. import synchronise
import zipfile

class usb_synchronisation(osv.osv_memory):
    _name = 'usb_synchronisation'
    
    def _format_results_dictionary(self, dict):
        res = ''
        for key in dict.keys():
            val = (dict[key][0] and 'Successful') or 'Errors: %s' % '\n'.join(dict[key][1])   
            res = res + '\n%s: %s' % (key, val)
        return res
            
    def _usb_sync_step(self, cr, uid, context):
        res = self.pool.get('sync.client.entity').get_entity(cr, uid, context=context).usb_sync_step
        return res
    
    def _get_entity_last_push_file(self, cr, uid, ids, field_name, arg, context):
        return dict.fromkeys(ids, self.pool.get('sync.client.entity').get_entity(cr, uid, context=context).usb_last_push_file)
    
    def _get_entity_last_push_file_name(self, cr, uid, ids, field_name, arg, context):
        last_push_date = self.pool.get('sync.client.entity').get_entity(cr, uid, context=context).usb_last_push_date
        last_push_file_name = '%s.zip' % last_push_date
        return dict.fromkeys(ids, last_push_file_name)
        
    _columns = {
        # used to store pulled and pushed data, and to show results in the UI
        'pull_data' : fields.binary('Pull Data', filters='*.zip'),
        'pull_result' : fields.text('Pull Results', readonly=True),
        'push_result' : fields.text('Pull Results', readonly=True),
        
        # used for view state logic
        'usb_sync_step' : fields.char('USB Sync step', size=64),
        
        # used to let user download pushed information
        'push_file' : fields.function(_get_entity_last_push_file, type='binary', method=True, string='Last Push File'),
        'push_file_name' : fields.function(_get_entity_last_push_file_name, type='char', method=True, string='Last Push File Name'),
    }
    
    _defaults = {
        'usb_sync_step': _usb_sync_step
    }
    
    def pull(self, cr, uid, ids, context=None):
        
        wizard = self.browse(cr, uid, ids[0])
        
        if not wizard.pull_data:
            raise osv.except_osv('No Data to Pull', 'You have not specified a file that contains the data you want to Pull')
        
        try:
            results = synchronise.pull(self, cr, uid, wizard.pull_data, context=context)
        except zipfile.BadZipfile:
            raise osv.except_osv('Not a Zip File', 'The file you uploaded was not a .zip file')
        
        # write results to wizard object to update ui
        vals = {
            'pull_result': self._format_results_dictionary(results),
            'usb_sync_step': self._usb_sync_step(cr, uid, context=context),
        }
        
        return self.write(cr, uid, ids, vals, context=context)
        
    def validate(self, cr, uid, ids, context=None):
        
        wizard = self.browse(cr, uid, ids[0])
        if wizard.usb_sync_step != 'pull_performed':
            raise osv.except_osv('Cannot Validated', 'We cannot Validate the last Pull until we have performed a Pull')
        
        synchronise.validate(self, cr, uid, wizard.pull_data, context=context)
                
        vals = {
            'usb_sync_step': self._usb_sync_step(cr, uid, context=context),
        }
        
        return self.write(cr, uid, ids, vals, context=context)
        
    def push(self, cr, uid, ids, context=None):
        
        wizard = self.browse(cr, uid, ids[0])
        if wizard.usb_sync_step not in ['pull_validated', 'first_sync']:
            raise osv.except_osv('Cannot Push', 'We cannot perform a Push until we have Validated the last Pull')
        
        res = synchronise.push(self, cr, uid, wizard.pull_data, context=context)
        if not res:
            raise osv.except_osv('No Updates', 'No changes that need to be synchronized have been made so there is nothing to download')
                
        vals = {
            'usb_sync_step': self._usb_sync_step(cr, uid, context=context),
        }
        
        return self.write(cr, uid, ids, vals, context=context)

usb_synchronisation()