# -*- coding: utf-8 -*-

from osv import fields, osv
import tools
from os.path import join as opj
from tools.translate import _


class msf_instance_setup(osv.osv_memory):
    _name = 'msf_instance.setup'
    _inherit = 'res.config'

    _columns = {
         'instance_id': fields.many2one('msf.instance', string="Proprietary instance", required=True, domain=[('instance', '=', False)]),
    }

    def check_name(self, cr, uid, id, instance_id, context=None):
        if instance_id:
            instance_code = self.pool.get('msf.instance').read(cr, uid, instance_id, ['code'])['code']
            entity_obj = self.pool.get('sync.client.entity').get_entity(cr, uid, context=context)
            if instance_code != entity_obj.name: #instance_code not in entity_obj.name:
                return {'warning': {'title': _('Warning'), 'message': _("The proprietary instance's name is not the same as the instance's name")}}
        return {}

    def get_instance(self, cr, uid, context=None):
        entity_obj = self.pool.get('sync.client.entity')
        if entity_obj:
            entity = entity_obj.get_entity(cr, uid, context=context)
            instance_ids = self.pool.get('msf.instance').search(cr, uid, [('code', '=', entity.name), ('instance','=', False)])
            if instance_ids:
                return instance_ids[0]
        return False

    _defaults = {
        'instance_id': get_instance,
    }

    def execute(self, cr, uid, ids, context=None):
        res = self.read(cr, uid, ids)
        self.pool.get('res.company').write(cr, uid, [self.pool.get('res.users').browse(cr, uid, uid).company_id.id], {'instance_id': res[0]['instance_id']})
        return {}

msf_instance_setup()
