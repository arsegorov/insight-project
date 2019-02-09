#!/usr/bin/env bash

num_loop=1
max_loop=200


declare tmpfile=/tmp/trafficspeed.xml.gz
# declare s3bucket=arsegorov-raw
# declare s3bucket=wengong

if [[ -z "${AWS_S3_BUCKET}" ]]; then
  echo "AWS_S3_BUCKET env var undefined"
  exit
else
  s3bucket=${AWS_S3_BUCKET}
fi



# set an end-date (do not run infinite loop)
if [[ -z "${AWS_S3_BUCKET}" ]]; then
  echo "AWS_S3_BUCKET env var undefined"
  exit
else
  s3bucket=${AWS_S3_BUCKET}
fi

if [[ -z "${INSIGHT_END_DATE}" ]]; then
  insight_end_date="2019-04-30"
else
  insight_end_date=${INSIGHT_END_DATE}
fi

d=$(TZ=Europe/Amsterdam date +%Y-%m-%d)

: <<'END_COMMENT'
echo "today=${d}"
echo "insight_end_date=${INSIGHT_END_DATE}"
if [[ "${d}" < "${insight_end_date}" ]]
then
    echo "within ${insight_end_date}"
fi
exit
END_COMMENT


minute=
old_minute=

while [[ "${d}" < "${insight_end_date}" ]]
do

    if [ $num_loop -gt $max_loop ]
    then
      break
    fi

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
        echo "${d} ${t}"

        # retrieving the real-time-data file
        wget -q -O ${tmpfile} http://opendata.ndw.nu/trafficspeed.xml.gz

        # local test
        # cp ${tmpfile} ${d}_${t}_Trafficspeed.gz

        # saving to the S3 bucket
        aws s3 cp ${tmpfile} s3://${s3bucket}/Traffic/${d}/${t}_Trafficspeed.gz

        ## rm -f ${tmpfile}

        # saving the last check's minute
        old_minute=${minute}

        let num_loop=num_loop+1

    fi


    sleep 5
done
