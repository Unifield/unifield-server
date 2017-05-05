## Debug method for development #############################################

## To use this, simply start the server in log_level DEBUG or lower
## and remove the logfile. Then call method debug() in RPC on any object

import os
import logging

from osv import orm
import tools

if not tools.config.options['logfile'] and tools.config.options['log_level'] <= logging.DEBUG:
    pdb = __import__(os.environ.get('OE_PDB', 'pdb'))

    def chuck_norris(self, cr, uid, context=None):
        context = dict(context or {})
        logger = logging.getLogger('chuck_norris')

        logger.debug("called on object %s" % self._name)
        logger.debug("type 'c' to let Chuck Norris continue his way")
        logger.debug("beware that the current transaction will be aborted.")
        logger.debug("if you really want to commit, call cr.commit()")
        try:
            import urllib2
            import HTMLParser
            import json
            
            logger.debug( '>> ' + HTMLParser.HTMLParser().unescape(
                json.loads(
                        urllib2.urlopen('http://api.icndb.com/jokes/random?limitTo=[nerdy]').read().decode('utf-8')
                    )['value']['joke']) )
        except:
            logger.exception()
        pdb.set_trace()

        cr.rollback()
        return True

    orm.orm_template.chuck_norris = chuck_norris
