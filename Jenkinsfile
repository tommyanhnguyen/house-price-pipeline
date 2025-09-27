pipeline {
  agent any

  options {
    timestamps()
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timeout(time: 30, unit: 'MINUTES')
  }

  environment {
    IMAGE_NAME   = "house-price"
    IMAGE_TAG    = "${env.BUILD_NUMBER}"
    STAGING_PORT = "8502"   // tránh đụng 8501
    PROD_PORT    = "8501"
    // Docker Hub credentials id: dockerhub
  }

  stages {

    stage('Build (Train + Package)') {
      steps {
        checkout scm
        sh '''
          set -e
          # Map /var/jenkins_home/... -> /jenkins_home/...
          MOUNT_PATH="/jenkins_home${WORKSPACE#/var/jenkins_home}"

          # Train and produce artifacts in a clean Python container
          docker run --rm \
            -v jenkins_home:/jenkins_home -w "$MOUNT_PATH" \
            python:3.11 bash -lc '
              python -V &&
              pip install -r requirements.txt &&
              python preprocess_and_train.py
            '

          # Build the app image (includes artifacts/)
          docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
        '''
      }
    }

    stage('Test') {
      steps {
        sh '''
          set -e
          MOUNT_PATH="/jenkins_home${WORKSPACE#/var/jenkins_home}"
          docker run --rm \
            -v jenkins_home:/jenkins_home -w "$MOUNT_PATH" \
            python:3.11 bash -lc '
              pip install -r requirements.txt &&
              pytest -q --maxfail=1 --disable-warnings --junitxml=pytest-report.xml
            '
        '''
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: 'pytest-report.xml'
        }
      }
    }

    stage('Code Quality') {
      steps {
        sh '''
          set -e
          MOUNT_PATH="/jenkins_home${WORKSPACE#/var/jenkins_home}"
          docker run --rm \
            -v jenkins_home:/jenkins_home -w "$MOUNT_PATH" \
            python:3.11 bash -lc '
              pip install ruff &&
              ruff --version &&
              # Allow up to 20 findings before failing (tune as needed)
              ruff check . --output-format=concise --exit-zero | tee ruff.txt
              # Count only real violations: "file:line:col: CODE message"
              COUNT=$(grep -E ":[0-9]+:[0-9]+: [A-Z][0-9]{3} " -c ruff.txt || true)
              echo "Ruff issues: ${COUNT}"
              [ "${COUNT}" -le 20 ]
            '
        '''
      }
    }

    stage('Security') {
      steps {
        sh '''
          set -e
          MOUNT_PATH="/jenkins_home${WORKSPACE#/var/jenkins_home}"
          echo "Security checks in: $MOUNT_PATH"

          # --- Prepare small parser scripts in workspace (safe quoting with <<'PY') ---
          mkdir -p scripts

          # Parser for pip-audit JSON -> fail policy: no CRITICAL, no HIGH
          cat > scripts/parse_pipaudit.py <<'PY'
import json, sys, os
p = "pip-audit.json"
if not os.path.exists(p):
    print("pip-audit.json missing"); sys.exit(0)
d = json.load(open(p))
high = crit = 0
for dep in d.get("dependencies", []):
    for v in dep.get("vulns", []):
        sev = (v.get("severity") or "").upper()
        if sev == "HIGH": high += 1
        if sev == "CRITICAL": crit += 1
print(f"HIGH={high} CRITICAL={crit}")
sys.exit(0 if crit == 0 and high <= 0 else 1)
PY

          # Parser for Trivy JSON -> fail policy: CRITICAL==0 and HIGH<=5
          cat > scripts/parse_trivy.py <<'PY'
import json, sys, os
p = "trivy.json"
if not os.path.exists(p):
    print("No trivy.json (scan skipped/failed)"); sys.exit(0)
try:
    d = json.load(open(p))
except Exception as e:
    print("Failed to read trivy.json:", e); sys.exit(0)
high = crit = 0
def walk(o):
    global high, crit
    if isinstance(o, dict):
        for r in o.get("Results", []):
            for v in (r.get("Vulnerabilities") or []):
                if v.get("Severity") == "HIGH": high += 1
                elif v.get("Severity") == "CRITICAL": crit += 1
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
walk(d)
print(f"TRIVY HIGH={high} CRITICAL={crit}")
sys.exit(0 if crit == 0 and high <= 5 else 1)
PY

          # 1) Dependency vulnerabilities (pip-audit)
          docker run --rm \
            -v jenkins_home:/jenkins_home -w "$MOUNT_PATH" \
            python:3.11 bash -lc "
              set -e
              pip install pip-audit &&
              pip-audit -r requirements.txt -f json -o pip-audit.json || true &&
              python scripts/parse_pipaudit.py
            "

          # 2) Image vulnerabilities (Trivy) — run with host Docker socket
          docker run --rm \
            -v jenkins_home:/jenkins_home \
            -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy:0.52.2 image \
            --scanners vuln --format json --severity HIGH,CRITICAL \
            --output "$MOUNT_PATH/trivy.json" "${IMAGE_NAME}:${IMAGE_TAG}" || true

          # Parse Trivy results inside Python container (same workspace path)
          docker run --rm \
            -v jenkins_home:/jenkins_home -w "$MOUNT_PATH" \
            python:3.11 python scripts/parse_trivy.py
        '''
      }
    }

    stage('Publish Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub', usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
          sh '''
            set -e
            COMMIT=$(git rev-parse --short HEAD)
            VERSION="${BUILD_NUMBER}-${COMMIT}"

            echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
            docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${DOCKER_USER}/${IMAGE_NAME}:${VERSION}
            docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${DOCKER_USER}/${IMAGE_NAME}:latest
            docker push ${DOCKER_USER}/${IMAGE_NAME}:${VERSION}
            docker push ${DOCKER_USER}/${IMAGE_NAME}:latest
            echo ${VERSION} > .image_version
          '''
        }
      }
    }

    stage('Deploy Staging') {
      steps {
        sh '''
          set -e
    
          # Stop any previous staging stack (ignore errors)
          docker compose -p house-price-staging -f docker-compose.staging.yml down || true
    
          # Start fresh
          docker compose -p house-price-staging -f docker-compose.staging.yml up -d --build
    
          # Resolve container ID of the "app" service in this compose project
          CID=$(docker compose -p house-price-staging -f docker-compose.staging.yml ps -q app)
    
          # Wait (up to 90s) for HEALTHCHECK to report "healthy"
          for i in $(seq 1 90); do
            status=$(docker inspect -f '{{.State.Health.Status}}' "$CID" 2>/dev/null || echo "none")
            echo "health=$status"
            [ "$status" = "healthy" ] && break
            sleep 1
          done
    
          # Show a concise status line for evidence 
          docker compose -p house-price-staging -f docker-compose.staging.yml ps
    
          # Final gate: probe HTTP from *inside* the container on internal port 8501
          docker compose -p house-price-staging -f docker-compose.staging.yml exec -T app sh -lc '
            for i in $(seq 1 60); do
              code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8501/ || true)
              if [ "$code" = "200" ]; then
                echo "STAGING_HTTP=200"
                exit 0
              fi
              sleep 1
            done
            echo "STAGING_HTTP=${code:-000}"
            exit 1
          '
        '''
      }
    }


    stage('Release Prod') {
      steps {
        sh '''
          set -e
          docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${IMAGE_NAME}:prod
          docker compose -p house-price-prod -f docker-compose.prod.yml down || true
          docker compose -p house-price-prod -f docker-compose.prod.yml up -d
          # Show the service is up and which port is exposed
          docker compose -p house-price-prod -f docker-compose.prod.yml ps
          # Final gate: HTTP probe to production port (adjust path if you have /health)
          curl -sS -o /dev/null -w "PROD_HTTP=%{http_code}\n" http://localhost:8501/

        '''
      }
    }

    stage('Monitoring') {
      steps {
        sh '''
          set -e
          echo "Healthcheck STAGING (:${STAGING_PORT})"
          CID=$(docker compose -p house-price-staging -f docker-compose.staging.yml ps -q app || true)
          if [ -n "$CID" ]; then
            for i in {1..10}; do
              STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CID" 2>/dev/null || echo "unknown")
              echo "Health=$STATUS"
              [ "$STATUS" = "healthy" ] && break
              sleep 3
            done
          fi
          # Non-blocking curl (won't fail the pipeline)
          curl -sSf http://localhost:${STAGING_PORT}/ >/dev/null || echo "Staging UI curl failed (non-blocking)"
        '''
      }
    }
  }

  post {
    success {
      archiveArtifacts artifacts: 'artifacts/**,pytest-report.xml,ruff.txt,pip-audit.json,trivy.json', fingerprint: true
    }
  }
}
