import os
from datetime import datetime

import netsvc
from tools.translate import _
from tools import config
from osv import osv, fields
import logging

class setup_remote_warehouse(osv.osv_memory):
    _name = 'setup_remote_warehouse'
    
    def get_existing_usb_instance_type(self, cr, uid, ids, field_name=None, arg=None, context=None):
        return self.pool.get('sync.client.entity').get_entity(cr, uid).usb_instance_type
    
    def _set_entity_type(self, cr, uid, entity_id, type, context=None):
        self.pool.get('sync.client.entity').write(cr, uid, entity_id, {'usb_instance_type': type}, context=context)
    
    def _set_entity_date(self, cr, uid, entity_id, date, context=None):
        self.pool.get('sync.client.entity').write(cr, uid, entity_id, {'clone_date': date}, context=context)
    
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
    
    # This is the list of the code of sequences
    _sequences_to_suffix = [
        'stock.lot.serial',
        'stock.picking.in',
        'picking.ticket',
        'stock.picking.internal',
        'stock.picking.out',
        'procurement.request',
        'sale.order',
        'purchase.order',
        'kit.creation',
        'kit.lot',
        'stock.lot.tracking',
        'ppl',
        'product.asset',
        'return.claim',
        'shipment',
    ]
    
    _logger = logging.getLogger('setup_remote_warehouse')
    
    def _set_sync_menu_active(self, cr, uid, active):
        """ Disable connection  manager menu to stop RW from synchronising normally """
        sync_menu_xml_id_id = self.pool.get('ir.model.data')._get_id(cr, uid, 'sync_client', 'connection_manager_menu');
        sync_menu_id = self.pool.get('ir.model.data').read(cr, uid, sync_menu_xml_id_id, ['res_id'])['res_id'];
        self.pool.get('ir.ui.menu').write(cr, uid, sync_menu_id, {'active': active})

    def _set_location_menu_in_rw(self, cr, uid, active):
        #US-702: Remove 2 menus on RW instance 
        menu_xml_id_id = self.pool.get('ir.model.data')._get_id(cr, uid, 'msf_config_locations', 'menu_stock_location_configuration_wizard');
        menu_id = self.pool.get('ir.model.data').read(cr, uid, menu_xml_id_id, ['res_id'])['res_id'];
        self.pool.get('ir.ui.menu').write(cr, uid, menu_id, {'active': active})
        
        menu_xml_id_id = self.pool.get('ir.model.data')._get_id(cr, uid, 'msf_config_locations', 'menu_stock_remove_location_wizard');
        menu_id = self.pool.get('ir.model.data').read(cr, uid, menu_xml_id_id, ['res_id'])['res_id'];
        self.pool.get('ir.ui.menu').write(cr, uid, menu_id, {'active': active})
           
    def _sync_disconnect(self, cr, uid):
        """ reset connection on connection manager """
        server_connection_pool = self.pool.get('sync.client.sync_server_connection')
        connection_manager_ids = server_connection_pool.search(cr, uid, [])
        if connection_manager_ids:
            server_connection_pool.disconnect(cr, uid)
            
    def _fill_ir_model_data_dates(self, cr):
        """ 
        For each record in ir.model.data that has no sync_date or usb_sync_date
        set the usb_sync_date to now, so when the first usb sync is performed
        on the new remote warehouse, it will ignore all records that didn't have those dates 
        """
        cr.execute("""
            UPDATE ir_model_data
            SET usb_sync_date = now()
            WHERE sync_date is null AND usb_sync_date is null;
        """)

    def _set_sequence_suffix(self, cr, uid, suffix="", context=None):
        """
        Put or remove the suffix of all the sequences in _sequences_to_suffix

        :param cr: Cursor to the database
        :param uid: ID of the user that calls the method
        :param suffix: Suffix that will be applied on all sequences
        :param context: Context of the call

        :return Nothing
        """
        if context is None:
            context = {}
        seq_obj = self.pool.get('ir.sequence')

        # US-27: Use this value and store in context for the reverting values of sequences        
        dict_seq_values = {}
        if context.get('dict_seq_values', False):
            dict_seq_values = context['dict_seq_values']         

        for seq_code in self._sequences_to_suffix:
            seq_ids = seq_obj.search(cr, uid, [('code', '=', seq_code)], context=context)
            for seq in seq_obj.browse(cr, uid, seq_ids, context=context):
                old_suffix = seq.suffix and seq.suffix.replace('-RW', '') or ''
                #US-27: If it's a RW instance, then just reset all the sequence for them, to restart by 1.
                temp = 'ir_sequence_%03d' % seq['id']
                if suffix == '-RW':
                    # US-27: Reset the sequence for the RW instance
                    cr.execute("SELECT 0 FROM pg_class where relname = '%s'" % temp)  # not_a_user_entry
                    res = cr.dictfetchone()
                    if res:
                        cr.execute("select last_value from %s" % temp)  # not_a_user_entry
                        res = cr.dictfetchone()
                        if res:
                            dict_seq_values[temp] = res['last_value']
                        cr.execute("ALTER SEQUENCE " + temp +" RESTART WITH " + str(1))  # not_a_user_entry
                else:
                    # US-27: Revert all the sequence that has been set before
                    value = dict_seq_values.get(temp, False)
                    if value:
                        cr.execute("ALTER SEQUENCE " + temp +" RESTART WITH " + str(value + 1))  # not_a_user_entry
                new_suffix = '%s%s' % (old_suffix, suffix)
                seq_obj.write(cr, uid, [seq.id], {'suffix': new_suffix}, context=context)

        
        if suffix == '-RW': # US-27: Store it for reverting purpose
            context['dict_seq_values'] = dict_seq_values
        elif context.get('dict_seq_values', False):
            del context['dict_seq_values']
        
    def _create_push_sequence(self, cr, uid, context=None):
        """
        Create the push sequence for instances of the remote where house

        :param cr: Cursor to the database
        :param uid: ID of the user that calls the method
        :param suffix: Suffix that will be applied on all sequences
        :param context: Context of the call

        :return Nothing
        """
        seq_obj = self.pool.get('ir.sequence')
        seq_code = 'rw.push.seq'

        seq_ids = seq_obj.search(cr, uid, [('code', '=', seq_code)], context=context)
        if len(seq_ids) > 0:
            seq_obj.write(cr, uid, seq_ids, {'number_next': 1}, context=context)
            
            entity_ob = self.pool.get('sync.client.entity')
            entity = entity_ob.get_entity(cr, uid, context=context)
            entity_ob.write(cr, uid, entity.id, {'rw_pull_sequence': 0}, context=context)
        else:
            seq_typ_pool = self.pool.get('ir.sequence.type')
            types = {'name':'RW push sequence', 'code':seq_code}
            seq_typ_pool.create(cr, uid, types)
            seq = {
                'name':'RW push sequence', 
                'code':seq_code, 
                'prefix':'', 
                'padding':5}
            seq_obj.create(cr, uid, seq)
        
    def _setup_remote_warehouse(self, cr, uid, entity_id, context=None):
        if context is None:
            context = {}
        """ Perform actions necessary to set up this instance as a remote warehouse """
        self._set_sync_menu_active(cr, uid, False)
        # US-702: Remove location menu items in RW
        #self._set_location_menu_in_rw(cr, uid, False)
     
        self._sync_disconnect(cr, uid)
        self._set_entity_type(cr, uid, entity_id, self.remote_warehouse)
        self._set_sequence_suffix(cr, uid, suffix="-RW", context=context)
        self._create_push_sequence(cr, uid, context=context)
    
    def _setup_central_platform(self, cr, uid, entity_id, context=None):
        if context is None:
            context = {}
        """ First set up as remote warehouse, save db backup, then revert changes and setup as central platform """
        # Fill ir model data dates then setup as remote warehouse
        self._fill_ir_model_data_dates(cr)
        
        #UF-2483: Make a fake sync on messages and set them all the sync before 
        self.pool.get('sync.client.entity').usb_push_create_message_initial(cr, uid)
        self._logger.info('Run the initial USB messages sync')
        self._setup_remote_warehouse(cr, uid, entity_id, context=context)
        
        # commit changes to db then take and save backup to file
        cr.commit()
        db_dump = self._get_db_dump(cr.dbname)
        dump_file_path = self._save_dump_file(db_dump)
        
        # revert remote warehouse changes and setup as central platform
        self._revert_remote_warehouse(cr, uid, entity_id,context=context)
        self._set_entity_type(cr, uid, entity_id, self.central_platform)
        # us-702: Reset it back for the current instance CP
        #self._set_location_menu_in_rw(cr, uid, True)
        
        #US-27: Remove the following call, as it is called already in _revert_remote_warehouse
