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

import itertools

from osv import fields,osv
import tools
import logging
import os
from tools.translate import _
import base64
import re
import threading
import pooler

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024 # = 10 MB

class ir_attachment(osv.osv):
    _order = 'create_date DESC, id'
    _logger = logging.getLogger('ir.attachment')

    def check(self, cr, uid, ids, mode, context=None, values=None):
        """Restricts the access to an ir.attachment, according to referred model
        In the 'document' module, it is overriden to relax this hard rule, since
        more complex ones apply there.
        """
        if not ids:
            return
        ima = self.pool.get('ir.model.access')
        res_ids = {}
        if ids:
            if isinstance(ids, (int, long)):
                ids = [ids]
            cr.execute('SELECT DISTINCT res_model, res_id FROM ir_attachment WHERE id = ANY (%s)', (ids,))
            for rmod, rid in cr.fetchall():
                if not (rmod and rid):
                    continue
                res_ids.setdefault(rmod,set()).add(rid)
        if values:
            if 'res_model' in values and 'res_id' in values:
                res_ids.setdefault(values['res_model'],set()).add(values['res_id'])

        for model, mids in res_ids.items():
            # ignore attachments that are not attached to a resource anymore when checking access rights
            # (resource was deleted but attachment was not)
            model_obj = self.pool.get(model)
            cr.execute('select id from '+model_obj._table+' where id in %s', (tuple(mids),))  # not_a_user_entry
            mids = [x[0] for x in cr.fetchall()]
            ima.check(cr, uid, model, mode, context=context)
            model_obj.check_access_rule(cr, uid, mids, mode, context=context)

    def search(self, cr, uid, args, offset=0, limit=None, order=None,
               context=None, count=False):
        ids = super(ir_attachment, self).search(cr, uid, args, offset=offset,
                                                limit=limit, order=order,
                                                context=context, count=False)
        if not ids:
            if count:
                return 0
            return []

        # admin user can see all attachments
        if uid == 1:
            if count:
                return len(ids)
            return ids

        # For attachments, the permissions of the document they are attached to
        # apply, so we must remove attachments for which the user cannot access
        # the linked document.
        targets = super(ir_attachment,self).read(cr, uid, ids, ['id', 'res_model', 'res_id'])
        model_attachments = {}
        for target_dict in targets:
            if not (target_dict['res_id'] and target_dict['res_model']):
                continue
            # model_attachments = { 'model': { 'res_id': [id1,id2] } }
            model_attachments.setdefault(target_dict['res_model'],{}).setdefault(target_dict['res_id'],set()).add(target_dict['id'])

        # To avoid multiple queries for each attachment found, checks are
        # performed in batch as much as possible.
        ima = self.pool.get('ir.model.access')
        for model, targets in model_attachments.iteritems():
            if not ima.check(cr, uid, model, 'read', raise_exception=False, context=context):
                # remove all corresponding attachment ids
                for attach_id in itertools.chain(*targets.values()):
                    ids.remove(attach_id)
                continue # skip ir.rule processing, these ones are out already

            # filter ids according to what access rules permit
            target_ids = targets.keys()
            if 'active' in self.pool.get(model)._columns:
                allowed_ids = self.pool.get(model).search(cr, uid, [
                    ('id', 'in', target_ids),
                    ('active', 'in', ('t', 'f'))], context=context)
            else:
                allowed_ids = self.pool.get(model).search(cr, uid, [('id', 'in', target_ids)], context=context)
            disallowed_ids = set(target_ids).difference(allowed_ids)
            for res_id in disallowed_ids:
                for attach_id in targets[res_id]:
                    ids.remove(attach_id)
        if count:
            return len(ids)
        return ids

    def get_attachment_max_size(self, cr, uid):
        return MAX_ATTACHMENT_SIZE

    def read(self, cr, uid, ids, fields_to_read=None, context=None, load='_classic_read'):
        self.check(cr, uid, ids, 'read', context=context)
        return super(ir_attachment, self).read(cr, uid, ids, fields_to_read, context, load)

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.check(cr, uid, ids, 'write', context=context, values=vals)

        store_data_in_db = self.store_data_in_db(cr, uid)
        if 'datas' in vals:
            # do not write the data in DB but on the local file system
            datas = vals.pop('datas')
            if store_data_in_db:
                vals['datas'] = datas
            else:
                vals['datas'] = '' # erase the old value in DB if any
            decoded_datas = base64.decodestring(datas or '')
            self.check_file_size(cr, uid, decoded_datas, context=context)
            vals['size'] = self.get_octet_size(decoded_datas)

            if not store_data_in_db:
                for attachment in self.read(cr, uid, ids, ['datas_fname', 'path']):
                    # delete the previous attachment on local file system if any
                    if attachment['path']:
                        if os.path.exists(attachment['path']):
                            os.remove(attachment['path'])
                    local_filename = self.get_file_name(cr, uid, attachment['id'],
                                                        datas_fname=attachment.get('datas_fname', ''))
                    vals['path'] = self.get_file_path(cr, uid, local_filename)
                    with open(vals['path'], 'wb') as f:
                        f.write(decoded_datas)
                    super(ir_attachment, self).write(cr, uid, attachment['id'], vals, context)
                return True
            return super(ir_attachment, self).write(cr, uid, ids, vals, context)

        return super(ir_attachment, self).write(cr, uid, ids, vals, context)

    def copy(self, cr, uid, id, default=None, context=None):
        self.check(cr, uid, [id], 'write', context=context)
        return super(ir_attachment, self).copy(cr, uid, id, default, context)

    def unlink(self, cr, uid, ids, context=None):
        self.check(cr, uid, ids, 'unlink', context=context)
        if isinstance(ids, (int, long)):
            ids = [ids]

        # remove the corresponding file if any
        for attachment in self.read(cr, uid, ids, ['path'], context):
            if attachment['path']:
                if os.path.exists(attachment['path']):
                    os.remove(attachment['path'])

        return super(ir_attachment, self).unlink(cr, uid, ids, context)

    def is_migration_done(self, cr, uid):
        '''
        check if the attachment have been migrated to the file system
        '''
        default_attachment_config = self.pool.get('ir.model.data').get_object(cr, uid,
                                                                              'base_setup', 'attachment_config_default')
        return default_attachment_config.is_migration_done(cr, uid)

    def store_data_in_db(self, cr, uid, ignore_migration=False):
        '''
        check if the data should be stored in the database (or file system)
        '''
        store_data_in_db = False

        attachment_config_obj = self.pool.get('attachment.config')
        if attachment_config_obj.is_migration_running:
            # during the migration, we need to store the data on file system
            store_data_in_db = False
        elif not ignore_migration and not self.is_migration_done(cr, uid):
            store_data_in_db = True

        if not store_data_in_db:
            try:
                self.get_root_path(cr, uid)
            except:
                store_data_in_db = True
        return store_data_in_db

    def get_root_path(self, cr, uid, check=True):
        '''
        return the path to store attachments.
        Raise if the path is not valid
        '''
        default_attachment_config = self.pool.get('ir.model.data').get_object(cr, uid,
                                                                              'base_setup', 'attachment_config_default')
        path = default_attachment_config.name
        if check:
            self.pool.get('attachment.config').check_path(cr, uid, path)
        return path

    def get_file_path(self, cr, uid, file_name, root_path=None):
        '''
        return a path corresponding to the file_name join with the root_path
        '''
        if not root_path:
            root_path = self.get_root_path(cr, uid)
        return os.path.join(root_path, file_name)

    def get_file_name(self, cr, uid, attachment_id, datas_fname=None):
        '''
        generate a unique name for the attachment
        '''
        resource_name = self._name_get_resname(cr, uid, [attachment_id],
                                               None, None, None)[attachment_id]
        datas_fname = tools.ustr(datas_fname or '')
        file_name = '%s_%s_%s' % (resource_name or 'NOT_LINKED_ATTACHMENT',
                                  attachment_id, datas_fname)

        # remove unsafe characters (like '/', ' ', ...) that can broke path on some OS
        safe_char = re.compile("[a-zA-Z0-9.,_-]")
        safe_file_name = ''.join([ch for ch in file_name if safe_char.match(ch)])
        return safe_file_name

    def check_file_size(self, cr, uid, datas, context):
        '''
        raise if the size of the len of datas is > MAX_ATTACHMENT_SIZE MB
        Raise only in case of web interface (to make possible for the system
        to create bigger attachments)
        '''
        if context is None:
            context = {}
        data_size = len(datas)
        if data_size > MAX_ATTACHMENT_SIZE:
            max_size_mb = round(MAX_ATTACHMENT_SIZE/1024/1024., 2)
            data_size_mb = round(data_size/1024/1024., 2)
            msg = _('You cannot upload files bigger than %sMB, current size is %sMB') % (max_size_mb, data_size_mb)
            if context.get('from_web_interface', False):
                raise osv.except_osv(_('Error'), msg)
            else:
                self._logger.warn('A file attached by the system is bigger than %sMB (%sMB)' % (max_size_mb, data_size_mb))

    def create(self, cr, uid, values, context=None):
        if context is None:
            context = {}
        self.check(cr, uid, [], mode='create', context=context, values=values)

        store_data_in_db = self.store_data_in_db(cr, uid)
        datas = ''
        if values.get('datas'):
            if not store_data_in_db:
                datas = values.pop('datas')
            else:
                datas = values['datas']

        decoded_datas = base64.decodestring(datas)
        values['size'] = self.get_octet_size(decoded_datas)
        self.check_file_size(cr, uid, decoded_datas, context=context)
        attachment_id = super(ir_attachment, self).create(cr, uid, values,
                                                          context)
        if not store_data_in_db:
            local_filename = self.get_file_name(cr, uid, attachment_id,
                                                datas_fname=values.get('datas_fname', ''))
            new_path = self.get_file_path(cr, uid, local_filename)
            self.write(cr, uid, attachment_id, {'path': new_path}, context=context)

            # create the file on the local file system
            with open(new_path, 'wb') as f:
                f.write(decoded_datas)
        return attachment_id

    def action_get(self, cr, uid, context=None):
        return self.pool.get('ir.actions.act_window').for_xml_id(
            cr, uid, 'base', 'action_attachment', context=context)

    def _name_get_resname(self, cr, uid, ids, object, method, context):
        data = {}
        for attachment in self.read(cr, uid, ids, ['res_model', 'res_id'], context=context):
            model_object = attachment['res_model']
            res_id = attachment['res_id']
            if model_object and res_id:
                model_pool = self.pool.get(model_object)
                res = model_pool.name_get(cr, uid, [res_id], context)
                res_name = res and res[0][1] or False
                if res_name:
                    field = self._columns.get('res_name',False)
                    if field and len(res_name) > field.size:
                        res_name = res_name[:field.size-3] + '...'
                data[attachment['id']] = res_name
            else:
                data[attachment['id']] = False
        return data

    def get_octet_size(self, data):
        return len(data)

    _name = 'ir.attachment'
    _columns = {
        'name': fields.char('Attachment Name',size=256, required=True),
        'path': fields.char('Path', size=256, readonly=True),
        'datas': fields.binary('Data'),
        'datas_fname': fields.char('Filename',size=256),
        'description': fields.text('Description'),
        'res_name': fields.function(_name_get_resname, type='char', size=128,
                                    string='Resource Name', method=True, store=True),
        'res_model': fields.char('Resource Object',size=64, readonly=True,
                                 help="The database object this attachment will be attached to"),
        'res_id': fields.integer('Resource ID', readonly=True,
                                 help="The record id this is attached to"),
        'url': fields.char('Url', size=512, oldname="link"),
        'type': fields.selection(
            [ ('url','URL'), ('binary','Binary'), ],
            'Type', help="Binary File or external URL", required=True, change_default=True),

        'create_date': fields.datetime('Date Created', readonly=True),
        'create_uid':  fields.many2one('res.users', 'Owner', readonly=True),
        'company_id': fields.many2one('res.company', 'Company', change_default=True),
        'size': fields.float('Size of the file'),
    }

    _defaults = {
        'type': 'binary',
        'company_id': lambda s,cr,uid,c: s.pool.get('res.company')._company_default_get(cr, uid, 'ir.attachment', context=c),
    }

    def _auto_init(self, cr, context=None):
        super(ir_attachment, self)._auto_init(cr, context)
        cr.execute('SELECT indexname FROM pg_indexes WHERE indexname = %s', ('ir_attachment_res_idx',))
        if not cr.fetchone():
            cr.execute('CREATE INDEX ir_attachment_res_idx ON ir_attachment (res_model, res_id)')
            cr.commit()

    # US-1690
    def migrate_attachment_from_db_to_file_system(self, cr, uid):
        '''
        The attachment have all been stored into the database. It was decided
        to store them on the file system. This method is there to do the
        migration.
        '''
        current_date = fields.datetime.now()
        attachment_config_obj = self.pool.get('attachment.config')
        default_attachment_config = self.pool.get('ir.model.data').get_object(cr, uid,
                                                                              'base_setup', 'attachment_config_default')
        if attachment_config_obj.is_migration_running:
            raise osv.except_osv(_('Error'),
                                 _("A migration or move of the attachments is currently running. You have to wait for it to be finished before to launch again."))
        try:
            attachment_config_obj.is_migration_running = True
            if not default_attachment_config:
                raise osv.except_osv(_('Error'),
                                     _("No path to save the attachment found. Check the Attachment config."))
            try:
                attachment_config_obj.check_path(cr, uid, default_attachment_config.name)
            except Exception as e:
                self._logger.exception(str(e))
                attachment_config_obj.write(cr, uid,
                                            default_attachment_config.id,
                                            {'migration_error': str(e),
                                             'migration_date': current_date})
                return False

            # if the path is ok, move everything there
            attachment_ids = self.search(cr, uid, [('datas', '!=', False)])

            self._logger.info('Start attachment migration: %s attachments to migrate...' % len(attachment_ids))

            # read one by one not to do one read that will read all the data of all
            # attachment in one shot
            error_list = []
            counter = 0
            nb_attachments = len(attachment_ids)
            for attachment_id in attachment_ids:
                attachment = self.read(cr, uid, attachment_id, ['path', 'datas', 'datas_fname'])
                if attachment['datas']:
                    if attachment['path']:
                        # check the path exist and if yes, delete the datas
                        if os.path.exists(attachment['path']):
                            self.write(cr, uid, attachment_id, {'datas': False})
                            counter +=1
                            continue
                        else:
                            error_list.append("attachement id=%s have a path but "\
                                              "this path don't exists, path=%s" % (attachment_id,
                                                                                   attachment['path']))
                    else:
                        attachment.pop('id')
                        # write is doing the migration
                        self.write(cr, uid, attachment_id, attachment)
                # commit for each attachment moved then if a problem happen,
                # the transaction are not rollback with some of the files alread moved
                cr.commit()

                # update rate for the progress bar
                counter +=1
                if counter % 10 == 0:
                    rate = counter/float(nb_attachments)*100
                    attachment_config_obj.write(cr, uid,
                                                default_attachment_config.id,
                                                {'moving_rate': rate})

            if error_list:
                self._logger.exception('\n'.join(error_list))
                attachment_config_obj.write(cr, uid,
                                            default_attachment_config.id,
                                            {'migration_error': '\n'.join(error_list),
                                             'migration_date': current_date})
                return False

            # migration finish without problem, clear error messages
            attachment_config_obj.write(cr, uid,
                                        default_attachment_config.id,
                                        {'migration_error': '',
                                         'migration_date': current_date})
        except Exception as e:
            self._logger.exception(str(e))
            attachment_config_obj.write(cr, uid,
                                        default_attachment_config.id,
                                        {'migration_error': str(e),
                                         'migration_date': current_date})
        finally:
            attachment_config_obj.is_migration_running = False
        return True

