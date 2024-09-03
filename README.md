# Bot for Dawn Extension [1.3]

## 🔗 Links

🔔 CHANNEL: https://t.me/JamBitPY

💬 CHAT: https://t.me/JamBitChat

💰 DONATION EVM ADDRESS: 0xe23380ae575D990BebB3b81DB2F90Ce7eDbB6dDa

## 🤖 | Features:
- **Auto registration/login**
- **Auto-completion of all tasks**
- **Auto-farm points**


## 📝 | Description:
[FARM MODULES]

The expansion delay between keepalive requests is 120 seconds, so it is recommended to use +- the same value in CYCLE FARMING MODULE.

[CAPTCHA]

In this version, the captcha is solved using services (2captcha, anti-captcha) because the developers changed the mathematical captcha to letters, numbers and symbols. I tried to write my own solution, but alas, the result is too bad. Capsolver also solves very badly.

[DATABASE]

A database is used to save time and optimize. In this case, the script do not need to solve the captcha every time log in. (The old authorization token is used)

[EMAILS]

If you receive an error that your mail is not supported, go to the configuration and add an IMAP server for your mail domain. It is important to remember that popular services use application passwords instead of email passwords. For example, for Gmail mail, you need to enter not a password, but an application code, otherwise you will receive an error.


## ⚙️ Config (config > settings.yaml):

```
FOR REGISTRATION MODULE:
Accounts: data > register.txt | Format:
- email:password

FOR FARM, EXPORT AND TASKS MODULES:
Accounts: data > farm.txt | Format:
- email:password

Proxies: data > proxies.txt | Format:
- type://user:pass@ip:port (http/socks5)
- type://user:pass:ip:port (http/socks5)
- type://ip:port:user:pass (http/socks5)
- type://ip:port@user:pass (http/socks5)
```


| Name              | Description                                           |
|-------------------|-------------------------------------------------------|
| threads           | Number of accounts that will work simultaneously      |
| keepalive_interval             | delay between keepalive requests in seconds           |
| imap_settings             | imap servers for your mails                           |
| captcha_service             | service for solving captcha (2captcha or anticaptcha) |
| two_captcha_api_key             | 2captcha api key                                      |
| anti_captcha_api_key             | anti-captcha api key                                  |



## 🚀 | How to start:
1. **Install python >= 3.11:**
```bash
https://www.python.org/downloads/
```
2. **Clone the repository:**
```bash
git clone this repo
```
3. **Create and activate a virtual environment:**
```bash
python -m venv venv
cd venv/Scripts
activate
cd ../..
```
3. **Install dependencies:**

```bash
pip install -r requirements.txt
```
4. **Run the bot:**
```bash
python run.py
```