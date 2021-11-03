import os
from tools import config
import logging


def migrate(cr, version):
    if not cr.table_exists('ir_model_data'):
        return

    logger = logging.getLogger('migration')
    queries = os.path.join(config['root_path'], 'addons/base/migrations/8.0.1.7/update_bar_sdref.sql')
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
