# -*- coding: utf-8 -*-

from report import report_sxw

class signature_export_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(signature_export_report, self).__init__(cr, uid, name,
                                                      context=context)

        self.localcontext.update({
            'getSign': self.getSign,
        })

    def getSign(self, objects):
        img_obj = self.pool.get('signature.image')
        o = self.pool.get('signature.export.wizard').browse(self.cr, self.uid, objects[0].id)
        ids = img_obj.search(self.cr, self.uid, [('from_date', '<=', o.end_date), '|', ('to_date', '=', False), ('to_date', '>=', o.start_date)], context=self.localcontext)
        return sorted(sorted(img_obj.browse(self.cr, self.uid, ids, context=self.localcontext), key=lambda x: x.user_id.login or ''), key=lambda z: z.to_date or '')

report_sxw.report_sxw('report.signature.export.report', 'signature.export.wizard', 'addons/base/res/report_module/signature.rml', header=False, parser=signature_export_report)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
