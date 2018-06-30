#!/usr/bin/env bash
declare file=trafficspeed-tmp

min=
old_min=

while true; do
    # current minutes and seconds
    min=$(date +%M)
    s=$(date +%S)

    # traffic data is published on the 42nd second after the minute

    # see if it's past the 45th second, and
    # that it's the first check during this minute
    if [ "${s}" -gt 45 -a "${min}" != "${old_min}" ]; then
        wget -O ${file} http://opendata.ndw.nu/trafficspeed.xml.gz

        # using the previous minute, and adding 6 hours to adjust for the time difference
        t=$(TZ=Europe/Amsterdam date +%H%M)
        d=$(TZ=Europe/Amsterdam date +%Y-%m-%d)

        aws s3 cp ${file} s3://arsegorov-raw/Traffic/${d}/${t}_Trafficspeed.gz

        # keeping track of the previous check's minute
        old_min=${min}
    fi
    sleep 10
done