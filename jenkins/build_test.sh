#!/bin/bash

whoami
# jenkins
# reset pwd and su - jenkins to install python3 and pytest

pwd
#/var/lib/jenkins/workspace/data-freeway

hostname
# ip-10-0-1-188

date

source ~/.aws/env_var
# define AWS env vars: db_name,db_host,db_user,db_pass

echo ${AWS_S3_BUCKET}
echo ${AWS_PG_DB_HOST}

source /var/lib/jenkins/py36/bin/activate
# /home/ec2-user/py3/py36/bin/activate: Permission
# create virtualenv for jenkins user

which python3
which pytest

cd src/lambda_xml

# python3 main_lambda_xml.py

pytest -q test_lambda_function_xml.py
# run pytest