#        self._set_sequence_suffix(cr, uid, suffix="", context=None)
        
        return dump_file_path
    
    def _revert_remote_warehouse(self, cr, uid, entity_id, context=None):
        """ Enables sync menu, un-prefixes sequences and clears entity usb instance type """
        self._set_sync_menu_active(cr, uid, True)
        self._set_entity_type(cr, uid, entity_id, "", context=context)
        self._set_sequence_suffix(cr, uid, suffix="", context=context)
    
    def _revert_central_platform(self, cr, uid, entity_id, context=None):
        self._set_entity_type(cr, uid, entity_id, "", context=context)
        #US-208: Do not change the suffixes of the documents
        self._set_sequence_suffix(cr, uid, suffix="", context=context)
        
    def _get_db_dump(self, database_name):
        """ Makes a dump of database_name and returns the base64 SQL """
        db_service = netsvc.ExportService.getService('db')
        dump_sql_base64 = db_service.exp_dump(database_name)
        return dump_sql_base64
    
    def _save_dump_file(self, dump_sql_base64):
        """ Creates a file in the self.backup_folder_name directory containing the string dump_sql_base64 """
        path = os.path.join(config['root_path'])
        target_directory = os.path.join(path, self.backup_folder_name)
        if not os.path.exists(target_directory):
            os.mkdir(target_directory)
        
        file_name = self.backup_file_name + '-' + datetime.now().strftime('%Y%M%d-%H%M%S-%f') + '.dump'
        file_path = os.path.join(target_directory, file_name)
        
        backup_file = open(file_path, 'w')
        backup_file.write(dump_sql_base64)
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
         - Add -RW suffix to all sequences in the _sequences_to_suffix list
        """
        
        # parameter validation
        if not isinstance(ids, (list, tuple)):
            raise TypeError("Expected IDS given to setup remote warehouse wizard to be a list or tuple")
        
        if len(ids) > 1:
            raise ValueError("Cannot run setup remote warehouse on multiple wizards")
        
        # get entity object
        wizard = self.browse(cr, uid, ids[0])
        entity_pool = self.pool.get('sync.client.entity')
        entity = entity_pool.get_entity(cr, uid, context=context)
        
        # Check that this is a valid action
        if entity.usb_instance_type:
            raise osv.except_osv('Already Setup', 'This instance is already set as a %s' % (filter(lambda x: x[0] == entity.usb_instance_type,self._columns['usb_instance_type'].selection)[0][1]))
        
        if not wizard.usb_instance_type:
            raise osv.except_osv('Please Choose an Instance Type', 'Please specify the type of instance that this is')
        
        # Set clone date
        self._set_entity_date(cr, uid, entity.id, datetime.now(), context=context)
        
        # Remote warehouse specific actions
        if wizard.usb_instance_type == self.remote_warehouse:
            self._logger.info('Setting up this instance as a remote warehouse')
            self._setup_remote_warehouse(cr, uid, entity.id)
        
        # Central platform specific actions          
        if wizard.usb_instance_type == self.central_platform:
            self._logger.info('Setting up this instance as a central platform')
            dump_file_path = self._setup_central_platform(cr, uid, entity.id)
            
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
        """ Undo changes made by the setup function """
        # Get entity info
        entity_pool = self.pool.get('sync.client.entity')
        entity = entity_pool.get_entity(cr, uid, context=context)
        
        # state checks
        if not entity.usb_instance_type:
            raise osv.except_osv('Not Yet Setup', 'This instance not yet setup with an instance type, so you don\'t need to revert it')

        # Remote warehouse specific actions  
        if entity.usb_instance_type == self.remote_warehouse:
            self._revert_remote_warehouse(cr, uid, entity.id)

        # Central platform specific actions
        if entity.usb_instance_type == self.central_platform:
            self._revert_central_platform(cr, uid, entity.id)
        
        # Close wizard
        return {
                'type': 'ir.actions.act_window_close',
        }

setup_remote_warehouse()
