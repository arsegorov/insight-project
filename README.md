# Data Freeway
_Making traffic data clean and accessible_



## Motivation

I've been interested in services that would process
vast amounts of sensor-recorded data, to provide customers with various insights.
To be able to provide such services, quick access to historical and real-time data is necessary.

In this project I was aming to create a system that could reliably
ingest, clean, and validate large amounts of sensor data, store the
preprocessed data in highly-available low-latency location, and provide
monitoring for this pipeline.


## Data

![sensorsMap]

The Netherlands have a
[network of sensors](http://www.ndw.nu/)
across the entire country,
with over 100K sensors reporting every minute.
One can [request historical data](http://83.247.110.3/OpenDataHistorie/) as far back as 2011,
as well as download [various real-time data](http://opendata.ndw.nu/) that is updated every minute.

However, historical data are somewhat difficult to acquire,
primarily because of a limited system throughput.

* Data for all the sensors is packaged together
* Minimum time period is 1 hour and maximum is about 1 week
* The request might take hours to days to complete before the data can be downloaded


## Challenges

Currently, the data are stored as XML files. The format has several shortcomings:
* It could take about 400 bytes to store just 1 sensor reading.
Selecting a less verbose format would
save on storage costs and
improve further processing speeds.
```xml
<!--Linebreaks and indents added for readability-->
<ns1:siteMeasurements>
    <ns1:measurementSiteReference id="PZH01_MST_0690_00" targetClass="MeasurementSiteRecord"
                                  version="1"/>
    <ns1:measurementTimeDefault>2017-12-31T22:59:00Z</ns1:measurementTimeDefault>
    <ns1:measuredValue index="1">
        <ns1:measuredValue>
            <ns1:basicData xsi:type="TrafficFlow">
                <ns1:vehicleFlow>
                    <ns1:vehicleFlowRate>60</ns1:vehicleFlowRate>
                </ns1:vehicleFlow>
            </ns1:basicData>
        </ns1:measuredValue>
    </ns1:measuredValue>
</ns1:siteMeasurements>
```
* The XML schema has changed multiple times over the years.
Finding a way to translate different schemas into a single one would
simplify future queries.


## Solving the Challenges

I decided to translate data from XML into JSON format,
while also removing the nodes that I didn't need.

To describe which information to extract, I used YAML, which I think is
reasonably easy to learn and is both machine- and human-readable.

```yaml
meta:
  files: '%Trafficspeed.xml'   # The filename pattern that is used for lookups in PostgreSQL
  version: '2018-06-26T23:13:00Z'
# ... More meta data ...
processing:
  data:
    ns1.siteMeasurements[]:
      #                           getter  type       key name
      ns1.measurementSiteReference: _.id, str,       measurementSiteReference
      ns1.measurementTimeDefault:   text, timestamp, measurementTimeDefault
      #
      ns1.measuredValue[]:     # Lists are used for alternatives
      - _: '.[@index]'         # An underscore refers to the parent node
        _.index: int, Channel  # E.g., `_.index` refers to the `index` attribute of the parent
        ns1.basicData:
        - _: '.[@xsi:type="TrafficFlow"]'
          _.xsi.type: text, Type
          ns1.vehicleFlowRate: text, float, Flow
        - _: '.[@xsi:type="TrafficSpeed"]'
          _.xsi.type: text, Type
          ns1.averageVehicleSpeed:
            _.numberOfInputValuesUsed: int, InputSize
            ns1.speed: text, float, Speed
```

In a schema description file, the YAML's nesting structure describes XML node nesting.
However, the YAML only lists the tags that are needed and specifies XPATH filters
so only some of the nodes could be selected.

For each XML tag, I specified its value's expected type and
what key to output to in the resulting JSON (if different from the tag itself).

Also, since the XML schema evolved, some fields have migrated
from node contents to attribute values.
To account for that, I had to specify how to access the value.
* For node contents, ``text`` is used
* For attribute values, ``_.<attrib_name>`` is used


## The Pipeline

Input files are put into an S3 bucket from where
they are ingested into a Lambda function.

![pipeline]

Depending on the file type, Lambda will do different things.

* If receiving a YAML file, the Lambda will just save
  the schema from it to Postgres
* If receiving an XML data file, the Lambda will:
  * Based on the data's publication time,
    look up the appropriate schema in Postgres
  * Extract data according to schema
  * Put extracted records into DynamoDB
  * Log progress updates and errors to Postgres

A frontend running on Flask displays which files have been processed for a given date.



[sensorsMap]: images/map_small.png
[pipeline]: images/DE-lambda.png

## Demo

test 21
test 22
test 23
