#!/usr/bin/env python
import datetime
import json
from wsgiref import simple_server

import falcon


def luhn_checksum(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = 0
    checksum += sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d*2))
    return checksum % 10


def calculate_luhn(partial_card_number):
    check_digit = luhn_checksum(int(partial_card_number) * 10)
    return check_digit if check_digit == 0 else 10 - check_digit


class RequireJSON(object):

    def process_request(self, req, resp):
        if not req.client_accepts_json:
            raise falcon.HTTPNotAcceptable(
                'This API only supports responses encoded as JSON.',
                href='http://docs.examples.com/api/json')

        if req.method in ('POST', 'PUT'):
            if 'application/json' not in req.content_type:
                raise falcon.HTTPUnsupportedMediaType(
                    'This API only supports requests encoded as JSON.',
                    href='http://docs.examples.com/api/json')


class JSONTranslator(object):

    def process_request(self, req, resp):
        # req.stream corresponds to the WSGI wsgi.input environ variable,
        # and allows you to read bytes from the request body.
        #
        # See also: PEP 3333
        if req.content_length in (None, 0):
            # Nothing to do
            return

        body = req.stream.read()
        if not body:
            raise falcon.HTTPBadRequest('Empty request body',
                                        'A valid JSON document is required.')

        try:
            req.context['doc'] = json.loads(body.decode('utf-8'))

        except (ValueError, UnicodeDecodeError):
            raise falcon.HTTPError(falcon.HTTP_753,
                                   'Malformed JSON',
                                   'Could not decode the request body. The '
                                   'JSON was incorrect or not encoded as '
                                   'UTF-8.')

    def process_response(self, req, resp, resource):
        if 'result' not in req.context:
            return

        resp.body = json.dumps(req.context['result'])


class LuhnResource(object):

    def on_post(self, request, response):
        try:
            doc = request.context['doc']
        except KeyError:
            raise falcon.HTTPBadRequest('Missing request body',
                                        'A request body must be provided.')
        try:
            r_iin = doc['iin']
            r_bin = doc['bin']
            r_sponsor = doc['sponsor']
            r_account = doc['account']
        except KeyError:
            raise falcon.HTTPBadRequest('Missing parameters',
                                        'The request body must contain: iin, bin, sponsor, account')
        # NOTE: I'm assuming this is the requested format; the description in the assignment doesn't
        # fit too precisely with the description with the description on Wikipedia for either the LUN
        # algorithm or ISO/IEC 7812. Both specify only that the first 6 digits represent the IIN, fka BIN,
        # then the following 10-12 digits represent the account identifier
        full_number = '%s%s%s%s' % (r_iin, r_bin, r_sponsor, r_account)
        try:
            full_number = '%s%s' % (full_number, calculate_luhn(full_number))
        except (ValueError, TypeError):
            raise falcon.HTTPBadRequest('Invalid data',
                                        'Input data was invalid; please provide only numbers')
        result = {'cardnumber': full_number,
                  'datetime_generated': str(datetime.datetime.utcnow())}
        request.context['result'] = result


application = falcon.API(middleware=[
    RequireJSON(),
    JSONTranslator(),
])
luhn = LuhnResource()
application.add_route('/v1.0/utilities/luhn', luhn)


if __name__ == '__main__':
    httpd = simple_server.make_server('127.0.0.1', 8003, application)
    httpd.serve_forever()
