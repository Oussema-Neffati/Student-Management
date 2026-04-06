pipeline {
    agent any

    environment {
        IMAGE_NAME = "oussemaneffati/student-management"
        KUBECONFIG = "/var/lib/jenkins/.kube/config"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Application') {
            steps {
                sh 'mvn clean package -DskipTests'
            }
        }

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

        stage('Push Docker Image') {
            steps {
                script {
                    docker.withRegistry('https://registry.hub.docker.com', 'dockerhub-credentials') {
                        docker.image("${IMAGE_NAME}:latest").push()
                    }
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
                        echo "Application is accessible at:"
                        minikube service student-management-service -n devops --url
                    '''
                }
            }
        }

        post {
            success {
                echo "✅ Deployment successful!"
            }
            failure {
                echo "❌ Deployment failed!"
            }
        }
    }
}