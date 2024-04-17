import uuid
import secrets
import string
import random
import datetime
import time
import os
import requests
from requests.auth import HTTPBasicAuth
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
import argparse


def generate_lmtp_id():
    runas = string.ascii_letters + string.digits + "+/"
    return ''.join(secrets.choice(runas) for _ in range(22))

def generate_b_header():
    runas = string.ascii_letters + string.digits + "+/"
    return ''.join(secrets.choice(runas) for _ in range(8))

def generate_esmtps_id():
    return str(random.randint(1000000, 9999999))

def generate_timestamp(t1, t2):
    t3 = random.uniform(t1, t2)
    return str(t3).split('.')[0]

def generate_full_date(t1):
    dc = datetime.datetime.fromtimestamp(t1)
    return dc.strftime("%a, %d %b %Y %H:%M:%S")

def generate_fake_mail_content(account_uid, t1, t2, template):
    fake_uuid = str(uuid.uuid4())
    fake_uuid_split = fake_uuid.split('-')

    message_id = fake_uuid.upper()
    esmtpsa_id = fake_uuid_split[0]
    dovecot_message_id = f"0{fake_uuid_split[0]}-0{fake_uuid_split[1]}".lower()
    lmtp_id = generate_lmtp_id()
    esmtps_id = generate_esmtps_id()
    timestamp_date = generate_timestamp(t1, t2)
    b_header = generate_b_header()
    full_date = generate_full_date(int(timestamp_date))

    content = template.replace("ENV_ACCOUNT_UID", account_uid)
    content = content.replace("ENV_DOVECOT_MESSAGE_ID", dovecot_message_id)
    content = content.replace("ENV_LMTP_ID", lmtp_id)
    content = content.replace("ENV_ESMTPS_ID", esmtps_id)
    content = content.replace("ENV_B_HEADER", b_header)
    content = content.replace("ENV_FULL_DATE", full_date)
    content = content.replace("ENV_TIMESTAMP_DATE", timestamp_date)
    content = content.replace("ENV_ESMTPSA_ID", esmtpsa_id)
    content = content.replace("ENV_MESSAGE_ID", message_id)

    return content, dovecot_message_id, int(timestamp_date)

def create_fake_mail(content, dovecot_message_id, timestamp, fake_dir):
    filename = f"{timestamp}.M655385P9377.mailstack-dovecot-server-{dovecot_message_id},S=SIZE:2,S"
    file_path = f"{fake_dir}/{filename}"

    with open(file_path, 'w') as file:
        file.write(content)

    new_filename = filename.replace("SIZE", str(os.path.getsize(file_path)))
    new_file_path = f"{fake_dir}/{new_filename}"
    os.rename(file_path, new_file_path)
    os.utime(new_file_path, (timestamp, timestamp))

def convert_total_size_to_bytes(account_size):
    match = re.match(r"(\d+)(MB|GB|TB)", account_size, re.IGNORECASE)
    if not match:
        raise ValueError("Invalid size format. Use the format such as '1GB'.")
    
    size, unit = match.groups()
    size = float(size)
    
    convert_to_bytes = {
        'MB': 1024 ** 2,
        'GB': 1024 ** 3,
        'TB': 1024 ** 4
    }
    
    b_size = size * convert_to_bytes[unit.upper()]

    return int(b_size)

def get_user_infos(account):
    try:
        data = '[["user",{"userMask":["' + account + '"]},"tag1"]]'
        headers = {
            'Content-Type': 'application/json'
        }

        doveadm_url = os.getenv("API_URL", "http://mailstack-dovecot-cluster:8080")
        doveadm_username = os.getenv("API_USERNAME", 'doveadm')
        doveadm_password = os.getenv("API_PASSWORD")
        url = f"{doveadm_url}/doveadm/v1"

        response = requests.post(url, data=data, headers=headers, auth=HTTPBasicAuth(doveadm_username, doveadm_password), timeout=10)

        if response.status_code == 200:
            respj = json.loads(response.text)
            uid = respj[0][1][account]['uid']
            gid = respj[0][1][account]['gid']

            return uid, gid
        elif response.status_code == 401:
            raise ValueError("Username or password is invalid")
        elif response.status_code == 403:
            raise ValueError("User does not have permission to access this resource")
        else:
            respj = json.loads(response.text)
            raise ValueError(f"Type: {respj[0][1]['type']}, Code: {doveadm_failure_codes(respj[0][1]['code'])}")
    except requests.exceptions.HTTPError as errh:
        raise Exception(errh)
    except requests.exceptions.ConnectionError as errc:
        raise Exception(errc)
    except requests.exceptions.Timeout as errt:
        raise Exception(errt)
    except requests.exceptions.RequestException as err:
        raise Exception(err)
    except Exception:
        raise
    
