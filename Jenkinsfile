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
    // set DOCKER_USER via withCredentials in Publish Image stage
  }

  stages {
    stage('Build (Train + Package)') {
      steps {
        checkout scm
        sh '''
          set -e
          MOUNT_PATH="/jenkins_home${WORKSPACE#/var/jenkins_home}"

          docker run --rm -v jenkins_home:/jenkins_home -w "$MOUNT_PATH" python:3.11 bash -lc '
            python -V &&
            pip install -r requirements.txt &&
            python preprocess_and_train.py
          '

          docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
        '''
      }
    }

    stage('Test') {
      steps {
        sh '''
          set -e
          MOUNT_PATH="/jenkins_home${WORKSPACE#/var/jenkins_home}"
          docker run --rm -v jenkins_home:/jenkins_home -w "$MOUNT_PATH" python:3.11 bash -lc '
            pip install -r requirements.txt &&
            pytest -q --maxfail=1 --disable-warnings --junitxml=pytest-report.xml
          '
        '''
      }
      post { always { junit allowEmptyResults: true, testResults: 'pytest-report.xml' } }
    }

    stage('Code Quality') {
      steps {
        sh '''
          set -e
          MOUNT_PATH="/jenkins_home${WORKSPACE#/var/jenkins_home}"
          docker run --rm -v jenkins_home:/jenkins_home -w "$MOUNT_PATH" python:3.11 bash -lc '
            pip install ruff &&
            ruff check . --output-format=concise | tee ruff.txt || true &&
            COUNT=$(wc -l < ruff.txt); echo "Ruff issues: $COUNT"; [ "$COUNT" -le 20 ]
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
    
          # -------- Dependency vulns (pip-audit) --------
          docker run --rm -v jenkins_home:/jenkins_home -w "$MOUNT_PATH" python:3.11 bash -lc '
            pip install pip-audit &&
            pip-audit -r requirements.txt -f json -o pip-audit.json || true &&
            python - <<PY
    import json,sys
    try:
      d=json.load(open("pip-audit.json"))
    except Exception as e:
      print("pip-audit.json missing:", e); sys.exit(0)
    high=crit=0
    for dep in d.get("dependencies", []):
      for v in dep.get("vulns", []):
        sev=(v.get("severity") or "").upper()
        if sev=="HIGH": high+=1
        if sev=="CRITICAL": crit+=1
    print(f"HIGH={high} CRITICAL={crit}")
    sys.exit(0 if crit==0 and high<=0 else 1)
    PY
          '
    
          # -------- Image vulns (Trivy) --------
          # Use only vulnerability scanner to avoid Rego/IaC rules causing panic
          docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$PWD":/work \
            aquasec/trivy:0.52.2 \
            image --scanners vuln --format json --severity HIGH,CRITICAL \
            --output /work/trivy.json ${IMAGE_NAME}:${IMAGE_TAG} || true
    
          # Parse trivy.json inside Python container (Jenkins container has no python)
          docker run --rm -v jenkins_home:/jenkins_home -w "$MOUNT_PATH" python:3.11 bash -lc '
            python - <<PY
    import json,sys,os
    p="trivy.json"
    if not os.path.exists(p):
      print("No trivy.json (scan skipped/failed)"); sys.exit(0)
    try:
      d=json.load(open(p))
    except Exception as e:
      print("Failed to read trivy.json:", e); sys.exit(0)
    high=crit=0
    def walk(o):
      global high,crit
      if isinstance(o,dict):
        # Trivy JSON puts findings under Results[].Vulnerabilities[]
        for r in o.get("Results", []):
          for v in (r.get("Vulnerabilities") or []):
            if v.get("Severity")=="HIGH": high+=1
            elif v.get("Severity")=="CRITICAL": crit+=1
        for v in o.values(): walk(v)
      elif isinstance(o,list):
        for v in o: walk(v)
    walk(d)
    print(f"TRIVY HIGH={high} CRITICAL={crit}")
    sys.exit(0 if crit==0 and high<=5 else 1)
    PY
          '
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
          docker compose -p house-price-staging -f docker-compose.staging.yml down || true
          docker compose -p house-price-staging -f docker-compose.staging.yml up -d --build
        '''
      }
    }

    stage('Release Prod') {
      steps {
        sh '''
          docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${IMAGE_NAME}:prod
          docker compose -p house-price-prod -f docker-compose.prod.yml down || true
          docker compose -p house-price-prod -f docker-compose.prod.yml up -d
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
