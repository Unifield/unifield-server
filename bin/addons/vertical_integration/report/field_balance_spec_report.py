# -*- coding: utf-8 -*-
from osv import fields, osv
from tools.translate import _
from datetime import datetime
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from openpyxl.cell import WriteOnlyCell
from openpyxl.drawing import image
from openpyxl.worksheet.header_footer import HeaderFooterItem
import tools
from PIL import Image as PILImage
from dateutil.relativedelta import relativedelta

class field_balance_spec_report(osv.osv_memory):
    _name = "field.balance.spec.report"


    def _get_has_multi_table(self, cr, uid, ids, name, arg=None, context=None):
        nb = self.pool.get('res.currency.table').search(cr, uid, [('sate', '=', 'valid')], count=True)
        ret = {}
        for _id in ids:
            ret[_id] = nb > 1
        return ret


    _columns = {
        'instance_id': fields.many2one('msf.instance', 'Top proprietary instance', required=True, domain=[('level', '=', 'coordo'), ('state', '=', 'active'), ('instance_to_display_ids','=',True)]),
        'period_id': fields.many2one('account.period', 'Period', required=True, domain=[('state', 'in', ['draft', 'field-closed', 'mission-closed']), ('number', 'not in', [0, 16])]),
        'selection': fields.selection([('total', 'Total of entries reconciled in later period'),
                                       ('details', 'Details of entries reconciled in later period')],
                                      string="Select", required=True),
        'eoy': fields.boolean('End of Year', help='Field is disabled if no valid currency table'),
        'has_one_table': fields.boolean('Has a single valid currency table', readonly=1),
    }

    def _get_instance(self, cr, uid, *a, **b):
        instance = self.pool.get('res.company')._get_instance_record(cr, uid)
        if instance.level == 'coordo':
            return instance.id
        return False

    def _get_has_currency_table(self, cr, uid, *a, **b):
        return self.pool.get('res.currency.table').search_exists(cr, uid, [('state', '=', 'valid')])

    _defaults = {
        'selection': lambda *a: 'details',
        'instance_id': lambda self, cr, uid, *a, **b: self._get_instance(cr, uid, *a, **b),
        'has_one_table': lambda self, cr, uid, *a, **b: self._get_has_currency_table(cr, uid, *a, **b),
    }

    def button_create_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        report = self.browse(cr, uid, ids[0], context=context)
        filename = '%s %s %s' % (report.instance_id.instance, report.period_id.name, _('Field Balance specification report'))
        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': filename,
            'report_name': 'field_balance_spec_report',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'field_balance_spec_report',
            'datas': {'ids': ids, 'target_filename': filename, 'context': context},
            'context': context,
        }

field_balance_spec_report()


