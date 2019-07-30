# -*- coding: utf-8 -*-

import pooler
from report import report_sxw

class export_user_rigths_content(report_sxw.report_sxw):

    def create(self, cr, uid, ids, data, context=None):
        ur = pooler.get_pool(cr.dbname).get('sync_server.user_rights').get_plain_zip(cr, uid, ids[0], context=context)
        return (ur, 'zip')

export_user_rigths_content('report.sync_server.user_rights.download', 'sync_server.user_rights', False, parser=False)

