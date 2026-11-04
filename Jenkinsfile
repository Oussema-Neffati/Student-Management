pipeline {
    agent any

    environment {
        IMAGE_NAME        = "oussemaneffati/student-management"
        KUBECONFIG        = "/var/lib/jenkins/.kube/config"
        NOTIFY_EMAIL      = "oussema.neffati@esprit.tn"   // who receives the build report
        ALLOWED_NODEPORTS = "30080"                       // ports allowed to be open outside the cluster (space-separated)
    }

    stages {
        // 1. Download the latest code from GitHub
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        // 2. PRE-COMMIT practice: search the whole Git history for passwords, tokens and keys
        //    (same tool as the local pre-commit hook, enforced again on the server)
        stage('Secrets Scan (Gitleaks)') {
            steps {
                sh '''
                    gitleaks git . --redact --no-banner \
                      --report-format json --report-path gitleaks-report.json
                '''
            }
        }

        // 3. Compile the Java code and package it as a .jar with Maven
        stage('Build Application') {
            steps {
                sh 'mvn clean package -DskipTests'
            }
        }

        // 4. SAST: SonarQube analyses the source code for bugs, code smells and security hotspots
        stage('SonarQube Analysis') {
            steps {
                withSonarQubeEnv('SonarQube') {
                    withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
                        sh '''
                            mvn sonar:sonar \
                            -Dsonar.projectKey=student-management \
                            -Dsonar.projectName=student-management \
                            -Dsonar.login=$SONAR_TOKEN \
                            -DskipTests
                        '''
                    }
                }
            }
        }

        // 5. Package the .jar into a Docker image (Dockerfile: patched Alpine, non-root user)
        stage('Build Docker Image') {
            steps {
                script {
                    docker.build("${IMAGE_NAME}:latest")
                }
            }
        }

        // 6. COMMIT practice - Container Security: scan the image BEFORE it is published.
        //    Report = HIGH + CRITICAL; gate = fail only on CRITICAL vulnerabilities that have a fix.
        stage('Container Scan (Trivy)') {
            steps {
                sh '''
                    trivy image --no-progress --scanners vuln --timeout 15m \
                      --severity HIGH,CRITICAL \
                      --format json --output trivy-report.json \
                      ${IMAGE_NAME}:latest

                    trivy image --no-progress --scanners vuln --timeout 15m \
                      --severity CRITICAL --ignore-unfixed \
                      --exit-code 1 \
                      ${IMAGE_NAME}:latest
                '''
            }
        }

        // 7. Publish the approved image to Docker Hub
        stage('Push Docker Image') {
            steps {
                script {
                    docker.withRegistry('https://registry.hub.docker.com', 'dockerhub-credentials') {
                        docker.image("${IMAGE_NAME}:latest").push()
                    }
                }
            }
        }

        // 8. Rolling update on Kubernetes: pods are replaced one by one, no downtime
        stage('Deploy to Kubernetes') {
            steps {
                sh '''
                    kubectl rollout restart deployment student-management-deployment -n devops
                    kubectl rollout status deployment student-management-deployment -n devops
                '''
            }
        }

        // 9. Smoke test: the new version must answer on its health endpoint
        stage('Verification') {
            steps {
                sh '''
                    kubectl get pods -n devops -l app=student-management
                    NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[0].address}')
                    curl -sf --retry 10 --retry-delay 10 --retry-all-errors \
                      "http://$NODE_IP:30080/student/actuator/health"
                '''
            }
        }

        // 10. Network security: scan the DEPLOYED app from the network, like an attacker would.
        //     Report = HTTP security headers, accepted methods, page title.
        //     Gate   = fail if a NodePort outside the allowlist is open.
        stage('Network Scan (Nmap)') {
            steps {
                sh '''
                    NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[0].address}')

                    # "+" forces the HTTP scripts to run even though Nmap does not recognise port 30080 as HTTP
                    nmap -sT -Pn -p 30080 \
                      --script "+http-headers,+http-methods,+http-title" \
                      --script-args "http-headers.path=/student/actuator/health,http-methods.url-path=/student/,http-title.url=/student/swagger-ui/index.html" \
                      -oX nmap-app-report.xml "$NODE_IP"

                    nmap -sT -Pn -p 30000-32767 --open -oG nmap-nodeports.gnmap "$NODE_IP"
                    OPEN=$(grep -oE '[0-9]+/open' nmap-nodeports.gnmap | cut -d/ -f1 | sort -n | tr '\\n' ' ')
                    echo "Open NodePorts: $OPEN"
                    for p in $OPEN; do
                      case " $ALLOWED_NODEPORTS " in
                        *" $p "*) ;;
                        *) echo "UNEXPECTED open port: $p - not in the allowlist"; exit 1 ;;
                      esac
                    done
                    echo "Network exposure matches the allowlist."
                '''
            }
        }

        // 11. Start Prometheus/Grafana if paused, and register the app as a metrics target
        stage('Monitoring') {
            steps {
                sh '''
                    kubectl scale deployment --all -n monitoring --replicas=1
                    kubectl rollout status deployment prometheus-kube-prometheus-operator -n monitoring --timeout=300s
                    kubectl rollout status deployment prometheus-grafana -n monitoring --timeout=300s
                    kubectl apply -f k8s/servicemonitor.yaml
                    kubectl get servicemonitor -n devops
                '''
            }
        }
    }

    // 12. Always runs, success or failure: build the readable security report, keep it, email it
    post {
        always {
            withEnv(["BUILD_RESULT=${currentBuild.currentResult}"]) {
                sh 'python3 security/generate_report.py || true'
            }
            archiveArtifacts artifacts: 'security-report.html, gitleaks-report.json, trivy-report.json, nmap-app-report.xml, nmap-nodeports.gnmap',
                             allowEmptyArchive: true
            emailext(
                to: "${NOTIFY_EMAIL}",
                subject: "[Jenkins] ${currentBuild.currentResult}: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                mimeType: 'text/html',
                body: '${FILE,path="security-report.html"}',
                attachmentsPattern: 'security-report.html'
            )
        }
    }
}