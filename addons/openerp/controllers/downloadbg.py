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
import cherrypy

from openerp.controllers import SecuredController
from openerp.utils import rpc
from openobject.tools import expose

import actions

class DownLoadBg(SecuredController):

    _cp_path = "/openerp/downloadbg"

    @expose(template="/openerp/controllers/templates/downloadbg.mako")
    def index(self, res_id):
    
        download = rpc.RPCProxy('memory.background.report')
        data_bg = download.read(int(res_id), ['report_id', 'percent', 'report_name', 'finished'], rpc.session.context)
        finish = ""
        finished = "False"
        if data_bg['percent'] >= 1.00:
            if not data_bg['finished']:
                download.write([int(res_id)], {'finished': True}, rpc.session.context)
                finished = "True"
            else:
                report = rpc.session.execute('report', 'report_get', data_bg['report_id'])
                finish = report['state'] or ""
                if finish:
                    report_type = report['format']
                    cherrypy.response.headers['Content-Type'] = 'application/octet-stream'
                    cherrypy.response.headers['Content-Disposition'] = 'filename="' + data_bg['report_name'] + '.' + report_type + '"'
                    return actions._print_data(report)

        return dict(finish=finish, percent=data_bg['percent'], total=finished)


