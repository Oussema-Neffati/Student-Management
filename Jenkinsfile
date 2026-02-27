pipeline {
    agent any
    
    environment {
        // Configuration Java et Maven
        JAVA_HOME = '/usr/lib/jvm/java-21-openjdk-amd64'
        M2_HOME = '/opt/maven'
        PATH = "/opt/maven/bin:/usr/lib/jvm/java-21-openjdk-amd64/bin:${env.PATH}"
        
        // Configuration Docker Hub
        DOCKER_HUB_CREDENTIALS = credentials('dockerhub-credentials')
        DOCKER_IMAGE_NAME = 'oussemaneffati/studentmanager'
        DOCKER_IMAGE_TAG = "${BUILD_NUMBER}"
    }
    
    stages {
        stage('Checkout') {
            steps {
                echo 'Récupération du code source depuis Git...'
                checkout scm
            }
        }
        
        stage('Build & Compile') {
            steps {
                echo 'Compilation de l\'application avec Maven...'
                sh '/opt/maven/bin/mvn clean compile'
            }
        }
        
        stage('Run Unit Tests') {
            steps {
                echo 'Exécution des tests unitaires...'
                sh '/opt/maven/bin/mvn test'
            }
            post {
                always {
                    junit '**/target/surefire-reports/*.xml'
                }
            }
        }
        
        stage('Package Application') {
            steps {
                echo 'Packaging de l\'application (JAR)...'
                sh '/opt/maven/bin/mvn package -DskipTests'
            }
        }
        
        stage('Build Docker Image') {
            steps {
                echo 'Construction de l\'image Docker...'
                script {
                    dockerImage = docker.build("${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}")
                    sh "docker tag ${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG} ${DOCKER_IMAGE_NAME}:latest"
                }
            }
        }
        
        stage('Test Docker Image') {
            steps {
                echo 'Test de l\'image Docker...'
                script {
                    sh """
                        docker run -d --name test-container -p 8081:8080 ${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}
                        sleep 15
                        docker logs test-container
                    """
                }
            }
            post {
                always {
                    sh 'docker stop test-container || true'
                    sh 'docker rm test-container || true'
                }
            }
        }
        
        stage('Push to Docker Hub') {
            steps {
                echo 'Push de l\'image vers Docker Hub...'
                script {
                    docker.withRegistry('https://registry.hub.docker.com', 'dockerhub-credentials') {
                        sh "docker push ${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}"
                        sh "docker push ${DOCKER_IMAGE_NAME}:latest"
                    }
                }
            }
        }
        
        stage('Clean Up') {
            steps {
                echo 'Nettoyage des images Docker locales...'
                sh """
                    docker rmi ${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG} || true
                    docker rmi ${DOCKER_IMAGE_NAME}:latest || true
                """
            }
        }
    }
    
    post {
        success {
            echo '=========================================='
            echo 'Pipeline exécuté avec succès !'
            echo '=========================================='
            echo "Image Docker : ${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}"
            echo "Docker Hub : https://hub.docker.com/r/${DOCKER_IMAGE_NAME}"
            echo '=========================================='
        }
        failure {
            echo '=========================================='
            echo 'Le pipeline a échoué !'
            echo 'Vérifiez les logs ci-dessus.'
            echo '=========================================='
        }
        always {
            echo 'Nettoyage final...'
            cleanWs()
        }
    }
}