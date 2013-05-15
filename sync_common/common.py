import re
import tools
import sys
import traceback
import functools
import pprint



MODELS_TO_IGNORE = [
                    'ir.actions.wizard',
                    'ir.actions.act_window.view',
                    'ir.report.custom',
                    'ir.ui.menu',
                    'ir.actions.act_window.view',
                    'ir.actions.wizard',
                    'ir.report.custom',
                    'ir.ui.menu',
                    'ir.ui.view',
                    'ir.sequence',
                    'ir.actions.url',
                    'ir.values',
                    'ir.report.custom.fields',
                    'ir.cron',
                    'ir.actions.report.xml',
                    'ir.property',
                    'ir.actions.todo',
                    'ir.sequence.type',
                    'ir.actions.act_window',
                    'ir.module.module',
                    'ir.ui.view',
                    'ir.module.repository',
                    'ir.model',
                    'ir.model.data',
                    'ir.model.fields',
                    'ir.model.access',
                    'ir.ui.view_sc',
                    'ir.config_parameter',

                    'sync.monitor',
                    'sync.client.rule',
                    'sync.client.push.data.information',
                    'sync.client.update_to_send',
                    'sync.client.update_received',
                    'sync.client.entity',
                    'sync.client.sync_server_connection',
                    'sync.client.message_rule',
                    'sync.client.message_to_send',
                    'sync.client.message_received',
                    'sync.client.message_sync',
                    'sync.client.orm_extended',

                    'sync.server.test',
                    'sync_server.version.manager',
                    'sync.server.entity_group',
                    'sync.server.entity',
                    'sync.server.group_type',
                    'sync.server.entity_group',
                    'sync.server.entity',
                    'sync.server.sync_manager',
                    'sync_server.sync_rule',
                    'sync_server.message_rule',
                    'sync_server.sync_rule.forced_values',
                    'sync_server.sync_rule.fallback_values',
                    'sync_server.rule.validation.message',
                    'sync.server.update',
                    'sync.server.message',
                    'sync_server.version',

                    'res.widget',
                  ]

MODELS_TO_IGNORE_DOMAIN = [
        'ir.%',
        'sync_client.%',
        'sync_server.%',
        'res.widget%',
        'base%',
        'board%',
        'workflow%',
    ]

XML_ID_TO_IGNORE = [
        'main_partner',
        'main_address',
        'main_company', 
    ]

def __compile_models_to_ignore():
    global MODELS_TO_IGNORE_DOMAIN
    simple_patterns = []
    exact_models = []
    for model in MODELS_TO_IGNORE_DOMAIN:
        if model.find('%') >= 0:
            simple_patterns.append(model)
        else:
            exact_models.append(model)
    MODELS_TO_IGNORE_DOMAIN[:] = [('model','not in',exact_models)]
    for pattern in simple_patterns:
        MODELS_TO_IGNORE_DOMAIN.extend(['!',('model','=like',pattern)])

__compile_models_to_ignore()



def xmlid_to_sdref(xmlid):
    if not xmlid: return None
    head, sep, tail = xmlid.partition('.')
    assert sep and head == 'sd', "The xmlid seems to not be owned by module sd, which is wrong"
    return tail if sep else head



def sync_log(obj, message=None, level='debug', ids=None, data=None, traceback=False):
    if not hasattr(obj, '_logger'):
        raise Exception("No _logger specified for object %s!" % obj._name)
    output = ""
    if traceback:
        output += traceback.format_exc()
    if message is None:
        previous_frame = sys._getframe(1)
        output += "%s.%s()" % (previous_frame.f_globals['__package__'], previous_frame.f_code.co_name)
    elif isinstance(message, BaseException):
        if hasattr(message, 'value'):
            output += message.value
        elif hasattr(message, 'message'):
            output += message.message
        else:
            output += tools.ustr(message)
        if output[-1] != "\n": output += "\n"
    else:
        output += "%s: %s" % (level.capitalize(), message)
    if ids is not None:
        output += " in model %s, ids %s\n" % (obj._name, ", ".join(ids))
    if data is not None:
        output += " in content: %s\n" % pprint.pformat(data)
    if output[-1] != "\n": output += "\n"
    getattr(obj._logger, level)(output[:-1])
    return output



def add_sdref_column(fn):
    @functools.wraps(fn)
    def wrapper(self, cr, context=None):
        cr.execute("""\
SELECT column_name 
  FROM information_schema.columns 
  WHERE table_name=%s AND column_name='sdref';""", [self._table])
        column_sdref_exists = bool( cr.fetchone() )
        fn(self, cr, context=context)
        if not column_sdref_exists:
            cr.execute("SELECT COUNT(*) FROM %s" % self._table)
            count = cr.fetchone()[0]
            if count > 0:
                cr.commit()
                cr_read = cr._cnx.cursor()
                self._logger.info("Populating column sdref for model %s, %d records to update... This operation can take a lot of time, please wait..." % (self._name, count))
                cr_read.execute("SELECT id, fields, values FROM %s" % self._table)
                i, row = 1, cr_read.fetchone()
                while row:
                    id, fields, values = row
                    cr.execute("SAVEPOINT make_sdref")
                    try:
                        data = dict(zip(eval(fields), eval(values)))
                        assert 'id' in data, "Cannot find column 'id' on model=%s id=%d" % (self._name, id)
                        sdref = xmlid_to_sdref(data['id'])
                        cr.execute("UPDATE %s SET sdref = %%s WHERE id = %%s" % self._table, [sdref, id])
                    except AssertionError, e:
                        self._logger.error("Cannot find SD ref on model=%s id=%d: %s" % (self._name, id, e.message))
                        cr.execute("ROLLBACK TO SAVEPOINT make_sdref")
                    except:
                        self._logger.exception("Cannot find SD ref on model=%s id=%d" % (self._name, id))
                        cr.execute("ROLLBACK TO SAVEPOINT make_sdref")
                    else:
                        cr.execute("RELEASE SAVEPOINT make_sdref")
                    if i % 20000 == 0:
                        self._logger.info("Intermittent commit, %d/%d (%d%%) SD refs created" % (i, count, int(100.0 * i / count)))
                        cr.commit()
                    i, row = i + 1, cr_read.fetchone()
                cr_read.close()
                cr.commit()
    return wrapper



__re_fancy_integer_field_name = re.compile(r'^fancy_(.+)')
def fancy_integer(self, cr, uid, ids, name, arg, context=None):
    global __re_fancy_integer_field_name
    re_match = __re_fancy_integer_field_name.match(name)
    assert re_match is not None, "Invalid field detection for fancy integer display"
    target_field = re_match.group(1)
    res = self.read(cr, uid, ids, [target_field], context=context)
    return dict(zip(
            (rec['id'] for rec in res),
            (rec[target_field] or '' for rec in res),
        ))
