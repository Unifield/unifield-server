# -*- coding: utf-8 -*-

from report import report_sxw


class transport_order_steps_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(transport_order_steps_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
        })


report_sxw.report_sxw('report.transport.order.ito.steps.pdf', 'transport.order.in',
                      'transport_mgmt/report/transport_order_steps_report.rml', header=False,
                      parser=transport_order_steps_report)

report_sxw.report_sxw('report.transport.order.oto.steps.pdf', 'transport.order.out',
                      'transport_mgmt/report/transport_order_steps_report.rml', header=False,
                      parser=transport_order_steps_report)
