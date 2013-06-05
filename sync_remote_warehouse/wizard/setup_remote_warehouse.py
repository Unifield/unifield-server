from osv import osv, fields

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
        
        # mark entity as remote warehouse and set clone date
        new_vals = {
            'clone_date': wizard.clone_date,
            'usb_instance_type': wizard.usb_instance_type,
        }
        
        entity_pool.write(cr, uid, entity.id, new_vals, context=context)
        
        # set inactive sync server connection line to stop RW from ever connecting
        if not wizard.usb_instance_type == 'central_platform':
            server_connection_pool = self.pool.get('sync.client.sync_server_connection')
            server_connection_ids = server_connection_pool.search(cr, uid, [])
            server_connection_pool.write(cr, uid, server_connection_ids, {'active': False})
        
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
        
        # mark entity as remote warehouse and set clone date
        new_vals = {
            'usb_instance_type': '',
        }
        
        entity_pool.write(cr, uid, entity.id, new_vals, context=context)
        
        # deactivate sync server connection line to stop RW from connecting
        server_connection_pool = self.pool.get('sync.client.sync_server_connection')
        active_server_connection_ids = server_connection_pool.search(cr, uid, [('active','=',True)])
        inactive_server_connection_ids = server_connection_pool.search(cr, uid, [('active','=',False)])
        
        if active_server_connection_ids:
            server_connection_pool.unlink(cr, uid, inactive_server_connection_ids)
        else:
            server_connection_pool.write(cr, uid, inactive_server_connection_ids, {'active': True})
        
        return {
                'type': 'ir.actions.act_window_close',
        }

setup_remote_warehouse()