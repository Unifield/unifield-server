# -*- coding: utf-8 -*-

from osv import osv

class group_type(osv.osv):
    _name = 'sync.server.group_type'
    _inherit = 'sync.server.group_type'

    def init(self, cr):
        if hasattr(super(group_type, self), 'init'):
            super(group_type, self).init(cr)

        if cr.table_exists('sync_server_group_type'):
            # fix xmlid for groups manually loaded before module installation
            for xmlid, group_name in [
                ('group_type_oc', 'OC'),
                ('group_type_usb', 'USB'),
                ('group_type_misson', 'MISSION'),
                ('group_type_coordo', 'COORDINATIONS'),
                ('group_type_hq_mission', 'HQ + MISSION'),
            ]:
                cr.execute("select id from sync_server_group_type where name=%s", (group_name, ))
                res_id = cr.fetchone()
                if res_id and res_id[0]:
                    cr.execute("select id from ir_model_data where name=%s and module='msf_sync_data_server'", (xmlid, ))
                    if not cr.fetchone():
                        cr.execute("""insert into ir_model_data (name, module, model, res_id, noupdate, force_recreation)
                            values (%s, 'msf_sync_data_server', 'sync.server.group_type', %s, 'f', 'f') """, (xmlid, res_id[0]))
group_type()
