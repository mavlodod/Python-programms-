pipeline {
  agent any
  
  environment {
    SERVER = "10.200.101.50"
    USER = "mavlodod"
    DIR = "/home/mavlodod/Birthday/Python-programms-"
    SSH_ID = "mavlodod-ssh-key"
  }
  
  stages {
    stage('Test Build') {
      steps {
        sh '''
          echo "Testing build on port 8081"
          
          # Create test compose file
          cp docker-compose.yml docker-compose.test.yml
          sed -i "s/8080:5000/8081:5000/g" docker-compose.test.yml
          
          # Test build and run
          docker compose -f docker-compose.test.yml build
          docker compose -f docker-compose.test.yml up -d
          sleep 5
          docker compose -f docker-compose.test.yml ps
          docker compose -f docker-compose.test.yml down
          
          # Cleanup
          rm -f docker-compose.test.yml
          
          echo "Test completed"
        '''
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
              echo 'Deployed to http://${SERVER}:8080'
            "
          """
        }
      }
    }
  }
}
