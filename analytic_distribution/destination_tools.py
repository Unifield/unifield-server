# -*- coding: utf-8 -*-

from osv import fields, osv
import warnings


class many2many_sorted(fields.many2many):
    def __init__(self, obj, rel, id1, id2, string='unknown', limit=None, **args):
        super(many2many_sorted, self).__init__(obj, rel, id1, id2, string, limit, **args)

    def get(self, cr, obj, ids, name, user=None, offset=0, context=None, values=None):
        if not context:
            context = {}
        if not values:
            values = {}
        res = {}
        if not ids:
            return res
        for id in ids:
            res[id] = []
        if offset:
            warnings.warn("Specifying offset at a many2many.get() may produce unpredictable results.",
                      DeprecationWarning, stacklevel=2)
        obj = obj.pool.get(self._obj)

        # static domains are lists, and are evaluated both here and on client-side, while string
        # domains supposed by dynamic and evaluated on client-side only (thus ignored here)
        # FIXME: make this distinction explicit in API!
        domain = isinstance(self._domain, list) and self._domain or []

        wquery = obj._where_calc(cr, user, domain, context=context)
        obj._apply_ir_rules(cr, user, wquery, 'read', context=context)
        from_c, where_c, where_params = wquery.get_sql()
        if where_c:
            where_c = ' AND ' + where_c

        order_by = ''
        rel_obj = obj.pool.get('account.destination.link')
        if rel_obj._order:
            order_by = ' ORDER BY '
            order_tab = []
            for order in rel_obj._order.split(','):
                order_tab.append('%s.%s' %(from_c, order.strip()))
            order_by += ','.join(order_tab)

        limit_str = ''
        if self._limit is not None:
            limit_str = ' LIMIT %d' % self._limit

        query = 'SELECT %(rel)s.%(id2)s, %(rel)s.%(id1)s \
                   FROM %(rel)s, %(from_c)s \
                  WHERE %(rel)s.%(id1)s IN %%s \
                    AND %(rel)s.%(id2)s = %(tbl)s.id \
                 %(where_c)s  \
                 %(order_by)s \
                 %(limit)s \
                 OFFSET %(offset)d' \
            % {'rel': self._rel,
               'from_c': from_c,
               'tbl': obj._table,
               'id1': self._id1,
               'id2': self._id2,
               'where_c': where_c,
               'limit': limit_str,
               'order_by': order_by,
               'offset': offset,
              }
        cr.execute(query, [tuple(ids),] + where_params)
        for r in cr.fetchall():
            res[r[1]].append(r[0])
        return res
