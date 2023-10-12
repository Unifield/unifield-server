# -*- coding: utf-8 -*-

import time
from osv import osv
from tools.translate import _
from report import report_sxw


class shipment_donation_certificate(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(shipment_donation_certificate, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getLines': self._get_lines,
            'getCompany': self._get_company,
        })

    def _get_lines(self, ship):
        '''
        Get the lines' data, and only combine the quantities of PPL lines having the same BN/ED
        '''
        uom_obj = self.pool.get('product.uom')
        curr_obj = self.pool.get('res.currency')

        lines = []
        if ship.state == 'cancel':
            return lines
        keys = []
        for pack in ship.pack_family_memory_ids:
            if pack.state == 'returned':
                continue
            for move in pack.move_lines:
                key = (move.product_id.id, move.prodlot_id and move.prodlot_id.id or False)
                move_price = move.price_unit
                line = {
                    'line_numbers': [str(move.line_number)],
                    'p_id': move.product_id.id,
                    'p_code': move.product_id.default_code,
                    'p_desc': move.product_id.name,
                    'qty': move.product_qty,
                    'uom_id': move.product_uom.id,
                    'uom_rounding': move.product_uom.rounding,
                    'uom': move.product_uom.name,
                    'prodlot_id': move.prodlot_id and move.prodlot_id.id or False,
                    'prodlot': move.prodlot_id and move.prodlot_id.name or '',
                    'exp_date': move.prodlot_id and move.prodlot_id.life_date or move.expired_date or '',
                    'currency': move.price_currency_id.name,
                    'unit_price': move_price,
                    'tot_value': move.product_qty * move_price,
                }
                if key in keys:
                    for line in lines:
                        if line['p_id'] == key[0] and line['prodlot_id'] == key[1]:
                            if str(move.line_number) not in line['line_numbers']:
                                line['line_numbers'].append(str(move.line_number))
                            move_qty = move.product_qty
                            if line['uom_rounding'] != move.product_uom.rounding:
                                move_qty = uom_obj._compute_round_up_qty(self.cr, self.uid, line['uom_rounding'],
                                                                         move_qty, context=self.localcontext)
                            tot_qty = line['qty'] + move_qty
                            if ship.currency_id.id != move.price_currency_id.id:
                                move_price = curr_obj.compute(self.cr, self.uid, move.price_currency_id.id,
                                                              ship.currency_id.id, move_price, round=False,
                                                              context=self.localcontext)
                            line.update({'qty': tot_qty, 'unit_price': move_price, 'tot_value': tot_qty * move_price})
                            break
                else:
                    keys.append(key)
                    lines.append(line)

        return lines

    def _get_company(self):
        '''
        Return information about the company.
        '''
        company = self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id

        res = {}
        if company:
            res['currency_name'] = company.currency_id and company.currency_id.name or False
            res['partner'] = company.partner_id and company.partner_id.name or False
            if company.partner_id and len(company.partner_id.address):
                res['street'] = company.partner_id.address[0].street
                res['street2'] = company.partner_id.address[0].street2
                if company.partner_id.address[0].zip is not False:
                    res['zip'] = company.partner_id.address[0].zip
                else:
                    res['zip'] = ""
                res['city'] = company.partner_id.address[0].city
                res['country'] = company.partner_id.address[0].country_id and company.partner_id.address[0].country_id.name or False
                res['phone'] = company.partner_id.address[0].phone or False

        return res

    def set_context(self, objects, data, ids, report_type=None):
        '''
        opening check
        '''
        for obj in objects:
            if not obj.backshipment_id:
                raise osv.except_osv(_('Warning !'), _('Donation Certificate is only available for Shipment Objects (not draft)!'))

        return super(shipment_donation_certificate, self).set_context(objects, data, ids, report_type=report_type)


report_sxw.report_sxw('report.shipment.donation.certificate', 'shipment',
                      'addons/msf_outgoing/report/shipment_donation_certificate.rml',
                      parser=shipment_donation_certificate, header=False)

