#-*- encoding:utf-8 -*-

from osv import osv
from osv import fields


class signature_follow_up_search_wizard(osv.osv_memory):
    _name = 'signature.follow_up.search.wizard'

    _columns = {
        'export_format': fields.selection([('xlsx', 'Excel'), ('pdf', 'PDF')], string="Export format", required=True),
    }

    def button_validate(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        for wiz in self.browse(cr, uid, ids, context=context):
            data = {
                'ids': [],
                'model': 'signature.follow_up',
                'context': context,
            }
            report_name = 'signature.follow_up.search.pdf'
            if wiz.export_format == 'xlsx':
                report_name = 'signature.follow_up.search.xlsx'
            return {
                'type': 'ir.actions.report.xml',
                'report_name': report_name,
                'datas': data,
            }
        return {'type': 'ir.actions.act_window_close'}


signature_follow_up_search_wizard()
