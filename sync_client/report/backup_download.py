# -*- coding: utf-8 -*-

import pooler
from report import report_sxw


class export_backup_content(report_sxw.report_sxw):
    def create(self, cr, uid, ids, data, context=None):
        bck_obj = pooler.get_pool(cr.dbname).get('backup.download')
        bck = bck_obj.read(cr, uid, ids[0], ['path'], context=context)
        f = open(bck['path'], 'rb')
        result = (f.read(), 'dump')
        f.close()
        return result

export_backup_content('report.backup.download', 'backup.download', False, parser=False)
