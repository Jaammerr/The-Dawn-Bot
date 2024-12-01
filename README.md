# 🌅 Dawn Extension Bot [v1.6]

<div align="center">
  <img src="./console/images/console.png" alt="Dawn Extension Bot Console" width="600"/>
  
  <p align="center">
    <a href="https://t.me/JamBitPY">
      <img src="https://img.shields.io/badge/Telegram-Channel-blue?style=for-the-badge&logo=telegram" alt="Telegram Channel">
    </a>
    <a href="https://t.me/JamBitChat">
      <img src="https://img.shields.io/badge/Telegram-Chat-blue?style=for-the-badge&logo=telegram" alt="Telegram Chat">
    </a>
  </p>
</div>

## 📋 Table of Contents
- [Features](#-features)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Configuration](#%EF%B8%8F-configuration)
- [Usage](#-usage)
- [Troubleshooting](#-troubleshooting)

## 🚀 Features

- ✨ **Account Management**
  - ✅ Automatic account registration and login
  - 📧 Smart account reverification system
  - 🛡️ Token-based authentication storage
  
- 🤖 **Automation**
  - 🌾 Intelligent task completion
  - 💰 Optimized point farming
  - 🔄 Advanced keepalive system
  
- 📊 **Analytics & Export**
  - 📈 Comprehensive account statistics
  - 📉 Banned account tracking
  - 📋 Unverified account monitoring
  
- 🔒 **Security**
  - 🧩 Advanced captcha solving integration
  - 🌐 Proxy support (HTTP/SOCKS5)
  - 🔐 Secure email integration

## 💻 Requirements

- Python 3.11 or higher
- Stable internet connection
- Valid email accounts
- Working proxies (HTTP/SOCKS5)
- Captcha service subscription (2captcha/anticaptcha)

## 🛠️ Installation

1. **Clone the Repository**
   ```bash
   git clone [repository URL]
   ```

2. **Set Up Virtual Environment**
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # Windows
   source venv/bin/activate      # Unix/MacOS
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## ⚙️ Configuration

### 📁 settings.yaml

```yaml
# Core Configuration
threads: 30                    # Concurrent operation threads (min: 1)
keepalive_interval: 120        # Keepalive signal interval (seconds)
referral_codes:               # Multiple referral code support
  - ""                        # Add your codes here

# Mail Redirect Settings
redirect_settings:
  enabled: false              # Enable/disable mail redirection
  email: "test@gmail.com"     # Redirect email address
  password: "password"        # Email password
  imap_server: "imap.gmail.com"
  use_proxy: true            # Use proxy for email operations

# Captcha Configuration
captcha_module: 2captcha      # Select: '2captcha' or 'anticaptcha'
two_captcha_api_key: ""       # 2captcha API key
anti_captcha_api_key: ""      # Anticaptcha API key

# Startup Settings
delay_before_start:
  min: 2                      # Minimum startup delay (seconds)
  max: 3                      # Maximum startup delay (seconds)

# Email Provider Settings
imap_settings:
  # Global Providers
  gmail.com: imap.gmail.com
  yahoo.com: imap.mail.yahoo.com
  outlook.com: imap-mail.outlook.com
  hotmail.com: imap-mail.outlook.com
  icloud.com: imap.mail.me.com
  
  # Regional Providers
  mail.ru: imap.mail.ru
  rambler.ru: imap.rambler.ru
  gmx.com: imap.gmx.com
  onet.pl: imap.poczta.onet.pl
```

### 📁 Input Files Structure

#### accounts/register.txt
```
email:password
email:password
```

#### accounts/farm.txt
```
email:password
email:password
```

#### accounts/reverify.txt
```
email:password
email:password
```

#### proxies/proxies.txt
```
http://user:pass@ip:port
http://ip:port:user:pass
socks5://user:pass@ip:port
```

## 🚀 Usage

1. Configure all necessary files as described above
2. Start the bot:
   ```bash
   python run.py
   ```

## ⚠️ Important Notes

- 🕒 Recommended keepalive interval: 120 seconds
- 📧 Gmail users: Use App-Specific Passwords
- 🔄 Unverified accounts can be reverified using the register module
- 💾 Authorization tokens are stored in local database
- 🤖 External captcha services required (2captcha/anticaptcha)

## 🔧 Troubleshooting

### Common Issues and Solutions

#### 📧 Email Verification Failed
- Verify IMAP settings in settings.yaml
- Check email provider's security settings
- Ensure app-specific password for Gmail

#### 🧩 Captcha Problems
- Verify API key validity
- Check service balance
- Ensure selected service is operational

#### 🌐 Proxy Issues
- Validate proxy format
- Check proxy functionality
- Ensure proxy authentication is correct

## 📞 Support

Join our Telegram community for support:
- 📢 Channel: [JamBitPY](https://t.me/JamBitPY)
- 💬 Chat: [JamBitChat](https://t.me/JamBitChat)