from osv import osv, fields

class setup_remote_warehouse(osv.osv_memory):
    _name = 'setup_remote_warehouse'
    _columns = {
        'clone_date': fields.datetime('Backup Date And Time', help='The date that the Central Platform database used to create this instance was backed up'),
        'usb_instance_type': fields.selection((('',''),('central_platform','Central Platform'),('remote_warehouse','Remote Warehouse')), string='USB Instance Type'),
    }
    
    def setup(self, cr, uid, ids, context=None):
        
        # mark entity as remote warehouse and set clone date
        wizard = self.browse(cr, uid, ids[0])
        entity_pool = self.pool.get('sync.client.entity')
        entity = entity_pool.get_entity(cr, uid, context=context)
        
        if entity.usb_instance_type:
            raise osv.except_osv('Already Setup', 'This instance is already set as a %s' % (filter(lambda x: x[0] == entity.usb_instance_type,self._columns['usb_instance_type'].selection)[0][1]))
        
        if not wizard.usb_instance_type:
            raise osv.except_osv('Please Choose an Instance Type', 'Please specify the type of instance that this is')
        
        new_vals = {
            'clone_date': wizard.clone_date,
            'usb_instance_type': wizard.usb_instance_type,
        }
        
        entity_pool.write(cr, uid, entity.id, new_vals, context=context)
        
        return {
                'type': 'ir.actions.act_window_close',
        }

setup_remote_warehouse()