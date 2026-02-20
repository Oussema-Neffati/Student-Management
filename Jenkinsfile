pipeline {
    agent any
    environment {
        JAVA_HOME = '/usr/lib/jvm/java-21-openjdk-amd64'
        M2_HOME = '/opt/maven'
        PATH = "/opt/maven/bin:/usr/lib/jvm/java-21-openjdk-amd64/bin:${env.PATH}"
    }
    stages {
        stage('Checkout GIT') {
            steps {
                echo 'Récupération du code...'
                git branch: 'main',
                    url: 'https://github.com/Oussema-Neffati/Student-Management.git'
            }
        }
        stage('Build Maven') {
            steps {
                echo 'Compilation du projet...'
                sh '/opt/maven/bin/mvn clean install -DskipTests'
            }
        }
    }
}