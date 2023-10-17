# -*- coding: utf-8 -*-

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from report import report_sxw


class loan_certificate_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(loan_certificate_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'displayValue': self._display_value,
            'getTotalValue': self._get_total_value,
            'getCurrencyName': self._get_currency_name,
            'getEstimatedDate': self._get_estimated_date,
        })

    def _display_value(self):
        return self.localcontext.get('data') and self.localcontext['data'].get('display_value', False) or False

    def _get_total_value(self, pick):
        '''
        Return the total with a calculated price
        '''
        tot_value = 0
        for move in pick.move_lines:
            tot_value += move.product_qty * (move.price_unit or move.product_id.standard_price or 0.00)

        return tot_value

    def _get_currency_name(self, pick):
        '''
        Return the currency to use
        '''
        curr_name = pick.company_id.currency_id.name
        if pick.sale_id:
            curr_name = pick.sale_id.pricelist_id.currency_id.name
        elif pick.purchase_id:
            curr_name = pick.purchase_id.pricelist_id.currency_id.name

        return curr_name

    def _get_estimated_date(self, pick):
        esti_date = pick.min_date
        if pick.sale_id:
            esti_date = (datetime.strptime(pick.sale_id.date_order, '%Y-%m-%d') +
                         relativedelta(months=pick.sale_id.loan_duration)).strftime('%Y-%m-%d %H:%M:%S')
        elif pick.purchase_id:
            esti_date = (datetime.strptime(pick.purchase_id.date_order, '%Y-%m-%d') +
                         relativedelta(months=pick.purchase_id.loan_duration)).strftime('%Y-%m-%d %H:%M:%S')
        return esti_date


report_sxw.report_sxw('report.loan.certificate', 'stock.picking', 'addons/order_types/report/loan_certificate.rml',
                      parser=loan_certificate_report, header=False)

report_sxw.report_sxw('report.loan.return.certificate', 'stock.picking', 'addons/order_types/report/loan_return_certificate.rml',
                      parser=loan_certificate_report, header=False)


class ship_loan_certificate_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(ship_loan_certificate_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getLoansData': self._get_loans_data,
            'displayValue': self._display_value,
            'getTotalValue': self._get_total_value,
            'getLines': self._get_lines,
            'getCompany': self._get_company,
        })

    def _get_loans_data(self, packs, ship_actual_date, loan_return=False):
        loan_id = self.localcontext['data'].get('loan_id', False)
        loan_return_id = self.localcontext['data'].get('loan_return_id', False)

        loan_id_to_check = loan_id
        if loan_return:
            loan_id_to_check = loan_return_id
        loans_data = []
        for pack in packs:
            if pack.ppl_id.reason_type_id.id == loan_id_to_check:
                loan_esti_date = ship_actual_date
                if pack.ppl_id.sale_id:
                    loan_esti_date = (datetime.strptime(pack.ppl_id.sale_id.date_order, '%Y-%m-%d') +
                                      relativedelta(months=pack.ppl_id.sale_id.loan_duration)).strftime('%Y-%m-%d %H:%M:%S')
                loans_data.append({
                    'loan_ref': pack.ppl_id.sale_id and pack.ppl_id.sale_id.name or '',
                    'loan_origin': pack.ppl_id.sale_id and (pack.ppl_id.sale_id.loan_id and
                                                            pack.ppl_id.sale_id.loan_id.name or pack.ppl_id.sale_id.origin) or '',
                    'loan_esti_date': loan_esti_date,
                })
        return loans_data

    def _display_value(self):
        return self.localcontext.get('data') and self.localcontext['data'].get('display_value', False) or False

    def _get_total_value(self):
        return self.localcontext.get('data') and self.localcontext['data'].get('value', 0.00) or 0.00

    def _get_lines(self, packs, loan_return=False):
        loan_id = self.localcontext['data'].get('loan_id', False)
        loan_return_id = self.localcontext['data'].get('loan_return_id', False)

        loan_id_to_check = loan_id
        if loan_return:
            loan_id_to_check = loan_return_id
        lines = []
        for pack in packs:
            if pack.ppl_id.reason_type_id.id == loan_id_to_check:
                for move in pack.move_lines:
                    lines.append({
                        'product_code': move.product_id.default_code,
                        'product_name': move.product_id.name,
                        'qty': move.product_qty,
                        'prodlot_name': move.prodlot_id and move.prodlot_id.name or '',
                        'expiry_date': move.prodlot_id and move.prodlot_id.life_date or '',
                    })
        return lines

    def _get_company(self):
        '''
        Return information about the company.
        '''
        company = self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id

        res = {}
        if company:
            res['full_name'] = company.instance_id and company.instance_id.name or False
            if company.partner_id and len(company.partner_id.address):
                res['street'] = company.partner_id.address[0].street
                res['street2'] = company.partner_id.address[0].street2
                if company.partner_id.address[0].zip is not False:
                    res['zip'] = company.partner_id.address[0].zip
                else:
                    res['zip'] = ""
                res['city'] = company.partner_id.address[0].city
                res['country'] = company.partner_id.address[0].country_id and company.partner_id.address[0].country_id.name or False

        return res


report_sxw.report_sxw('report.ship.loan.certificate', 'shipment', 'addons/order_types/report/ship_loan_certificate.rml',
                      parser=ship_loan_certificate_report, header=False)

report_sxw.report_sxw('report.ship.loan.return.certificate', 'shipment', 'addons/order_types/report/ship_loan_return_certificate.rml',
                      parser=ship_loan_certificate_report, header=False)
