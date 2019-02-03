steps to run this project

1) upload-lambda-xml.sh : 
	upload lambda function
2) src/dash/app.py : 
	Dash/Flask file
3) src/retrieve-realtime-data.sh :
	download Traffic data everytime, run from commandline
	* change infinite loop to have an end-date (e.g. 2019-04-01)

devopsgong@osboxes:~
$ ssh -i "~/.ssh/wen-IAM-keypair.pem" ec2-user@ec2-52-3-227-246.compute-1.amazonaws.com
$ cd /var/lib/jenkins/workspace/insight-project_master/src

4) add a new table to track transaction and support integration test
    CREATE TABLE xml_txns (
        id              SERIAL PRIMARY KEY,
        filename        varchar(100) NOT NULL,
        begin_datetime  timestamp,
        end_datetime    timestamp,
        num_locations   int default 0,
        status  SMALLINT  default 2  /* 0 - success, 1 - failed, 2 - processing */
    );

select * from xml_txns order by begin_datetime desc;

insert into xml_txn(filename,begin_datetime) values ('Traffic/2019-01-28/1839_Trafficspeed.gz', '2019-01-28 17:44:19');

5) Lambda settings
Timeout=15 mins (max)
Memory = 3GB

Lambda testing Steps:
============================
setup Lambda
https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions/preprocess_xml?tab=graph

use IAM to grant resource permission to Lambda
https://console.aws.amazon.com/iam/home?region=us-east-1#/roles/lambda_basic_execution

use CloudWatch to view Lambda log for each test
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logStream:group=/aws/lambda/preprocess_xml;streamFilter=typeLogStreamPrefix

use S3 to monitor file upload (as Lambda trigger)
https://us-east-1.console.aws.amazon.com/s3/buckets/wengong/Traffic/2019-01-27/?region=us-east-1&tab=overview#

use SQL Workbench to view schema and log activities
	select * from xml_schemas;  /* check schema */
	select * from xml_log;   /* monitor job */
	select * from xml_log 
        where date_time_utc > timestamp '2019-01-27 10:00:00' 
        order by date_time_utc desc;


use AWS DynamoDB console to view Traffic data
https://console.aws.amazon.com/dynamodb/home?region=us-east-1#tables:selected=TrafficSpeed;tab=items


run Dash 
devopsgong@osboxes:~/GitHub/insight-project/src/dash
$ python3 app.py
Running on http://0.0.0.0:5000/

Test case 1: upload schema - Traffic.yml
devopsgong@osboxes:~/GitHub/insight-project/test$ aws s3 cp Traffic.yml s3://wengong/Traffic/test/Traffic.yml

Test case 2: upload data - Traffic.yml
devopsgong@osboxes:~/GitHub/insight-project/test$ aws s3 cp sample_Trafficspeed.xml s3://wengong/Traffic/test/Trafficspeed.xml




Lambda testing issues:
============================

1) 
not authorized to perform: dynamodb
https://stackoverflow.com/questions/34784804/aws-dynamodb-issue-user-is-not-authorized-to-perform-dynamodbputitem-on-resou


2)
{"2019-01-27 06:36:35.759564: Requesting file `Traffic/test/Traffic.yml` from S3","2019-01-27 06:36:36.008564: Error while retrieving `Traffic/test/Traffic.yml`: AccessDenied"}
https://stackoverflow.com/questions/35589641/aws-lambda-function-getting-access-denied-when-getobject-from-s3


3) 
not authorized to perform: dynamodb:BatchWriteItem on resource
https://stackoverflow.com/questions/34784804/aws-dynamodb-issue-user-is-not-authorized-to-perform-dynamodbputitem-on-resou

revise policy for lambda_basic_execution role
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject"
            ],
            "Resource": "arn:aws:s3:::*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:DescribeTable",
                "dynamodb:GetItem",
                "dynamodb:PutItem"            ],
            "Resource": "arn:aws:dynamodb:::*"
        }
    ]
}

An error occurred (AccessDeniedException) when calling the BatchWriteItem operation: User: arn:aws:sts::629309645488:assumed-role/lambda_basic_execution/preprocess_xml is not authorized to perform: dynamodb:BatchWriteItem on resource: arn:aws:dynamodb:us-east-1:629309645488:table/TrafficSpeed: ClientError

        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:DescribeTable",
                "dynamodb:BatchWriteItem",
                "dynamodb:GetItem",
                "dynamodb:PutItem"            ],
            "Resource": "arn:aws:dynamodb:us-east-1:629309645488:table/TrafficSpeed"
        }


4)
REPORT RequestId: 978fd8e8-bb6f-46b7-af24-54ef01f7efbd	Duration: 8398.55 ms	Billed Duration: 8400 ms Memory Size: 128 MB	Max Memory Used: 128 MB	

go to Lambda > Configure > Basic settings
increase Max Memory to 3 GB, Save

5) 
An error occurred (ProvisionedThroughputExceededException) when calling the BatchWriteItem operation (reached max retries: 9): The level of configured provisioned throughput for the table was exceeded. Consider increasing your provisioning level with the UpdateTable API.: ProvisionedThroughputExceededException


6) 
getting python3 to work in jenkins
https://stackoverflow.com/questions/45986494/getting-python3-to-work-in-jenkins

https://issues.jenkins-ci.org/browse/JENKINS-29007
Does Jenkins support Python3


https://www.stratoscale.com/blog/devops/using-jenkins-build-deploy-python-web-applications-part-2/

build integration test case, and run it manually successfully


build integration test case, and run it manually successfully

test #2 

test #10:
    recreate table xml_txns
    $ git add .; git commit -m "recreate xml_txns"; git push









## install on devopsgong@osboxes (locally)
devopsgong@osboxes:~$ python --version
Python 3.6.5 :: Anaconda, Inc.


## install on EC2 instance
ssh to jenkins instance
$ ssh -i "~/.ssh/wen-IAM-keypair.pem" ec2-user@ec2-52-3-227-246.compute-1.amazonaws.com



install python 3.6 on Amazon Linux
https://gist.github.com/niranjv/f80fc1f488afc49845e2ff3d5df7f83b

$ python --version
Python 2.7.15

$ pip --version
pip 9.0.3 from /usr/lib/python2.7/dist-packages (python 2.7)



##########################
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

##########################

2019-01-30:
finally have a working build script running by Jenkins

2019-02-02:
https://stackoverflow.com/questions/8588768/how-do-i-avoid-the-specification-of-the-username-and-password-at-every-git-push

how to cache auth with git

```
    $ git config credential.helper store
    $ git push git+ssh://git@github.com/wgong/insight-project.git HEAD:master
```

push from my own account
