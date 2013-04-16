from osv import osv, fields

class setup_remote_warehouse(osv.osv_memory):
    _name = 'setup_remote_warehouse'
    _columns = {
        'clone_date': fields.datetime('Backup Date And Time', help='The date that the Central Platform database used to create this instance was backed up'),
        'rw': fields.boolean('Remote Warehouse'),
        'cp': fields.boolean('Central Platform'),
    }
    
    def setup(self, cr, uid, ids, context=None):
        
        # mark entity as remote warehouse and set clone date
        wizard = self.browse(cr, uid, ids[0])
        entity_pool = self.pool.get('sync.client.entity')
        entity = entity_pool.get_entity(cr, uid, context=context)
        
        if entity.is_remote_warehouse or entity.is_central_platform:
            type = '';
            if entity.is_remote_warehouse:
                type = 'Remote Warehouse'
            else:
                type = 'Central Platform'
            raise osv.except_osv('Already Setup', 'Entity is already set as a %s!' % type)
        
        new_vals = {
            'clone_date': wizard.clone_date,
            'is_remote_warehouse': wizard.rw,
            'is_central_platform': wizard.cp,
        }
        
        entity_pool.write(cr, uid, entity.id, new_vals, context=context)
        
        return {
                'type': 'ir.actions.act_window_close',
        }

setup_remote_warehouse()