class field_balance_spec_parser(XlsxReportParser):
    _name = "field.balance.spec.parser"

    def add_cell(self, value=None, style='default_style'):
        # None value set an xls empty cell
        # False value set the xls False()
        new_cell = WriteOnlyCell(self.workbook.active, value=value)
        new_cell.style = style
        self.rows.append(new_cell)

    def generate(self, context=None):

        bk_id = self.context.get('background_id')
        bk_obj = self.pool.get('memory.background.report')

        company = self.pool.get('res.users').browse(self.cr, self.uid, self.uid, fields_to_fetch=['company_id'], context=context).company_id

        date_used = company.currency_date_type == 'Posting Date' and 'date' or 'document_date'
        date_used_label = company.currency_date_type == 'Posting Date' and _('Posting') or _('Booking')
        report = self.pool.get('field.balance.spec.report').browse(self.cr, self.uid, self.ids[0], context=context)

        all_instance_ids = [report.instance_id.id] + [x.id for x in report.instance_id.child_ids]

        self.cr.execute('''
            select
                distinct cur.id, cur.name
            from
                account_move_line l, account_move m, res_currency cur, account_account a, account_period p
            where
                cur.id = l.currency_id
                and a.id = l.account_id
                and l.date <= %(last_date)s
                and p.id = l.period_id
                and p.number not in (0, 16)
                and m.id = l.move_id
                and m.state='posted'
                and m.instance_id in %(instance)s
                and (a.reconcile = 't' or a.type = 'liquidity')
                and l.reconcile_id is null
            group by
                cur.id, cur.name
            order by
                cur.name
        ''', {'last_date': report.period_id.date_stop, 'instance': tuple(all_instance_ids)} )

        list_curr = ['EUR', 'USD']
        curr_id = {}
        for x in self.cr.fetchall():
            if x[1] not in ('EUR', 'USD'):
                list_curr.append(x[1])
            curr_id[x[0]] = x[1]

        if bk_id:
            bk_obj.write(self.cr, self.uid, bk_id, {'percent': 0.1})

        fx_rates = {}
        fx_rates_by_id = {}
        self.cr.execute('''
            select cur.name,
                (select rate.rate
                    from res_currency_rate rate
                    where rate.currency_id = cur.id and rate.name <= %s
                    order by
                    rate.name desc
                    limit 1
                ) as fx_rate,
                cur.id
            from res_currency cur
            where currency_table_id is null and cur.name in %s
        ''', (report.period_id.date_start, tuple(list_curr) ))
        for x in self.cr.fetchall():
            fx_rates[x[0]] = x[1]
            fx_rates_by_id[x[2]] = x[1]

        ct_fx_rates = {}
        ct_fx_rates_by_id = {}
        if report.eoy:
            self.cr.execute('''
                select cur.name,
                    (select rate.rate
                        from res_currency_rate rate
                        where rate.currency_id = cur.id
                        order by
                        rate.name desc
                        limit 1
                    ) as fx_rate,
                    cur.reference_currency_id
                from res_currency cur, res_currency_table t
                where
                    cur.currency_table_id = t.id
                    and t.state = 'valid'
                    and cur.name in %s
            ''', (tuple(list_curr), ))
            for x in self.cr.fetchall():
                ct_fx_rates[x[0]] = x[1]
                ct_fx_rates_by_id[x[2]] = x[1]

        rates = {}
        for n, cur in enumerate(list_curr[1:]):
            if report.eoy:
                rates[n] = {'name': cur, 'value': ct_fx_rates[cur]}
            else:
                rates[n] = {'name': cur, 'value': fx_rates[cur]}

        page_title = _('Field Balance Specification Report From UniField')

        sheet = self.workbook.active
        sheet.sheet_view.zoomScale = 75
        sheet.protection.formatCells = False
        sheet.protection.formatRows = False
        sheet.protection.formatColumns = False
        sheet.protection.autoFilter = False
        sheet.protection.sheet = True
        sheet.sheet_view.showGridLines = True
        sheet.page_setup.orientation = 'landscape'
        sheet.page_setup.fitToPage = True
        sheet.page_setup.fitToHeight = False
        sheet.page_setup.paperSize = 9 # A4

        footer = HeaderFooterItem()
        footer.left.text = "%s, %s, %s, %s &[Page]/&N" % (page_title, report.instance_id.mission, report.period_id.name, _('page'))
        footer.left.size = 8
        sheet.oddFooter = footer
        sheet.evenFooter = footer
        sheet.page_margins.left = 0.2
        sheet.page_margins.right = 0.2
        sheet.page_margins.top = 0.2
        sheet.page_margins.bottom = 1

        self.duplicate_column_dimensions()
        self.duplicate_row_dimensions(range(1, 9))
        pil_img = PILImage.open(tools.file_open('addons/msf_doc_import/report/images/msf-logo.png', 'rb'))
        img = image.Image(pil_img)
        orig_width = img.width
        orig_height = img.height
        img.width = 100.
        img.height = orig_height * (img.width/orig_width)

        sheet.add_image(img, 'A1')


        self.create_style_from_template('logo_style', 'A1')
        self.create_style_from_template('title_cell1_style', 'B1')
        self.create_style_from_template('title_style', 'I1')
        self.create_style_from_template('user_header', 'K1')
        self.create_style_from_template('rate_style', 'G1')
        self.create_style_from_template('current_period_style', 'H1')
        self.create_style_from_template('func_curr_name', 'G2')
        self.create_style_from_template('func_curr_value', 'H2')
        self.create_style_from_template('header_full_date', 'D3')
        self.create_style_from_template('header_month_date', 'B4')
        self.create_style_from_template('end_doc', 'B37')
        self.create_style_from_template('end_doc_left', 'A37')
        self.create_style_from_template('end_doc_right', 'L37')

        self.create_style_from_template('user_line', 'L2')
        self.create_style_from_template('default_header_style', 'B3')
        self.create_style_from_template('header_1st_info_title', 'A3')
        self.create_style_from_template('header_other_info_title', 'C3')
        self.create_style_from_template('cur_name', 'G3')
        self.create_style_from_template('cur_value', 'H3')
        self.create_style_from_template('user_name', 'B5')
        self.create_style_from_template('user_date', 'C5')

        self.create_style_from_template('title_account', 'A18')
        self.create_style_from_template('title_text', 'B18')
        self.create_style_from_template('title_amount', 'F18')
        self.create_style_from_template('title_info', 'I18')
        self.create_style_from_template('title_hq_comment', 'L9')
        self.create_style_from_template('line_account', 'A19')
        self.create_style_from_template('line_amount', 'H19')
        self.create_style_from_template('line_text', 'B19')
        self.create_style_from_template('line_date', 'D19')
        self.create_style_from_template('line_total', 'H25')
        self.create_style_from_template('line_curr', 'E15')
        self.create_style_from_template('line_info', 'I24')
        self.create_style_from_template('line_selection', 'A23')
        self.create_style_from_template('field_comment', 'K10')
        self.create_style_from_template('hq_comment', 'L10')



        sheet.title = '%s %s' % (report.period_id.name, report.instance_id.code)
        sheet.row_dimensions[1].height = 25

        sheet.append([
            self.cell_ro('', 'logo_style'),
            self.cell_ro(page_title, 'title_cell1_style'),
            self.cell_ro('', 'title_style'),
            self.cell_ro('', 'title_style'),
            self.cell_ro('', 'title_style'),
            self.cell_ro('', 'title_style'),
            self.cell_ro(_('Rates'), 'rate_style'),
            self.cell_ro(_('Current period'), 'current_period_style'),
            self.cell_ro('', 'title_style'),
            self.cell_ro('', 'title_style'),
            self.cell_ro('', 'user_header'),
            self.cell_ro('', 'user_header'),
        ])
        sheet.merged_cells.ranges.append("B1:F1")
        sheet.merged_cells.ranges.append("K1:L1")

        sheet.append(
            [self.cell_ro('', 'header_1st_info_title')] +
            [self.cell_ro('', 'default_header_style')]*5 +
            [self.cell_ro(company.currency_id.name, 'func_curr_name'), self.cell_ro(1,  'func_curr_value')] +
            [self.cell_ro('', 'default_header_style')] * 2 +
            [self.cell_ro('', 'user_line')] * 2
        )
        sheet.merged_cells.ranges.append("K2:L2")

        sheet.append([
            self.cell_ro(_('Country Program'), 'header_1st_info_title'),
            self.cell_ro(report.instance_id.mission or '', 'default_header_style'),
            self.cell_ro(_('Date of the report'), 'header_other_info_title'),
            self.cell_ro(datetime.now(), style='header_full_date')
        ] +
            [self.cell_ro('', 'default_header_style')] * 2 +
            [self.cell_ro(rates.get(0, {}).get('name', ''), 'cur_name'), self.cell_ro(rates.get(0, {}).get('value', ''), 'cur_value')] +
            [self.cell_ro('', 'default_header_style')] * 2 +
            [self.cell_ro('', 'user_line')] * 2
        )
        sheet.merged_cells.ranges.append("K3:L3")

        sheet.append([
            self.cell_ro(_('Month:'), 'header_1st_info_title'),
            self.cell_ro(datetime.strptime(report.period_id.date_start, '%Y-%m-%d'), 'header_month_date'),
            self.cell_ro(_('Date of review'), 'header_other_info_title'),
            self.cell_ro('', style='header_full_date')
        ] +
            [self.cell_ro('', 'default_header_style')] * 2 +
            [self.cell_ro(rates.get(1, {}).get('name', ''), 'cur_name'), self.cell_ro(rates.get(1, {}).get('value', ''), 'cur_value')] +
            [self.cell_ro('', 'default_header_style')] * 2 +
            [self.cell_ro('', 'user_line')] * 2
        )
        sheet.merged_cells.ranges.append("K4:L4")

        sheet.append([
            self.cell_ro(_('Finco Name:'), 'header_1st_info_title'),
            self.cell_ro('', 'user_name', unlock=True),
            self.cell_ro('', 'user_date', unlock=True),
        ] +
            [self.cell_ro('', 'default_header_style')] * 3 +
            [self.cell_ro(rates.get(2, {}).get('name', ''), 'cur_name'), self.cell_ro(rates.get(2, {}).get('value', ''), 'cur_value')] +
            [self.cell_ro('', 'default_header_style')] * 2 +
            [self.cell_ro('', 'user_line')] * 2
        )
        sheet.merged_cells.ranges.append("K5:L5")

        sheet.append([
            self.cell_ro(_('HoM Name:'), 'header_1st_info_title'),
            self.cell_ro('', 'user_name', unlock=True),
            self.cell_ro('', 'user_date', unlock=True),
        ] +
            [self.cell_ro('', 'default_header_style')] * 3 +
            [self.cell_ro(rates.get(3, {}).get('name', ''), 'cur_name'), self.cell_ro(rates.get(3, {}).get('value', ''), 'cur_value')] +
            [self.cell_ro('', 'default_header_style')] * 2 +
            [self.cell_ro('', 'user_line')] * 2
        )
        sheet.merged_cells.ranges.append("K6:L6")

        sheet.append([
            self.cell_ro(_('HQ reviewer Name:'), 'header_1st_info_title'),
            self.cell_ro('', 'user_name', unlock=True),
            self.cell_ro('', 'user_date', unlock=True),
        ] +
            [self.cell_ro('', 'default_header_style')] * 3 +
            [self.cell_ro(rates.get(4, {}).get('name', ''), 'cur_name'), self.cell_ro(rates.get(4, {}).get('value', ''), 'cur_value')] +
            [self.cell_ro('', 'default_header_style')] * 2 +
            [self.cell_ro('', 'user_line')] * 2
        )
        sheet.merged_cells.ranges.append("K7:L7")
        rate_idx = 5
        line = 8
        while rates.get(rate_idx):
            sheet.append(
                [self.cell_ro('', 'header_1st_info_title')] +
                [self.cell_ro('', 'default_header_style')] * 5 +
                [self.cell_ro(rates.get(rate_idx, {}).get('name', ''), 'cur_name'), self.cell_ro(rates.get(rate_idx, {}).get('value', ''), 'cur_value')] +
                [self.cell_ro('', 'default_header_style')] * 2 +
                [self.cell_ro('', 'user_line', unlock=True)] * 2
            )
            sheet.merged_cells.ranges.append("K%(line)d:L%(line)d" % {'line': line})
            rate_idx += 1
            line += 1

        sheet.append([self.cell_ro('', 'header_1st_info_title')] + [self.cell_ro('', 'default_header_style')] * 9 + [self.cell_ro('', 'user_line', unlock=True)] * 2)
        sheet.merged_cells.ranges.append("K%(line)d:L%(line)d" % {'line': line})
        line += 1
        sheet.append(
            [self.cell_ro(_('Balance accounts'), style='title_account')] +
            [self.cell_ro('', style='title_text')] * 6 +
            [self.cell_ro(_('UniField Balance in %s') % (company.currency_id.name,) , style='title_amount')] +
            [self.cell_ro('', style='title_text')] * 2 +
            [self.cell_ro(_("Field's Comments"), style='title_text'), self.cell_ro(_("HQ Comments"), style='title_hq_comment')]
        )

        line += 1

        register_details = {}
        # sum of liquidity accounts
        liq_account_ids = self.pool.get('account.account').search(self.cr, self.uid, [('type', '=', 'liquidity'), ('reconcile', '=', False)], context=context)
        for liq_account in self.pool.get('account.account').browse(self.cr, self.uid, liq_account_ids, fields_to_fetch=['code', 'name'], context=context):
            self.cr.execute('''
                select
                    l.currency_id, sum(coalesce(amount_currency,0)), j.id
                from
                    account_move_line l, account_move m, account_period p, account_journal j
                where
                    l.move_id = m.id
                    and l.period_id = p.id
                    and j.id = l.journal_id
                    and l.instance_id in %(instance)s
                    -- and m.state = 'posted'
                    and p.number not in (0, 16)
                    and l.account_id = %(account_id)s
                    and ( p.date_start < %(period_start)s or p.date_start = %(period_start)s and p.number <= %(period_number)s)
                    and j.type in ('bank', 'cash')
                group by
                    l.currency_id, j.id
                ''', {
                'instance': tuple(all_instance_ids),
                'period_start': report.period_id.date_start,
                'period_number': report.period_id.number,
                'account_id': liq_account.id,
            }
            )
            liq_sum = 0
            # total entry encoding
            for liq in self.cr.fetchall():
                register_details[liq[2]] = liq[1]
                liq_sum += liq[1] / fx_rates_by_id[liq[0]]

            sheet.append(
                [self.cell_ro('%s %s' % (liq_account.code, liq_account.name), style='line_account')] +
                [self.cell_ro('', style='line_text')] * 6 +
                [self.cell_ro(round(liq_sum, 2), style='line_amount')] +
                [self.cell_ro('', style='line_text')] * 2 +
                [self.cell_ro('', style='field_comment', unlock=True), self.cell_ro('', style='hq_comment', unlock=True)]
            )
            line += 1

        if bk_id:
            bk_obj.write(self.cr, self.uid, bk_id, {'percent': 0.2})

        # sum of reconciliable accounts
        ctx_with_date = context.copy()
        ctx_with_date['date'] = (datetime.strptime(report.period_id.date_stop, '%Y-%m-%d') + relativedelta(days=1)).strftime('%Y-%m-%d')
        inactive_accounts = {}

        req_account_ids = self.pool.get('account.account').search(self.cr, self.uid, [('reconcile', '=', True), ('code', '!=', '15640')], context=context)
        special_account_id = self.pool.get('account.account').search(self.cr, self.uid, [('reconcile', '=', True), ('code','=', '15640')], context=context)

        all_account_ids = self.pool.get('account.account').search(self.cr, self.uid, [('reconcile', '=', True)], context=context) # list ordered by code

        list_sum = {}
        for list_accounts in [req_account_ids, special_account_id]:
            if not list_accounts:
                continue
            if list_accounts == ['15640']:
                req_cond = 'and l.employee_id is not null'
            else:
                req_cond = '''        and (
                            l.reconcile_id is null
                            or exists(
                                select rec_line.id from account_move_line rec_line, account_period rec_p
                            where
                                rec_line.reconcile_id = l.reconcile_id
                                and rec_p.id = rec_line.period_id
                                and (
                                    rec_p.date_start > %(period_start)s
                                    or rec_p.date_start = %(period_start)s and rec_p.number > %(period_number)s
                                )
                            )
                        )
                '''
            self.cr.execute('''
                select
                    sum(coalesce(l.debit,0) - coalesce(l.credit,0)),
                    l.account_id
                from
                    account_move_line l
                    inner join account_period p on p.id = l.period_id
                    inner join account_move m on l.move_id = m.id
                    inner join account_journal j on j.id = l.journal_id
                where
                    l.account_id in %(account_id)s
                    and j.type != 'revaluation'
                    and p.number not in (0, 16)
                    and ( p.date_start < %(period_start)s or p.date_start = %(period_start)s and p.number <= %(period_number)s)
                    and m.state='posted'
                    and m.instance_id in %(instance)s
                    ''' + req_cond + '''
                group by
                    l.account_id
                ''', {
                'account_id': tuple(list_accounts),
                'period_number': report.period_id.number,
                'period_start': report.period_id.date_start,
                'instance': tuple(all_instance_ids),
            })
            for ssum in self.cr.fetchall():
                list_sum[ssum[1]] = ssum[0]

        for req_account in self.pool.get('account.account').browse(self.cr, self.uid, all_account_ids, fields_to_fetch=['code', 'name', 'filter_active'], context=ctx_with_date):
            if not req_account.filter_active and not list_sum.get(req_account.id):
                inactive_accounts[req_account.id] = True
                continue

            sheet.append(
                [self.cell_ro('%s %s' % (req_account.code, req_account.name), style='line_account')] +
                [self.cell_ro('', style='line_text')] * 6 +
                [self.cell_ro(round(list_sum.get(req_account.id) or 0, 2), style='line_amount')] +
                [self.cell_ro('', style='line_text')] * 2 +
                [self.cell_ro('', style='field_comment', unlock=True), self.cell_ro('', style='hq_comment', unlock=True)]
            )
            line += 1

        sheet.append([self.cell_ro('', 'header_1st_info_title')] + [self.cell_ro('', 'default_header_style')] * 9 + [self.cell_ro('', 'user_line', unlock=True)] * 2)
        sheet.merged_cells.ranges.append("K%(line)d:L%(line)d" % {'line': line})
        line += 1

        year = datetime.strptime(report.period_id.date_start, '%Y-%m-%d').year
        for j_type in ['cash', 'bank']:
            j_ids = self.pool.get('account.journal').search(self.cr, self.uid, ['&', ('type', '=', j_type), '|', ('is_active', '=', True), ('inactivation_date', '>', '%s-01-31' % (year, )), ('instance_id', 'in', all_instance_ids)], context=context)
            first_line = True
            account_sum = 0
            ct_account_sum = 0
            for journal in self.pool.get('account.journal').browse(self.cr, self.uid, j_ids, context=context):
                if first_line:
                    sheet.append(
                        [
                            self.cell_ro('%s - %s' % (journal.default_debit_account_id.code, journal.default_debit_account_id.name), style='title_account'),
                            self.cell_ro(_('Journal Name'), style='title_text'),
                            self.cell_ro(_('Proprietary instance'), style='title_text'),
                            self.cell_ro(_('Journal Status'), style='title_text'),
                            self.cell_ro(_('Curr'), style='title_info'),
                            self.cell_ro(_('Currency Amount'), style='title_amount'),
                            self.cell_ro(_('Period Rate'), style='title_amount'),
                            self.cell_ro(_('%s Amount with Current Period Rate') % company.currency_id.name, style='title_amount'),
                            self.cell_ro(report.eoy and _('Year End Rate Currency Table') or '', style='title_amount'),
                            self.cell_ro(report.eoy and '%s %s' % (company.currency_id.name, _('Amount with Year End Rate Currency Table')) or '', style='title_amount'),
                            self.cell_ro(_("Field's Comments"), style='title_text'),
                            self.cell_ro(_("HQ Comments"), style='title_hq_comment'),
                        ]
                    )
                    line += 1
                    first_line = False
                sheet.append([
                    self.cell_ro(journal.code, style='line_account'),
                    self.cell_ro(journal.name, style='line_text'),
                    self.cell_ro(journal.instance_id.instance, style='line_text'),
                    self.cell_ro(not journal.is_active and _('Inactive') or '', style='line_text'),
                    self.cell_ro(journal.currency.name, style='line_curr'),
                    self.cell_ro(register_details.get(journal.id, 0), style='line_amount'),
                    self.cell_ro(fx_rates_by_id.get(journal.currency.id, 0), style='line_amount'),
                    self.cell_ro(register_details.get(journal.id,0) / fx_rates_by_id.get(journal.currency.id, 1), style='line_amount'),
                    self.cell_ro(ct_fx_rates_by_id.get(journal.currency.id, 0) if report.eoy else '', style='line_amount'),
                    self.cell_ro(register_details.get(journal.id,0) / ct_fx_rates_by_id.get(journal.currency.id, 1) if report.eoy else '', style='line_amount'),
                    self.cell_ro('', style='field_comment', unlock=True),
                    self.cell_ro('', style='hq_comment', unlock=True),
                ])
                line += 1
                account_sum += round(register_details.get(journal.id,0) / fx_rates_by_id.get(journal.currency.id, 1), 2)
                if report.eoy:
                    ct_account_sum += round(register_details.get(journal.id,0) / ct_fx_rates_by_id.get(journal.currency.id, 1), 2)

            sheet.append(
                [self.cell_ro('', 'header_1st_info_title')] +
                [self.cell_ro('', 'default_header_style')] * 6  +
                [self.cell_ro(account_sum, style='line_total')] +
                [self.cell_ro('', 'default_header_style'), self.cell_ro(ct_account_sum if report.eoy else '', style='line_total')]  +
                [self.cell_ro('', style='field_comment', unlock=True), self.cell_ro('', style='hq_comment', unlock=True)]
            )
            line += 1


            sheet.append([self.cell_ro('', 'header_1st_info_title')] + [self.cell_ro('', 'default_header_style')] * 9 + [self.cell_ro('', 'user_line', unlock=True)] * 2)
            sheet.merged_cells.ranges.append("K%(line)d:L%(line)d" % {'line': line})
            line += 1

        if bk_id:
            bk_obj.write(self.cr, self.uid, bk_id, {'percent': 0.5})

        # details of reconciliable accounts
        total_account = float(len(all_account_ids))
        nb_account_done = 0
        for req_account in self.pool.get('account.account').browse(self.cr, self.uid, all_account_ids, fields_to_fetch=['code', 'name'], context=context):
            if req_account.id in inactive_accounts:
                continue
            account_sum = 0
            if req_account.code == '15640':
                sheet.append(
                    [self.cell_ro('%s - %s' % (req_account.code, req_account.name), style='title_account')] +
                    [self.cell_ro('', style='title_text')] * 6 +
                    [
                        self.cell_ro(_('%s Amount') % (company.currency_id.name, ), style='title_amount'),
                        self.cell_ro(_('Subaccount Number'), style='title_info'),
                        self.cell_ro('', style='title_text'),
                        self.cell_ro(_("Field's Comments"), style='title_text'),
                        self.cell_ro(_("HQ Comments"), style='title_hq_comment'),
                    ]
                )
                line += 1
                # unreconciled or partial rec
                self.cr.execute('''
                   select name, sum(balance), identification_id from
                   (
                        select
                            res.name as name,
                            sum(coalesce(l.debit, 0) - coalesce(l.credit, 0)) as balance,
                            emp.identification_id as identification_id
                        from
                            hr_employee emp
                            inner join resource_resource res on res.id = emp.resource_id
                            inner join account_move_line l on l.employee_id = emp.id
                            inner join account_account a on a.id = l.account_id
                            inner join account_period p on p.id = l.period_id
                            inner join account_move m on l.move_id = m.id
                            inner join account_journal j on j.id = l.journal_id
                        where
                            l.account_id = %(account_id)s
                            and j.type != 'revaluation'
                            and p.number not in (0, 16)
                            and ( p.date_start < %(period_start)s or p.date_start = %(period_start)s and p.number <= %(period_number)s)
                            and m.state='posted'
                            and m.instance_id in %(instance)s
                        group by emp.id, res.name, emp.identification_id, res.active
                        having
                            res.active = 't' or abs(sum(coalesce(l.debit, 0) - coalesce(l.credit, 0))) > 0.001

                    UNION
                        select res.name as name, 0 as balance, emp.identification_id as identification_id
                        from
                            hr_employee emp, resource_resource res
                        where
                            res.id = emp.resource_id
                            and emp.employee_type='ex'
                            and res.active='t'
                    ) as EMP_ALL
                    group by
                        name, identification_id
                    order by
                        EMP_ALL.identification_id
                    ''', {
                    'account_id': req_account.id,
                    'period_number': report.period_id.number,
                    'period_start': report.period_id.date_start,
                    'instance': tuple(all_instance_ids),
                })
                for emp in self.cr.fetchall():
                    sheet.append(
                        [self.cell_ro(emp[0], style='line_account')] +
                        [self.cell_ro('', style='line_text')] * 6 +
                        [
                            self.cell_ro(round(emp[1], 2), style='line_amount'),
                            self.cell_ro(emp[2], style='line_text'),
                            self.cell_ro('', style='line_text'),
                            self.cell_ro('', style='field_comment', unlock=True),
                            self.cell_ro('', style='hq_comment', unlock=True),
                        ]
                    )
                    line += 1
                    account_sum += round(emp[1], 2)

                if report.selection == 'details':
                    title_sum = _('List of entries reconciled in later periods >>>')
                else:
                    title_sum = _('Total of entries reconciled in later periods >>>')

                sheet.append(
                    [self.cell_ro(title_sum, style='line_selection')] +
                    [self.cell_ro('', 'default_header_style')] * 9 +
                    [self.cell_ro('', style='field_comment', unlock=True), self.cell_ro('', style='hq_comment', unlock=True)]
                )
                line += 1

            else:
                sheet.append([
                    self.cell_ro('%s - %s' % (req_account.code, req_account.name), style='title_account'),
                    self.cell_ro(_('Description of the entry'), style='title_text'),
                    self.cell_ro(_('Reference of the entry'), style='title_text'),
                    self.cell_ro(_(company.currency_date_type), style='title_text'),
                    self.cell_ro(_('Curr'), style='title_info'),
                    self.cell_ro(_('Currency Amount'), style='title_amount'),
                    self.cell_ro('%s %s' % (date_used_label,_('Rate')), style='title_amount'),
                    self.cell_ro(_('%s Amount') % (company.currency_id.name, ), style='title_amount'),
                    self.cell_ro(_('Reconcile Number'), style='title_info'),
                    self.cell_ro(_('Third Party'), style='title_info'),
                    self.cell_ro(_("Field's Comments"), style='title_text'),
                    self.cell_ro(_("HQ Comments"), style='title_hq_comment'),
                ])

                line += 1

                # unreconciled or partial rec
                self.cr.execute('''
                    select
                        m.name, l.name, l.ref, l.''' + date_used + ''', cur.name, coalesce(l.amount_currency, 0),
                        (select
                            rate.rate
                        from
                            res_currency_rate rate
                        where
                            rate.currency_id = l.currency_id
                            and currency_table_id is null
                            and rate.name < coalesce(l.source_date, l.''' + date_used + ''')
                        order by
                            rate.name desc
                        limit 1
                        ) as fx_rate,
                        coalesce(l.debit, 0) - coalesce(l.credit, 0),
                        partial.name,
                        coalesce(partner.name, j.code, emp.name_resource||' '||emp.identification_id),
                        (
                            select sum(amount_currency) from account_move_line where reconcile_partial_id is not null and reconcile_partial_id = partial.id
                        )
                    from
                        account_move_line l
                        inner join account_account a on a.id = l.account_id
                        inner join account_period p on p.id = l.period_id
                        inner join account_move m on l.move_id = m.id
                        inner join res_currency cur on cur.id = l.currency_id
                        inner join account_journal journal on journal.id = l.journal_id
                        left join account_move_reconcile partial on partial.id = l.reconcile_partial_id
                        left join res_partner partner on partner.id = l.partner_id
                        left join hr_employee emp on emp.id = l.employee_id
                        left join account_journal j on j.id = l.transfer_journal_id
                    where
                        l.account_id = %(account_id)s
                        and p.number not in (0, 16)
                        and journal.type != 'revaluation'
                        and ( p.date_start < %(period_start)s or p.date_start = %(period_start)s and p.number <= %(period_number)s)
                        and m.state='posted'
                        and m.instance_id in %(instance)s
                        and l.reconcile_id is null
                    order by
                        m.name, l.id
                    ''', {
                    'account_id': req_account.id,
                    'period_number': report.period_id.number,
                    'period_start': report.period_id.date_start,
                    'instance': tuple(all_instance_ids),
                })

                for account_line in self.cr.fetchall():
                    sheet.append([
                        self.cell_ro(account_line[0], style='line_account'),
                        self.cell_ro(account_line[1], style='line_text'),
                        self.cell_ro(account_line[2], style='line_text'),
                        self.cell_ro(self.to_datetime(account_line[3]), style='line_date'),
                        self.cell_ro(account_line[4], style='line_curr'),
                        self.cell_ro(account_line[5], style='line_amount'),
                        self.cell_ro(account_line[6], style='line_amount'),
                        self.cell_ro(account_line[7], style='line_amount'),
                        self.cell_ro(account_line[8] and '%s (%.02lf)' % (account_line[8], account_line[10]) or '', style='line_info'),
                        self.cell_ro(account_line[9], style='line_text'),
                        self.cell_ro('', style='field_comment', unlock=True),
                        self.cell_ro('', style='hq_comment', unlock=True),
                    ])
                    line += 1
                    account_sum += round(account_line[7], 2)

                if report.selection == 'details':
                    sheet.append(
                        [self.cell_ro(_('List of entries reconciled in later periods >>>'), style='line_selection')] +
                        [self.cell_ro('', 'default_header_style')] * 9 +
                        [self.cell_ro('', style='field_comment', unlock=True), self.cell_ro('', style='hq_comment', unlock=True)]
                    )
                    line += 1

                    # reconciled later
                    self.cr.execute('''
                        select
                            m.name, l.name, l.ref, l.date, cur.name, coalesce(l.amount_currency, 0),
                            (select
                                rate.rate
                            from
                                res_currency_rate rate
                            where
                                rate.currency_id = l.currency_id
                                and currency_table_id is null
                                and rate.name < coalesce(l.source_date, l.''' + date_used + ''')
                            order by
                                rate.name desc
                            limit 1
                            ) as fx_rate,
                            coalesce(l.debit, 0) - coalesce(l.credit, 0),
                            rec.name,
                            coalesce(partner.name, j.code, emp.name_resource||' '||emp.identification_id)
                        from
                            account_move_line l
                            inner join account_account a on a.id = l.account_id
                            inner join account_period p on p.id = l.period_id
                            inner join account_move m on l.move_id = m.id
                            inner join res_currency cur on cur.id = l.currency_id
                            inner join account_move_reconcile rec on rec.id = l.reconcile_id
                            inner join account_journal journal on journal.id = l.journal_id
                            left join res_partner partner on partner.id = l.partner_id
                            left join hr_employee emp on emp.id = l.employee_id
                            left join account_journal j on j.id = l.transfer_journal_id
                        where
                            l.account_id = %(account_id)s
                            and journal.type != 'revaluation'
                            and p.number not in (0, 16)
                            and ( p.date_start < %(period_start)s or p.date_start = %(period_start)s and p.number <= %(period_number)s)
                            and m.state='posted'
                            and m.instance_id in %(instance)s
                            and
                                exists(
                                    select rec_line.id from account_move_line rec_line, account_period rec_p
                                where
                                    rec_line.reconcile_id = l.reconcile_id
                                    and rec_p.id = rec_line.period_id
                                    and (
                                        rec_p.date_start > %(period_start)s
                                        or rec_p.date_start = %(period_start)s and rec_p.number > %(period_number)s
                                    )
                                )
                        order by
                            m.name, l.id
                        ''', {
                        'account_id': req_account.id,
                        'period_number': report.period_id.number,
                        'period_start': report.period_id.date_start,
                        'instance': tuple(all_instance_ids),
                    })
                    for account_line in self.cr.fetchall():
                        sheet.append([
                            self.cell_ro(account_line[0], style='line_account'),
                            self.cell_ro(account_line[1], style='line_text'),
                            self.cell_ro(account_line[2], style='line_text'),
                            self.cell_ro(self.to_datetime(account_line[3]), style='line_date'),
                            self.cell_ro(account_line[4], style='line_curr'),
                            self.cell_ro(account_line[5], style='line_amount'),
                            self.cell_ro(account_line[6], style='line_amount'),
                            self.cell_ro(account_line[7], style='line_amount'),
                            self.cell_ro(account_line[8], style='line_info'),
                            self.cell_ro(account_line[9], style='line_text'),
                            self.cell_ro('', style='field_comment', unlock=True),
                            self.cell_ro('', style='hq_comment', unlock=True),
                        ])
                        line += 1
                        account_sum += round(account_line[7], 2)
                else:
                    # sum reconciled later
                    self.cr.execute('''
                        select
                            sum(coalesce(l.debit, 0) - coalesce(l.credit, 0))
                        from
                            account_move_line l
                            inner join account_account a on a.id = l.account_id
                            inner join account_period p on p.id = l.period_id
                            inner join account_move m on l.move_id = m.id
                            inner join res_currency cur on cur.id = l.currency_id
                            inner join account_move_reconcile rec on rec.id = l.reconcile_id
                            inner join account_journal journal on journal.id = l.journal_id
                        where
                            l.account_id = %(account_id)s
                            and p.number not in (0, 16)
                            and journal.type != 'revaluation'
                            and ( p.date_start < %(period_start)s or p.date_start = %(period_start)s and p.number <= %(period_number)s)
                            and m.state='posted'
                            and m.instance_id in %(instance)s
                            and
                                exists(
                                    select rec_line.id from account_move_line rec_line, account_period rec_p
                                where
                                    rec_line.reconcile_id = l.reconcile_id
                                    and rec_p.id = rec_line.period_id
                                    and (
                                        rec_p.date_start > %(period_start)s
                                        or rec_p.date_start = %(period_start)s and rec_p.number > %(period_number)s
                                    )
                                )
                        ''', {
                        'account_id': req_account.id,
                        'period_number': report.period_id.number,
                        'period_start': report.period_id.date_start,
                        'instance': tuple(all_instance_ids),
                    })
                    total_later = self.cr.fetchone()[0] or 0
                    account_sum += round(total_later, 2)
                    sheet.append(
                        [self.cell_ro(_('Total of entries reconciled in later periods >>>'), style='line_selection')] +
                        [self.cell_ro('', 'default_header_style')] * 6 +
                        [self.cell_ro(total_later, style='line_amount')] +
                        [self.cell_ro('', 'default_header_style')] * 2 +
                        [self.cell_ro('', style='field_comment', unlock=True), self.cell_ro('', style='hq_comment', unlock=True)]
                    )
                    line += 1

            sheet.append(
                [self.cell_ro('', 'header_1st_info_title')] +
                [self.cell_ro('', 'default_header_style')] * 6  +
                [self.cell_ro(account_sum, style='line_total')] +
                [self.cell_ro('', 'default_header_style')] * 2  +
                [self.cell_ro('', style='field_comment', unlock=True), self.cell_ro('', style='hq_comment', unlock=True)]
            )
            line += 1


            sheet.append([self.cell_ro('', 'header_1st_info_title')] + [self.cell_ro('', 'default_header_style')] * 9 + [self.cell_ro('', 'user_line', unlock=True)] * 2)
            sheet.merged_cells.ranges.append("K%(line)d:L%(line)d" % {'line': line})
            line += 1

            nb_account_done += 1
            if bk_id:
                bk_obj.write(self.cr, self.uid, bk_id, {'percent': max(0.95, 0.5 + 0.45 * nb_account_done/total_account)})


        sheet.append(
            [self.cell_ro('', 'end_doc_left')] +
            [self.cell_ro('---%s---' % _('END OF FIELD BALANCE SPECIFICATION REPORT'), style='end_doc')] +
            [self.cell_ro('', style='end_doc')] * 9 +
            [self.cell_ro('', 'end_doc_right')]
        )
        line += 1

        sheet.print_area = 'A1:L%d' % line
        if bk_id:
            bk_obj.write(self.cr, self.uid, bk_id, {'percent': 1.})

XlsxReport('report.field_balance_spec_report', parser=field_balance_spec_parser, template='addons/vertical_integration/report/field_balance_spec_report_template.xlsx')
