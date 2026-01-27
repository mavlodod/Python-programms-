pipeline {
  agent any

  environment {
    REMOTE_HOST    = "10.200.101.50"
    REMOTE_USER    = "mavlodod"
    REMOTE_DIR     = "/home/mavlodod/Birthday/Python-programms-"

    IMAGE_NAME     = "birthday-app"
    IMAGE_TAG      = "latest"

    CONTAINER_NAME = "birthday_app_container"
    HOST_PORT      = "5000"
    APP_PORT       = "5000"

    SSH_CRED_ID    = "mavlodod-ssh-key"
  }

  stages {
    stage('Build (Jenkins)') {
      steps {
        sh 'docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .'
      }
    }

    stage('Smoke test (Jenkins)') {
      steps {
        sh '''
          docker rm -f test_app >/dev/null 2>&1 || true
          docker run -d -p 5000:5000 --name test_app ${IMAGE_NAME}:${IMAGE_TAG}
          sleep 5
          docker ps | grep test_app
          docker stop test_app
          docker rm test_app
        '''
      }
    }

    stage('Deploy to 10.200.101.50') {
      steps {
        sshagent(credentials: ["${SSH_CRED_ID}"]) {
          sh '''
            set -e

            ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} "
              set -e

              cd ${REMOTE_DIR}

              echo '==> Git pull'
              git pull

              echo '==> Build image on remote'
              docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

              echo '==> Restart container'
              docker rm -f ${CONTAINER_NAME} >/dev/null 2>&1 || true

              docker run -d --restart unless-stopped \
                -p ${HOST_PORT}:${APP_PORT} \
                --name ${CONTAINER_NAME} \
                -v ${REMOTE_DIR}/employees.db:/app/employees.db \
                -v ${REMOTE_DIR}/notification_history.json:/app/notification_history.json \
                ${IMAGE_NAME}:${IMAGE_TAG}

              echo '==> Container status'
              docker ps | grep ${CONTAINER_NAME}
            "
          '''
        }
      }
    }
  }
}
