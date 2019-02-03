pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                sh '''
                    echo "upload Lambda function"
                    ./upload-lambda-xml.sh
                '''
            }
        }
        stage('Test') {
            steps {
                sh 'echo "run integration test"'
                sh '''
                    git --version
                    source ~/.aws/env_var
                    echo ${AWS_S3_BUCKET}
                    echo ${AWS_PG_DB_HOST}
                    echo "activate py3"
                    source ~/py36/bin/activate
                    which python3
                    which pytest
                    echo "run pytest"
                    cd src/lambda_xml
                    pytest -q test_lambda_function_xml.py
                '''
            }
        }
    }
    post {
        success {
            echo 'This build is successful'
            mail bcc: 'wen.g.gong@gmail.com', body: "<b>Build OK</b><br>: ${env.JOB_NAME} <br>Build Number: ${env.BUILD_NUMBER} <br> build URL : ${env.BUILD_URL}", cc: '', charset: 'UTF-8', from: '', mimeType: 'text/html', replyTo: '', subject: "OK CI: Project name -> ${env.JOB_NAME}", to: "wen.gong@oracle.com";
        }
        failure {
            echo 'revert to prior commit'
            which git
            echo 'This build failed, alert by email ...'
            mail bcc: 'wen.g.gong@gmail.com', body: "<b>Build Failed</b><br>: ${env.JOB_NAME} <br>Build Number: ${env.BUILD_NUMBER} <br> build URL : ${env.BUILD_URL}", cc: '', charset: 'UTF-8', from: '', mimeType: 'text/html', replyTo: '', subject: "ERROR CI: Project name -> ${env.JOB_NAME}", to: "wen.gong@oracle.com";
        }
    }
}

