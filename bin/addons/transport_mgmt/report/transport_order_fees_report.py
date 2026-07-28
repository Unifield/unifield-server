# -*- coding: utf-8 -*-

from report import report_sxw
from osv import osv
from tools.translate import _


class transport_order_fees_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(transport_order_fees_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
        })


report_sxw.report_sxw('report.transport.order.ito.customs.fees.pdf', 'transport.order.in',
                      'transport_mgmt/report/transport_order_customs_fees_report.rml', header=False,
                      parser=transport_order_fees_report)

report_sxw.report_sxw('report.transport.order.oto.customs.fees.pdf', 'transport.order.out',
                      'transport_mgmt/report/transport_order_customs_fees_report.rml', header=False,
                      parser=transport_order_fees_report)

report_sxw.report_sxw('report.transport.order.ito.transport.fees.pdf', 'transport.order.in',
                      'transport_mgmt/report/transport_order_transport_fees_report.rml', header=False,
                      parser=transport_order_fees_report)

report_sxw.report_sxw('report.transport.order.oto.transport.fees.pdf', 'transport.order.out',
                      'transport_mgmt/report/transport_order_transport_fees_report.rml', header=False,
                      parser=transport_order_fees_report)
