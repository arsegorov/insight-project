import os
import boto3
import psycopg2
import json
import yaml
import decimal
from xml.etree.ElementTree import fromstring, ParseError
import gzip
import schemas_xml

############
# AWS stuff
############
s3 = boto3.resource('s3')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

#################
# Database stuff
#################

password = os.environ.get('PGPASSWORD')
meta_db = "'meta'"
rds_db_user = "'arsegorovDB'"
rds_host = "'metainstance.cagix2mfixd1.us-east-1.rds.amazonaws.com'"

connection = psycopg2.connect(f"dbname={meta_db} "
                              f"user={rds_db_user} "
                              f"host={rds_host} "
                              f"password='{password}'")
cur = connection.cursor()

traffic_table = dynamodb.Table('TrafficSpeed')


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if abs(o) % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


def main(event, context):
    """
    This Lambda's entry point

    :param event: the event received from the s3 bucket
    :param context: the runtime environment information
    """
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    object_key = event['Records'][0]['s3']['object']['key']

    obj = s3.Object(bucket_name, object_key)

    # If the uploaded file is a schema, add it to the Postgres
    if object_key[-3:] == 'yml':
        body = obj.get()['Body']
        schema = yaml.load(body.read().decode('utf-8'))
        schemas_xml.add_schema(schema, connection)

    # If the uploaded file is the actual data
    elif object_key[-3:] == 'xml' or object_key[-2:] == 'gz':
        # Read the contents of the file
        body = obj.get()['Body'].read()

        # for gzip-compressed files, decompress first
        if object_key[-2:] == 'gz':
            body = gzip.decompress(body)
            object_key = object_key.replace('.gz', '.xml')

        try:
            xml_data = fromstring(body.decode('utf-8'))
        except ParseError:
            # Todo: replace with a log message
            print(f'Couldn\'t parse XML data from "{object_key.split(".")[0]}"')
            return

        # Find the matching schema in the Postgres
        date = next(xml_data.iter('{http://datex2.eu/schema/2/2_0}publicationTime')).text
        schema = schemas_xml.find_schema(object_key, date, connection)

        if schema is None:
            # Todo: replace with a log message
            print(f'Couldn\'t find a matching schema for '
                  f'"{object_key.split(".")[0]}"')
            return

        # Load the schema
        prefix = schema[3]['prefixes']
        data_schema = schema[3]['data']

        # Form the batch to upload to Dynamo
        data = schemas_xml \
            .extract_data(xml_data,
                          data_schema,
                          prefix,
                          lambda x: 1) \
            .popitem()[1]

        # Break the batch into reasonably sized chunks
        size = len(data)
        chunk_size = 500
        for i in range(0, size, chunk_size):
            j = min(size, i + chunk_size)
            with traffic_table.batch_writer(
                    overwrite_by_pkeys=['measurementSiteReference', 'measurementTimeDefault']
            ) as batch:
                for item in data[i:j]:
                    batch.put_item(Item=item)
