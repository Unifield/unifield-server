# -*- coding: utf-8 -*-

from osv import fields
import warnings
import pooler

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
        for i in ids:
            res[i] = []
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
        if obj._order:
            order_by = ' ORDER BY '
            order_tab = []
            for order in obj._order.split(','):
                order_tab.append('%s.%s' %(from_c, order.strip()))
            order_by += ','.join(order_tab)

        limit_str = ''
        if self._limit is not None:
            limit_str = ' LIMIT %d' % self._limit

        if self._rel == 'account_destination_link' and not context.get('display_disabled'):
            where_c = " %s AND disabled='f' " % (where_c, )
        query = '''SELECT %(rel)s.%(id2)s, %(rel)s.%(id1)s
                   FROM %(rel)s, %(from_c)s
                  WHERE %(rel)s.%(id1)s IN %%s
                    AND %(rel)s.%(id2)s = %(tbl)s.id
                 %(where_c)s
                 %(order_by)s
                 %(limit)s
                 OFFSET %(offset)d''' % {'rel': self._rel,  # not_a_user_entry
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


class many2many_notlazy(many2many_sorted):
    def __init__(self, obj, rel, id1, id2, string='unknown', limit=None, **args):
        super(many2many_notlazy, self).__init__(obj, rel, id1, id2, string, limit, **args)

    def set(self, cr, obj, m_id, name, values, user=None, context=None):
        if context is None:
            context = {}
        if not values:
            return
        obj = obj.pool.get(self._obj)
        newargs = []
        for act in values:
            if not (isinstance(act, list) or isinstance(act, tuple)) or not act:
                continue
            if act[0] == 4 and self._rel == 'account_destination_link':
                link_obj = pooler.get_pool(cr.dbname).get('account.destination.link')
                link_obj.create(cr, user, {self._id1: m_id, self._id2: act[1]})
            if act[0] == 6:
                d1, d2,tables = obj.pool.get('ir.rule').domain_get(cr, user, obj._name, context=context)
                if d1:
                    d1 = ' and ' + ' and '.join(d1)
                else:
                    d1 = ''
                args = [m_id, m_id]+d2
                if not act[2]:
                    args.append((0,))
                else:
                    args.append(tuple(act[2]))

                # JIRA UTP-334
                if self._rel == 'account_destination_link':
                    cr.execute('select id from '+self._rel+' where '+self._id1+'=%s AND '+self._id2+' IN (SELECT '+self._rel+'.'+self._id2+' FROM '+self._rel+', '+','.join(tables)+' WHERE '+self._rel+'.'+self._id1+'=%s AND '+self._rel+'.'+self._id2+' = '+obj._table+'.id '+ d1 +' and '+self._rel+'.'+self._id2+' not in %s)', args)  # not_a_user_entry
                    unlink_obj = pooler.get_pool(cr.dbname).get('account.destination.link')
                    for unlinked_id in cr.fetchall():
                        unlink_obj.unlink(cr, user, unlinked_id[0])
                else:
                    cr.execute('delete from '+self._rel+' where '+self._id1+'=%s AND '+self._id2+' IN (SELECT '+self._rel+'.'+self._id2+' FROM '+self._rel+', '+','.join(tables)+' WHERE '+self._rel+'.'+self._id1+'=%s AND '+self._rel+'.'+self._id2+' = '+obj._table+'.id '+ d1 +' and '+self._rel+'.'+self._id2+' not in %s)', args)  # not_a_user_entry


                cr.execute('select '+self._id2+' from '+self._rel+' where '+self._id1+'=%s', [m_id, ])  # not_a_user_entry
                existing = [x[0] for x in cr.fetchall()]

                for act_nbr in act[2]:
                    if act_nbr not in existing:
                        if self._rel == 'account_destination_link':
                            link_obj = pooler.get_pool(cr.dbname).get('account.destination.link')
                            link_obj.create(cr, user, {self._id1: m_id, self._id2: act_nbr})
                        else:
                            cr.execute('insert into '+self._rel+' ('+self._id1+','+self._id2+') values (%s, %s)', (m_id, act_nbr))  # not_a_user_entry

            else:
                newargs.append(act)
        if newargs:
            return super(many2many_notlazy, self).set(cr, obj, m_id, name, newargs, user=user, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
