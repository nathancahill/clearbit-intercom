
import math

from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

CLEARBIT_USER_ENDPOINT = 'https://person-stream.clearbit.com/v1/people/email/{email}'
CLEARBIT_COMPANY_ENDPOINT = 'https://company-stream.clearbit.com/v1/companies/domain/{domain}'
INTERCOM_ENDPOINT = 'https://api.intercom.io/notes'


def millify(n):
    """
    Convert number to human-readable amount with K, M, B, T suffixes.

    Adapted from http://stackoverflow.com/a/3155023/1377021
    """
    n = float(n)
    millnames = ['', 'K', 'M', 'B', 'T']
    millidx = max(0, min(len(millnames) - 1, int(math.floor(math.log10(abs(n)) / 3))))
    amount = n / 10 ** (3 * millidx)

    if amount.is_integer():
        return '%.0f%s' % (amount, millnames[millidx])
    else:
        return '%.1f%s' % (amount, millnames[millidx])


def create_note(person, company=None):
    """
    Create an Intercom.io note from a person and optional compay object.
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

    :clearbitkey: Clearbit API key.
    :appid: Intercom.io app id.
    :intercomkey: Intercom.io API key.

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
        res = requests.get(CLEARBIT_USER_ENDPOINT.format(email=email),
                           auth=(clearbitkey, ''))
    except:
        return jsonify(error='API call failed to Clearbit.', **res_objs)

    try:
        person = res.json()
    except:
        return jsonify(error='Invalid response from Clearbit.', **res_objs)

    res_objs['person'] = person

    if 'error' in person:
        return jsonify(error='Error response from Clearbit.', **res_objs)

    domain = person['employment']['domain']
    company = None

    if domain:
        try:
            res = requests.get(CLEARBIT_COMPANY_ENDPOINT.format(domain=domain),
                               auth=(clearbitkey, ''))
        except:
            pass
        else:
            try:
                company = res.json()
            except:
                pass
            else:
                if 'error' in company:
                    company = None

    res_objs['company'] = company

    try:
        note = create_note(person, company)
    except:
        return jsonify(error='Failed to generate note for user.', **res_objs)

    try:
        res = requests.post(INTERCOM_ENDPOINT,
                            json=dict(user=dict(id=id), body=note),
                            headers=dict(accept='application/json'),
                            auth=(appid, intercomkey))
    except:
        return jsonify(error='API call failed to Intercom.', **res_objs)

    try:
        result = res.json()
    except:
        return jsonify(error='Invalid response from Intercom', **res_objs)

    return jsonify(note=result, **res_objs)


if __name__ == '__main__':
    app.run(debug=True)
