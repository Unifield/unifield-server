# -*- coding: utf-8 -*-

from osv import osv
from osv import fields
from tools.translate import _
from tools.misc import email_send

class hq_monitor(osv.osv):
    _name = 'hq.monitor'
    _description = 'Email alert'
    _rec_name = 'title'

    _columns = {
        'email': fields.char('Destination emails', size=1024, help='comma separated list of email addresses'),
        'title': fields.char('Title', size=1024, required=1),
        'not_run_data': fields.integer('Notification threshold for update'),
        'not_run_msg': fields.integer('Notification threshold for message'),
        'last_instance_id': fields.integer('ID of the last message checked for this instance'),
        'last_other_instances_id': fields.integer('ID of the last message checked for the other instances'),
    }

    _defaults = {
        'last_instance_id': 0,
        'last_other_instances_id': 0,
        'not_run_data': 1,
        'not_run_msg': 1,
    }

    def check_not_run(self, cr, uid, context=None):
        monitor_obj = self.pool.get('sync.monitor')
        instance = self.pool.get('res.users').get_browse_user_instance(cr, uid, context)


        ids = self.search(cr, uid, [('email', '!=', False)])
        if not ids:
            return False

        template = self.browse(cr, uid, ids[0])
        # KO
        max_instance_id = monitor_obj.search(cr, uid, [('status', '=', 'ok'), ('instance_id', '=', instance.id), ('id', '>', template.last_instance_id)], order='id desc', limit=1)
        max_other_instances_id = monitor_obj.search(cr, uid, [('instance_id', '!=', instance.id)], order='id desc', limit=1)

        if not max_other_instances_id and not max_instance_id:
            return False

        emails = template.email.split(',')
        subject = _('Not Run on UniField instances')
        body = _("""Hello,

On %s, the system detected Not Run data:
""") % (instance and instance.name or '', )

        monitor_ids = []

        if max_other_instances_id:
            max_other_instances_id = max_other_instances_id[0]
            cr.execute(""" select max(id) from sync_monitor mon
                where mon.id > %s and
                mon.id <= %s and
                instance_id != %s
                group by instance_id
            """, (template.last_other_instances_id, max_other_instances_id, instance.id))
            monitor_ids = [x[0] for x in cr.fetchall()]
        else:
            max_other_instances_id = template.last_other_instances_id

        if max_instance_id:
            max_instance_id = max_instance_id[0]
            monitor_ids.append(max_instance_id)
        else:
            max_instance_id = template.last_instance_id

        found = False
        for monitor in monitor_obj.read(cr, uid, monitor_ids, ['instance_id', 'nb_msg_not_run', 'nb_data_not_run']):
            if monitor['nb_msg_not_run'] >= template.not_run_msg or monitor['nb_data_not_run'] >= template.not_run_data:
                found = True
                body += "  - "
                error = []
                if monitor['nb_msg_not_run'] >= template.not_run_msg:
                    error.append(_("%s message%s") % (monitor['nb_msg_not_run'], monitor['nb_msg_not_run'] > 1 and 's' or ''))
                if monitor['nb_data_not_run'] >= template.not_run_data:
                    error.append(_("%s update%s") % (monitor['nb_data_not_run'], monitor['nb_data_not_run'] > 1 and 's' or ''))
                body += _("%s from instance %s.\n") % (' and '.join(error), monitor['instance_id'] and monitor['instance_id'][1] or '')
        if found:
            body += _("""

This is an automatically generated email, please do not reply.
""")
            email_send(False, emails, subject, body)

        self.write(cr, uid, ids[0], {'last_instance_id': max_instance_id, 'last_other_instances_id': max_other_instances_id})
        return True

hq_monitor()
