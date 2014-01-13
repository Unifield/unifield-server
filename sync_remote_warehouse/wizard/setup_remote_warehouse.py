import os
from os.path import expanduser
import subprocess
from datetime import datetime

from tools.translate import _
from osv import osv, fields
import logging

class setup_remote_warehouse(osv.osv_memory):
    _name = 'setup_remote_warehouse'
    
    def get_existing_usb_instance_type(self, cr, uid, ids, field_name=None, arg=None, context=None):
        return self.pool.get('sync.client.entity').get_entity(cr, uid).usb_instance_type
    
    remote_warehouse = "remote_warehouse"
    central_platform = "central_platform"
    backup_folder_name = 'openerp_remote_warehouse_backup'
    backup_file_name = 'cp_backup'
    
    _defaults = {
        'existing_usb_instance_type' : get_existing_usb_instance_type
    }
    
    _columns = {
        'usb_instance_type': fields.selection((('',''),(central_platform,'Central Platform'),(remote_warehouse,'Remote Warehouse')), string='USB Instance Type'),
        'existing_usb_instance_type': fields.function(get_existing_usb_instance_type, method=True, type='char', string="Instance Type"),
    }
    
    _sequences_to_prefix = [
        'specific_rules.sequence_production_lots',
        'stock.seq_picking_internal',
        'stock.seq_picking_in',
        'procurement_request.seq_procurement_request',
    ]
    
    _logger = logging.getLogger('setup_remote_warehouse')
    
    def _set_sync_menu_active(self, cr, uid, active):
        """ Disable connection  manager menu to stop RW from synchronising normally """
        sync_menu_xml_id_id = self.pool.get('ir.model.data')._get_id(cr, uid, 'sync_client', 'connection_manager_menu');
        sync_menu_id = self.pool.get('ir.model.data').read(cr, uid, sync_menu_xml_id_id, ['res_id'])['res_id'];
        self.pool.get('ir.ui.menu').write(cr, uid, sync_menu_id, {'active': active})
    
    def _sync_connection_manager_disconnect(self, cr, uid):
        """ reset connection on connection manager """
        server_connection_pool = self.pool.get('sync.client.sync_server_connection')
        connection_manager_ids = server_connection_pool.search(cr, uid, [])
        if connection_manager_ids:
            server_connection_pool.browse(cr, uid, connection_manager_ids[0]).disconnect()
            
    def _prefix_sequences(self, cr, uid): 
        """ add "/RW" prefix to sequences in _sequences_to_prefix to avoid conflicts with central platform """
        ir_sequence_object = self.pool.get('ir.sequence')
        
        for sequence in self._sequences_to_prefix:
            try:
                sequence_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, *sequence.split('.', 1))[1]
            except ValueError:
                self._logger.warning('Could not find sequence with XML ID: %s' % sequence)
                continue
            
            sequence_prefix = ir_sequence_object.read(cr, 1, [sequence_id], ['prefix'])[0]['prefix']
            if sequence_prefix[-3:] != 'RW/':
                ir_sequence_object.write(cr, 1, sequence_id, {'prefix' : '%sRW/' % sequence_prefix})
                
    def _fill_ir_model_data_dates(self, cr):
        """ 
        For each record in ir.model.data that has no sync_date or usb_sync_date
        set the usb_sync_date to now, so when the first usb sync is performed
        on the new remote warehouse, it will ignore all records that didn't have those dates 
        """
        cr.execute("""
            UPDATE ir_model_data
            SET sync_date = now()
            WHERE sync_date is null AND usb_sync_date is null;
        """)
        
    def _get_db_dump(self, database_name):
        """ Makes a dump of database_name and returns the SQL """
        dump = subprocess.Popen(['pg_dump', database_name, '--format=c'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        dump_sql, dump_err = dump.communicate()
        if dump_err:
            raise osv.except_osv(_("Error While Backing Up"), _("There was an error while backing up the database: %s") % dump_err)
        return dump_sql
    
    def _save_dump_file(self, dump_sql):
        """ Creates a file in the self.backup_folder_name directory containing the string dump_sql """
        home = expanduser("~")
        target_directory = home + '/' + self.backup_folder_name
        if not os.path.exists(target_directory):
            os.mkdir(target_directory)
        
        file_name = self.backup_file_name + '-' + datetime.now().strftime('%Y%M%d-%H%M%S-%f') + '.sql'
        file_path = home + '/' + self.backup_folder_name + '/' + file_name
        
        backup_file = open(file_path, 'w')
        backup_file.write(dump_sql)
        backup_file.close()
        
        return file_path

    def setup(self, cr, uid, ids, context=None):
        """
        Sets up the server as a central platform or a remote warehouse.
        
        If it is a central platform:
         - First set type to remote warehouse
         - Then set the sync_date to now for all records in ir.model.data that don't have a sync_date or usb_sync_date
         - Then make a pg_dump and save to a file on the file system
         - Then set the type to central platform 
         - Then show a wizard with a functional field to allow the user to download the dump
         
        Otherwise if it is a remote warehouse:
         - Disable the normal synchronisation menu item
         - Disconnect from the main sync server
         - Add /RW prefix to all sequences in the _sequences_to_prefix list
        """
        
        def set_entity_type(entity_id, type, context=None):
            entity_pool.write(cr, uid, entity.id, {'usb_instance_type': type}, context=context)
            
        def set_entity_date(entity_id, date, context=None):
            entity_pool.write(cr, uid, entity.id, {'clone_date': date}, context=context)
        
        wizard = self.browse(cr, uid, ids[0])
        entity_pool = self.pool.get('sync.client.entity')
        entity = entity_pool.get_entity(cr, uid, context=context)
        
        # Check that this is a valid action
        if entity.usb_instance_type:
            raise osv.except_osv('Already Setup', 'This instance is already set as a %s' % (filter(lambda x: x[0] == entity.usb_instance_type,self._columns['usb_instance_type'].selection)[0][1]))
        
        if not wizard.usb_instance_type:
            raise osv.except_osv('Please Choose an Instance Type', 'Please specify the type of instance that this is')
        
        # Set clone date
        set_entity_date(entity.id, datetime.now(), context=context)
        
        # Remote warehouse specific actions
        if wizard.usb_instance_type == self.remote_warehouse:
            self._logger.info('Setting up this instance as a remote warehouse')
            self._set_sync_menu_active(cr, uid, False)
            self._sync_connection_manager_disconnect(cr, uid)
            self._prefix_sequences(cr, uid)
        
        # Central platform specific actions          
        if wizard.usb_instance_type == self.central_platform:
            self._logger.info('Setting up this instance as a central platform')
            set_entity_type(entity.id, self.remote_warehouse, context=context)
            self._fill_ir_model_data_dates(cr)
            cr.commit()
            
            dump_sql = self._get_db_dump(cr.dbname)
            dump_file_path = self._save_dump_file(dump_sql)
            
        # mark entity as usb_instance_type 
        set_entity_type(entity.id, wizard.usb_instance_type, context=None)
        cr.commit()

        if wizard.usb_instance_type == self.remote_warehouse:
            # close wizard
            return {
                'type': 'ir.actions.act_window_close',
            }
        elif wizard.usb_instance_type == self.central_platform:
            # show wizard to download the dump
            download_dump_obj = self.pool.get('download_dump')
            wizard_id = download_dump_obj.create(cr, uid, {'dump_path': dump_file_path}, context=context)
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sync_remote_warehouse', 'wizard_download_dump')[1]
            
            return {
                'name':_("Download Remote Warehouse Database"),
                'view_mode': 'form',
                'view_id': [view_id],
                'view_type': 'form',
                'res_model': 'download_dump',
                'res_id': wizard_id,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }

    def revert(self, cr, uid, ids, context=None):

        # init
        entity_pool = self.pool.get('sync.client.entity')
        entity = entity_pool.get_entity(cr, uid, context=context)
        
        # state checks
        if not entity.usb_instance_type:
            raise osv.except_osv('Not Yet Setup', 'This instance not yet setup with an instance type, so you don\'t need to revert it')
        
        if entity.usb_instance_type != self.central_platform:
            
            # reactivate sync server connection line to let remote warehouse perform normal sync again
            self._set_sync_menu_active(cr, uid, True)
            
            # remove /RW from ir.sequence prefixes 
            ir_sequence_object = self.pool.get('ir.sequence')
            
            for sequence in self._sequences_to_prefix:
                try:
                    sequence_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, *sequence.split('.', 1))[1]
                except ValueError, v:
                    self._logger.warning('Could not find sequence with XML ID: %s' % sequence)
                    continue
                
                sequence_prefix = ir_sequence_object.read(cr, 1, [sequence_id], ['prefix'])[0]['prefix']
                if sequence_prefix[-3:] == 'RW/':
                    ir_sequence_object.write(cr, 1, sequence_id, {'prefix' : sequence_prefix[:-3]})

        # clear usb instance type
        entity_pool.write(cr, uid, entity.id, {'usb_instance_type': ''}, context=context)
        
        return {
                'type': 'ir.actions.act_window_close',
        }

setup_remote_warehouse()

