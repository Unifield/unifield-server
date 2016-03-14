# -*- coding: utf-8 -*-

import pooler
from report import report_sxw
from tools.misc import Path

class export_backup_content(report_sxw.report_sxw):

    def create(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}

        bck_obj = pooler.get_pool(cr.dbname).get('backup.download')
        bck = bck_obj.read(cr, uid, ids[0], ['path'], context=context)

        if context.get('report_fromfile'):
            return (Path(bck['path'], delete=False), 'dump')

        f = open(bck['path'], 'rb')
        result = (f.read(), 'dump')
        f.close()
        return result

export_backup_content('report.backup.download', 'backup.download', False, parser=False)
