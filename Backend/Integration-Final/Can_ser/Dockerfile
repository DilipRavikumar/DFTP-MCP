# Multi-stage build for Can_ser Service
FROM maven:3.9.4-eclipse-temurin-17 AS builder

# Set working directory
WORKDIR /app

# Copy pom.xml first for better Docker layer caching
COPY pom.xml .

# Download dependencies (this layer will be cached if pom.xml doesn't change)
RUN mvn dependency:go-offline -B

# Copy source code
COPY src ./src

# Build the application (skip tests for faster build)
RUN mvn clean package -DskipTests

# Production stage - use smaller JRE image
FROM eclipse-temurin:17-jre-alpine

# Install curl and wget for health checks
RUN apk add --no-cache curl wget

# Create non-root user for security
RUN addgroup -g 1000 appuser && \
    adduser -D -u 1000 -G appuser appuser

# Set working directory
WORKDIR /app

# Create temp directory for file processing
RUN mkdir -p ./temp && chown -R appuser:appuser ./temp

# Copy JAR file from builder stage
COPY --from=builder /app/target/*.jar app.jar

# Copy any additional resources if needed
COPY --from=builder /app/target/classes/rules ./rules/

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8086

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8086/actuator/health || exit 1

# Run the application
ENTRYPOINT ["java", "-Djava.security.egd=file:/dev/./urandom", "-jar", "app.jar"]