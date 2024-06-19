# -*- coding: utf-8 -*-

from osv import fields, osv


class msf_instance_setup(osv.osv_memory):
    _name = 'msf_instance.setup'
    _inherit = 'res.config'

    _columns = {
        'instance_id': fields.many2one('msf.instance', string="Proprietary instance", required=True, domain=[('instance', '=', False), ('restrict_level_from_entity', '=', True)]),
        'message': fields.text(string='', readonly=True),
        'first_run': fields.boolean(string='First Run'),
    }

    def get_instance(self, cr, uid, context=None):
        return False

    _defaults = {
        'instance_id': get_instance,
        'message': None,
        'first_run': lambda *a: True,
    }

    def execute(self, cr, uid, ids, context=None):

        # because the step to define the langage is now hidden, do the action
        # done during this step here.
        lang_setup = self.pool.get('lang.setup')
        lang_setup.set_lang(cr, uid, 'en_MF', context=context)
        return {}

    def action_check(self, cr, uid, ids, context=None):
        current_obj = self.read(cr, uid, ids)[0]
        if not current_obj['first_run']:
            self.pool.get('res.company').write(cr, uid, [self.pool.get('res.users').browse(cr, uid, uid).company_id.id], {'instance_id': current_obj['instance_id']})

            # clean instance groups if not HQ:
            level = self.pool.get('msf.instance').read(cr, uid, current_obj['instance_id'], ['level'])['level']
            if level != 'section':
                # do a write on all users to update their group by removing the to hight level ones
                user_obj = self.pool.get('res.users')
                user_ids = user_obj.search(cr, uid, [], context=context)
                if 1 in user_ids:
                    # admin can stay member of higher groups
                    user_ids.remove(1)
                read_result = user_obj.read(cr, uid, user_ids, ['groups_id'],
                                            context=context)
                for user in read_result:
                    if user['groups_id']:
                        user_obj.write(cr, uid, user['id'],
                                       {'groups_id': [(6, 0, user['groups_id'])]},
                                       context=context)

                # trigger update on account.period.state closed by sync
                self.pool.get('patch.scripts').update_us_435_2(cr, uid)


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
            self._set_previous_todo(cr, uid, 'open', context)
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
