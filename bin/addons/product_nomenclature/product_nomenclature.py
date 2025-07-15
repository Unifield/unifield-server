# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv, fields
from tools.translate import _
import tools
from os import path
import logging
import random
import string

# maximum depth of level
_LEVELS = 4
# numbers of sub levels (optional levels)
_SUB_LEVELS = 6

RANDOM_XMLID_CODE_PREFIX = 'XID-'
#----------------------------------------------------------
# Nomenclatures
#----------------------------------------------------------
class product_nomenclature(osv.osv):

    def export_data(self, cr, uid, ids, fields_to_export, context=None):
        '''
        UF-1952 : Don't display complete name of each level when exporting
        the product nomenclatures
        '''
        if not context:
            context = {}

        if not context.get('sync_update_execution') and not context.get('sync_message_execution'):
            context.update({'nolevel': True})
        return super(product_nomenclature, self).export_data(cr, uid, ids, fields_to_export, context=context)

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []

        # Here we explicitly want to recreate another context in case the
        # context is empty. Because name_get() call read(), which call
        # name_get(), which call read(), ...... and if we reuse the same
        # context all the time it ends up in an infinite loop error
        if not context:
            context = {}

        if not context.get('sync_update_execution') and not context.get('sync_message_execution') and \
                (not context.get('lang') or context.get('lang') == 'en_US'):
            # UF-1662: Set the correct lang of the user, otherwise the system will get by default the wrong en_US value
            lang_dict = self.pool.get('res.users').read(cr, uid, uid, ['context_lang'])
            if not context.get('yml_test', False):
                if lang_dict.get('context_lang'):
                    context['lang'] = lang_dict.get('context_lang')

        fields = ['name', 'parent_id']
        if context.get('withnum') == 1:
            fields.append('number_of_products')
        reads = self.read(cr, uid, ids, fields, context=context)

        res = []
        for record in reads:
            name = record['name']
            if not context.get('nolevel') and record['parent_id']:
                name = record['parent_id'][1] + ' | ' + name
            if context.get('withnum') == 1:
                name = "%s (%s)" % (name, record['number_of_products'])
            res.append((record['id'], name))
        return res


    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    def _returnConstants(self):
        '''
        return contants of product_nomenclature object
        '''
        return {'levels':_LEVELS, 'sublevels':_SUB_LEVELS}

    def _getDefaultLevel(self, cr, uid, context=None):
        '''
        Return the default level for the created object.
        Default value is equal to 1
        cannot be modified by the user (not displayed on screen)
        '''
        # default level is 1 if no parent it is a root
        result = 0

        # test = self._columns.get('parent_id')
        # test = self._columns['name']

        # get the parent object's level + 1
        # result = self.browse(cr, uid, self.parent_id, context).level + 1

        return result

    def _getDefaultSequence(self, cr, uid, context=None):
        '''
        not use presently. the idea was to use the sequence
        in order to sort nomenclatures in the tree view
        '''
        return 0

    def onChangeParentId(self, cr, uid, id, type, parentId):
        '''
        parameters:
        - type : the selected type for nomenclature
        - parentId : the id of newly selected parent nomenclature

        onChange method called when the parent nomenclature changes updates the parentLevel value from the parent object

        improvement :

        '''
        value = {'level': 0}
        result = {'value': value, 'warning': {}}

        # empty field
        if not parentId:
            return result

        parentLevel = self.browse(cr, uid, parentId).level
        level = parentLevel + 1

        # level check - parent_id : False + error message
        if level > _LEVELS:
            result['value'].update({'parent_id': False})
            result['warning'].update({'title': _('Error!'), 'message': _('The selected nomenclature should not be proposed.')})
            return result

        if level == _LEVELS:
            # this nomenclature must be of type optional
            if type != 'optional':
                result['value']['parent_id'] = False
                result['warning'].update({
                    'title': _('Warning!'),
                    'message': _("You selected a nomenclature of the last mandatory level as parent, the new nomenclature's type must be 'optional'."),
                })
                return result

        # selected parent ok
        result['value']['level'] = level

        return result

    def _nomenclatureCheck(self, vals):
        '''
        Integrity function for creation and update of nomenclature

        check level value and type value
        '''
        if ('level' in vals) and ('type' in vals):
            level = int(vals['level'])
            type = vals['type']
            # level test
            if level > _LEVELS:
                raise osv.except_osv(_('Error'), _('Level (%s) must be smaller or equal to %s') % (level, _LEVELS))
            # type test
            if (level == _LEVELS) and (type != 'optional'):
                raise osv.except_osv(_('Error'), _('The type (%s) must be equal to "optional" to inherit from leaves') % (type,))

    def write(self, cr, user, ids, vals, context=None):
        '''
        override write method to check the validity of selected
        parent
        '''
        if not ids:
            return True
        self._nomenclatureCheck(vals)
        # save the data to db
        return super(product_nomenclature, self).write(cr, user, ids, vals, context=context)

    def create(self, cr, user, vals, context=None):
        '''
        override create method to check the validity of selected parent
        '''
        self._nomenclatureCheck(vals)
        return super(product_nomenclature, self).create(cr, user, vals,
                                                        context=context)

    def unlink(self, cr, uid, ids, context=None):
        """
        Check if the deleted product nomenclature is not a system one
        """
        data_obj = self.pool.get('ir.model.data')

        nomen_data_id = [
            'nomen_tbd0',
            'nomen_tbd1',
            'nomen_tbd2',
            'nomen_tbd3',
        ]

        for data_id in nomen_data_id:
            try:
                nomen_id = data_obj.get_object_reference(
                    cr, uid, 'msf_doc_import', data_id)[1]
                if nomen_id in ids:
                    nomen_name = self.read(cr, uid, nomen_id, ['name'])['name']
                    raise osv.except_osv(
                        _('Error'),
                        _('''The nomenclature '%s' is an Unifield internal nomenclature, so you can't remove it''') % nomen_name,
                    )
            except ValueError:
                pass

        return super(product_nomenclature, self).unlink(cr, uid, ids, context=context)

    def _getNumberOfProducts(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns the number of products for the nomenclature
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for nomen in self.browse(cr, uid, ids, fields_to_fetch=['type', 'level', 'sub_level'], context=context):
            name = ''
            if nomen.type == 'mandatory':
                name = 'nomen_manda_%s' % nomen.level
            if nomen.type == 'optional':
                name = 'nomen_sub_%s' % nomen.sub_level
            products = self.pool.get('product.product').search(cr, uid, [(name, '=', nomen.id)], count=True, context=context)
            if not products:
                res[nomen.id] = 0
            else:
                res[nomen.id] = products

        return res

    def _search_complete_name(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []
        if args[0][1] not in ('=', '=ilike'):
            raise osv.except_osv(_('Error !'), _('Filter not implemented on %s') % (name,))

        parent_ids = None
        lang = context.get('lang', 'en_MF')
        for path_s in args[0][2].split('|'):
            sql_cond = {'nomen_name': path_s.strip(), 'lang': lang}
            if parent_ids is None:
                sql_parent = " AND parent_id IS NULL"
            else:
                sql_parent = " AND parent_id IN %(parent_ids)s"
                sql_cond['parent_ids'] = tuple(parent_ids)
            sql = """
                SELECT n.id FROM product_nomenclature n 
                LEFT JOIN ir_translation t ON t.lang = %(lang)s AND t.name = 'product.nomenclature,name' AND t.res_id = n.id
                WHERE (t.value ILIKE %(nomen_name)s OR n.name ILIKE %(nomen_name)s)
            """ + sql_parent # not_a_user_entry
            cr.execute(sql, sql_cond)
            ids = [x[0] for x in cr.fetchall()]
            if not ids:
                return [('id', '=', 0)]
            parent_ids = ids

        return [('id', 'in', ids)]

    def _get_category_id(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the first category of the nomenclature
        '''
        res = {}
        for nom in self.browse(cr, uid, ids, context=context):
            res[nom.id] = False
            if nom.category_ids:
                res[nom.id] = nom.category_ids[0].id

        return res

    def _src_category_id(self, cr, uid, obj, name, args, context=None):
        '''
        Returns all nomenclature according to the category
        '''
        if not args:
            return []

        res = [('level', '=', 2), ('type', '=', 'mandatory')]
        if args[0][1] == 'ilike':
            res.append(('name', 'ilike', args[0][2]))
            return res

        if args[0][1] not in ('=', '!=', 'ilike'):
            raise osv.except_osv(_('Error'), _('Bad operator : You can only use \'=\', \'!=\' or \'ilike\' as operator'))

        if args[0][2] != False and not isinstance(args[0][2], int):
            raise osv.except_osv(_('Error'), _('Bad operand : You can only give False or the id of a category'))

        if args[0][2] == False:
            res.append(('category_ids', args[0][1], False))
            return res

        if isinstance(args[0][2], int):
            categ = self.pool.get('product.category').browse(cr, uid, args[0][2])
            return [('id', args[0][1], categ.family_id.id)]

        return res

    def _get_nomen_s(self, cr, uid, ids, fields, *a, **b):
        """
        With the UF-1853, we display the nomenclature levels in 4 different columns.
        """
        ret = {}
        context = len(a) > 1 and a[1] or b.get('context')
        if context is None:
            context = {}
        for nomen in self.browse(cr, uid, ids, context):
            ret[nomen.id] = {'nomen_manda_0_s': False, 'nomen_manda_1_s': False, 'nomen_manda_2_s': False, 'nomen_manda_3_s': False}
            level = nomen.level or 0
            record = nomen
            while level >= 0:
                ret[nomen.id]['nomen_manda_%s_s' % level] = record and (record.id, record.name) or False
                record = record.parent_id
                level -= 1
        return ret

    def _get_childs(self, cr, uid, narg, ids):
        ids_p = self.search(cr, uid, [('parent_id', 'in', ids)])
        if ids_p:
            ids_p += self._get_childs(cr, uid, narg, ids_p)
        narg += ids_p
        return narg

    def _search_nomen_s(self, cr, uid, obj, name, args, context=None):
        if context is None:
            context = {}
        if not args:
            return []
        narg = []
        for arg in args:
            ids_rech = self._get_childs(cr, uid, narg, [arg[2]])
        ids_rech += [arg[2]]
        return [('id', 'in', ids_rech)]

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        '''
        the nomenclature selection search changes
        '''
        if context is None:
            context = {}
        # UF-1662: Set the correct lang of the user, otherwise the system will get by default the wrong en_US value
        lang_dict = self.pool.get('res.users').read(cr, uid, uid, ['context_lang'])
        if lang_dict.get('context_lang'):
            context['lang'] = lang_dict.get('context_lang')

        mandaName = 'nomen_manda_%s'
        # selected value
        selected = eval('nomen_manda_%s' % position)
        # if selected value is False, the first False value -1 is used as selected
        if not selected:
            mandaVals = []
            for i in range(_LEVELS):
                if not eval('nomen_manda_%s' % i):
                    mandaVals.append(i)
            if mandaVals[0] == 0:
                # first drop down, initialization
                selected = False
                position = -1
            else:
                # the first drop down with False value -1
                position = mandaVals[0] - 1
                selected = eval('nomen_manda_%s' % position)

        values = {}
        result = {'value': values}

        # clear upper levels mandatory
        for i in range(position + 1, _LEVELS):
            values[mandaName % (i)] = [()]

        # nomenclature object
        nomenObj = self.pool.get('product.nomenclature')

        if position == 2 and nomen_manda_2:
            for n in nomenObj.read(cr, uid, [nomen_manda_2], ['category_id'], context=context):
                values['categ_id'] = n['category_id'] or False

        # loop through children nomenclature of mandatory type
        shownum = num or context.get('withnum') == 1
        if position < 3:
            nomenids = nomenObj.search(cr, uid, [('active', 'in', ['t', 'f']), ('type', '=', 'mandatory'), ('parent_id', '=', selected)], order='name', context=context)
            if nomenids:
                for n in nomenObj.read(cr, uid, nomenids, ['name'] + (shownum and ['number_of_products'] or []), context=context):
                    # get the name and product number
                    id = n['id']
                    name = n['name']
                    if shownum:
                        values[mandaName % (position + 1)].append((id, name))
                    else:
                        values[mandaName % (position + 1)].append((id, name))

        if num:
            newval = {}
            for x in values:
                newval['%s_s' % x] = values[x]
            result['value'] = newval
        return result

    def _get_fake(self, cr, uid, ids, fields, *a, **b):
        ret = {}
        for id in ids:
            ret[id] = False
        return ret

    def _search_nomen_type_s(self, cr, uid, obj, name, args, context=None):
        if context is None:
            context = {}
        if not args:
            return []
        narg = []
        for arg in args:
            if arg[2] == 'mandatory':
                narg += [('type', '=', arg[2])]
            else:
                narg += [('type', '=', arg[2])]
        return narg

    def _get_custom_name(self, cr, uid, ids, field_name, args, context=None):
        '''
        return false for each id
        '''
        if isinstance(ids, int):
            ids = [ids]
        result = {}
        for id in ids:
            result[id] = False
        return result

    def _search_custom_name(self, cr, uid, obj, name, args, context=None):
        """
        Enable to search a nomenclature level according all its levels
        """
        if not args:
            return []
        if args[0][1] != "ilike":
            raise osv.except_osv(_('Error !'), _('Filter not implemented on %s') % (name,))
        dom = ['|', ('name', 'ilike', args[0][2]), ('parent_id', 'ilike', args[0][2])]
        ids = self.search(cr, uid, dom, context=context)
        if not ids:
            return [('id', '=', 0)]
        return [('id', 'in', ids)]

    _name = "product.nomenclature"
    _description = "Product Nomenclature"
    _columns = {
        'active': fields.boolean('Active', help="If the active field is set to False, it allows to hide the nomenclature without removing it."),
        'name': fields.char('Name', size=128, required=True, select=True, translate=1),
        'complete_name': fields.function(_name_get_fnc, method=True, type="char", string='Full name', fnct_search=_search_complete_name),
        'custom_name': fields.function(_get_custom_name, method=True, type="char", string='Name', fnct_search=_search_custom_name),
        # technic fields - tree management
        'parent_id': fields.many2one('product.nomenclature', 'Parent Nomenclature', select=True),
        # TODO try to display child_ids on screen. which result ?
        'child_id': fields.one2many('product.nomenclature', 'parent_id', string='Child Nomenclatures'),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of product nomenclatures.", select=1),
        'level': fields.integer('Level', size=256, select=1),
        'type': fields.selection([('mandatory', 'Mandatory'), ('optional', 'Optional')], 'Nomenclature Type', select=1),
        # corresponding level for optional levels, must be string, because integer 0 is treated as False, and thus required test fails
        'sub_level': fields.selection([('0', '1'), ('1', '2'), ('2', '3'), ('3', '4'), ('4', '5'), ('5', '6')], 'Sub-Level', size=256),
        'number_of_products': fields.function(_getNumberOfProducts, type='integer', method=True, store=False, string='Number of Products', readonly=True),
        'category_id': fields.function(_get_category_id, fnct_search=_src_category_id,
                                       method=True, type='many2one',
                                       relation='product.category', string='Category',
                                       help='If empty, please contact accounting member to create a new product category associated to this family.'),
        'category_ids': fields.one2many('product.category', 'family_id', string='Categories'),

        'nomen_manda_0_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Main Type', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_1_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Group', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_2_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Family', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_3_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Root', fnct_search=_search_nomen_s, multi="nom_s"),

        'nomen_type_s': fields.function(_get_fake, method=True, type='selection', selection=[('mandatory', 'Mandatory'), ('optional', 'Optional')], string='Nomenclature type', fnct_search=_search_nomen_type_s),
        'msfid': fields.char('MSFID', size=128, select=True),
        'status': fields.selection([('valid', 'Valid'), ('archived', 'Archived')], 'Status', readonly=True),
    }

    _defaults = {
        'level': _getDefaultLevel,  # no access to actual new values, use onChange function instead
        'type': lambda *a: 'mandatory',
        'sub_level': lambda *a: '0',
        'sequence': _getDefaultSequence,
        'active': True,
        'status': 'valid',
    }

    _order = "sequence, level, msfid, id"

    _sql_constraints = [('check_msfid_unique', 'unique (msfid)', 'MSFID must be unique !')]


    def _auto_init(self, cr, context=None):
        super(product_nomenclature, self)._auto_init(cr, context)
        cr.execute("SELECT indexname FROM pg_indexes WHERE indexname = 'product_nomenclature_sequence_level_msfid_id_idx'")
        if not cr.fetchone():
            cr.execute('CREATE INDEX product_nomenclature_sequence_level_msfid_id_idx ON product_nomenclature (sequence, level, msfid, id)')
            cr.commit()


    def _check_recursion(self, cr, uid, ids, context=None):
        level = 100
        while len(ids):
            cr.execute('select distinct parent_id from product_nomenclature where id IN %s', (tuple(ids),))
            ids = [_f for _f in [x[0] for x in cr.fetchall()] if _f]
            if not level:
                return False
            level -= 1
        return True

    def _check_link(self, cr, uid, ids, context=None):
        for level in self.browse(cr, uid, ids, context=context):
            if level.category_ids:
                if len(level.category_ids) > 1:
                    return False

        return True

    def _check_complete_name_uniq(self, cr, uid, ids, context=None):
        # UF-2022: Because of this constraint, the initial sync of nomenclature got blocked - as the list of Nomenclature got sync-ed
        # first, and the link to parent got sync-ed afterward, which violates the uniqueness on name.
        # Currently we don't have any better solution for this, we will temporarily "disable" it

        #        if isinstance(ids, int):
        #            ids = [ids]
        #        for nomen in self.browse(cr, uid, ids, context=context):
        #            if self.search_count(cr, uid, [('complete_name', '=', nomen.complete_name)], context=context)>1:
        #                return False
        return True

    _constraints = [
        (_check_recursion, 'Error ! You can not create recursive nomenclature.', ['parent_id']),
        (_check_link, 'Error ! You can not have a category linked to two different family', ['category_ids']),
        (_check_complete_name_uniq, 'Error! The nomenclature complete name must be unique.', [])
    ]
    def child_get(self, cr, uid, ids):
        return [ids]

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}

        default.update({'category_ids': []})
        return super(product_nomenclature, self).copy(cr, uid, id, default, context=context)


    def get_nomen(self, cr, uid, obj, id, field, context=None):
        if context is None:
            context = {}
        context['nolevel'] = 1
        parent = {'nomen_manda_1': 'nomen_manda_0', 'nomen_manda_2': 'nomen_manda_1', 'nomen_manda_3': 'nomen_manda_2'}
        level = {'nomen_manda_1': 1, 'nomen_manda_2': 2, 'nomen_manda_3': 3}
        p_id = obj.read(cr, uid, id, [parent[field]])[parent[field]]
        # when dealing with osv_memory, the read method for many2one returns the id and not the tuple (id, name) as for osv.osv
        if p_id and isinstance(p_id, int):
            name = self.name_get(cr, uid, [p_id], context=context)[0]
            p_id = name
        dom = [('level', '=', level.get(field)), ('type', '=', 'mandatory'), ('parent_id', '=', p_id and p_id[0] or 0)]
        return self._name_search(cr, uid, '', dom, limit=None, name_get_uid=1, context=context)

    def get_sub_nomen(self, cr, uid, obj, id, field):
        parent = ['nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3']
        level = {'nomen_sub_0': '0', 'nomen_sub_1': '1', 'nomen_sub_2': '2', 'nomen_sub_3': '3', 'nomen_sub_4': '4', 'nomen_sub_5': '5'}
        read = parent + list(level.keys())
        nom = obj.read(cr, uid, id, read)
        parent_id = [False]
        for p in parent:
            if nom[p]:
                parent_id.append(nom[p][0])
        sub = []
        for p in list(level.keys()):
            if p != field and nom[p]:
                sub.append(nom[p][0])
        dom = [('type', '=', 'optional'), ('parent_id', 'in', parent_id), ('sub_level', '=', level.get(field)), ('id', 'not in', sub)]
        return [('', '')] + self._name_search(cr, uid, '', dom, limit=None, name_get_uid=1, context={'nolevel':1})

product_nomenclature()

#----------------------------------------------------------
# Products
#----------------------------------------------------------
class product_template(osv.osv):

    _inherit = "product.template"
    _description = "Product Template"

    def _get_nomen_s(self, cr, uid, ids, fields, *a, **b):
        value = {}
        for f in fields:
            value[f] = False

        ret = {}
        for id in ids:
            ret[id] = value
        return ret

    def _search_nomen_s(self, cr, uid, obj, name, args, context=None):
        # Some verifications
        if context is None:
            context = {}

        if not args:
            return []
        narg = []
        for arg in args:
            el = arg[0].split('_')
            el.pop()
            narg = [('_'.join(el), arg[1], arg[2])]

        return narg

    def _get_archived_nomenclature(self, cr, uid, ids, fields, *a, **b):
        if isinstance(ids, int):
            ids = [ids]

        if not ids:
            return {}

        ret = {}
        for _id in ids:
            ret[_id] = False

        cr.execute('''
            select
                t.id
            from
                product_template t, product_nomenclature n
            where
                t.id in %s and
                n.status = 'archived' and
                (n.level = 2 and t.nomen_manda_2 = n.id or n.level = 3 and t.nomen_manda_3 = n.id)
        ''', (tuple(ids), ))
        for x in cr.fetchall():
            ret[x[0]] = True
        return ret

    def _search_archived_nomenclature(self, cr, uid, obj, name, args, context=None):
        if not args:
            return []

        dom = []
        for arg in args:
            if arg[1] != '=':
                raise osv.except_osv(_('Error !'), _('Filter not implemented on %s') % (name,))
            if arg[2]:
                dom = ['|', ('nomen_manda_2.status', '=', 'archived'), ('nomen_manda_3.status', '=', 'archived')]
            else:
                dom = ['&', ('nomen_manda_2.status', '!=', 'archived'), ('nomen_manda_3.status', '!=', 'archived')]

        return dom
    # ## EXACT COPY-PASTE TO order_nomenclature
    _columns = {
        # mandatory nomenclature levels
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', required=True, select=1),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', required=True, select=1),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', required=True, select=1, join=True),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', required=True, select=1, join=True),

        # optional nomenclature levels
        'nomen_sub_0': fields.many2one('product.nomenclature', 'Sub Class 1', select=1),
        'nomen_sub_1': fields.many2one('product.nomenclature', 'Sub Class 2', select=1),
        'nomen_sub_2': fields.many2one('product.nomenclature', 'Sub Class 3', select=1),
        'nomen_sub_3': fields.many2one('product.nomenclature', 'Sub Class 4', select=1),
        'nomen_sub_4': fields.many2one('product.nomenclature', 'Sub Class 5', select=1),
        'nomen_sub_5': fields.many2one('product.nomenclature', 'Sub Class 6', select=1),
        # for search view :(
        'nomen_manda_0_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Main Type', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_1_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Group', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_2_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Family', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_manda_3_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Root', fnct_search=_search_nomen_s, multi="nom_s"),

        'nomen_sub_0_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 1', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_1_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 2', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_2_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 3', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_3_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 4', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_4_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 5', fnct_search=_search_nomen_s, multi="nom_s"),
        'nomen_sub_5_s': fields.function(_get_nomen_s, method=True, type='many2one', relation='product.nomenclature', string='Sub Class 6', fnct_search=_search_nomen_s, multi="nom_s"),

        'archived_nomenclature': fields.function(_get_archived_nomenclature, method=True, type='boolean', string='Archived Nomenclature', fnct_search=_search_archived_nomenclature),
        # concatenation of nomenclature in a visible way
        'nomenclature_description': fields.char('Nomenclature', size=1024),
        'property_account_income': fields.many2one('account.account',
                                                   string='Income Account',
                                                   help='This account will be used for invoices instead of the default one to value sales for \
the current product'),
        'property_account_expense': fields.many2one('account.account',
                                                    string='Expense Account',
                                                    help='This account will be used for invoices instead of the default one to value expenses \
for the current product'),
        'property_stock_procurement': fields.many2one('stock.location',
                                                      string='Procurement Location',
                                                      domain=[('usage', 'like', 'procurement')],
                                                      # FIXME
                                                      required=False,
                                                      help='For the current product, this stock location will be used, instead of the default one, \
as the source location for stock moves generated by procurements'),
        'property_stock_production': fields.many2one('stock.location',
                                                     string='Production Location',
                                                     domain=[('usage', 'like', 'production')],
                                                     # FIXME
                                                     required=False,
                                                     help='For the current product, this stock location will be used, instead of the default one, \
as the source location for stock moves generated by production orders'),
        'property_stock_inventory': fields.many2one('stock.location',
                                                    string='Inventory Location',
                                                    domain=[('usage', 'like', 'inventory')],
                                                    # FIXME
                                                    required=False,
                                                    help='For the current product, this stock location will be used, instead of the default one, \
as the source location for stock moves generated when you do an inventory'),
        'property_stock_account_input': fields.many2one('account.account',
                                                        string='Stock Input Account',
                                                        help='When doing real-time inventory valuation, counterpart Journal Items for all incoming \
stock moves will be posted in this account. If not set on the product, the one from the product category is used.'),
        'property_stock_account_output': fields.many2one('account.account',
                                                         string='Stock Output Account',
                                                         help='When doing real-time inventory valuation, counterpart Journal Items for all outgoing \
stock moves will be posted in this account. If not set on the product, the one from the product category is used.'),
    }
    # ## END OF COPY

    def _get_property_stock(self, cr, uid, location_xml_id, context=None):
        try:
            loc_ids = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', location_xml_id)
        except ValueError:
            return False
        if loc_ids:
            return loc_ids[1]

        return False

    _defaults = {
        'property_stock_procurement': lambda self, cr, uid, c = {}: self._get_property_stock(cr, uid, 'location_procurement', context=c),
        'property_stock_production': lambda self, cr, uid, c = {}: self._get_property_stock(cr, uid, 'location_production', context=c),
        'property_stock_inventory': lambda self, cr, uid, c = {}: self._get_property_stock(cr, uid, 'location_inventory', context=c),
        'property_account_income': False,
        'property_account_expense': False,
        'property_stock_account_input': False,
        'property_stock_account_output': False,
    }

    def _get_default_nom(self, cr, uid, context=None):
        # Some verifications
        if context is None:
            context = {}

        res = {}
        toget = [('nomen_manda_0', 'nomen_med'), ('nomen_manda_1', 'nomen_med_drugs'),
                 ('nomen_manda_2', 'nomen_med_drugs_infusions'), ('nomen_manda_3', 'nomen_med_drugs_infusions_dex')]

        for field, xml_id in toget:
            nom = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_nomenclature', xml_id)
            res[field] = nom[1]
        return res

    def create(self, cr, uid, vals, context=None):
        '''
        Set default values for datas.xml and tests.yml
        '''
        if context is None:
            context = {}

        from_import_menu = context.get('from_import_menu', False)

        nomen_obj = self.pool.get('product.nomenclature')
        if from_import_menu:
            if not hasattr(nomen_obj, '_cache'):
                nomen_obj._cache = {}

            # Create a cache
            if not nomen_obj._cache.get(cr.dbname, False):
                nomen_obj._cache.setdefault(cr.dbname, {})

        # Set the category according to the Family
        if vals.get('nomen_manda_2'):
            if from_import_menu and nomen_obj._cache.get(cr.dbname, {}).get(vals['nomen_manda_2'], False):
                vals['categ_id'] = nomen_obj._cache.get(cr.dbname, {}).get(vals['nomen_manda_2'], False)
            else:
                categ_ids = nomen_obj.read(cr, uid, vals['nomen_manda_2'], ['category_id'], context=context)['category_id']
                if categ_ids and len(categ_ids) > 0:
                    vals['categ_id'] = categ_ids[0]
                    if from_import_menu:
                        nomen_obj._cache[cr.dbname][vals['nomen_manda_2']] = vals['categ_id']
                else:
                    raise osv.except_osv(_('Error'), _('No Product Category found for %s. Please contact an accounting member to create a new one for this family.')
                                         % vals['nomenclature_description'])

        if vals.get('name'):
            vals['name'] = vals['name'].strip()

        return super(product_template, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Set the category according to the Family
        '''
        if not ids:
            return True
        if vals.get('nomen_manda_2'):
            vals['categ_id'] = self.pool.get('product.nomenclature').browse(cr, uid, vals['nomen_manda_2'], fields_to_fetch=['category_id'], context=context).category_id.id
        if vals.get('name'):
            vals['name'] = vals['name'].strip()

        return super(product_template, self).write(cr, uid, ids, vals, context)

product_template()

class product_product(osv.osv):

    _inherit = "product.product"
    _description = "Product"

    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field)

    def get_sub_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_sub_nomen(cr, uid, self, id, field)

    def copy(self, cr, uid, old_id, new_vals=None, context=None):
        if new_vals is None:
            new_vals = {}
        if 'msfid' not in new_vals:
            new_vals['msfid'] = False
        if 'xmlid_code' not in new_vals:
            new_vals['xmlid_code'] = False
        return super(product_product, self).copy(cr, uid, old_id, new_vals, context=context)

    def create(self, cr, uid, vals, context=None):
        '''
        override to complete nomenclature_description
        '''
        # Objects
        sale = self.pool.get('sale.order.line')

        if context is None:
            context = {}

        default_code = vals.get('default_code', False)
        p_type = vals.get('type', False)

        if p_type == 'service':
            vals.update({'type': 'service_recep',
                         'procure_method': 'make_to_order'})
        '''
        if a product is not of type product, it is set to single subtype
        '''
        # fetch the product
        if p_type != 'product':
            vals['subtype'] = 'single'

        # save the data to db
        if 'batch_management' in vals:
            vals.update({
                'track_production': vals['batch_management'],
                'track_incoming': vals['batch_management'],
                'track_outgoing': vals['batch_management'],
                'perishable': vals.get('perishable', vals['batch_management']),
            })

        if default_code:
            vals['duplicate_ok'] = default_code == 'XXX'
        '''
        UF-2254: When creating the product, there are 3 different cases:
         1. the creation comes from the sync, in this case, report any error if duplication on default_code or xmlid_code
             otherwise, there will be problem with the update later
         2. from import product menu: the context contains from_import_menu: default code and xmlid_code must exist and unique
         3. manually creation: the default code must be new (no duplication), xmlid_code = valid default_code
         4. duplication from GUI: the default code XXX is saved, then modify in the write
        '''
        # The first 2 cases: dup of default_code/xmlid_code not allow
        if context.get('sync_update_execution', False):
            if not default_code or not vals.get('xmlid_code', False):
                raise Exception("Problem creating product: Missing xmlid_code/default_code in the data")
        if not vals.get('xmlid_code'):
            vals['xmlid_code'] = RANDOM_XMLID_CODE_PREFIX + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(14))

        sale._setNomenclatureInfo(cr, uid, vals, context)

        # Non-synced product creation with archived nomenclature is not authorized. Local products can use the archived MISC roots
        if vals.get('nomen_manda_3') and vals.get('international_status') and not (context.get('sync_update_creation') or context.get('sync_update_execution')):
            nomen_3 = self.pool.get('product.nomenclature').read(cr, uid, vals['nomen_manda_3'], ['status', 'msfid'], context=context)
            status_local_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_4')[1]
            if nomen_3['status'] != 'valid' and (vals['international_status'] != status_local_id or
                    (vals['international_status'] == status_local_id and nomen_3['msfid'].split('-')[-1] != 'MISC')):
                raise osv.except_osv(_('Error'), _('You can not create a product with an archived Root Nomenclature.'))

        res = super(product_product, self).create(cr, uid, vals, context=context)

        prod_default_code = default_code or self.read(cr, uid, res, ['default_code'], context=context)['default_code']
        if prod_default_code != 'XXX':
            return res

        # if the default code is empty or XXX, then delete the relevant xmlid from the ir_model_data table
        model_data_obj = self.pool.get('ir.model.data')
        sdref_ids = model_data_obj.search(cr, uid, [('model', '=', self._name), ('res_id', '=', res), ('module', '=', 'sd')])
        if sdref_ids:
            model_data_obj.unlink(cr, uid, sdref_ids, context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        '''
        override to complete nomenclature_description
        '''
        if not ids:
            return True
        sale = self.pool.get('sale.order.line')
        sale._setNomenclatureInfo(cr, uid, vals, context)


        default_code = vals.get('default_code', False)

        if default_code:
            read_result = self.read(cr, uid, ids, ['default_code'], context=context)

        res = super(product_product, self).write(cr, uid, ids, vals, context)

        # check if default_code change
        if default_code:
            all_msf_lines_to_upgrade = []
            msf_line_obj = self.pool.get('stock.mission.report.line')
            for product in read_result:
                if product['default_code'] != default_code:
                    # if the default_code change, update the corresponding MSR lines
                    msf_lines_to_update = msf_line_obj.search(cr, 1,
                                                              [('product_id', '=', product['id'])],
                                                              context=context)
                    all_msf_lines_to_upgrade.extend(msf_lines_to_update)
            if all_msf_lines_to_upgrade:
                msf_line_obj.write(cr, 1, all_msf_lines_to_upgrade,
                                   {}, context=context)
        return res

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, prod_code=False, international_status=False, context=None):
        '''
        the nomenclature selection search changes
        '''
        if context is None:
            context = {}
        # UF-1662: Set the correct lang of the user, otherwise the system will get by default the wrong en_US value
        lang_dict = self.pool.get('res.users').read(cr, uid, uid, ['context_lang'])
        if lang_dict.get('context_lang'):
            context['lang'] = lang_dict.get('context_lang')

        mandaName = 'nomen_manda_%s'
        optName = 'nomen_sub_%s'
        # selected value
        selected = eval('nomen_manda_%s' % position)
        # if selected value is False, the first False value -1 is used as selected
        if not selected:
            mandaVals = []
            for i in range(_LEVELS):
                if not eval('nomen_manda_%s' % i):
                    mandaVals.append(i)
            if mandaVals[0] == 0:
                # first drop down, initialization
                selected = False
                position = -1
            else:
                # the first drop down with False value -1
                position = mandaVals[0] - 1
                selected = eval('nomen_manda_%s' % position)

        values = {}
        result = {'value': values}

        # clear upper levels mandatory
        for i in range(position + 1, _LEVELS):
            values[mandaName % (i)] = [()]

        # clear all optional level
        for i in range(_SUB_LEVELS):
            values[optName % (i)] = [()]

        # nomenclature object
        nomenObj = self.pool.get('product.nomenclature')

        if position == 2 and nomen_manda_2:
            for n in nomenObj.read(cr, uid, [nomen_manda_2], ['category_id'], context=context):
                values['categ_id'] = n['category_id'] or False

        # loop through children nomenclature of mandatory type
        shownum = num or context.get('withnum') == 1
        if position < 3:
            if position == 1:
                nomenids = nomenObj.search(cr, uid, [('category_id', '!=', False), ('type', '=', 'mandatory'), ('parent_id', '=', selected)], order='name', context=context)
            else:
                # During manual creation
                if not id and position == 2 and prod_code:
                    nomen_msfid = nomenObj.read(cr, uid, nomen_manda_2, ['msfid'], context=context)['msfid']
                    if not prod_code.upper().startswith(nomen_msfid.split('-')[-1]):
                        result['warning'] = {
                            'title': 'Warning',
                            'message': _('You are about to create a product with a Code which does not correspond to the nomenclature\'s Family, do you wish to proceed ?')
                        }

                nomenids = nomenObj.search(cr, uid, [('type', '=', 'mandatory'), ('parent_id', '=', selected)], order='name', context=context)
            if nomenids:
                for n in nomenObj.read(cr, uid, nomenids, ['name'] + (shownum and ['number_of_products'] or []), context=context):
                    # get the name and product number
                    n_id = n['id']
                    name = n['name']
                    if shownum:
                        number = n['number_of_products']
                        values[mandaName % (position + 1)].append((n_id, name + ' (%s)' % number))
                    else:
                        values[mandaName % (position + 1)].append((n_id, name))
        elif not num and not context.get('withnum') and position == 3 and nomen_manda_3 and international_status:
            # Archived nomenclature is not authorized. Local products can use the archived MISC roots
            nomen_3 = nomenObj.read(cr, uid, nomen_manda_3, ['status', 'msfid'], context=context)
            status_local_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product_attributes', 'int_4')[1]
            if nomen_3['status'] != 'valid' and (international_status != status_local_id or
                    (international_status == status_local_id and nomen_3['msfid'].split('-')[-1] != 'MISC')):
                return {
                    'value': {'nomen_manda_3': False},
                    'warning': {'title': _('Warning'), 'message': _('You can not select an archived Root Nomenclature.')}
                }

        # find the list of optional nomenclature related to products filtered by mandatory nomenclatures
        optionalList = []
        if not selected:
            optionalList.extend(nomenObj.search(cr, uid, [('type', '=', 'optional'), ('parent_id', '=', False)], order='name', context=context))
        else:
            optionalList = nomenObj.search(cr, uid, [('type', '=', 'optional'), ('parent_id', 'in', [nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False])])

        # sort the optional nomenclature according to their id
        optionalList.sort()
        if optionalList:
            for n in nomenObj.read(cr, uid, optionalList, ['name', 'sub_level'] + (num and ['number_of_products'] or []), context=context):
                # get the name and product number
                n_id = n['id']
                name = n['name']
                sublevel = n['sub_level']
                if num:
                    number = n['number_of_products']
                    values[optName % (sublevel)].append((n_id, name + ' (%s)' % number))
                else:
                    values[optName % (sublevel)].append((n_id, name))
        if num:
            newval = {}
            for x in values:
                newval['%s_s' % x] = values[x]
            result['value'] = newval
        return result

    def _resetNomenclatureFields(self, values):
        '''
        reset all nomenclature's fields
        because the dynamic domain for product_id is not
        re-computed at windows opening.
        '''
        for x in range(_LEVELS):
            values.update({'nomen_manda_%s' % x:False})

        for x in range(_SUB_LEVELS):
            values.update({'nomen_sub_%s' % x:False})

    def _generateValueDic(self, cr, uid, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, *optionalList):
        '''
        generate original dictionary
        all values are placed in the update dictionary
        to ease the generation of dynamic domain in order_nomenclature
        '''
        result = {}

        # mandatory levels values
        for i in range(_LEVELS):
            name = 'nomen_manda_%i' % (i)
            value = eval(name)

            result.update({name:value})

        # optional levels values
        for i in range(_SUB_LEVELS):
            name = 'nomen_sub_%i' % (i)
            value = optionalList[i]

            result.update({name:value})

        return result

    def _clearFieldsBelow(self, cr, uid, level, optionalList, result):
        '''
        Clear fields below (hierarchically)

        possible improvement:

        '''
        levels = list(range(_LEVELS))

        # level not of interest
        if level not in levels:
            raise osv.except_osv(_('Error'), _('Level (%s) must be smaller or equal to %s') % (level, levels))

        for x in levels[level + 1:]:
            result['value'].update({'nomen_manda_%s' % x:False})

        # always update all sub levels
        for x in range(_SUB_LEVELS):
            # clear optional fields with level below 'level'
            subId = optionalList[x]
            if subId:
                subNomenclature = self.pool.get('product.nomenclature').browse(cr, uid, subId)
                subNomenclatureLevel = subNomenclature.level
                if subNomenclatureLevel > level:
                    result['value'].update({'nomen_sub_%s' % x:False})

        return result

    def nomenChange(self, cr, uid, id, fieldNumber, nomenclatureId, nomenclatureType,
                    nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None, *optionalList):
        '''
        for mandatory types, level (nomenclature object)
        and fieldNumber (field) are directly linked

        for optional types, the fields can contain nomenclature
        of any level, they are not directly linked. in this case,
        we make a clear distinction between fieldNumber and level

        when a nomenclature field changes:
        1. if the nomenclature is of newType "mandatory", we reset
           below levels and codes.
        2. we update the corresponding newCode (whatever the newType)

        possible improvement:
        - if a selected level contains only one sub level, update
          the sub level with that unique solution
        '''
        assert context, 'No context, error on function call'
        # values to be updated
        result = {}
        if 'result' in context:
            result = context['result']
        else:
            result = {'value':{}, 'warning':{}}
            context['result'] = result

        # all values are updated, ease dynamic domain generation in order_nomenclature
        allValues = self._generateValueDic(cr, uid, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, *optionalList)
        result['value'].update(allValues)

        # retrieve selected nomenclature object
        if nomenclatureId:
            selectedNomenclature = self.pool.get('product.nomenclature').browse(cr, uid, nomenclatureId)
            newId = nomenclatureId
            newType = selectedNomenclature.type
            newLevel = selectedNomenclature.level
            # converted to int, because string from selection
            newSubLevel = int(selectedNomenclature.sub_level)
            # newType check
            if nomenclatureType != newType:
                result['warning'].update({'title': _('Error!'),
                                          'message': _("The selected nomenclature's type is '%s'. Must be '%s' (field's type).") % (newType, nomenclatureType)
                                          })
                newId = False
                newType = nomenclatureType


            # level check
            if  newType == 'mandatory':
                if fieldNumber != newLevel:
                    result['warning'].update({'title': _('Error!'),
                                              'message': _("The selected nomenclature's level is '%s'. Must be '%s' (field's level).") % (newLevel, fieldNumber)
                                              })
                    newId = False

            elif newType == 'optional':
                if fieldNumber != newSubLevel:
                    # ## NOTE adapt level to user level for warning message (+1)
                    result['warning'].update({'title': _('Error!'),
                                              'message': _("The selected nomenclature's level is '%s'. Must be '%s' (field's level).") % (newSubLevel + 1, fieldNumber + 1)
                                              })
                    newId = False

        else:
            # the field has been cleared, we simply want to clear the code field as well
            newId = False
            newType = nomenclatureType


        if newType == 'mandatory':
            # clear all below (from fieldNumber+1) mandatory levels
            # all optional
            self._clearFieldsBelow(cr, uid, level=fieldNumber, optionalList=optionalList, result=result)

            # update selected level
            result['value'].update({'nomen_manda_%s' % fieldNumber:newId})

        if newType == 'optional':

            # update selected level
            result['value'].update({'nomen_sub_%s' % fieldNumber:newId})

        result = context['result']

        # correction of bug when we select the nomenclature with a mouse click
        # the nomenclature was reset to False
        # this is due to the fact that onchange is called twice when we use the mouse click
        # the first time with the selected value to False. This value was set to False
        # at the first call which reset the selected value.
        #
        # in product_nomenclature > product_nomenclature.py > product_product > nomenChange
        #
        if not nomenclatureId:
            # we remove the concerned field if it is equal to False
            if nomenclatureType == 'mandatory':
                nameToRemove = 'nomen_manda_%i' % fieldNumber
                result['value'].pop(nameToRemove, False)

            elif nomenclatureType == 'optional':
                nameToRemove = 'nomen_sub_%i' % fieldNumber
                result['value'].pop(nameToRemove, False)

        return result

product_product()


class product_category(osv.osv):
    _name = 'product.category'
    _inherit = 'product.category'

    def init(self, cr):
        """
        Load product_nomenclature_data.xml brefore product
        """
        if hasattr(super(product_category, self), 'init'):
            super(product_category, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        demo = False
        mod_id = mod_obj.search(cr, 1, [('name', '=', 'product_nomenclature')])
        if mod_id:
            demo = mod_obj.read(cr, 1, mod_id, ['demo'])[0]['demo']

        if demo:
            logging.getLogger('init').info('HOOK: module product_nomenclature: loading product_nomenclature_data.xml')
            pathname = path.join('product_nomenclature', 'product_nomenclature_data.xml')
            file = tools.file_open(pathname)
            tools.convert_xml_import(cr, 'product_nomenclature', file, {}, mode='init', noupdate=False)

    _columns = {
        'active': fields.boolean('Active', help="If the active field is set to False, it allows to hide the nomenclature without removing it."),
        'family_id': fields.many2one('product.nomenclature', string='Family',
                                     domain="[('level', '=', '2'), ('type', '=', 'mandatory'), ('category_id', '=', False)]",
                                     ),
        'msfid': fields.char('MSFID', size=128, select=True),
    }

    _defaults = {
        'active': True,
    }

    _sql_constraints = [('check_msfid_unique', 'unique (msfid)', 'MSFID must be unique !')]

    def unlink(self, cr, uid, ids, context=None):
        """
        Check if the deleted product category is not a system one
        """
        data_obj = self.pool.get('ir.model.data')

        categ_data_id = [
            'cat_tbd',
        ]

        for data_id in categ_data_id:
            try:
                categ_id = data_obj.get_object_reference(
                    cr, uid, 'msf_doc_import', data_id)[1]
                if categ_id in ids:
                    categ_name = self.read(cr, uid, categ_id, ['name'])['name']
                    raise osv.except_osv(
                        _('Error'),
                        _('''The category '%s' is an Unifield internal category, so you can't remove it''') % categ_name,
                    )
            except ValueError:
                pass

        return super(product_category, self).unlink(cr, uid, ids, context=context)

product_category()


class act_window(osv.osv):
    _name = 'ir.actions.act_window'
    '''
    inherit act_window to extend domain size, as the size for screen sales>product by nomenclature is longer than 250 character
    '''
    _inherit = 'ir.actions.act_window'
    _columns = {
        'domain': fields.char('Domain Value', size=1024,
                              help="Optional domain filtering of the destination data, as a Python expression"),
    }

act_window()

class product_uom_categ(osv.osv):
    _name = 'product.uom.categ'
    _inherit = 'product.uom.categ'

    _columns = {
        'active': fields.boolean('Active', help="If the active field is set to False, it allows to hide the nomenclature without removing it."),
    }

    _defaults = {
        'active': True,
    }

    def unlink(self, cr, uid, ids, context=None):
        """
        Check if the deleted product UoM category is not a system one
        """
        data_obj = self.pool.get('ir.model.data')

        uom_data_id = [
            'product_uom_tbd',
        ]

        for data_id in uom_data_id:
            try:
                cat_id = data_obj.get_object_reference(
                    cr, uid, 'msf_doc_import', data_id)[1]
                if cat_id in ids:
                    uom_name = self.read(cr, uid, cat_id, ['name'])['name']
                    raise osv.except_osv(
                        _('Error'),
                        _('''The UoM category '%s' is an Unifield internal Uom category, so you can't remove it''') % uom_name,
                    )
            except ValueError:
                pass

        return super(product_uom_categ, self).unlink(cr, uid, ids, context=context)

product_uom_categ()
