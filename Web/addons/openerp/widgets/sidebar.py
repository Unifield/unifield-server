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
from openerp.utils import rpc
from openerp.widgets import TinyWidget
from openerp import utils


class Sidebar(TinyWidget):

    template = "/openerp/widgets/templates/sidebar.mako"
    params = ['reports', 'actions', 'relates', 'attachments', 'sub_menu',
              'view_type', 'model', 'id', 'ctx', 'max_attachment_size']

    def add_remote_action_values(self, action_type, current_actions):
        actions = rpc.RPCProxy('ir.values').get(
            'action', action_type, [(self.model, False)], False, self.context, False, True, True, self.view_id)
        for action in [a[-1] for a in actions]:
            if action['id'] not in [a['id'] for a in current_actions]:
                action['context'] = self.context
                current_actions.append(action)

    def __init__(self, model, submenu=None, toolbar=None, id=None, view_type="form", multi=True, context=None, **kw):
        super(Sidebar, self).__init__(model=model, id=id)
        self.multi = multi
        self.context = context or {}
        self.ctx = context
        self.view_type = view_type
        toolbar = toolbar or {}
        submenu = submenu
        self.id = id or None
        self.reports = toolbar.get('print', [])
        self.actions = toolbar.get('action', [])
        self.relates = toolbar.get('relate', [])
        self.max_attachment_size = utils.get_max_attachment_size()
        self.attachments = []
        self.sub_menu = None
        self.view_id = kw.get('view_id', False)

        # add context to relate action to get the lang
        if self.context:
            newctx = self.context.copy()
            # remove the active_id of ir.ui.view
            to_remove = ['active_id', 'active_ids']
            for to_del in to_remove:
                if to_del in newctx:
                    del newctx[to_del]
            for relate in self.relates:
                relate['context'] = newctx

        action = 'client_action_multi'
        if self.view_type == 'form':
            action = 'tree_but_action'
        self.add_remote_action_values(action, self.actions)

        self.add_remote_action_values('client_print_multi', self.reports)

        if self.view_type == 'form' and id:
            attachments = rpc.RPCProxy('ir.attachment')
            attachment_ids = attachments.search(
                [('res_model', '=', model), ('res_id', '=', id), ('type', 'in', ['binary', 'url'])],
                0, 0, 0, self.context)

            if attachment_ids:
                self.attachments = attachments.read(attachment_ids, ['name', 'url', 'type'])

            self.sub_menu = submenu
