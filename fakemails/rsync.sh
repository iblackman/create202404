#!/bin/sh

account=$1
uid=$2
gid=$3
fakedir=$4

echo "Copying fake emails to the $account email account."
rsync -a --no-perms --chown $uid:$gid $fakedir/* "/var/mail/$account/Maildir/cur/"
echo "Copy to $account has been completed."