pipeline {
    agent any
    
    environment {
        // AWS Account ID (Updated from user input)
        AWS_ACCOUNT_ID = '254800774891' 
        AWS_REGION     = 'us-east-2'
        // ECR Registry URL based on region and account
        ECR_REGISTRY   = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        IMAGE_TAG      = "${BUILD_NUMBER}"
        NAMESPACE      = 'dftp-mcp'
        
        // Optional: Role to assume for deployment
        IAM_ROLE_ARN   = credentials('aws-deployment-role-arn') 
    }

    stages {
        stage('Init') {
            steps {
                script {
                    echo "Starting Build #${BUILD_NUMBER}"
                }
            }
        }

        stage('Login to ECR') {
            steps {
                // Ensure AWS CLI and Docker are configured on the agent
                sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}"
            }
        }

        stage('Build & Push Frontend') {
            steps {
                dir('Frontend') {
                    sh "docker build -t ${ECR_REGISTRY}/dftp-mcp/frontend:${IMAGE_TAG} ."
                    sh "docker push ${ECR_REGISTRY}/dftp-mcp/frontend:${IMAGE_TAG}"
                }
            }
        }

        stage('Build & Push Auth Services') {
            steps {
                dir('Auth_gateway') {
                    // Build Auth Service
                    sh "docker build -f Dockerfile.auth -t ${ECR_REGISTRY}/dftp-mcp/auth-service:${IMAGE_TAG} ."
                    sh "docker push ${ECR_REGISTRY}/dftp-mcp/auth-service:${IMAGE_TAG}"

                    // Build Auth Gateway
                    sh "docker build -f Dockerfile.openresty -t ${ECR_REGISTRY}/dftp-mcp/auth-gateway:${IMAGE_TAG} ."
                    sh "docker push ${ECR_REGISTRY}/dftp-mcp/auth-gateway:${IMAGE_TAG}"
                }
            }
        }

        stage('Deploy to K8s') {
            steps {
                script {
                    // Update Kubernetes Manifests with the new image tag
                    // NOTE: In a real gitops flow, we might push to a separate repo. 
                    // Here we update the local formatting files for application.
                    
                    sh "sed -i 's|dftp-mcp/frontend:latest|${ECR_REGISTRY}/dftp-mcp/frontend:${IMAGE_TAG}|g' k8s/frontend.yaml"
                    sh "sed -i 's|dftp-mcp/auth-service:latest|${ECR_REGISTRY}/dftp-mcp/auth-service:${IMAGE_TAG}|g' k8s/auth-service.yaml"
                    sh "sed -i 's|dftp-mcp/auth-gateway:latest|${ECR_REGISTRY}/dftp-mcp/auth-gateway:${IMAGE_TAG}|g' k8s/auth-gateway.yaml"
                    
                    // Apply Namespace first
                    sh "kubectl apply -f k8s/namespace.yaml"
                    
                    // Apply all other resources
                    sh "kubectl apply -f k8s/ --namespace ${NAMESPACE}"
                }
            }
        }
    }
}
