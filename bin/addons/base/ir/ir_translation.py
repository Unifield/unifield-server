# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

from osv import fields, osv
import tools
import logging

TRANSLATION_TYPE = [
    ('field', 'Field'),
    ('model', 'Object'),
    ('rml', 'RML  (deprecated - use Report)'), # Pending deprecation - to be replaced by report!
    ('report', 'Report/Template'),
    ('selection', 'Selection'),
    ('view', 'View'),
    ('wizard_button', 'Wizard Button'),
    ('wizard_field', 'Wizard Field'),
    ('wizard_view', 'Wizard View'),
    ('xsl', 'XSL'),
    ('help', 'Help'),
    ('code', 'Code'),
    ('constraint', 'Constraint'),
    ('sql_constraint', 'SQL Constraint')
]

class ir_translation(osv.osv):
    _name = "ir.translation"
    _log_access = False

    def _get_language(self, cr, uid, context):
        lang_obj = self.pool.get('res.lang')
        lang_ids = lang_obj.search(cr, uid, [],
                                   context=context)
        langs = lang_obj.read(cr, uid, lang_ids, ['code', 'name'], context=context)
        res = [(lang['code'], lang['name']) for lang in langs]
        for lang_dict in tools.scan_languages():
            if lang_dict not in res:
                res.append(lang_dict)
        return res

    _columns = {
        'name': fields.char('Field Name', size=128, required=True),
        'res_id': fields.integer('Resource ID', select=True),
        'lang': fields.selection(_get_language, string='Language', size=16),
        'type': fields.selection(TRANSLATION_TYPE, string='Type', size=16, select=True),
        'src': fields.text('Source'),
        'value': fields.text('Translation Value'),
        # These two columns map to ir_model_data.module and ir_model_data.name.
        # They are used to resolve the res_id above after loading is done.
        'module': fields.char('Module', size=64, help='Maps to the ir_model_data for which this translation is provided.'),
        'xml_id': fields.char('XML Id', size=128, help='Maps to the ir_model_data for which this translation is provided.', select=True),
        'updated_by_modules': fields.boolean('Updated by last msf_profile update'),
    }

    _defaults = {
        'updated_by_modules': False,
    }

    def has_duplicate(self, cr, uid, verbose=False, context=None):

        cr.execute("""select src,type,count(*), lang
            from ir_translation
            where
                type in ('code', 'sql_constraint') and
                lang in ('fr_MF', 'en_MF')
            group by src,type, lang
            having count(distinct(value)) > 1"""
                   )

        nb = cr.rowcount
        if verbose:
            logger = logging.getLogger('translate')
            for x in cr.fetchall():
                logger.warn("%s duplicated %s %s translations: %s" % (x[2], x[3], x[1], x[0]))
        return nb

    def _auto_init(self, cr, context={}):
        super(ir_translation, self)._auto_init(cr, context)

        # there is a size limit on btree indexed values so we can't index src column with normal btree.
        # hash indexes are not compatible with postgres streaming replication
        for idx in ['ir_translation_ltns', 'ir_translation_lts', 'ir_translation_src_hash_idx']:
            cr.execute('SELECT indexname FROM pg_indexes WHERE indexname = %s', (idx,))
            if cr.fetchone():
                query = 'DROP INDEX %s' % (idx,) # not_a_user_entry
                cr.execute(query)
                cr.commit()

        # Add separate md5 index on src (no size limit on values, and good performance).
        cr.execute('SELECT indexname FROM pg_indexes WHERE indexname = %s', ('ir_translation_src_md5_idx',))
        if not cr.fetchone():
            cr.execute('CREATE INDEX ir_translation_src_md5_idx ON ir_translation (md5(src))')

        cr.execute('SELECT indexname FROM pg_indexes WHERE indexname = %s', ('ir_translation_ltn',))
        if not cr.fetchone():
            cr.execute('CREATE INDEX ir_translation_ltn ON ir_translation (name, lang, type)')
            cr.commit()

    @tools.cache(skiparg=3, multi='ids')
    def _get_ids(self, cr, uid, name, tt, lang, ids):
        translations = dict.fromkeys(ids, False)
        if ids:
            cr.execute('SELECT res_id,value ' \
                       'FROM ir_translation ' \
                       'WHERE lang=%s ' \
                       'and type=%s ' \
                       'and name=%s ' \
                       'and res_id IN %s',
                       (lang,tt,name,tuple(ids)))
            for res_id, value in cr.fetchall():
                translations[res_id] = value
        return translations

    @tools.cache(skiparg=3, multi='ids')
    def _get_ids_dict(self, cr, uid, name, tt, lang, ids):
        translation_dict = dict.fromkeys(ids, None)
        if ids:
            cr.execute('SELECT id, res_id,value ' \
                       'FROM ir_translation ' \
                       'WHERE lang=%s ' \
                       'and type=%s ' \
                       'and name=%s ' \
                       'and res_id IN %s',
                       (lang,tt,name,tuple(ids)))
            for ir_trans_id, res_id, value in cr.fetchall():
                translation_dict[res_id] = {'ir_trans_id':ir_trans_id, 'value':value}
        return translation_dict

    def _set_ids(self, cr, uid, name, tt, lang, ids, value, src=None, clear=True, context=None):
        if context is None:
            context = {}
        translation_dict = self._get_ids_dict(cr, uid, name, tt, lang, ids)
        if clear:
            # clear the caches
            for res_id in ids:
                if translation_dict[res_id]:
                    self._get_source.clear_cache(cr.dbname, uid, name, tt,
                                                 lang, translation_dict[res_id]['value'])
            self._get_source.clear_cache(cr.dbname, uid, name, tt, lang)
            self._get_ids.clear_cache(cr.dbname, uid, name, tt, lang, ids)
            self._get_ids_dict.clear_cache(cr.dbname, uid, name, tt, lang, ids)

        # BKLG-52 Change delete/create for Update
        for obj_id in ids:
            if translation_dict[obj_id] is not None:
                if not value or value==src or lang=='en_US':
                    self.unlink(cr, uid,
                                translation_dict[obj_id]['ir_trans_id'],
                                clear=clear, context=context)
                else:
                    values = {'value': value, 'src': src}
                    self.write(cr, uid,
                               translation_dict[obj_id]['ir_trans_id'],
                               values, clear=clear, context=context)
            elif value!=src:
                self.create(cr, uid, {
                    'lang': lang,
                    'type': tt,
                    'name': name,
                    'res_id': obj_id,
                    'value': value,
                    'src': src,
                },
                    clear=clear,
                    context=context)
        return len(ids)

    @tools.cache(skiparg=3)
    def _get_source(self, cr, uid, name, types, lang, source=None, false_if_no_trad = False):
        """
        Returns the translation for the given combination of name, type, language
        and source. All values passed to this method should be unicode (not byte strings),
        especially ``source``.

        :param name: identification of the term to translate, such as field name (optional if source is passed)
        :param types: single string defining type of term to translate (see ``type`` field on ir.translation), or sequence of allowed types (strings)
        :param lang: language code of the desired translation
        :param source: optional source term to translate (should be unicode)
        :rtype: unicode
        :return: the request translation, or an empty unicode string if no translation was
                 found and `source` was not passed
        """
        # FIXME: should assert that `source` is unicode and fix all callers to always pass unicode
        # so we can remove the string encoding/decoding.
        if not lang:
            return u''
        if isinstance(types, basestring):
            types = (types,)

        if source:
            query = """SELECT value
                       FROM ir_translation
                       WHERE lang=%s
                        AND type in %s
                        AND src=%s"""
            params = (lang or '', types, tools.ustr(source))
            if name:
                query += " AND name=%s"
                params += (tools.ustr(name),)
            cr.execute(query, params)
        else:
            cr.execute("""SELECT value
                          FROM ir_translation
                          WHERE lang=%s
                           AND type in %s
                           AND name=%s""",
                       (lang or '', types, tools.ustr(name)))
        res = cr.fetchone()
        trad = res and res[0] or u''
        if source and not trad:
            if false_if_no_trad:
                return False
            return tools.ustr(source)
        return trad

    def _truncate_value_size(self, cursor, user, vals, id=None, context=None):
        # SP-193 / US-145 : translation must limited to object limitation
        if not 'value' in vals:
            return  # nothing to truncate

        other_vals = {}  # other vals than 'value' required to check limitation
        wanted_other_vals = ('name', 'type', )
        for wv in wanted_other_vals:
            if wv in vals:
                other_vals[wv] = vals[wv]

        if id is not None:
            # from a write: read potential missing vals
            fields_to_load = [
                wv for wv in wanted_other_vals if not wv in vals ]
            if fields_to_load:
                r = self.read(cursor, user, [id], fields_to_load,
                              context=context)[0]
                for ftl in fields_to_load:
                    other_vals[ftl] = r[ftl]

        # truncate value if required
        if ',' in other_vals['name'] and other_vals.get('type') == 'model' \
                and vals.get('value'):
            model_name = other_vals['name'].split(",")[0]
            field = other_vals['name'].split(",")[1]
            if field:
                model_obj = self.pool.get(model_name)
                if hasattr(model_obj, 'fields_get'):
                    field_obj = model_obj.fields_get(cursor, user, context=context)
                    if 'size' in field_obj.get(field, {}):
                        size = field_obj[field]['size']
                        vals['value'] = tools.ustr(vals['value'])[:size]

    def create(self, cursor, user, vals, clear=True, context=None):
        if context is None:
            context = {}

        # SP-193 : translation must limited to object limitation
        # (no need to check when syncing as already checked for regular create)
        if not context.get('sync_update_execution'):
            self._truncate_value_size(cursor, user, vals, id=None, context=context)

        ids = super(ir_translation, self).create(cursor, user, vals, context=context)
        if clear:
            self.clear_transid(cursor, user, ids, context=context)
        return ids

    def write(self, cursor, user, ids, vals, clear=True, context=None):
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # US-145 : translation must limited to object limitation
        # (no need to check when syncing as already checked for regular write)
        if context.get('sync_update_execution'):
            result = super(ir_translation, self).write(cursor, user, ids, vals, context=context)
        else:
            if not 'name' in vals or not 'type' in vals:
                # in case of missing vals needed for limitation check,
                # need to read them record per record
                result = True
                for id in ids:
                    self._truncate_value_size(cursor, user, vals, id=id, context=context)
                    res = super(ir_translation, self).write(cursor, user, [id], vals, context=context)
                    if not res:
                        result = False
            else:
                # no missing vals for limitation check: do check per transaction
                self._truncate_value_size(cursor, user, vals, id=None, context=context)
                result = super(ir_translation, self).write(cursor, user, ids, vals, context=context)

        if clear:
            self.clear_transid(cursor, user, ids, context=context)
        return result

    def clear_transid(self, cr, uid, ids, context=None):
        """
        Clears the translation cache
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for trans_obj in self.read(cr, uid, ids, ['name','type','res_id','src','lang'], context=context):
            self._get_source.clear_cache(cr.dbname, uid, trans_obj['name'], trans_obj['type'], trans_obj['lang'], source=trans_obj['src'])
            self._get_ids.clear_cache(cr.dbname, uid, trans_obj['name'], trans_obj['type'], trans_obj['lang'], [trans_obj['res_id']])
            self._get_ids_dict.clear_cache(cr.dbname, uid, trans_obj['name'], trans_obj['type'],trans_obj['lang'], [trans_obj['res_id']])
        return True

    def unlink(self, cursor, user, ids, clear=True, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if clear:
            for trans_obj in self.read(cursor, user, ids, ['name','type','res_id','src','lang'], context=context):
                self._get_source.clear_cache(cursor.dbname, user, trans_obj['name'], trans_obj['type'], trans_obj['lang'], source=trans_obj['src'])
                self._get_ids.clear_cache(cursor.dbname, user, trans_obj['name'], trans_obj['type'], trans_obj['lang'], [trans_obj['res_id']])
                self._get_ids_dict.clear_cache(cursor.dbname, user,
                                               trans_obj['name'], trans_obj['type'],
                                               trans_obj['lang'], [trans_obj['res_id']])
        result = super(ir_translation, self).unlink(cursor, user, ids, context=context)
        return result

ir_translation()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
