#!/usr/bin/env python3
import os
import requests
import json
from flask import Flask, request, Response

app = Flask(__name__)

with open(os.environ['CONFIG_FILE']) as f:
    config = json.load(f)

@app.route('/<string:token>')
def dyn(token):
    if token in config['TOKEN_SUBDOMAIN_MAP']:
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            ip = real_ip
        else:
            ip = request.remote_addr

        h = {'X-API-Key': config['PDNS_API_KEY']}
        ret = 'UPDATE FAILED'

        if '.' in ip:
            record_type = 'A'
        elif ':' in ip:
            record_type = 'AAAA'

        ZONE_URL = config['PDNS_API_BASE'] + 'servers/' + config['PDNS_SERVER_ID'] + '/zones/' + config['PDNS_ZONE_ID']
        req = requests.get(ZONE_URL, headers=h)
        try:
            j = req.json()
            for r in j['rrsets']:
                fqdn = subdomain + '.' + config['PDNS_ZONE_ID'] + '.'
                r_sub = r['name']
                r_type = r['type']
                r_ip = r['records'][0]['content']
                if r_sub == fqdn and r_type == record_type:
                    if r_ip == ip:
                        ret = 'NO CHANGE'
                    else:
                        payload = { "rrsets": [ {
                            "name": fqdn,
                            "type": record_type,
                            "ttl": 60,
                            "changetype": 'REPLACE',
                            "records": [ {
                                "content": ip,
                                "disabled": False,
                                "set-ptr": False
                            } ]
                        } ] }
                        req = requests.patch(ZONE_URL, data=json.dumps(payload), headers=h)
                        if req.status_code == 204:
                            req = requests.put(ZONE_URL + '/notify', headers=h)
                            if req.status_code == 200:
                                ret = 'UPDATED'
                    break
        except Exception:
            pass

        resp = ret + ' ' + record_type + ' ' + ip
        status = req.status_code
    else:
        resp = 'INVALID TOKEN'
        status = 403

    return Response(resp, status=status, mimetype='text/plain')


if __name__ == "__main__":
    from gevent.pywsgi import WSGIServer
    http_server = WSGIServer(('127.0.0.1', config['LISTEN_PORT']), app)
    http_server.serve_forever()
