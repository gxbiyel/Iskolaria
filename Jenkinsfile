// Iskolaria CI/CD pipeline (declarative, pipeline as code)
// Flow: Checkout -> Test -> Build Images -> Deploy -> Smoke Test
// A failing Test stage stops the pipeline, so broken code never reaches Deploy.

// Sends the build result to Discord. The webhook URL comes from Jenkins Credentials
// (ID: discord-webhook). \$DISCORD_URL is escaped so the shell expands it and
// Groovy never interpolates the secret. "|| true" means a Discord outage, and the
// try/catch means a missing credential, can never fail an otherwise good build.
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
        // Must match "name:" in docker-compose.yml. Same project name = same named volumes,
        // so the database and uploaded files survive every redeploy.
        COMPOSE_PROJECT_NAME = 'iskolaria'
        // Images are tagged with the build number, so any earlier build can be redeployed (rollback).
        // docker-compose.yml reads ${TAG}; the frontend footer shows it too.
        TAG = "${env.BUILD_NUMBER}"
    }

    triggers {
        githubPush()                          // fired by the GitHub webhook
        pollSCM('* * * * *')             // fallback: uncomment if the webhook is unavailable
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
                sh 'docker build --target test -t iskolaria/auth-service:test ./auth-service'
                sh 'docker build --target test -t iskolaria/scholarship-api:test ./scholarship-api'
                sh 'docker build --target test -t iskolaria/application-api:test ./application-api'
                sh 'docker build --target test -t iskolaria/upload-service:test ./upload-service'
                sh 'docker build --target test -t iskolaria/worker:test ./worker'
            }
        }

        stage('Build Images') {
            steps {
                // Builds every service and tags it iskolaria/<service>:<build number>
                sh 'docker compose build'
            }
        }

        stage('Deploy') {
            steps {
                // The real .env lives in Jenkins Credentials (Secret file), never in Git.
                withCredentials([file(credentialsId: 'iskolaria-env', variable: 'ENV_FILE')]) {
                    sh 'cp "$ENV_FILE" .env'
                    sh 'docker compose up -d --no-build --remove-orphans'
                }
            }
        }

        stage('Smoke Test') {
            // Checks the health endpoints through the reverse proxy, retrying for up to 60 seconds.
            // 127.0.0.1 instead of localhost: busybox wget may try IPv6 (::1) first,
            // and nginx here listens on IPv4 only.
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
            sh 'rm -f .env'                    // never leave secrets in the workspace
            sh 'docker image prune -f || true' // removes only untagged leftovers; tagged builds stay for rollback
        }
    }
}