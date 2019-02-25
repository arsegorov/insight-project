# coding: utf-8
BREAK_BUILD=False



import os
import psycopg2
import subprocess


# query xml_txns table for status
def get_txn_status(connection, s3_filename, poll_freq, poll_timeout):
    import time
    status = 2  # assume status in processing
    cur = connection.cursor()
    sql_statement = f"select id,status,msg from xml_txns where filename='{s3_filename}' order by status limit 1;"
    for i in range(int(poll_timeout/poll_freq)):
        cur.execute(sql_statement)
        rows = cur.fetchall()
        if len(rows):
            id_txn, status, msg = rows[0][0], rows[0][1], rows[0][2]
            if status == 0 or status == 1: 
                break
        time.sleep(poll_freq)

    if status == 0:
        ret_msg = "Success"
    elif status == 1:
        ret_msg = "Failed"
    else:
        status = 1
        ret_msg = "Timeout"

    # beyond timeout to check Lambda if fired on test-event
    cur.execute(sql_statement)
    rows = cur.fetchall()
    if len(rows) == 0:
        status, ret_msg = 1, "Lambda error"
    
    cur.close()
           
    return status, ret_msg

def lambda_xml():


    # config
    poll_freq = 10  # 10 sec
    poll_timeout = 1*60     # 1 min

    s3bucket = os.environ.get('AWS_S3_BUCKET')
    db_host = os.environ.get('AWS_PG_DB_HOST')
    db_name = os.environ.get('AWS_PG_DB_NAME')
    db_user = os.environ.get('AWS_PG_DB_USER')
    password = os.environ.get('AWS_PG_DB_PASS')

    db_connection_string = f"dbname='{db_name}' user='{db_user}' host='{db_host}' password='{password}'"
    connection = psycopg2.connect(db_connection_string)

    # download traffic data
    tmpfile="/tmp/trafficspeed.xml.gz"
    cmd = f"wget -O {tmpfile} http://opendata.ndw.nu/trafficspeed.xml.gz"
    wget=subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')

    cmd = f"env TZ=Europe/Amsterdam date +%Y-%m-%d:%H%M"
    dt=subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')

    s3_filename = f"Traffic/{dt[:10]}/{dt[11:15]}_Trafficspeed.gz"
    cmd = f"aws s3 cp {tmpfile} s3://{s3bucket}/{s3_filename}"
    aws_s3_cp=subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')

    cd,msg = get_txn_status(connection, s3_filename, poll_freq, poll_timeout)
    connection.close()

    return cd,msg

def test_lambda_xml():
    status_cd, status_msg = lambda_xml()
    print(status_cd, status_msg)

    if BREAK_BUILD and status_cd != 0:
        cmd = f"git revert HEAD --no-edit"
        git_revert=subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')

        cmd = f"git push origin HEAD:master"
        git_revert=subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode('utf-8')

    assert status_cd == 0
