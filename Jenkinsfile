pipeline {
  agent any
  
  environment {
    SERVER = "10.200.101.50"
    USER   = "mavlodod"
    DIR    = "/home/mavlodod/Birthday/Python-programms-"
    SSH_ID = "mavlodod-ssh-key"
  }
  
  stages {
    stage('Test Build on Jenkins') {
      steps {
        sh '''
          echo "=== Testing Docker Compose build ==="
          
          # Собираем образы
          docker compose build --no-cache
          
          # Запускаем на 5 секунд для теста
          docker compose up -d
          sleep 5
          
          # Проверяем что контейнеры запустились
          echo "📊 Container status:"
          docker compose ps
          
          # Проверяем что есть хотя бы один запущенный контейнер
          if docker compose ps | grep -q "Up"; then
            echo "✅ Smoke test passed - containers are running"
          else
            echo "❌ Smoke test failed - containers not running"
            docker compose logs
            exit 1
          fi
          
          # Останавливаем тестовые контейнеры
          echo "🛑 Stopping test containers..."
          docker compose down
        '''
      }
    }
    
    stage('Deploy to Production Server') {
      steps {
        sshagent([SSH_ID]) {
          sh """
            echo "🚀 Deploying to production server..."
            
            ssh -o StrictHostKeyChecking=no ${USER}@${SERVER} "
              set -e
              cd ${DIR}
              
              echo '1. Pulling latest code from GitHub...'
              git pull origin main
              
              echo '2. Stopping existing containers...'
              docker compose down 2>/dev/null || true
              
              echo '3. Building new images...'
              docker compose build --no-cache
              
              echo '4. Starting services...'
              docker compose up -d
              
              echo '5. Waiting for startup...'
              sleep 10
              
              echo '6. Checking status...'
              docker compose ps
              
              echo '🎉 Deployment completed successfully!'
              echo ''
              echo '=== Application Information ==='
              echo '🌐 Web Interface: http://${SERVER}:8080'
              echo '🔑 Admin login: admin / admin123'
              echo ''
              echo '=== Useful Commands ==='
              echo 'View logs:    docker compose logs -f'
              echo 'Restart:      docker compose restart'
              echo 'Stop:         docker compose down'
              echo 'Update:       git pull && docker compose up -d --build'
            "
          """
        }
      }
    }
  }
  
  post {
    always {
      sh '''
        echo "🧹 Cleaning up Jenkins workspace..."
        docker compose down 2>/dev/null || true
        echo "Build ${currentBuild.result} - #${BUILD_NUMBER}"
      '''
    }
    
    success {
      sh """
        echo "✅ DEPLOYMENT SUCCESSFUL!"
        echo "Application URL: http://${SERVER}:8080"
      """
    }
    
    failure {
      sh """
        echo "❌ DEPLOYMENT FAILED!"
        echo "Check logs above for details"
      """
    }
  }
}
