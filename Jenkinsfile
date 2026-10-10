// ScholarHub CI/CD pipeline (declarative, pipeline as code)
// Flow: Checkout -> Test -> Build Images -> Deploy -> Smoke Test
// A failing Test stage stops the pipeline, so broken code never reaches Deploy.

// Sends the build result to Discord. The webhook URL comes from Jenkins Credentials
// (ID: discord-webhook). \$DISCORD_URL is escaped so the shell expands it and
// Groovy never interpolates the secret. "|| true" means a Discord outage
// can never fail an otherwise good build.
def notifyDiscord(String emoji, String status, String extra = '') {
    withCredentials([string(credentialsId: 'discord-webhook', variable: 'DISCORD_URL')]) {
        sh """
            curl -sS -H 'Content-Type: application/json' -X POST "\$DISCORD_URL" \\
            -d '{"content": "${emoji} **${status}** | ScholarHub build #${env.BUILD_NUMBER} | ${env.BUILD_URL} ${extra}"}' || true
        """
    }
}

pipeline {
    agent any

    environment {
        // Keep this constant: same project name = same named volumes,
        // so database and uploaded files survive every redeploy.
        COMPOSE_PROJECT_NAME = 'scholarhub'
        // Images are tagged with the build number, so any earlier build can be redeployed (rollback).
        // docker-compose.yml reads ${TAG}; the frontend footer shows it too.
        TAG = "${env.BUILD_NUMBER}"
    }

    triggers {
        githubPush()                          // fired by the GitHub webhook
        // pollSCM('H/2 * * * *')             // fallback: uncomment if the webhook is unavailable
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
            // Runs the "test" stage of each Dockerfile. If any test fails,
            // docker build exits non-zero, this stage fails, and the pipeline
            // stops here: Build Images and Deploy never run.
            steps {
                sh 'docker build --target test -t scholarhub/auth-service:test ./auth-service'
                sh 'docker build --target test -t scholarhub/scholarship-api:test ./scholarship-api'
                sh 'docker build --target test -t scholarhub/application-api:test ./application-api'
                sh 'docker build --target test -t scholarhub/upload-service:test ./upload-service'
                sh 'docker build --target test -t scholarhub/worker:test ./worker'
            }
        }

        stage('Build Images') {
            steps {
                // Builds every service and tags it scholarhub/<service>:<build number>
                sh 'docker compose build'
            }
        }

        stage('Deploy') {
            steps {
                // The real .env lives in Jenkins Credentials (Secret file), never in Git.
                withCredentials([file(credentialsId: 'scholarhub-env', variable: 'ENV_FILE')]) {
                    sh 'cp "$ENV_FILE" .env'
                    sh 'docker compose up -d --no-build --remove-orphans'
                }
            }
        }

        stage('Smoke Test') {
            // Checks the health endpoints through the reverse proxy, retrying for up to 60 seconds.
            steps {
                sh '''
                    for i in $(seq 1 12); do
                        if docker compose exec -T proxy wget -qO- http://localhost/api/auth/health \
                        && docker compose exec -T proxy wget -qO- http://localhost/api/scholarships/health \
                        && docker compose exec -T proxy wget -qO- http://localhost/api/applications/health \
                        && docker compose exec -T proxy wget -qO- http://localhost/api/uploads/health \
                        && docker compose exec -T proxy wget -qO /dev/null http://localhost/; then
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
            echo "ScholarHub build ${TAG} is live at http://localhost:8080"
            notifyDiscord('✅', 'DEPLOYED', '| smoke test passed')
        }
        failure {
            echo "Build ${TAG} failed. Check the stage logs. Roll back with: TAG=<previous> docker compose -p scholarhub up -d --no-build"
            notifyDiscord('❌', 'FAILED', '| previous version still running, check the Stage View')
        }
        always {
            sh 'rm -f .env'                    // never leave secrets in the workspace
            sh 'docker image prune -f || true' // removes only untagged leftovers; tagged builds stay for rollback
        }
    }
}