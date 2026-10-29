# Image Java légère pour runtime
FROM eclipse-temurin:21-jre-alpine

# Sécurité : appliquer les correctifs Alpine disponibles (ex: brotli-libs)
RUN apk upgrade --no-cache

# Sécurité : ne pas exécuter l'application en root
RUN addgroup -S app && adduser -S app -G app

# Répertoire de travail
WORKDIR /app

# Copier le livrable généré par Maven
COPY --chown=app:app target/student-management-0.0.1-SNAPSHOT.jar app.jar

USER app

# Exposer le port de l'application (server.port=8089)
EXPOSE 8089

# Lancer l'application
ENTRYPOINT ["java", "-jar", "app.jar"]