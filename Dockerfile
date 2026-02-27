# Image Java légère pour runtime
FROM eclipse-temurin:21-jre-alpine

# Répertoire de travail
WORKDIR /app

# Copier le livrable généré par Maven
COPY target/student-management-0.0.1-SNAPSHOT.jar app.jar

# Exposer le port
EXPOSE 8080

# Lancer l'application
ENTRYPOINT ["java", "-jar", "app.jar"]