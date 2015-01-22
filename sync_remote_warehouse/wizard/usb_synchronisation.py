import zipfile
import datetime
import dateutil.parser

from osv import osv, fields
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
        last_push_file_name = '%s.zip' % last_push_date[:16].replace(' ','_') if last_push_date else False
        return dict.fromkeys(ids, last_push_file_name)

    def _get_entity_last_tarball_patches(self, cr, uid, ids, field_name, arg, context=None):
        return dict.fromkeys(ids, self._get_entity(cr, uid, context).usb_last_tarball_patches)

    def _get_entity_last_tarball_file_name(self, cr, uid, ids, field_name, arg, context=None):
        last_push_date = self._get_entity(cr, uid, context).usb_last_push_date
        last_push_file_name = 'patches_%s.tar' % last_push_date[:16].replace(' ','_') if last_push_date else False
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

        # patch file for the OpenERP server instance
        'patch_file' : fields.function(_get_entity_last_tarball_patches, type='binary', method=True, string='Tarball Patches'),
        'patch_file_name' : fields.function(_get_entity_last_tarball_file_name, type='char', method=True, string='Tarball Patches File Name'),
        'patch_file_visible': fields.boolean('Tarball Patch File Visible'),
    }
    
    _defaults = {
        'usb_sync_step': _get_usb_sync_step,
        'push_file_visible': False,
        'patch_file_visible': False,
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
        
        
        #US-26: Added a check if the zip file has already been imported before
        syncusb = self.pool.get('sync.usb.files')
        md5 = syncusb.md5(wizard.pull_data)
        zipfile_ids = syncusb.search(cr, uid, [('sum', '=', md5)], context=context)
        if zipfile_ids:
            zipfiles = syncusb.browse(cr, uid, zipfile_ids, context=context)
            zipfile = zipfiles[0]
            imported_date = zipfile.date 
            if imported_date:
                imported_date = dateutil.parser.parse(imported_date).strftime("%H:%M on %A, %d.%m.%Y")
            raise osv.except_osv( _('Import couldn\'t be done twice.'), _('The zip file has already been uploaded at %s') % imported_date)
            
        updates_pulled = update_pull_error = updates_ran = update_run_error = \
        messages_pulled = message_pull_error = messages_ran = message_run_error = 0
        try:
            updates_pulled, update_pull_error, updates_ran, update_run_error, \
            messages_pulled, message_pull_error, messages_ran, message_run_error = self.pool.get('sync.client.entity').usb_pull(cr, uid, wizard.pull_data, context=context)
        except zipfile.BadZipfile:
            raise osv.except_osv(_('Not a Zip File'), _('The file you uploaded was not a valid .zip file'))
        
        #Update list of pulled files
        syncusb.create(cr, uid, {
            'sum': md5,
            'date': datetime.datetime.now().isoformat(),
        }, context=context)
        
        # handle returned values
        pull_result = ''
        if not update_pull_error:
            pull_result += 'Pulled %d update(s)' % updates_pulled 
            if not update_run_error:
                pull_result += '\nRan %s update(s)' % updates_ran
            else:
                pull_result += '\nError while executing %s update(s): %s' % (updates_ran, update_run_error)
        else:
            pull_result += 'Got an error while pulling %d update(s): %s' % (updates_pulled, update_pull_error)
            
        if not message_pull_error:
            pull_result += '\nPulled %d message(s)' % messages_pulled 
            if not message_run_error:
                pull_result += '\nRan %s message(s)' % messages_ran
            else:
                pull_result += '\nError while executing %s message(s): %s' % (messages_ran, message_run_error)
        else:
            pull_result += '\nGot an error while pulling %d message(s): %s' % (messages_pulled, message_pull_error)
        
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
        entity = self._get_entity(cr, uid, context=context)
        last_push_date = entity.usb_last_push_date

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
        updates_result = 'Exported %s update(s)\n' % updates
        deletions_result = 'Exported %s deletion(s)\n' % deletions
        messages_result = 'Exported %s message(s)\n' % messages
        
        vals['push_result'] = updates_result + deletions_result + messages_result
        vals['push_file_visible'] = True,
         
        # generate new tarball patches
        revisions = self.pool.get('sync_client.version')
        if revisions:
            rev_ids = revisions.search_installed_since(cr, uid, last_push_date, context=context)
            vals['patch_file_visible'] = bool(rev_ids)
            self.pool.get('sync.client.entity').write(cr, uid, [entity.id],
                {'usb_last_tarball_patches' : revisions.export_patch(cr, uid, rev_ids, 'warn', context=context)},
                context=context)

        res = self.write(cr, uid, ids, vals, context=context)
        # UF-2397: Change the result into an attachment so that the user can use again an export
        attachment_obj = self.pool.get('ir.attachment')
        import base64
        import time
        for synchro in self.read(cr, uid, ids, ['push_file', 'push_file_name'], context=context):
            # Create the attachment
            name = synchro.get('push_file_name', 'noname')
            attachment_obj.create(cr, uid, {
                'name': name,
                'datas_fname': name,
                'description': 'USB Synchronization file @%s' % time.strftime('%Y-%m-%d_%H%M'),
                'res_model': 'res.company',
                'res_id': self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
                'datas': base64.encodestring(base64.decodestring(synchro.get('push_file'))),
            })
        # Delete all previous attachment except last 10
        number = 5 # default value
        to_delete = []
        a_ids = attachment_obj.search(cr, uid, [], order='id desc')
        for idx, el in enumerate(a_ids):
            if idx >= number:
                to_delete.append(el)
        attachment_obj.unlink(cr, uid, to_delete)
        return res

usb_synchronisation()
