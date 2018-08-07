from osv import osv
from osv import fields
from tools.safe_eval import safe_eval
import logging

class res_log(osv.osv):

    _inherit = 'res.log'

    _columns = {
        'read_ok': fields.boolean(
            string='Read OK',
            help='Indicate if the user is able to open the document in res.log',
        ),
        'action_xmlid': fields.char('Xmlid of action to open', size=512),
    }

    _defaults = {
        'read_ok': False,
    }

    def _check_parent_menu_access(self, cr, uid, menu_id, context=None):
        """
        Check if the use can access to parent menus
        """
        menu_obj = self.pool.get('ir.ui.menu')

        menu_ids = []
        while menu_id:
            menu_ids.append(menu_id)
            cr.execute('''
                SELECT
                    m.parent_id, m.id
                FROM ir_ui_menu m
                WHERE m.id = %(menu_id)s
            ''', {'menu_id': menu_id})
            menus = cr.dictfetchall()
            for menu in menus:
                if menu.get('parent_id'):
                    menu_id = menu.get('parent_id')
                else:
                    menu_id = False

        # Check the visibility
        menu_acl = menu_obj._filter_visible_menus(cr, uid, menu_ids, context=context)
        menu_ids.reverse()
        for menu_id in menu_ids:
            if menu_id not in menu_acl:
                return False

        return True


    def _check_menu_access(self, cr, uid, model, context=None):
        """
        Check if the user can access to this object by checking the access to
        menus.
        """
        menu_obj = self.pool.get('ir.ui.menu')

        menus = False

        cr.execute('''
            SELECT
                m.parent_id, m.id
            FROM ir_ui_menu m
                LEFT JOIN
                    ir_values v ON v.res_id = m.id
            WHERE
                v.model = 'ir.ui.menu'
              AND
                v.key = 'action'
              AND
                v.key2 = 'tree_but_open'
              AND
                v.value IN (SELECT
                                'ir.actions.act_window,' || w.id
                            FROM
                                ir_act_window w
                            WHERE
                                w.res_model = %(model)s
                              AND
                                w.type = 'ir.actions.act_window')
        ''', {'model': model})

        menus = cr.dictfetchall()

        res = False
        for m in menus:
            m_access = True
            if m.get('parent_id'):
                m_access = self._check_parent_menu_access(cr, uid, m.get('parent_id'), context=context)
                if m_access:
                    res = True

            if m.get('id') and m_access:
                if m['id'] in menu_obj._filter_visible_menus(cr, uid, [m['id']], context=context):
                    res = True

        return res

    def _check_read_rights(self, cr, uid, model=False, rr=None, context=None):
        if rr is None:
            rr = {}

        user_id = hasattr(uid, 'realUid') and uid.realUid or uid
        read_ok = False
        if user_id and model:

            if (user_id, model) in rr:
                return rr[(user_id, model)]

            read_ok = self.pool.get('ir.model.access').check(cr, user_id, model, 'read', context=context)
            if read_ok:
                read_ok = self._check_menu_access(cr, user_id, model, context=context)

            rr[(user_id, model)] = read_ok

        return read_ok

    def create(self, cr, uid, vals, context=None):
        if vals is None:
            vals = {}

#        vals['read_ok'] = self._check_read_rights(cr, uid, vals.get('res_model', False), context=context)

        return super(res_log, self).create(cr, hasattr(uid, 'realUid') and uid.realUid or uid, vals, context=context)

    def get(self, cr, uid, context=None):
        unread_log_ids = self.search(cr, uid, [
            ('user_id', '=', uid),
            ('read', '=', False),
        ], context=context)
        result = []
        if not unread_log_ids:
            return result

        list_of_fields = [
            'name',
            'res_model',
            'res_id',
            'context',
            'domain',
            'read_ok',
            'action_xmlid',
        ]

        read_rights = {}

        res = self.read(cr, uid, unread_log_ids, list_of_fields, context=context)
        res.reverse()

        res_dict = {}
        action_seen = {}
        for r in res:
            if r['action_xmlid'] and (not r['domain'] or r['domain'] == '[]' or not r['context']):
                if r['action_xmlid'] not in action_seen:
                    try:
                        module, xmlid = r['action_xmlid'].split('.', 1)
                        action_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, module, xmlid)
                        action_seen[r['action_xmlid']] = self.pool.get('ir.actions.act_window').read(cr, uid, action_id[1], ['domain', 'context', 'views', 'view_mode', 'search_view_id'], context=context)
                    except ValueError:
                        action_seen[r['action_xmlid']] = False
                        logging.getLogger('res.log').warning('Action %s not found' % (r['action_xmlid']))

                action_data = action_seen.get(r['action_xmlid'])
                if action_data:
                    r['action_id'] = action_data['id']
                    action_ctx = {}
                    if r['context']:
                        try:
                            action_ctx = safe_eval(r['context'])
                            if action_data['search_view_id']:
                                action_ctx['search_view'] = action_data['search_view_id'][0]
                            if 'view_id' in action_ctx:
                                del(action_ctx['view_id'])
                            r['context'] = action_ctx
                        except:
                            pass
                    r['view_mode'] = '%s' % (action_data['view_mode'].split(','),)
                    r['view_ids'] = [x[0] for x in action_data['views']]
                    if action_data['domain'] and (not r['domain'] or r['domain'] == '[]'):
                        r['domain'] = action_data['domain']
                    if action_data['context'] and not r['context']:
                        r['context'] = action_data['context']
            r['read_ok'] = self._check_read_rights(cr, uid, r['res_model'], read_rights, context=context)
            t = (r['name'], r['res_model'], r['res_id'])
            if t not in res_dict:
                res_dict[t] = True
                result.insert(0,r)

        self.write(cr, uid, unread_log_ids, {'read': True}, context=context)
        return result

res_log()
