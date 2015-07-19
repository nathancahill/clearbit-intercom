
import math
from urlparse import urlparse

from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

CLEARBIT_USER = 'https://person-stream.clearbit.com/v1/people/email/{email}'
CLEARBIT_COMPANY = 'https://company-stream.clearbit.com/v1/companies/domain/{domain}'
INTERCOM_ENDPOINT = 'https://api.intercom.io/notes'


def millify(n):
    """
    Convert number to a human-readable amount with K, M, B, T suffixes.

    Adapted from http://stackoverflow.com/a/3155023/1377021

    :n: float. the number to convert to human-readable amount
    :ret: string. the human-readable amount with K, M, B, T suffixes
    """
    n = float(n)
    millnames = ['', 'K', 'M', 'B', 'T']
    millidx = max(0, min(len(millnames) - 1, int(math.floor(math.log10(abs(n)) / 3))))
    amount = n / 10 ** (3 * millidx)

    if amount.is_integer():
        return '%.0f%s' % (amount, millnames[millidx])
    else:
        return '%.1f%s' % (amount, millnames[millidx])


def safe_requests(method, *args, **kwargs):
    """
    Return a JSON response from Requests or raise a human-readable exception.

    :method: string. the requests method to call, i.e. 'get' or 'post'
    :args: args. the args to pass to the requests method
    :kwargs: kwargs. the kwargs to pass to the requests method
    :ret: obj. the JSON response
    """
    func = getattr(requests, method)
    domain = urlparse(kwargs.get('url', args[0])).netloc

    try:
        res = func(*args, **kwargs)
    except:
        raise Exception('API call failed to {domain}.'.format(domain=domain))

    try:
        obj = res.json()
    except:
        raise Exception('Invalid response from {domain}.'.format(domain=domain))

    if 'error' in obj:
        raise Exception('Error response from {domain}.'.format(domain=domain))

    return obj


def create_note(person, company=None):
    """
    Create an Intercom.io note from a person and optional compay object.

    :person: obj. a Clearbit person object: https://dashboard.clearbit.com/docs#person-api
    :company: obj. a Clearbit company object: https://dashboard.clearbit.com/docs#company-api
    :ret: string. a note string with line breaks for Intercom
    """
    note = ''
    employment = person['employment']

    if employment['title'] and employment['name']:
        note += '{title} @ {name}\n'.format(**employment)
    elif employment['name']:
        note += 'Works @ {name}\n'.format(**employment)

    if not company:
        return note.strip()

    metrics = company['metrics']

    if metrics['raised']:
        try:
            metrics['raised'] = millify(metrics['raised'])
        except:
            pass

    if metrics['employees']:
        try:
            metrics['employees'] = millify(metrics['employees'])
        except:
            pass

    if metrics['raised'] and metrics['employees']:
        note += 'Raised ${raised}, {employees} employees\n'.format(**metrics)
    elif metrics['raised']:
        note += 'Raised ${raised}\n'.format(**metrics)
    elif metrics['employees']:
        note += '{employees} employees\n'.format(**metrics)

    return note.strip()


@app.route('/<clearbitkey>+<appid>:<intercomkey>', methods=['POST'])
def webhook(clearbitkey, appid, intercomkey):
    """
    Webhook endpoint for Intercom.io events. Uses this format for Clearbit and
    Intercom.io keys:

    /<clearbitkey>+<appid>:<intercomkey>

    :clearbitkey: string. Clearbit API key
    :appid: string. Intercom.io app id
    :intercomkey: string. Intercom.io API key

    :json: obj. The user event object posted to the webhook
    :ret: obj. JSON response with either an error or the created note object

    Supports User events, specifically designed for the User Created event.
    Adds a note to the user with their employment and company metrics.
    """
    event = request.get_json()
    res_objs = dict(event=event)

    try:
        event_type = event['data']['item']['type']
    except KeyError:
        return jsonify(error='Unexpected JSON format.', **res_objs)

    if event_type != 'user':
        return jsonify(error='Event type is not supported.', **res_objs)

    try:
        id = event['data']['item']['id']
        email = event['data']['item']['email']
    except KeyError:
        return jsonify(error='User object missing fields.', **res_objs)

    try:
        person = safe_requests('get',
                               CLEARBIT_USER.format(email=email),
                               auth=(clearbitkey, ''))
    except Exception as e:
        return jsonify(error=str(e), **res_objs)

    domain = person['employment']['domain']

    if domain:
        try:
            company = safe_requests('get',
                                    CLEARBIT_COMPANY.format(domain=domain),
                                    auth=(clearbitkey, ''))
        except:
            company = None

    res_objs['company'] = company

    try:
        note = create_note(person, company)
    except:
        return jsonify(error='Failed to generate note for user.', **res_objs)

    try:
        result = safe_requests('post',
                               INTERCOM_ENDPOINT,
                               json=dict(user=dict(id=id), body=note),
                               headers=dict(accept='application/json'),
                               auth=(appid, intercomkey))
    except Exception as e:
        return jsonify(error=str(e), **res_objs)

    return jsonify(note=result, **res_objs)


if __name__ == '__main__':
    app.run(debug=True)
