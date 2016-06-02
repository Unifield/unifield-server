# -*- coding: utf-8 -*-

from osv import fields, osv
import tools
from os.path import join as opj
from tools.translate import _


class msf_instance_setup(osv.osv_memory):
    _name = 'msf_instance.setup'
    _inherit = 'res.config'

    _columns = {
         'instance_id': fields.many2one('msf.instance', string="Proprietary instance", required=True, domain=[('instance', '=', False), ('restrict_level_from_entity', '=', True)]),
         'message': fields.text(string='message', readonly=True),
         'first_run': fields.boolean(string='First Run'),
    }

    def get_instance(self, cr, uid, context=None):
        return False
#        entity_obj = self.pool.get('sync.client.entity')
#        if entity_obj:
#            entity = entity_obj.get_entity(cr, uid, context=context)
#            instance_ids = self.pool.get('msf.instance').search(cr, uid, [('code', '=', entity.name), ('instance','=', False)])
#            if instance_ids:
#                return instance_ids[0]
#        return False

    _defaults = {
        'instance_id': get_instance,
        'message': None,
        'first_run': lambda *a: True,
    }

    def execute(self, cr, uid, ids, context=None):
        res = self.read(cr, uid, ids)
        self.pool.get('res.company').write(cr, uid, [self.pool.get('res.users').browse(cr, uid, uid).company_id.id], {'instance_id': res[0]['instance_id']})
        return {}

    def action_check(self, cr, uid, ids, context=None):
        current_obj = self.read(cr, uid, ids)[0]
        if not current_obj['first_run']:
            res = self.read(cr, uid, ids)
            self.pool.get('res.company').write(cr, uid, [self.pool.get('res.users').browse(cr, uid, uid).company_id.id], {'instance_id': res[0]['instance_id']})
            return self.action_next(cr, uid, ids, context=context)
        if current_obj['instance_id']:
            instance_code = self.pool.get('msf.instance').read(cr, uid, current_obj['instance_id'], ['code'])['code']
            entity_obj = self.pool.get('sync.client.entity').get_entity(cr, uid, context=context)
            vals = {
                    'message': "You have selected the proprietary instance '%s' "\
                        "for this instance '%s'. This choice cannot be changed.\n"\
                        "Do you want to continue?" % (instance_code, entity_obj.name),
                    'first_run': False,
            }
            self.write(cr, uid, [ids[0]], vals, context)
        return {
            'view_type': 'form',
            "view_mode": 'form',
            'res_model': 'msf_instance.setup',
            'res_id': ids[0],
            'view_id':self.pool.get('ir.ui.view')\
                .search(cr,uid,[('name','=','Instance Configuration')]),
            'type': 'ir.actions.act_window',
            'target':'new',
            }

msf_instance_setup()