ir_attachment()

class attachment_config(osv.osv):
    """ Attachment configuration """
    _name = "attachment.config"
    _description = "Attachment configuration"
    is_migration_running = False

    def _is_migration_running(self, cr, uid, ids, name, arg, context=None):
        return dict.fromkeys(ids, self.is_migration_running)

    _columns = {
        'name': fields.char('Path to save the attachments to', size=256,
                            help="The complete path to the local folder where Unifield will save attachment files.",
                            required=True),
        'next_migration' : fields.datetime('Next migration date',
                                           help="Next planned execution of the migration to move the old attachment to the path defined"),
        'migration_date': fields.datetime('Last migration execution date', readonly=True),
        'migration_error': fields.text('Migration errors', readonly=True),
        'is_migration_running': fields.function(_is_migration_running,
                                                type='boolean', string='Moving files...', method=True,
                                                readonly=True),
        'moving_rate': fields.float(string='Moving process',
                                    readonly=True),
    }

    _defaults = {
        'name' : 'c:\\attachments\\',
    }

    def _check_only_one_obj(self, cr, uid, ids, context=None):
        obj = self.search(cr, uid, [], context=context)
        if len(obj) > 1:
            return False
        return True

    _constraints = [
        (_check_only_one_obj, 'You cannot have more than one Attachment configuration', ['name']),
    ]

    def is_migration_done(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        return True if the migration as been done, False otherwise
        '''
        done = True
        for conf in self.read(cr, uid, ids, ['migration_date',
                                             'migration_error', 'is_migration_running']):
            if conf['is_migration_running']:
                done = False
                break
            if not conf['migration_date']:
                done = False
                break
            if conf['migration_error']:
                done = False
                break
        return done

    def check_path(self, cr, uid, attachments_path):
        '''
        raise with an explicit message if any condition is not fulfill
        '''
        if not attachments_path:
            raise osv.except_osv(_('Error'),
                                 _("No attachments_path provided. Check the Attachment config."))
        # check path existence
        if not os.path.exists(attachments_path):
            raise osv.except_osv(_('Error'),
                                 _("attachments_path '%s' doesn't exists. Check the Attachment config.") % attachments_path)
        # check write permission on this path
        if not os.access(attachments_path, os.W_OK):
            raise osv.except_osv(_('Error'),
                                 _("You don't have permission to write in '%s'. Check the Attachment config.") % attachments_path)

    def move_all_attachments(self, cr, uid, ids, new_root_path, context=None):
        """
        Create a new thread to move all attachment to the new root path
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param new_root_path: new path to move the attachments
        :return: True
        """
        if self.is_migration_running:
            raise osv.except_osv(_('Error'),
                                 _("A migration or move of the attachments is currently running. You have to wait for it to be finished before to launch again."))
        th = threading.Thread(
            target=self._do_move_all_attachments,
            args=(cr, uid, ids, new_root_path, True, context),
        )
        th.start()
        return True

    def _do_move_all_attachments(self, cr, uid, ids, new_root_path,
                                 use_new_cursor=False, context=None):
        """
        Move all attachments from the new_root_path
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param new_root_path: new path to move the attachments
        :param use_new_cursor: True if this method is called into a new thread
        :return: True
        """
        if use_new_cursor:
            cr = pooler.get_db(cr.dbname).cursor()

        self.is_migration_running = True
        try:
            # check there is some files to move
            attachment_obj = self.pool.get('ir.attachment')
            attachment_id_to_move = attachment_obj.search(cr, uid, [('path', '!=', False)])
            nb_attachments = len(attachment_id_to_move)
            counter = 0
            if attachment_id_to_move:
                for attachment in attachment_obj.read(cr, uid, attachment_id_to_move,
                                                      ['datas_fname'], context):
                    old_path = attachment['path']
                    file_name = attachment_obj.get_file_name(cr, uid, attachment['id'],
                                                             datas_fname=attachment.get('datas_fname', ''))
                    new_path = attachment_obj.get_file_path(cr, uid, file_name,
                                                            root_path=new_root_path)
                    if new_path == old_path:
                        continue
                    # move the file on the file system
                    os.rename(old_path, new_path)
                    # change the path in the DB
                    attachment_obj.write(cr, uid, attachment['id'], {'path':new_path}, context)
                    cr.commit()
                    # update rate for the progress bar
                    counter +=1
                    if counter % 10 == 0:
                        rate = counter/float(nb_attachments)*100
                        self.write(cr, uid, ids, {'moving_rate': rate},
                                   context)

        except Exception as e:
            raise osv.except_osv(_('Error'), str(e))
        finally:
            self.is_migration_running = False
            # reset the moving rate
            self.write(cr, uid, ids, {'moving_rate': 0},
                       context)
            if use_new_cursor:
                try:
                    cr.commit()
                    cr.close(True)
                except Exception:
                    pass
        return True

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if 'name' in vals:

            attachments_path = vals.get('name')
            self.check_path(cr, uid, attachments_path)

            # add db_name in the path
            db_name = cr.dbname
            create_db_dir = tools.config.get('create_db_dir_for_attachment')
            if create_db_dir and not db_name in attachments_path:
                attachments_path = os.path.join(attachments_path, db_name)
                if not os.path.exists(attachments_path):
                    os.makedirs(attachments_path)
                vals['name'] = attachments_path

            migration_error = vals.get('migration_error', False)
            if migration_error:
                raise osv.except_osv(_('Error'),
                                     _("You cannot change the path to save attachment because the migration have some errors. Please fix them before."))
            # if new_path is different from current one
            current_path = self.read(cr, uid, ids, ['name'], context)[0]['name']
            if attachments_path != current_path:
                self.move_all_attachments(cr, uid, ids, attachments_path,
                                          context=context)

        if 'next_migration' in vals and vals['next_migration']:
            # create a ir_cron with this values
            cron_obj = self.pool.get('ir.cron')
            default_migrate_attachment = self.pool.get('ir.model.data').get_object(cr, uid,
                                                                                   'base', 'ir_cron_migrate_attachment')
            values = {
                'nextcall': vals['next_migration'],
                'numbercall': 1,
                'active': True,
            }
            cron_obj.write(cr, uid, default_migrate_attachment.id, values, context=context)
        return super(attachment_config, self).write(cr, uid, ids, vals, context=context)

attachment_config()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

