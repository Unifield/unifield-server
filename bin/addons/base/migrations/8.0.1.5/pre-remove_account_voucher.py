import os
from tools import config
import logging


def migrate(cr, version):
    if not cr.table_exists('ir_module_module'):
        return

    cr.execute("update ir_module_module set state='uninstalled' where name='account_voucher'")

    if not cr.table_exists('wkf'):
        return
    cr.execute("delete from wkf where osv='payment.order'")

    logger = logging.getLogger('migration')
    queries = os.path.join(config['root_path'], 'addons/base/migrations/8.0.1.5/update_ir_model_data_fields.sql')
    if os.path.exists(queries):
        with open(queries) as lines:
            for line in lines:
                if line:
                    cr.execute('SAVEPOINT migration')
                    try:
                        cr.execute(line)
                    except:
                        logger.warn('SQL error %s' % line)
                        cr.execute('ROLLBACK TO SAVEPOINT migration')
    return True
