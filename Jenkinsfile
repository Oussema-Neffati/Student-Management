pipeline {
    agent any

    environment {
        IMAGE_NAME = "oussemaneffati/student-management"
        KUBECONFIG = "/var/lib/jenkins/.kube/config"
        NOTIFY_EMAIL = "oussema.neffati@esprit.tn"   // who receives the build report
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        // DevSecOps - PRE-COMMIT: same Gitleaks rules as the local pre-commit hook,
        // enforced on the server so a commit made without the hook is still caught.
        stage('Secrets Scan (Gitleaks)') {
            steps {
                sh '''
                    gitleaks git . --redact \
                      --report-format json --report-path gitleaks-report.json
                '''
            }
        }

        stage('Build Application') {
            steps {
                sh 'mvn clean package -DskipTests'
            }
        }

        // SAST (COMMIT column) - already covered by SonarQube
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

        stage('Build Docker Image') {
            steps {
                script {
                    docker.build("${IMAGE_NAME}:latest")
                }
            }
        }

        // DevSecOps - COMMIT: Container Security.
        // The image is scanned BEFORE it is pushed, so a vulnerable image never reaches Docker Hub.
        stage('Container Scan (Trivy)') {
            steps {
                sh '''
                    # Full report (HIGH + CRITICAL), kept as a build artifact
                    trivy image --no-progress --scanners vuln \
                      --severity HIGH,CRITICAL \
                      --format table --output trivy-report.txt \
                      ${IMAGE_NAME}:latest

                    # Security gate: fail only on CRITICAL vulnerabilities that have a fix available
                    trivy image --no-progress --scanners vuln \
                      --severity CRITICAL --ignore-unfixed \
                      --exit-code 1 \
                      ${IMAGE_NAME}:latest
                '''
            }
        }

        stage('Push Docker Image') {
            steps {
                script {
                    docker.withRegistry('https://registry.hub.docker.com', 'dockerhub-credentials') {
                        docker.image("${IMAGE_NAME}:latest").push()
                    }
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                sh '''
                    kubectl rollout restart deployment student-management-deployment -n devops
                    kubectl rollout status deployment student-management-deployment -n devops
                '''
            }
        }

        stage('Verification') {
            steps {
                sh '''
                    echo "Checking deployment status..."
                    kubectl get pods -n devops -l app=student-management
                    NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[0].address}')
                    curl -sf --retry 10 --retry-delay 10 --retry-all-errors \
                      "http://$NODE_IP:30080/student/actuator/health"
                '''
            }
        }

        // Monitoring: Prometheus scrapes the app's /actuator/prometheus endpoint, Grafana shows it
        stage('Monitoring') {
            steps {
                sh '''
                    # Bring the Prometheus/Grafana stack up (it can be paused to save RAM between sessions);
                    # the operator then recreates Prometheus and Alertmanager by itself
                    kubectl scale deployment --all -n monitoring --replicas=1
                    kubectl rollout status deployment prometheus-kube-prometheus-operator -n monitoring --timeout=300s
                    kubectl rollout status deployment prometheus-grafana -n monitoring --timeout=300s

                    # Register the application as a Prometheus scrape target
                    kubectl apply -f k8s/servicemonitor.yaml
                    kubectl get servicemonitor -n devops
                '''
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'gitleaks-report.json, trivy-report.txt', allowEmptyArchive: true

            // E-mail notification: sent on success AND failure, with the security reports attached
            emailext(
                to: "${NOTIFY_EMAIL}",
                subject: "[Jenkins] ${currentBuild.currentResult}: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                mimeType: 'text/html',
                body: """
                    <h2>${env.JOB_NAME} - build #${env.BUILD_NUMBER}: ${currentBuild.currentResult}</h2>
                    <p>Duration: ${currentBuild.durationString}</p>
                    <p>Console output: <a href="${env.BUILD_URL}console">${env.BUILD_URL}console</a></p>
                    <p>Attached: Gitleaks (secrets) and Trivy (container vulnerabilities) reports.</p>
                """,
                attachmentsPattern: 'gitleaks-report.json, trivy-report.txt'
            )
        }
        success {
            echo "Deployment successful!"
        }
        failure {
            echo "Pipeline failed - check the security reports in the build artifacts."
        }
    }
}
