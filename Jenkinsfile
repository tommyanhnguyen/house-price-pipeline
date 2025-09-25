pipeline {
  agent any

  environment {
    IMAGE_NAME = "house-price"
    IMAGE_TAG  = "${env.BUILD_NUMBER}"
  }

  stages {
    stage('Build (Train + Package)') {
      steps {
        checkout scm
        sh '''
          set -e
          echo "== Workspace (inside Jenkins container) =="
          pwd
          ls -la
    
          # Convert /var/jenkins_home/... -> /jenkins_home/...
          MOUNT_PATH="/jenkins_home${WORKSPACE#/var/jenkins_home}"
          echo "Mounting Jenkins volume path: $MOUNT_PATH"
    
          # Train inside a clean Python container with the jenkins_home volume
          docker run --rm \
            -v jenkins_home:/jenkins_home -w "$MOUNT_PATH" \
            python:3.11 bash -lc "
              ls -la &&
              python -V &&
              pip install -r requirements.txt &&
              python preprocess_and_train.py
            "
    
          # Build the app image including generated artifacts
          docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
        '''
      }
    }




    stage('Test') {
      steps {
        sh '''
          pip install -r requirements.txt
          pytest -q
        '''
      }
      post {
        always { junit allowEmptyResults: true, testResults: '**/pytest*.xml' }
      }
    }

    stage('Code Quality') {
      steps {
        sh '''
          echo "Run code quality tools (e.g., flake8/ruff or SonarQube) here"
          # Example lightweight:
          pip install ruff || true
          ruff check . || true
        '''
      }
    }

    stage('Security') {
      steps {
        sh '''
          pip install pip-audit || true
          pip-audit || true
          # If you have Trivy available on Jenkins node:
          # trivy image --severity HIGH,CRITICAL ${IMAGE_NAME}:${IMAGE_TAG} || true
        '''
      }
    }

    stage('Deploy Staging') {
      steps {
        sh '''
          docker compose -f docker-compose.staging.yml down || true
          docker compose -f docker-compose.staging.yml up -d --build
        '''
      }
    }

    stage('Release Prod') {
      steps {
        sh '''
          docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${IMAGE_NAME}:prod
          docker compose -f docker-compose.prod.yml down || true
          docker compose -f docker-compose.prod.yml up -d
        '''
      }
    }

    stage('Monitoring') {
      steps {
        sh '''
          # Simple healthcheck (replace with curl to /health if you add one)
          sleep 3
          curl -sSf http://localhost:8501/ || echo "Streamlit UI reachable check"
          echo "Integrate with Prometheus/New Relic here if available"
        '''
      }
    }
  }
}

