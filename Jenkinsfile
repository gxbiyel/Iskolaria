def notifyDiscord(String emoji, String status, String extra = '') {
    try {
        withCredentials([string(credentialsId: 'discord-webhook', variable: 'DISCORD_URL')]) {
            sh """
                curl -sS -H 'Content-Type: application/json' -X POST "\$DISCORD_URL" \\
                -d '{"content": "${emoji} **${status}** | Iskolaria build #${env.BUILD_NUMBER} | ${env.BUILD_URL} ${extra}"}' || true
            """
        }
    } catch (err) {
        echo "Discord notification skipped: ${err.message}"
    }
}

pipeline {
    agent any

    environment {
        
        COMPOSE_PROJECT_NAME = 'iskolaria'
        TAG = "${env.BUILD_NUMBER}"
    }

    triggers {
        githubPush()                          
        pollSCM('* * * * *')     
    }

    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '15'))
        timeout(time: 30, unit: 'MINUTES')
    }

    stages {

        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Test') {
            
            steps {
                sh 'docker build --target test -t iskolaria/auth-service:test ./auth-service'
                sh 'docker build --target test -t iskolaria/scholarship-api:test ./scholarship-api'
                sh 'docker build --target test -t iskolaria/application-api:test ./application-api'
                sh 'docker build --target test -t iskolaria/upload-service:test ./upload-service'
                sh 'docker build --target test -t iskolaria/worker:test ./worker'
            }
        }

        stage('Build Images') {
            steps {
                
                sh 'docker compose build'
            }
        }

        stage('Deploy') {
            steps {
                
                withCredentials([file(credentialsId: 'iskolaria-env', variable: 'ENV_FILE')]) {
                    sh 'cp "$ENV_FILE" .env'
                    sh 'docker compose up -d --no-build --remove-orphans'
                }
            }
        }

        stage('Smoke Test') {
            
            steps {
                sh '''
                    for i in $(seq 1 12); do
                        if docker compose exec -T proxy wget -qO- http://127.0.0.1/api/auth/health \
                        && docker compose exec -T proxy wget -qO- http://127.0.0.1/api/scholarships/health \
                        && docker compose exec -T proxy wget -qO- http://127.0.0.1/api/applications/health \
                        && docker compose exec -T proxy wget -qO- http://127.0.0.1/api/uploads/health \
                        && docker compose exec -T proxy wget -qO /dev/null http://127.0.0.1/; then
                            echo "Smoke test passed"; exit 0
                        fi
                        echo "Waiting for services..."; sleep 5
                    done
                    echo "Smoke test failed"; exit 1
                '''
            }
        }
    }

    post {
        success {
            echo "Iskolaria build ${TAG} is live at http://localhost:8080"
            notifyDiscord('✅', 'DEPLOYED', '| smoke test passed')
        }
        failure {
            echo "Build ${TAG} failed. Check the stage logs. Roll back with: TAG=<previous> docker compose -p iskolaria up -d --no-build (needs the real .env in that folder)"
            notifyDiscord('❌', 'FAILED', '| previous version still running, check the Stage View')
        }
        always {
            sh 'rm -f .env'                    
            sh 'docker image prune -f || true' 
        }
    }
}