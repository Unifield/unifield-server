# -*- coding: utf-8 -*-
from spreadsheet_xml.xlsx_write import XlsxReport
from spreadsheet_xml.xlsx_write import XlsxReportParser
from datetime import datetime
from tools.translate import _


class hq_product_mml_nonconform(XlsxReportParser):
    def generate(self, context=None):
        if context is None:
            context = {}

        prod_obj = self.pool.get('product.product')

        company_record = self.pool.get('res.company')._get_instance_record(self.cr, self.uid)
        instance_code = company_record.code
        self.instance_id = company_record.id

        sheet = self.workbook.active

        self.create_style_from_template('title_style', 'A1')
        self.create_style_from_template('filter_txt', 'A2')
        self.create_style_from_template('filter_date', 'B3')


        self.create_style_from_template('header_row', 'A5')
        self.create_style_from_template('stock_row', 'G5')
        self.create_style_from_template('row', 'A6')


        self.duplicate_column_dimensions(default_width=10.75)
        sheet.freeze_panes = 'A6'


        title = _('Products not in MML')
        sheet.title = title

        sheet.merged_cells.ranges.append("A1:F1")
        sheet.append([self.cell_ro(title, 'title_style')])

        sheet.append([
            self.cell_ro(_('Instance'), 'filter_txt'),
            self.cell_ro(instance_code, 'filter_txt'),
        ])
        sheet.append([
            self.cell_ro(_('Date'), 'filter_txt'),
            self.cell_ro(datetime.now(), 'filter_date'),
        ])
        sheet.append([])

        sheet.append([
            self.cell_ro(_('Code'), 'header_row'),
            self.cell_ro(_('Description'), 'header_row'),
            self.cell_ro(_('Product Creator'), 'header_row'),
            self.cell_ro(_('Standardization Level'), 'header_row'),
            self.cell_ro(_('UniData Status'), 'header_row'),
            self.cell_ro(_('UniField Status'), 'header_row'),
            self.cell_ro(_('Instance/Mission'), 'stock_row'),
            self.cell_ro(_('Instance stock'), 'stock_row'),
            self.cell_ro(_('Pipeline Qty'), 'stock_row'),
            self.cell_ro(_('In Instance MSL?'), 'stock_row'),
            self.cell_ro(_('Mission / Project Restriction'), 'stock_row')
        ])


        fields = prod_obj.fields_get(self.cr, self.uid, ['standard_ok', 'state_ud'], context=context)
        label_standard_ok = dict(fields['standard_ok']['selection'])
        label_state_ud = dict(fields['state_ud']['selection'])

        product_code = {}

        extra_join_cond = ''
        include_pipe = self.pool.get('non.conform.inpipe').read(self.cr, self.uid, self.ids[0], ['include_pipe'])['include_pipe']
        if include_pipe:
            extra_join_cond = 'smrl.in_pipe_qty > 0 or'

        # get oc_validation=f prod with stock/pipe
        self.cr.execute('''
            select p.id, p.default_code
            from product_product p
            inner join product_template tmpl on tmpl.id = p.product_tmpl_id
            inner join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
            inner join stock_mission_report_line smrl on p.id = smrl.product_id and (''' + extra_join_cond + ''' smrl.internal_qty > 0)
            inner join stock_mission_report smr on smr.id=smrl.mission_report_id and smr.full_view = 'f'
            inner join product_international_status creator on creator.id = p.international_status
            where
                nom.name='MED'
                and nom.level = 0
                and creator.code not in ('local', 'temp')
                and coalesce(oc_validation,'f')='f'
            group by p.id, p.default_code
        ''')
        for p in self.cr.fetchall():
            product_code[p[1]] = p[0]

        # get restricted prod with stock/pipe
        self.cr.execute('''
                select distinct p.id, p.default_code
            from product_product p
            inner join product_template tmpl on tmpl.id = p.product_tmpl_id
            inner join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
            inner join stock_mission_report_line smrl on p.id = smrl.product_id and (''' + extra_join_cond + ''' smrl.internal_qty > 0)
            inner join stock_mission_report smr on smr.id=smrl.mission_report_id and smr.full_view = 'f'
            inner join product_international_status creator on creator.id = p.international_status
            left join product_project_rel p_rel on p.id = p_rel.product_id
            left join product_country_rel c_rel on p_rel is null and c_rel.product_id = p.id
            left join unidata_project up1 on up1.id = p_rel.unidata_project_id or up1.country_id = c_rel.unidata_country_id
            where
                nom.name='MED'
                and nom.level = 0
                and creator.code not in ('local', 'temp')
                and coalesce(oc_validation,'f')='t'
            group by p.id, p.default_code, smr.instance_id
            HAVING
                (
                        not ARRAY[smr.instance_id]<@array_agg(up1.instance_id)
                        and
                        count(up1.instance_id)>0
                 )
        ''')
        for p in self.cr.fetchall():
            product_code[p[1]] = p[0]

        p_ids = [product_code[x] for x in sorted(product_code.keys())]
        len_p_ids = len(p_ids)
        page_size = 500
        offset = 0

        bk_id = self.context.get('background_id')

        while True:
            prod_ids = p_ids[offset:offset+page_size]
            if not prod_ids:
                break
            offset += page_size
            self.cr.execute('''
            select x.id, x.instance_name, x.internal_qty, x.in_pipe_qty, x.has_msl from (
                select p.id, instance.name as instance_name, smrl.internal_qty, smrl.in_pipe_qty, count(msl_rel) as has_msl
                from product_product p
                inner join product_template tmpl on tmpl.id = p.product_tmpl_id
                inner join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
                inner join stock_mission_report_line smrl on p.id = smrl.product_id and (smrl.in_pipe_qty > 0 or smrl.internal_qty > 0)
                inner join stock_mission_report smr on smr.id=smrl.mission_report_id and smr.full_view = 'f'
                inner join product_international_status creator on creator.id = p.international_status
                inner join msf_instance instance on instance.id = smr.instance_id
                left join unidata_project ud_proj on ud_proj.instance_id = smr.instance_id
                left join product_msl_rel msl_rel on msl_rel.product_id = p.id and msl_rel.creation_date is not null and msl_rel.msl_id = ud_proj.id
                where
                    nom.name='MED'
                    and nom.level = 0
                    and creator.code not in ('temp', 'local')
                    and coalesce(oc_validation,'f')='f'
                    and p.id in %(prod_ids)s
                group by p.id, instance.name, smrl.internal_qty, smrl.in_pipe_qty

            UNION ALL

                select p.id, instance.name as instance_name, smrl.internal_qty, smrl.in_pipe_qty, count(msl_rel) as has_msl
                from product_product p
                inner join product_template tmpl on tmpl.id = p.product_tmpl_id
                inner join product_nomenclature nom on tmpl.nomen_manda_0 = nom.id
                inner join stock_mission_report_line smrl on p.id = smrl.product_id and (smrl.in_pipe_qty > 0 or smrl.internal_qty > 0)
                inner join stock_mission_report smr on smr.id=smrl.mission_report_id and smr.full_view = 'f'
                inner join product_international_status creator on creator.id = p.international_status
                inner join msf_instance instance on instance.id = smr.instance_id
                left join product_project_rel p_rel on p.id = p_rel.product_id
                left join product_country_rel c_rel on p_rel is null and c_rel.product_id = p.id
                left join unidata_project up1 on up1.id = p_rel.unidata_project_id or up1.country_id = c_rel.unidata_country_id
                left join unidata_project ud_proj on ud_proj.instance_id = smr.instance_id
                left join product_msl_rel msl_rel on msl_rel.product_id = p.id and msl_rel.creation_date is not null and msl_rel.msl_id = ud_proj.id
                where
                    nom.name='MED'
                    and nom.level = 0
                    and creator.code not in ('temp', 'local')
                    and coalesce(oc_validation,'f')='t'
                    and p.id in %(prod_ids)s
                group by p.id, smr.instance_id, instance.name, smrl.internal_qty, smrl.in_pipe_qty
                HAVING
                    (
                            not ARRAY[smr.instance_id]<@array_agg(up1.instance_id)
                            and
                            count(up1.instance_id)>0
                     )
                ) x
                order by x.id, x.instance_name
            ''', {'prod_ids': tuple(prod_ids)})

            prod_instance = {}
            for x in self.cr.fetchall():
                prod_instance.setdefault(x[0], []).append(x)

            for prod in prod_obj.browse(self.cr, self.uid, prod_ids, fields_to_fetch=['default_code', 'name', 'international_status', 'standard_ok', 'state_ud', 'state', 'restrictions_txt'], context=context):
                for instance in prod_instance.get(prod.id, []):
                    sheet.append([
                        self.cell_ro(prod.default_code, 'row'),
                        self.cell_ro(prod.name, 'row'),
                        self.cell_ro(prod.international_status.name, 'row'),
                        self.cell_ro(label_standard_ok.get(prod.standard_ok), 'row'),
                        self.cell_ro(label_state_ud.get(prod.state_ud), 'row'),
                        self.cell_ro(prod.state.name, 'row'),
                        self.cell_ro(instance[1], 'row'),
                        self.cell_ro(instance[2] or '', 'row'),
                        self.cell_ro(instance[3] or '', 'row'),
                        self.cell_ro(instance[4] and _('Y') or _('N'), 'row'),
                        self.cell_ro(prod.restrictions_txt, 'row'),
                    ])
            if bk_id:
                self.pool.get('memory.background.report').write(self.cr, self.uid, bk_id, {'percent': offset/float(len_p_ids)})


        sheet.auto_filter.ref = "A5:G5"


XlsxReport('report.report.hq_product_mml_nonconform', parser=hq_product_mml_nonconform, template='addons/product_attributes/report/hq_product_mml_nonconform.xlsx')

