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
    STAGING_PORT = "8502"   
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
          docker compose -p house-price-staging -f docker-compose.staging.yml down || true
          docker compose -p house-price-staging -f docker-compose.staging.yml up -d --build
    
          docker compose -p house-price-staging -f docker-compose.staging.yml ps
    
          docker compose -p house-price-staging -f docker-compose.staging.yml exec -T app python - <<'PY'
import sys, time, urllib.request
url = "http://localhost:8501/"
deadline = time.time() + 90
code = 0
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            code = r.getcode()
            if code == 200:
                print("STAGING_HTTP=200")
                sys.exit(0)
    except Exception:
        pass
    time.sleep(1)
print(f"STAGING_HTTP={code or 0}")
sys.exit(1)
PY
        '''
      }
    }



    // Capture the image currently running in PROD (for rollback)
    stage('Capture Current Prod Image') {
      steps {
        sh '''
          set -e
          # Get container ID of the "app" service if it exists
          CID=$(docker compose -p house-price-prod -f docker-compose.prod.yml ps -q app || true)
    
          # Store the exact image reference (repo:tag). Empty if not running yet.
          if [ -n "$CID" ]; then
            docker inspect -f '{{.Config.Image}}' "$CID" > prev_prod_image.txt || true
          else
            : > prev_prod_image.txt
          fi
    
          echo "PREV_IMAGE=$(cat prev_prod_image.txt || echo '')"
        '''
      }
    }

    // Release to Production (with readiness gate and auto-rollback) 
    stage('Release Production') {
      steps {
        sh '''
          set -e
    
          # Ensure we have image name/tag values (fallbacks if env not set)
          IMAGE_NAME="${IMAGE_NAME:-house-price}"
          IMAGE_TAG="${IMAGE_TAG:-latest}"
    
          echo "Deploying ${IMAGE_NAME}:${IMAGE_TAG} to PROD…"
    
          # Stop current stack (ignore errors) and start fresh
          docker compose -p house-price-prod -f docker-compose.prod.yml down || true
          IMAGE_NAME="$IMAGE_NAME" IMAGE_TAG="$IMAGE_TAG" \
            docker compose -p house-price-prod -f docker-compose.prod.yml up -d --build
    
          # Short, screenshot-friendly status lines
          docker compose -p house-price-prod -f docker-compose.prod.yml ps
          docker compose -p house-price-prod -f docker-compose.prod.yml images || true
    
          # Readiness probe INSIDE the container using Python stdlib (no curl dependency)
          set +e
          docker compose -p house-price-prod -f docker-compose.prod.yml exec -T app python - <<'PY'
import sys, time, urllib.request
URL = "http://localhost:8501/"
deadline = time.time() + 90
while time.time() < deadline:
    try:
        if urllib.request.urlopen(URL, timeout=2).getcode() == 200:
            print("PROD_HTTP=200")
            sys.exit(0)
    except Exception:
        pass
    time.sleep(1)
print("PROD_HTTP=000")
sys.exit(1)
PY
          RC=$?
          set -e
    
          if [ "$RC" -ne 0 ]; then
            echo "Production readiness probe failed. Attempting rollback…"
    
            PREV_IMAGE=$(cat prev_prod_image.txt 2>/dev/null || echo "")
            if [ -n "$PREV_IMAGE" ]; then
              # Split "repo:tag" -> repo & tag (simple, tag-based images)
              PREV_NAME="${PREV_IMAGE%%:*}"
              PREV_TAG="${PREV_IMAGE#*:}"
    
              if [ -n "$PREV_TAG" ] && [ "$PREV_TAG" != "$PREV_IMAGE" ]; then
                echo "Rolling back to ${PREV_NAME}:${PREV_TAG}…"
                IMAGE_NAME="$PREV_NAME" IMAGE_TAG="$PREV_TAG" \
                  docker compose -p house-price-prod -f docker-compose.prod.yml up -d --build
    
                docker compose -p house-price-prod -f docker-compose.prod.yml ps
                echo "Rolled back to ${PREV_NAME}:${PREV_TAG}"
              else
                echo "Could not parse previous tag from '${PREV_IMAGE}'. No rollback performed."
              fi
            else
              echo "No previous image recorded. Cannot rollback."
            fi
    
            # Fail the stage so the pipeline surfaces the issue
            exit 1
          fi
    
          echo "Production release succeeded."
        '''
      }
    }



    stage('Monitoring') {
      steps {
        sh '''
          set -e
    
          echo "Healthcheck STAGING (:8502)"
          CID=$(docker compose -p house-price-staging -f docker-compose.staging.yml ps -q app || true)
          if [ -n "$CID" ]; then
            for i in $(seq 1 10); do
              s=$(docker inspect -f '{{.State.Health.Status}}' "$CID" 2>/dev/null || echo "none")
              echo "STAGING health=$s"
              sleep 3
            done
            set +e
            docker compose -p house-price-staging -f docker-compose.staging.yml exec -T app python - <<'PY'
import urllib.request
try:
    code = urllib.request.urlopen("http://localhost:8501/", timeout=2).getcode()
    print(f"STAGING_HTTP={code}")
except Exception:
    print("STAGING_HTTP=000")
PY
            set -e
          fi
    
          echo "Healthcheck PROD (:8501)"
          PID=$(docker compose -p house-price-prod -f docker-compose.prod.yml ps -q app || true)
          if [ -n "$PID" ]; then
            for i in $(seq 1 10); do
              s=$(docker inspect -f '{{.State.Health.Status}}' "$PID" 2>/dev/null || echo "none")
              echo "PROD health=$s"
              sleep 3
            done
            set +e
            docker compose -p house-price-prod -f docker-compose.prod.yml exec -T app python - <<'PY'
import urllib.request
try:
    code = urllib.request.urlopen("http://localhost:8501/", timeout=2).getcode()
    print(f"PROD_HTTP={code}")
except Exception:
    print("PROD_HTTP=000")
PY
            set -e
          fi
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
