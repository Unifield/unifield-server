from osv import osv, fields
import logging

class setup_remote_warehouse(osv.osv_memory):
    _name = 'setup_remote_warehouse'
    
    def get_existing_usb_instance_type(self, cr, uid, ids, field_name=None, arg=None, context=None):
        return self.pool.get('sync.client.entity').get_entity(cr, uid).usb_instance_type
    
    _defaults = {
        'existing_usb_instance_type' : get_existing_usb_instance_type
    }
    
    _columns = {
        'clone_date': fields.datetime('Backup Date And Time', help='The date that the Central Platform database used to create this instance was backed up'),
        'usb_instance_type': fields.selection((('',''),('central_platform','Central Platform'),('remote_warehouse','Remote Warehouse')), string='USB Instance Type'),
        'existing_usb_instance_type': fields.function(get_existing_usb_instance_type, method=True, type='char', string="Instance Type"),
    }
    
    _sequences_to_prefix = [
        'specific_rules.sequence_production_lots',
    ]
    
    _logger = logging.getLogger('setup_remote_warehouse')
    
    def _dbid_from_xmlid(self, cr, module, model):
        ir_model_data_object = self.pool.get('ir.model.data')
        ir_model_data_id = ir_model_data_object._get_id(cr, 1, module, model)
        return ir_model_data_object.read(cr, 1, [ir_model_data_id], ['res_id'])[0]['res_id']
    
    def setup(self, cr, uid, ids, context=None):
        
        # init
        wizard = self.browse(cr, uid, ids[0])
        entity_pool = self.pool.get('sync.client.entity')
        entity = entity_pool.get_entity(cr, uid, context=context)
        
        # state checks
        if entity.usb_instance_type:
            raise osv.except_osv('Already Setup', 'This instance is already set as a %s' % (filter(lambda x: x[0] == entity.usb_instance_type,self._columns['usb_instance_type'].selection)[0][1]))
        
        if not wizard.usb_instance_type:
            raise osv.except_osv('Please Choose an Instance Type', 'Please specify the type of instance that this is')
        
        if not wizard.usb_instance_type == 'central_platform':
            # set inactive sync server connection line to stop RW from ever connecting
            server_connection_pool = self.pool.get('sync.client.sync_server_connection')
            server_connection_ids = server_connection_pool.search(cr, uid, [])
            server_connection_pool.write(cr, uid, server_connection_ids, {'active': False})
            
            # add "/RW" prefix to sequences in _sequences_to_prefix
            ir_sequence_object = self.pool.get('ir.sequence')
            
            for sequence in self._sequences_to_prefix:
                try:
                    sequence_id = self._dbid_from_xmlid(cr, *sequence.split('.'))
                except ValueError:
                    self._logger.warning('Could not find sequence with XML ID: %s' % sequence)
                    continue
                
                sequence_prefix = ir_sequence_object.read(cr, 1, [sequence_id], ['prefix'])[0]['prefix']
                ir_sequence_object.write(cr, 1, sequence_id, {'prefix' : '%s/RW' % sequence_prefix})
        
        # mark entity as usb_instance_type and set clone date
        new_vals = {
            'clone_date': wizard.clone_date,
            'usb_instance_type': wizard.usb_instance_type,
        }
        entity_pool.write(cr, uid, entity.id, new_vals, context=context)
        
        return {
                'type': 'ir.actions.act_window_close',
        }
        
    def revert(self, cr, uid, ids, context=None):

        # init
        wizard = self.browse(cr, uid, ids[0])
        entity_pool = self.pool.get('sync.client.entity')
        entity = entity_pool.get_entity(cr, uid, context=context)
        
        # state checks
        if not entity.usb_instance_type:
            raise osv.except_osv('Not Yet Setup', 'This instance not yet setup with an instance type, so you don\'t need to revert it')
        
        if entity.usb_instance_type != 'central_platform':
            
            # reactive sync server connection line to let remote warehouse perform normal sync again
            server_connection_pool = self.pool.get('sync.client.sync_server_connection')
            active_server_connection_ids = server_connection_pool.search(cr, uid, [('active','=',True)])
            inactive_server_connection_ids = server_connection_pool.search(cr, uid, [('active','=',False)])
            
            if active_server_connection_ids:
                server_connection_pool.unlink(cr, uid, inactive_server_connection_ids)
            else:
                server_connection_pool.write(cr, uid, inactive_server_connection_ids, {'active': True})
            
            # remove /RW from ir.sequence prefixes 
            ir_sequence_object = self.pool.get('ir.sequence')
            
            for sequence in self._sequences_to_prefix:
                try:
                    sequence_id = self._dbid_from_xmlid(cr, *sequence.split('.'))
                except ValueError, v:
                    self._logger.warning('Could not find sequence with XML ID: %s' % sequence)
                    continue
                
                sequence_prefix = ir_sequence_object.read(cr, 1, [sequence_id], ['prefix'])[0]['prefix']
                if sequence_prefix[-3:] == '/RW':
                    ir_sequence_object.write(cr, 1, sequence_id, {'prefix' : sequence_prefix[:-3]})

        # mark entity as remote warehouse and set clone date
        entity_pool.write(cr, uid, entity.id, {'usb_instance_type': ''}, context=context)
        
        return {
                'type': 'ir.actions.act_window_close',
        }

setup_remote_warehouse()