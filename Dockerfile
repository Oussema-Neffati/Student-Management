# Stage 1: Build de l'application avec Maven
FROM maven:3.9.9-eclipse-temurin-17 AS build

WORKDIR /app

# Copier le pom.xml
COPY pom.xml .

# Télécharger les dépendances Maven
RUN mvn dependency:go-offline -B

# Copier le code source
COPY src ./src

# Compiler et packager l'application
RUN mvn clean package -DskipTests

# Stage 2: Image finale légère avec seulement le JAR
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# Copier le JAR depuis le stage de build
COPY --from=build /app/target/*.jar app.jar

# Exposer le port de l'application Spring Boot
EXPOSE 8080

# Variables d'environnement
ENV JAVA_OPTS="-Xmx512m -Xms256m"

# Démarrer l'application
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/actuator/health || exit 1