
import os
import logging
import socket
from base64 import b64decode
from io import StringIO
import tarfile

from osv import osv, fields
from tools.translate import _
import base64
from tools import config
import updater

from .version import IMPORT_PATCH_SUCCESS, IMPORT_PATCH_INVALID, IMPORT_PATCH_UNKNOWN, IMPORT_PATCH_IGNORED

class upgrade(osv.osv_memory):
    _name = 'sync_client.upgrade'
    _description = "OpenERP Upgrade Wizard"

    _logger = logging.getLogger('sync.client.upgrade')

    def is_sync_server_reachable(self, cr, uid, context=None):
        if context is None:
            context = {}
        res = True
        try:
            con = self.pool.get("sync.client.sync_server_connection")._get_connection_manager(cr, uid, context=context)
            address = os.environ.get('UF_TEST_URL', con.host)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._logger.info("Check the connection is open: %s port %s ..." % (address, con.port))
            result = sock.connect_ex((address, con.port))
            res = result == 0
            self._logger.info("%s:%s %s reachable." % (address, con.port, res and 'is' or 'is not'))
        except:
            res = False
        return res

    def restart(self, cr, uid, ids, context=None):
        os.chdir( config['root_path'] )
        updater.restart_server()
        return {'type': 'ir.actions.act_window_close'}

    def _get_error(self, cr, uid, context=None):
        text = ""
        account_move_obj = self.pool.get('account.move')
        a_m_ids = account_move_obj.get_valid_but_unbalanced(cr, uid, context)
        if a_m_ids:
            text += "Warning ! Before patching please correct the following unbalanced Journal Entries: \n"
            for a_m in account_move_obj.read(cr, uid, a_m_ids, ['name']):
                text += " - %s\n"% (a_m['name'])
        return text

    def download(self, cr, uid, ids, context=None):
        """Downlad the patch to fill the version record"""
        revisions = self.pool.get('sync_client.version')
        next_revisions = revisions._get_next_revisions(cr, uid, context=context)
        if not next_revisions:
            raise osv.except_osv(_("Error!"), _("Nothing to do."))
        proxy = self.pool.get("sync.client.sync_server_connection").get_connection(cr, uid, "sync.server.sync_manager")
        uuid = self.pool.get('sync.client.entity').get_uuid(cr, uid)
        text = _("This/These patche(s) have been downloaded and are ready to install:")
        text += "\n\n"
        for rev in revisions.browse(cr, uid, next_revisions, context=context):
            text += (" - [%(importance)s] %(name)s (%(date)s)\n   " % rev) + \
                    (_("Comment: %(comment)s (sum is %(sum)s)") % rev) + "\n\n"
            offset = 0
            patch_name = revisions.get_patch_file(cr, uid, rev.id, context=context)
            if os.path.exists(patch_name):
                offset = os.path.getsize(patch_name)
            with open(patch_name, 'ab') as fp:
                while True:
                    patch = proxy.get_zip( uuid,  self.pool.get("sync.client.entity")._hardware_id, rev.sum, offset)
                    if not patch[0]:
                        raise osv.except_osv(_("Error!"), _("Can't retrieve the patch %(name)s (%(sum)s)!") % rev)
                    if not patch[1]:
                        break
                    d_patch = b64decode(patch[1])
                    fp.write(d_patch)
                    offset += len(d_patch)
            revisions.write(cr, uid, rev.id, {'patch_path': patch_name}, context=context)

        return self.write(cr, uid, ids, {
            'message' : text,
            'state' : 'need-install',
        }, context=context)

    def do_upgrade(self, cr, uid, ids, context=None, sync_type='manual'):
        """Actualy, prepare the upgrade to be done at server restart"""
        # backup before patching
        self.pool.get('backup.config').exp_dump_for_state(cr, uid,
                                                          'beforepatching', context=context, force=True)

        connection_module = self.pool.get("sync.client.sync_server_connection")
        proxy = connection_module.get_connection(cr, uid, "sync.server.sync_manager")
        # in case of automatic patching,  create a file to store the actual
        # SYNC_SERVER connection credentials to be able to automatically
        # reconnect to the SYNC_SERVER after an upgrade
        automatic_patching = sync_type=='automatic' and\
            connection_module.is_automatic_patching_allowed(cr, uid)
        if automatic_patching:
            password = list(connection_module._get_password(cr, uid, [proxy], None, None, None).values())[0]
            password = base64.b64encode(bytes(password, 'utf8'))
            db_name = base64.b64encode(bytes(cr.dbname, 'utf8'))
            credential_filepath = os.path.join(config['root_path'], 'unifield-socket.py')
            f = open(credential_filepath, 'wb')
            f.write(db_name)
            f.write(password)
            f.close()

        ## Check if revision upgrade applies
        next_state = self._get_state(cr, uid, context=context)
        if next_state != 'need-install':
            if next_state == 'need-download' and automatic_patching:
                self.download(cr, uid, ids, context)
            else:
                return self.write(cr, uid, ids, {
                    'message' : _("Cannot install now.\n\n%s") % self._generate(cr, uid, context=context),
                    'state' : next_state,
                }, context=context)
        next_revisions = self.pool.get('sync_client.version')._get_next_revisions(cr, uid, context=context)
        ## Prepare
        (status, message, values) = updater.do_prepare(cr, next_revisions)
        wiz_value = {'message':_(message)}
        if status in ('corrupt','missing'):
            wiz_value['state'] = 'need-download'
        elif status == 'success':
            wiz_value['state'] = 'need-restart'
            wiz_value['message'] = self._generate(cr, uid, context=context),
        ## Refresh the window
        if values: wiz_value['message'] = wiz_value['message'] % values
        res = self.write(cr, uid, ids, wiz_value, context=context)
        if status != 'success':
            return res
        ## Restart automatically
        self.restart(cr, uid, ids, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def import_patch(self, cr, uid, ids, context=None):
        revisions = self.pool.get('sync_client.version')
        count = 0
        ignored = 0
        unknown = 0

        for wiz in self.browse(cr, uid, ids, context=context):
            status = revisions.import_patch(cr, uid, patch=wiz.patch, context=context)
            if status == IMPORT_PATCH_SUCCESS:
                cr.commit()
                count += 1
            elif status == IMPORT_PATCH_INVALID:
                try:
                    tar = tarfile.open(fileobj=StringIO(b64decode(wiz.patch)))
                    for content in (fh.read() for fh in (tar.extractfile(name) for name in tar.getnames()) if fh):
                        status = revisions.import_patch(cr, uid,
                                                        decoded=content, context=context)
                        cr.commit()
                        if status == IMPORT_PATCH_SUCCESS: count += 1
                        elif status == IMPORT_PATCH_INVALID: pass
                        elif status == IMPORT_PATCH_UNKNOWN: unknown += 1
                        elif status == IMPORT_PATCH_IGNORED: ignored += 1
                except tarfile.ReadError:
                    raise osv.except_osv(_("Error!"), _("Not recognized patch file!"))
            elif status == IMPORT_PATCH_UNKNOWN:
                unknown += 1
            elif status == IMPORT_PATCH_IGNORED:
                ignored += 1

        self._logger.info("%d patches imported / %d ignored patches / %d unknown zip." \
                          % (count, ignored, unknown))

        if not count:
            if ignored:
                text = _("%d patches found already present in the database. " \
                         "Nothing to do.") % count
            elif unknown:
                text = _("%d potential patches are found but they are unknown. " \
                         "You may run first the synchronization process.") % unknown
            else:
                text = _("No patch has been found in the file provided. " \
                         "Please check you uploaded the right file.")
            self.write(cr, uid, ids, {'message':text}, context=context)
        else:
            self.write(cr, uid, ids, {
                'message' : _("%d revision(s) has been imported.") % count + \
                "\n\n" + self._generate(cr, uid, context=context),
                'state' : self._get_state(cr, uid, context=context),
            }, context=context)

        return {}

    def _generate(self, cr, uid, context=None):
        """Make the wizard caption"""
        if self.pool.get('sync.client.entity').is_syncing():
            return _("Blocked during synchro.\n\nPlease try again later.")
        revisions = self.pool.get('sync_client.version')
        if revisions._need_restart(cr, uid, context=context):
            return _("OpenERP needs to be restarted to complete the installation.")
        text = ""
        currev = revisions._get_last_revision(cr, uid, context=context)
        if currev:
            if all([currev.name, currev.date]):
                text += _("The current revision is %s (%s at %s) and has been applied at %s.") % (currev.name, currev.sum, currev.date, currev.applied)
            else:
                text += _("The server last sum is %s and has been applied on that database at %s.") % (currev.sum, currev.applied)
        else:
            text += _("No revision has been applied yet.")
        text += "\n"
        next_revisions = revisions.browse(cr, uid,
                                          revisions._get_next_revisions(cr, uid, context=context),
                                          context=context)
        if next_revisions:
            text += "\n"
            if len(next_revisions) == 1:
                text += _("There is one revision available.")
            else:
                text += _("There are %d revisions available.") % len(next_revisions)
            text += "\n"
            for rev in next_revisions:
                info = "[%(importance)s] %(name)s (%(date)s)" % rev
                need_download = _("(need to be downloaded)") if rev.need_download else ''
                text += (" - %s\n   " % " ".join([info, need_download])) + \
                        (_("Comment: %(comment)s (sum is %(sum)s)") % rev) + "\n\n"
            if any(rev.need_download for rev in next_revisions) and not self.is_sync_server_reachable(cr, uid):
                text += _("But it seems you don't have an Internet access. " \
                          "Please provide the patches manually.")+"\n"
        else:
            text += "\n"+_("Your OpenERP version is up-to-date.")+"\n"
        return text

    def _get_state(self, cr, uid, context=None):
        if self.pool.get('sync.client.entity').is_syncing():
            return 'blocked'
        revisions = self.pool.get('sync_client.version')
        if revisions._need_restart(cr, uid, context=context):
            return 'need-restart'
        next_revisions = revisions._get_next_revisions(cr, uid, context=context)
        if not next_revisions:
            return 'up-to-date'
        if not revisions._is_update_available(cr, uid, next_revisions, context=context):
            if self._is_remotewarehouse(cr, uid):
                return 'need-provide-manually'
            else:
                return 'need-download'
        return 'need-install'

    def _is_remotewarehouse(self, cr, uid, context=None):
        try:
            entity = self.pool.get('sync.client.entity').get_entity(cr, uid)
            if entity.usb_instance_type == 'remote_warehouse':
                return True
        except Exception:
            pass
        return False

    _columns = {
        'message' : fields.text("Caption", readonly=True),
        'state' : fields.selection([
            ('need-provide-manually','Need To Provide Manually The Files'),
            ('need-download','Need Download'),
            ('up-to-date','Up-To-Date'),
            ('need-install','Need Install'),
            ('need-restart','Need Restart'),
            ('blocked','Blocked')
        ], string="Status"),
        'patch' : fields.binary("Patch"),
        'error': fields.text('Error', readonly="1"),
    }

    _defaults = {
        'message' : _generate,
        'state' : _get_state,
        'error': _get_error,
    }

upgrade()
