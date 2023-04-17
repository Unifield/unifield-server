# -*- coding: utf-8 -*-

import pooler
from report import report_sxw
from tools.misc import Path
import zipfile
import tempfile
import os


class export_unidata_sync_log(report_sxw.report_sxw):

    def create(self, cr, uid, ids, data, context=None):
        d = pooler.get_pool(cr.dbname).get('unidata.sync.log').read(cr, uid, ids[0], ['log_file'], context=context)
        null1, tmpzipname = tempfile.mkstemp()
        zf = zipfile.ZipFile(tmpzipname, 'w')
        zf.write(d['log_file'], os.path.basename(d['log_file']), compress_type=zipfile.ZIP_DEFLATED)
        zf.close()
        os.close(null1)
        return (Path(tmpzipname, delete=True), 'zip')

export_unidata_sync_log('report.product_attributes.unidata_sync_log_download', 'unidata.sync.log', False, parser=False)

