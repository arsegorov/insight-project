#! /usr/bin/env bash
cd src/lambda_xml

# Save the untimestamped version
cp lambda_function_xml.py lambda_function_xml.py~

# Apply a timestamp to the lambda's main file
sed "1s/^/# Uploaded on $(date)\n\n/" lambda_function_xml.py > tmp
mv tmp lambda_function_xml.py

# Create a .zip file from the sources
zip -r package.zip *.py psycopg2/ yaml/

# Remove the timestamped version
mv lambda_function_xml.py~ lambda_function_xml.py

# Upload the updated function to the cloud
aws lambda update-function-code --function-name preprocess_xml --zip-file fileb://./package.zip --publish
