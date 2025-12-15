FROM eclipse-temurin:21-jre-noble
WORKDIR /app
COPY target/status-0.0.1-SNAPSHOT.jar app.jar
EXPOSE 8088
ENTRYPOINT ["java", "-jar", "app.jar"]
