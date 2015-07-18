## Clearbit - Intercom.io Integration

Automatically note a user's employment and company metrics on Intercom.io.

![](http://i.imgur.com/CBzmn2B.png)

### Usage

Add a Webhook Integation in Intercom.io for the User Created event. The format of the URL is:

`http://clearbit-intercom.herokuapp.com/<clearbitkey>+<appid>:<itercomkey>`

![](http://i.imgur.com/UNKh3up.png)

### Deploy

If you'd rather use your own deployment, deploy to Heroku:

[![Deploy](https://www.herokucdn.com/deploy/button.png)](https://heroku.com/deploy)

### Development

Install the requirements and run the app:

```
$ pip install -r requirements.txt
$ python server.py
```

