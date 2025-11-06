# -*- coding: utf-8 -*-

from osv import osv
from osv import fields

class transport_setup(osv.osv_memory):
    _name = 'transport.setup'
    _inherit = 'res.config'

    _columns = {
        'transport': fields.boolean(string='Does the system manage Transport documents: ITO / OTO ?'),
    }

    _defaults = {
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        '''
        Display the default value for fixed asset and
        update the value of is_inactivable.
        '''
        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res = super(transport_setup, self).default_get(cr, uid, fields, context=context, from_web=from_web)

        res['transport'] = setup_id.transport
        return res

    def execute(self, cr, uid, ids, context=None):
        '''
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)

        setup_obj = self.pool.get('unifield.setup.configuration')
        setup_id = setup_obj.get_config(cr, uid)
        setup_obj.write(cr, uid, [setup_id.id], {'transport': payload.transport}, context=context)
        menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'transport_mgmt', 'menu_transportation_root')[1]
        if menu_id:
            self.pool.get('ir.ui.menu').write(cr, uid, menu_id, {'active': payload.transport}, context=context)

transport_setup()
