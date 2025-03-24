# -*- coding: utf-8 -*-

import time
import locale
from report import report_sxw
from osv import osv
from tools.translate import _

class asset_register_report_landscape(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(asset_register_report_landscape, self).__init__(cr, uid, name=name, context=context)
        self.context = context
        self.cr = cr
        self.uid = uid
        self.localcontext.update({
            'get_data': self._get_data,
            'all_assets': self._all_assets,
        })

    def _get_data(self):
        return self.pool.get('asset.register.commons').get_asset_register_data(self.cr, self.uid, self.uid, context= self.context)

    def _get_asset_ad(self, asset):
        asset_ad = ''
        ads = []
        if asset.analytic_distribution_id and asset.analytic_distribution_id.funding_pool_lines:
            for fp_line in asset.analytic_distribution_id.funding_pool_lines:
                cc_code = fp_line.cost_center_id.code
                dest_code = fp_line.destination_id.code
                fp_code = fp_line.analytic_id.code
                percentage = str(fp_line.percentage)
                line_ad = '; '.join([cc_code, dest_code, fp_code, percentage])
                ads.append(line_ad)
            asset_ad = ' \n/\n '.join(ads)
        return asset_ad

    def _format_asset_state(self, state):
        states = {
            'draft': _('Draft'),
            'open': _('Open'),
            'running': _('Active'),
            'depreciated': _('Fully Depreciated'),
            'disposed': _('Disposed')}
        return states.get(state, '')

    def format_data(self, asset):
        booking_rate = self.pool.get('res.currency').browse(self.cr, self.uid, asset.invo_currency.id,
                                                    fields_to_fetch=['rate'], context=None).rate
        format_data = {
            'asset_name': asset.name,
            'ji_entry_sequence': asset.move_line_id and asset.move_line_id.move_id and asset.move_line_id.move_id.name or '',
            'capitalization_period': asset.move_line_id and asset.move_line_id.period_id and asset.move_line_id.period_id.name or '',
            'product_code': asset.prod_int_code or '',
            'product_description': asset.prod_int_name or '',
            'serial_number': asset.serial_nb or '',
            'instance_creator': asset.instance_id and asset.instance_id.instance or '',
            'instance_use': asset.used_instance_id and asset.used_instance_id.instance or '',
            'ad': self._get_asset_ad(asset),
            'asset_type': asset.asset_type_id and asset.asset_type_id.name or '',
            'useful_life': asset.useful_life_id and asset.useful_life_id.year or '',
            'booking_currency': asset.invo_currency and asset.invo_currency.name or '',
            'init_value': asset.invo_value,
            'depreciation_amount': asset.depreciation_amount,
            'book_remaining_value': asset.disposal_amount,
            'func_remaining_value': asset.disposal_amount / booking_rate,
            'state': self._format_asset_state(asset.state),
            'external_asset_id': asset.external_asset_id or '',
        }
        return format_data

    def _all_assets(self):
        """
        Returns the assets to be displayed in the report as a list of product.assets browse records
        """
        asset_obj = self.pool.get('product.asset')
        data = self._get_data()
        to_display = []
        asset_count = 0
        total_init_value = 0
        total_depreciation_amount = 0
        total_remaining_value_book = 0
        total_remaining_value_func = 0
        for a in asset_obj.browse(self.cr, self.uid, data.get('sorted_asset_ids', []), fields_to_fetch=data.get('asset_fields', []), context=self.context):
            asset = self.format_data(a)
            to_display.append(asset)
            asset_count += 1
            total_init_value += a.invo_value or 0
            total_depreciation_amount += a.depreciation_amount or 0
            total_remaining_value_book += a.disposal_amount or 0
            total_remaining_value_func += asset.get('func_remaining_value', 0)
        totals = {
            'asset_count': asset_count,
            'total_init_value': total_init_value,
            'total_depreciation_amount': total_depreciation_amount,
            'total_remaining_value_book': total_remaining_value_book,
            'total_remaining_value_func': total_remaining_value_func,
        }

        return to_display,totals


report_sxw.report_sxw(name='report.asset.register.report.landscape', table='product.asset', rml='addons/product_asset/report/asset_register_report_landscape.rml', parser=asset_register_report_landscape, header="internal landscape")