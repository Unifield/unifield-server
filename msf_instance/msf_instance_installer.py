# -*- coding: utf-8 -*-

from osv import fields, osv
import tools
from os.path import join as opj
from tools.translate import _


class msf_instance_setup(osv.osv_memory):
    _name = 'msf_instance.setup'
    _inherit = 'res.config'

    _columns = {
         'instance_id': fields.many2one('msf.instance', string="Proprietary instance", required=True),
    }

    def get_instance(self, cr, uid, context=None):
        instance_ids = self.pool.get('msf.instance').search(cr, uid, [], limit=1)
        return instance_ids and instance_ids[0] or False

    _defaults = {
        'instance_id': get_instance,
    }

    def execute(self, cr, uid, ids, context=None):
        res = self.read(cr, uid, ids)
        self.pool.get('res.company').write(cr, uid, [self.pool.get('res.users').browse(cr, uid, uid).company_id.id], {'instance_id': res[0]['instance_id']})
        return {}

msf_instance_setup()
