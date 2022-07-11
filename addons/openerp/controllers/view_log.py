###############################################################################
#
#  Copyright (C) 2007-TODAY OpenERP SA. All Rights Reserved.
#
#  $Id$
#
#  Developed by OpenERP (http://openerp.com) and Axelor (http://axelor.com).
#
#  The OpenERP web client is distributed under the "OpenERP Public License".
#  It's based on Mozilla Public License Version (MPL) 1.1 with following 
#  restrictions:
#
#  -   All names, links and logos of OpenERP must be kept as in original
#      distribution without any changes in all software screens, especially
#      in start-up page and the software header, even if the application
#      source code has been changed or updated or code has been added.
#
#  You can see the MPL licence at: http://www.mozilla.org/MPL/MPL-1.1.html
#
###############################################################################
from openerp.controllers import SecuredController
from openerp.utils import rpc

from openobject.tools import expose

import base64
import urllib
import zlib

class progress_bar(SecuredController):
    _cp_path = '/openerp/progressbar'

    @expose('json')
    def get(self, id, model, job_id):
        job = rpc.RPCProxy('job.in_progress').read(int(job_id))
        if not job or job['state'] == 'done' or job['res_id'] != int(id) or job['model'] != model:
            url = ''
            if job['target_link']:
                payload = str({
                    'action': job['target_link'],
                    'data': {}
                })
                compressed_payload = base64.urlsafe_b64encode(zlib.compress(payload))
                url = ('/openerp/execute?' + urllib.urlencode({'payload': compressed_payload}))
            return {'progress': 100, 'state': 'done', 'target': url, 'target_name': job['target_name'], 'src_name': job['src_name'], 'job_name': job['name']}

        percent = 100*(job['nb_processed'] or 0)/(job['total'] or 1)
        if job['state'] == 'error':
            return {'state': 'error', 'errormsg': job['error'], 'progress': percent}

        return {'progress': percent, 'state': 'in-progress'}

    @expose('json')
    def setread(self, id, model, job_id):
        job_obj = rpc.RPCProxy('job.in_progress')
        job_id = job_obj.search([('id', '=', int(job_id)), ('res_id', '=', int(id)), ('model', '=', model)])
        if job_id:
            job_obj.write(job_id, {'read': True})

        return {}

    @expose(template="/openerp/controllers/templates/progress.mako")
    def index(self, id, model, job_id):
        return {'id': id, 'model': model, 'job_id': job_id}


class View_Log(SecuredController):

    _cp_path = "/openerp/viewlog"

    fields = [
        ('id', _('ID')),
        ('create_uid', _('Creation User')),
        ('create_date', _('Creation Date')),
        ('write_uid', _('Latest Modification by')),
        ('write_date', _('Latest Modification Date')),
        ('uid', _('Owner')),
        ('gid', _('Group Owner')),
        ('level', _('Access Level')),
        ('xmlid',_('Internal module data ID'))
    ]

    @expose(template="/openerp/controllers/templates/view_log.mako")
    def index(self, id=None, model=None):

        values = {}
        fields = self.fields[:]
        if id:
            res = rpc.session.execute('object', 'execute', model,
                                      'perm_read', [id], rpc.session.context)

            for line in res:
                for field, label in self.fields:
                    if line.get(field) and field in ('create_uid','write_uid','uid'):
                        line[field] = line[field][1]

                    values[field] = ustr(line.get(field) or '/')

            if model == 'product.product':
                xmlid = rpc.session.execute('object', 'execute', model, 'read', [id], ['xmlid_code'], rpc.session.context)
                values['xmlid_code'] = xmlid[0]['xmlid_code']
                fields.append(('xmlid_code', _('UniData xmlid_code')))

            if rpc.session.uid == 1:
                model_ids = rpc.session.execute('object', 'execute', 'ir.model', 'search', [('model', '=', model)])
                if model_ids:
                    fields.insert(7, ('model_sdref', 'Model Sdref'))
                    values['model_sdref'] = 'sd.%s' % rpc.session.execute('object', 'execute', 'ir.model', 'get_sd_ref', model_ids[0])

        return {'values': values, 'fields': fields, 'rpc': rpc, 'model': model}


class Show_Fields(SecuredController):

    _cp_path = "/openerp/showfields"

    @expose(template="/openerp/controllers/templates/show_fields.mako")
    def index(self, model=None):
        model_fields = rpc.session.execute('object', 'execute', model, 'fields_get', False, rpc.session.context)
        res = {'model': model}
        if model_fields:
            res.update({'model_fields': model_fields.items()})
        return res
