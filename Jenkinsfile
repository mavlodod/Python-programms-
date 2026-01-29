pipeline {
  agent any
  
  environment {
    SERVER = "10.200.101.50"
    USER   = "mavlodod"
    DIR    = "/home/mavlodod/Birthday/Python-programms-"
    SSH_ID = "mavlodod-ssh-key"
    
    # Порт для теста на Jenkins
    TEST_PORT = "8081"
    # Порт для продакшна
    PROD_PORT = "8080"
  }
  
  stages {
    stage('Test Build') {
      steps {
        script {
          // Читаем оригинальный docker-compose.yml
          def composeContent = readFile('docker-compose.yml')
          
          // Меняем порт для теста
          def testCompose = composeContent.replace("8080:5000", "${TEST_PORT}:5000")
          
          // Записываем временный файл
          writeFile(file: 'docker-compose.test.yml', text: testCompose)
          
          // Тестируем
          sh """
            docker compose -f docker-compose.test.yml build
            docker compose -f docker-compose.test.yml up -d
            sleep 5
            docker compose -f docker-compose.test.yml ps
            docker compose -f docker-compose.test.yml down
          """
        }
      }
    }
    
    stage('Deploy') {
      steps {
        sshagent([SSH_ID]) {
          sh """
            ssh ${USER}@${SERVER} "
              cd ${DIR}
              git pull
              docker compose down
              docker compose up -d --build
              echo '✅ Application deployed on port ${PROD_PORT}'
            "
          """
        }
      }
    }
  }
  
  post {
    always {
      sh '''
        rm -f docker-compose.test.yml 2>/dev/null || true
        docker system prune -f 2>/dev/null || true
      '''
    }
  }
}
