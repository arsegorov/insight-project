#!/usr/bin/env bash
declare tmpfile=trafficspeed-tmp
# declare s3bucket=arsegorov-raw
declare s3bucket=wengong

minute=
old_minute=

while true
do
    # current minute and second
    minute=$(date +%M)
    sec=$(date +%S)

    # traffic data is published on the 42nd second after the minute

    # see if it's past the 45th second, and
    # that it's the first check during this minute
    if [ "${sec}" -gt 45 -a "${minute}" != "${old_minute}" ]
    then
        # getting the current date and time in the Netherlands
        d=$(TZ=Europe/Amsterdam date +%Y-%m-%d)
        t=$(TZ=Europe/Amsterdam date +%H%M)

        # retrieving the real-time-data file
        wget -O ${tmpfile} http://opendata.ndw.nu/trafficspeed.xml.gz

        # saving to the S3 bucket
        aws s3 cp ${tmpfile} s3://${s3bucket}/Traffic/${d}/${t}_Trafficspeed.gz

        # saving the last check's minute
        old_minute=${minute}
    fi
    sleep 5
done