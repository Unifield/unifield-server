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
    
    _columns = {
        # used to store pulled and pushed data, and to show results in the UI
        'pull_data' : fields.binary('Pull Data', filters='*.zip'),
        'pull_result' : fields.text('Pull Results', readonly=True),
        'push_result' : fields.text('Pull Results', readonly=True),
        
        # used for view state logic
        'usb_sync_step' : fields.char('USB Sync step', size=64),
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
        
        self.write(cr, uid, ids, vals, context=context)
        
    def validate(self, cr, uid, ids, context=None):
        
        wizard = self.browse(cr, uid, ids[0])
        if wizard.usb_sync_step != 'pull_performed':
            raise osv.except_osv('Cannot Validated', 'We cannot Validate the last Pull until we have performed a Pull')
        
        synchronise.validate(self, cr, uid, wizard.pull_data, context=context)
                
        vals = {
            'usb_sync_step': self._usb_sync_step(cr, uid, context=context),
        }
        
        self.write(cr, uid, ids, vals, context=context)
        
    def push(self, cr, uid, ids, context=None):
        
        wizard = self.browse(cr, uid, ids[0])
        if wizard.usb_sync_step not in ['pull_validated', 'first_sync']:
            raise osv.except_osv('Cannot Push', 'We cannot perform a Push until we have Validated the last Pull')
        
        synchronise.push(self, cr, uid, wizard.pull_data, context=context)
                
        vals = {
            'usb_sync_step': self._usb_sync_step(cr, uid, context=context),
        }
        
        self.write(cr, uid, ids, vals, context=context)

usb_synchronisation()