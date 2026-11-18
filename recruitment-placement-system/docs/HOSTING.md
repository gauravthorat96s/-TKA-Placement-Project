# Hosting on PythonAnywhere (free tier)

## 1. Create the MySQL database
Databases tab: set a MySQL password, then create the database `<username>$rpms_db`.
Host: `<username>.mysql.pythonanywhere-services.com`

## 2. Upload and install
Files tab: upload `recruitment-placement-system-hosting.zip`, unzip it.
Bash console:
```bash
cd ~/recruitment-placement-system
pip3.10 install --user -r requirements.txt
```

## 3. Create tables and demo data
```bash
export RPMS_DB_HOST=<username>.mysql.pythonanywhere-services.com
export RPMS_DB_USER=<username>
export RPMS_DB_PASSWORD='your-mysql-password'
export RPMS_DB_NAME='<username>$rpms_db'
python3.10 scripts/init_hosted.py
```

## 4. Web app
Web tab: Add a new web app, Manual configuration, Python 3.10.
Source code: `/home/<username>/recruitment-placement-system`
WSGI configuration file: replace contents with:
```python
import os, sys
sys.path.insert(0, "/home/<username>/recruitment-placement-system")
os.environ["RPMS_DB_HOST"] = "<username>.mysql.pythonanywhere-services.com"
os.environ["RPMS_DB_USER"] = "<username>"
os.environ["RPMS_DB_PASSWORD"] = "your-mysql-password"
os.environ["RPMS_DB_NAME"] = "<username>$rpms_db"
os.environ["RPMS_SECRET_KEY"] = "a-long-random-string"
from wsgi import app as application
```
Click Reload. The site is at `https://<username>.pythonanywhere.com`.

## Before going public
- Change every demo password (`Demo@123`) with the admin account.
- Use a strong `RPMS_SECRET_KEY` and a strong MySQL password.
- Do not share passwords in chat or screenshots.
