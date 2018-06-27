#! /usr/bin/env bash
declare path=src/lambda_xml

# Save the untimestamped version
cp ${path}/lambda_function_xml.py ${path}/lambda_function_xml.py~

# Apply a timestamp to the lambda's main file 
sed "1s/^/# Uploaded on $(date)\n\n/" ${path}/lambda_function_xml.py > ${path}/tmp
mv ${path}/tmp ${path}/lambda_function_xml.py

# Create a .zip file from the sources
zip -r ${path}/package.zip ${path}/*.py ${path}/psycopg2/ ${path}/yaml/

# Remove the timestamped version
mv ${path}/lambda_function_xml.py~ ${path}/lambda_function_xml.py

# Upload the updated function to the cloud
aws lambda update-function-code --function-name preprocess_xml --zip-file fileb://./${path}/package.zip --publish
