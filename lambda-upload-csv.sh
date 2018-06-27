#! /usr/bin/env bash
declare path=src/lambda_csv

# Save the untimestamped version
cp ${path}/lambda_function.py ${path}/lambda_function.py~

# Apply a timestamp to the lambda's main file 
sed "1s/^/# Uploaded on $(date)\n\n/" ${path}/lambda_function.py > ${path}/tmp
mv ${path}/tmp ${path}/lambda_function.py

# Create a .zip file from the sources
zip -r ${path}/package.zip ${path}/*.py ${path}/psycopg2/

# Remove the timestamped version
mv ${path}/lambda_function.py~ ${path}/lambda_function.py

# Upload the updated function to the cloud
aws lambda update-function-code --function-name preprocess --zip-file fileb://./${path}/package.zip --publish

