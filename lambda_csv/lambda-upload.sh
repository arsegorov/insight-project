#! /usr/bin/env bash
# Save the untimestamped version
cp lambda_function.py lambda_function.py~

# Apply a timestamp to the lambda's main file 
sed "1s/^/# Uploaded on $(date)\n\n/" lambda_function.py > tmp
mv tmp lambda_function.py

# Create a .zip file from the sources
zip -r package.zip *.py psycopg2/

# Remove the timestamped version
mv lambda_function.py~ lambda_function.py

# Upload the updated function to the cloud
aws lambda update-function-code --function-name preprocess --zip-file fileb://./package.zip --publish

