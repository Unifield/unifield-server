# -*- coding: utf-8 -*-

import pooler
from report import report_sxw
from tools.misc import Path

class export_unidata_sync_log(report_sxw.report_sxw):

    def create(self, cr, uid, ids, data, context=None):
        d = pooler.get_pool(cr.dbname).get('unidata.sync.log').read(cr, uid, ids[0], ['log_file'], context=context)
        return (Path(d['log_file'], delete=False), 'txt')

export_unidata_sync_log('report.product_attributes.unidata_sync_log_download', 'unidata.sync.log', False, parser=False)

