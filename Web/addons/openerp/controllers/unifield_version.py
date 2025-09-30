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

from openerp.controllers import SecuredController, actions
from openerp.utils import rpc

from openobject.tools import expose


class UnifieldVersion(SecuredController):

    _cp_path = "/openerp/unifield_version"

    @expose()
    def default(self):
        vid = rpc.RPCProxy('unifield.version').create({})
        return actions.execute(
            rpc.RPCProxy('ir.actions.act_window')\
                    .for_xml_id('msf_profile', 'action_unifield_version_form_view'), domain=('id', '=', vid)
        )
