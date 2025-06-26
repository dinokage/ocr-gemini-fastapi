pipeline {
    agent any
    
    environment {
        // Environment variables
        DOCKER_COMPOSE_FILE = 'docker-compose.yml'
        APP_NAME = 'pdf-tag-extraction'
        // Credentials defined in Jenkins credential store
        GEMINI_API_KEY = credentials('gemini-api-key')
    }
    
    options {
        // Set build timeout to prevent hanging builds
        timeout(time: 30, unit: 'MINUTES')
        // Keep only the last 10 builds
        buildDiscarder(logRotator(numToKeepStr: '10'))
        // Don't run concurrent builds of the same branch
        disableConcurrentBuilds()
        // Show timestamps in the console output
        timestamps()
    }
    
    stages {
        stage('Checkout') {
            steps {
                echo "🔍 Checking out code..."
                checkout scm
                
                // Create directories for Docker volumes if they don't exist
                sh 'mkdir -p ./tmp/uploads ./tmp/logs'
                sh 'chmod -R 777 ./tmp'
            }
        }
        
        stage('Environment Setup') {
            steps {
                echo "🔧 Setting up environment..."
                
                // Create .env file for Docker
                sh '''
                echo "GEMINI_API_KEY=${GEMINI_API_KEY}" > .env
                echo "Environment file created with API key"
                '''

            }
        }
        
        stage('Build Docker Image') {
            steps {
                echo "🏗️ Building Docker image..."
                sh 'docker-compose build --no-cache'
            }
        }
        
        stage('Start Service') {
            steps {
                echo "🚀 Starting service with Docker Compose..."
                sh 'docker-compose up -d'
                
                // Wait for service to become available
                sh '''
                # Wait for service to be ready (max 60 seconds)
                for i in $(seq 1 12); do
                    if curl -s http://localhost:8000/health | grep -q "healthy"; then
                        echo "✅ Service is up and running!"
                        break
                    fi
                    echo "Waiting for service to start... ($i/12)"
                    sleep 5
                done
                
                # Final check
                if ! curl -s http://localhost:8000/health | grep -q "healthy"; then
                    echo "❌ Service failed to start within timeout"
                    exit 1
                fi
                '''
            }
        }
        
        stage('Run Tests') {
            steps {
                echo "🧪 Running tests..."
                
                // Copy test files to the workspace if needed
                // sh 'cp /path/to/test/files/*.pdf .'
            
            }
        }
        
        stage('Deployment') {
            when {
                expression { 
                    return env.BRANCH_NAME == 'main' || env.BRANCH_NAME == 'master' 
                }
            }
            steps {
                echo "📦 Deploying to production environment..."
                
                // Example: Push to Docker registry
                // sh 'docker tag ${APP_NAME} myregistry/${APP_NAME}:latest'
                // sh 'docker push myregistry/${APP_NAME}:latest'
                
                // Example: Deploy to server
                // Use SSH to deploy to server or update service
                echo "Deployment would happen here in a real pipeline"
            }
        }
    }
    
    post {
        always {
            echo "🧹 Cleaning up..."
            
            // Capture logs
            sh '''
            mkdir -p logs
            docker-compose logs > logs/docker-compose.log
            '''
            
            // Stop and remove containers
            sh 'docker-compose down || true'
            
            // Clean up environment file
            sh 'rm -f .env || true'
            
            // Archive artifacts
            archiveArtifacts artifacts: 'logs/**/*.log', allowEmptyArchive: true
        }
        
        success {
            echo "✅ Build successful!"
            // Slack or email notification for success
            // slackSend color: 'good', message: "✅ Build Succeeded: ${env.JOB_NAME} #${env.BUILD_NUMBER}"
        }
        
        failure {
            echo "❌ Build failed!"
            // Slack or email notification for failure
            // slackSend color: 'danger', message: "❌ Build Failed: ${env.JOB_NAME} #${env.BUILD_NUMBER}"
        }
    }
}