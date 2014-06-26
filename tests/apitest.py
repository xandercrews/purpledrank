__author__ = 'achmed'

from purpledrank.log import init_logger
init_logger()

import logging
logger = logging.getLogger('purpledrank.api')

from purpledrank.api import app

app.config['ARANGO_DB'] = 'purpledrank'
app.config['ARANGO_SERVER'] = 'tools.svcs.aperobot.net'

app.run(port=8888, debug=True)
