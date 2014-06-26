__author__ = 'achmed'

import flask
from flask import Response, jsonify, abort
import arango

import operator
import collections
import json

import logging
logger = logging.getLogger(__name__)
logging.basicConfig()
logger.setLevel(logging.DEBUG)


app = flask.Flask('purpledrank-api')


@app.errorhandler(404)
def page_not_found(e):
    return jsonify(error='Not Found', code=404)


@app.before_first_request
def initialize():
    app.arango = arango.create(db=app.config.get('ARANGO_DB'), host=app.config.get('ARANGO_SERVER'))


@app.route('/api/vm', methods=['GET'])
def list_vms():
    q = app.arango.purpledoc.query

    q = q.iter('u')
    q = q.filter('u.type == "kvm_vm"')
    q = q.result(fields={'_id': 'u._id', 'id': 'u.id', 'sourceid': 'u.sourceid'})

    c = q.execute()

    d = sorted(map(lambda o: "%s:%s" % (o.body['sourceid'], o.body['id']), c))

    if len(d) == 0:
        abort(404)

    return Response(json.dumps(d, indent=2), mimetype='application/json')


@app.route('/api/vm/<vm>', methods=['GET'])
def get_vm(vm):
    q = app.arango.purpledoc.query

    q = q.iter('u')
    q = q.filter('u.type == "kvm_vm" && u.id == @name').bind(name=vm).result('u')
    q = q.result('u')
    c = q.execute()

    d = collections.OrderedDict(sorted(map(lambda o: (o.body['id'], o.body), c), key=operator.itemgetter(0)))

    if len(d) == 0:
        abort(404)

    return Response(json.dumps(d, indent=2), mimetype='application/json')
