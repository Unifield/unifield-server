# -*- coding: utf-8 -*-

from osv import fields,osv
from tools.translate import _


class res_partner_category(osv.osv):
    _inherit = 'res.partner.category'
    _name = 'res.partner.category'


    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        #@@@override res.partner.category._name_get_fnc()
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)
        # @@@end

    def _search_complete_name(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        if args[0][1] != "=":
            raise osv.except_osv(_('Error !'), _('Filter not implemented on %s')%(name,))

        parent_ids = None
        for path in args[0][2].split('/'):
            dom = [('name', '=', path.strip())]
            if parent_ids is None:
                dom.append(('parent_id', '=', False))
            else:
                dom.append(('parent_id', 'in', parent_ids))
            ids = self.search(cr, uid, dom)
            if not ids:
                return [('id', '=', 0)]
            parent_ids = ids

        return [('id', 'in', ids)]
    
    _columns = {
        'complete_name': fields.function(_name_get_fnc, method=True, type="char", string='Full Name', fnct_search=_search_complete_name),
    }
res_partner_category()
