# -*- coding: utf-8 -*-

from report import report_sxw

class asset_register_report_landscape(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(asset_register_report_landscape, self).__init__(cr, uid, name=name, context=context)
        self.context = context
        self.cr = cr
        self.uid = uid
        self.localcontext.update({
            'get_data': self.get_data,
            'all_assets': self.all_assets,
        })

    def get_data(self):
        return self.pool.get('asset.register.commons').get_asset_register_data(self.cr, self.uid, self.uid, context= self.context)

    def format_data(self, asset):
        commons_obj = self.pool.get('asset.register.commons')
        booking_rate = False
        if asset and asset.invo_currency and asset.invo_currency.id:
            book_currency = self.pool.get('res.currency').browse(self.cr, self.uid, asset.invo_currency.id, fields_to_fetch=['rate'], context=self.context)
            booking_rate = book_currency and book_currency.rate or False

        format_data = {
            'asset_name': asset.name or '',
            'ji_entry_sequence': asset.move_line_id and asset.move_line_id.move_id and asset.move_line_id.move_id.name or '',
            'capitalization_period': asset.move_line_id and asset.move_line_id.period_id and asset.move_line_id.period_id.name or '',
            'product_code': asset.prod_int_code or '',
            'product_description': asset.prod_int_name or '',
            'serial_number': asset.serial_nb or '',
            'instance_creator': asset.instance_id and asset.instance_id.instance or '',
            'instance_use': asset.used_instance_id and asset.used_instance_id.instance or '',
            'ad': commons_obj.get_asset_ad(asset) or '',
            'asset_type': asset.asset_type_id and asset.asset_type_id.name or '',
            'useful_life': asset.useful_life_id and asset.useful_life_id.year or '',
            'booking_currency': asset.invo_currency and asset.invo_currency.name or '',
            'init_value': asset.invo_value or 0,
            'depreciation_amount': asset.depreciation_amount or 0,
            'book_remaining_value': asset.disposal_amount or 0,
            'func_remaining_value': booking_rate and booking_rate > 0 and asset.disposal_amount / booking_rate or 0,
            'state': commons_obj.format_asset_state(asset.state, context=self.context) or '',
            'external_asset_id': asset.external_asset_id or '',
        }
        return format_data

    def all_assets(self):
        """
        Returns the assets to be displayed in the report as a list of product.assets browse records +
        Compute the totals fields
        """
        asset_obj = self.pool.get('product.asset')
        data = self.get_data()
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