def doveadm_failure_codes(code):
    if code == 2:
        return "Success but mailbox changed during operation"
    elif code == 64:
        return "Invalid parameters"
    elif code == 65:
        return "Data error"
    elif code == 67:
        return "User does not exist"
    elif code == 68:
        return "User does not have session"
    elif code == 73:
        return "User quota is full"
    elif code == 75:
        return "Temporary error"
    elif code == 77:
        return "No permission"
    elif code == 78:
        return "Invalid configuration"
    else:
        return code
    
def copy_fake_tempates(account, fake_dir):
    try:
        if os.path.exists(f"/var/mail/{account}/Maildir/cur") == True:
            uid, gid = get_user_infos(account)
            subprocess.run(["/bin/bash", "./rsync.sh", account, uid, gid, fake_dir])
        else:
            print(f"Default folder for {account} does not exists")
    except Exception as e:
        print(f"Failed to retrieve account information for {account}: {e}")

def exec_copy(accounts, fake_dir):
    num_processes = 5

    with ThreadPoolExecutor(max_workers=num_processes) as executor:
        futures = [executor.submit(copy_fake_tempates, account, fake_dir) for account in accounts]
        
        for future in futures:
            future.result()

if __name__ == '__main__':
    tdates = [1609459200, 1640995200, 1672531200, 1704067200, round(time.time())]
    templates = {}
    files_size = 0
    accounts = []

    parser = argparse.ArgumentParser()
    parser.add_argument('--accountsfile', type=str, help='List of users accounts', default=f'{os.getcwd()}/accounts')
    parser.add_argument('--templatedir', type=str, help='Template directory', default=f'{os.getcwd()}/mail-templates')
    parser.add_argument('--fakedir', type=str, help='Destination directory for fake emails', default=f'{os.getcwd()}/fake-mails')
    args = parser.parse_args()

    if os.path.exists(args.fakedir) == False:
        os.mkdir(args.fakedir)

    if os.path.isfile(args.accountsfile) == True:
        with open(args.accountsfile, 'r') as f:
            accounts = [line.strip() for line in f.readlines() if line.strip()]
    else:
        print(f"File {args.accountsfile} does not exists")
        os._exit(1)

    for dirpath, _, filenames in os.walk(args.templatedir):
        for file in filenames:
            with open(f"{args.templatedir}/{file}", 'r') as f:
                templates[file] = f.read()
                files_size += len(templates[file])

    total_size = input("What is the total size that you would like to generate for each account? You can use MB, GB or TB : ")
    bsize = convert_total_size_to_bytes(total_size)

    if bsize < 31457280:
        print("Total size needs to be greater than 30MB.")
        os._exit(1)

    total_files = round(bsize / files_size)
    total_iterations = round(total_files / 4)
    print(f"The script will generate {total_iterations * 4} files for each template based on {total_size} of fake emails for each user on the list. Emails will be generated from the beginning of the year 2021 up to the present moment.")
    
    for key, value in templates.items():
        for i, t in enumerate(tdates[0:4]):
            for z in range(total_iterations):
                content, dovecot_message_id, timestamp = generate_fake_mail_content("admin", t, tdates[i+1: i+2][0], value)
                create_fake_mail(content, dovecot_message_id, timestamp, args.fakedir)

    exec_copy(accounts, args.fakedir)

