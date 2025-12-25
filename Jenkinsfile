pipeline {
    agent any

    environment {
        IMAGE_NAME = "python-app"
        IMAGE_TAG  = "latest"
    }

    stages {
        stage('Build') {
            steps {
                sh 'docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .'
            }
        }

        stage('Smoke test') {
            steps {
                sh '''
                  docker run -d -p 5000:5000 --name test_app ${IMAGE_NAME}:${IMAGE_TAG}
                  sleep 5
                  docker ps | grep test_app
                  docker stop test_app
                '''
            }
        }
    }
}
