# -*- coding: utf-8 -*-

from osv import osv
from osv import fields
from tools.translate import _


class merged_ud_products(osv.osv_memory):
    _name = 'merged_ud_products'

    _columns = {
        'start_date': fields.date('Merge date from'),
        'end_date': fields.date('Merge date to'),
        'product_code': fields.char('Product Code', size=128),
        'main_type_id': fields.many2one('product.nomenclature', 'Main Type', domain=[('level', '=', 0)]),
    }


    def _get_non_kept_ids(self, cr, uid, ids, limit, offset=0, context=None):
        if isinstance(ids, int):
            ids = [ids]
        wiz = self.browse(cr, uid, ids[0], context=context)
        query_cond = [
            'old.kept_initial_product_id = new.id',
            'tmp.id = new.product_tmpl_id'
        ]
        query_filters = []
        if wiz.start_date:
            query_cond.append('old.unidata_merge_date >= %s')
            query_filters.append('%s 00:00:00' % wiz.start_date)
        if wiz.end_date:
            query_cond.append('old.unidata_merge_date <= %s')
            query_filters.append('%s 23:59:59' % wiz.end_date)
        if wiz.product_code:
            query_cond.append("(old.default_code ilike %s or new.default_code ilike %s)")
            query_filters += ['%%%s%%' % wiz.product_code, '%%%s%%' % wiz.product_code]
        if wiz.main_type_id:
            query_cond.append("tmp.nomen_manda_0 = %s")
            query_filters.append(wiz.main_type_id.id)


        query_filters += [limit, offset]
        cr.execute("""
            select
                old.id
            from
                product_product old, product_product new, product_template tmp
            where
            """ + ' and '.join(query_cond) + """
            order by
                new.default_code
            limit %s offset %s
        """, query_filters) # not_a_user_entry
        return [x[0] for x in cr.fetchall()]

    def print_excel(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        if not self._get_non_kept_ids(cr, uid, ids, limit=1, context=context):
            raise osv.except_osv(_('Not found'), _('No product matches the selection.'))

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'report_merged_ud_products',
            'datas': {'ids': ids},
            'context': context,
        }

merged_ud_products()
