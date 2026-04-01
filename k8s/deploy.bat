@echo off
REM RAG System K8s Deploy Script (Minikube)
REM Usage: deploy.bat [--skip-build]

setlocal enabledelayedexpansion

echo.
echo ==========================================
echo   RAG System K8s Deploy Script (Minikube)
echo ==========================================
echo.

REM Parse arguments
set SKIP_BUILD=0
if "%1"=="--skip-build" set SKIP_BUILD=1

REM ========================================
REM Step 1: Environment check
REM ========================================

echo [CHECK] 1. Checking environment...

where kubectl >nul 2>&1
if errorlevel 1 (
    echo [ERROR] kubectl not found
    exit /b 1
)

where minikube >nul 2>&1
if errorlevel 1 (
    echo [ERROR] minikube not found
    exit /b 1
)

where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] docker not found
    exit /b 1
)

REM Check minikube status
minikube status >nul 2>&1
if errorlevel 1 (
    echo [START] Starting Minikube...
    minikube start --cpus=4 --memory=8192 --driver=docker
)

set IMAGE_NAME=rag-api
set IMAGE_TAG=latest
set TAR_FILE=%TEMP%\rag-api.tar

echo [OK] Environment check passed

REM ========================================
REM Step 2-4: Build and sync image
REM ========================================

if "%SKIP_BUILD%"=="0" (
    echo.
    echo [BUILD] 2. Building Docker image...
    
    cd /d "%~dp0.."
    docker build -t %IMAGE_NAME%:%IMAGE_TAG% .
    
    if errorlevel 1 (
        echo [ERROR] Image build failed
        exit /b 1
    )
    echo [OK] Image built
    
    echo.
    echo [EXPORT] 3. Exporting image to file...
    docker save %IMAGE_NAME%:%IMAGE_TAG% -o "%TAR_FILE%"
    
    if errorlevel 1 (
        echo [ERROR] Image export failed
        exit /b 1
    )
    echo [OK] Image exported
    
    echo.
    echo [COPY] 4. Copying and loading image to minikube...
    
    minikube cp "%TAR_FILE%" /tmp/rag-api.tar
    
    if errorlevel 1 (
        echo [ERROR] Copy failed
        del "%TAR_FILE%" 2>nul
        exit /b 1
    )
    
    minikube ssh "docker load -i /tmp/rag-api.tar"
    
    if errorlevel 1 (
        echo [ERROR] Image load failed
        del "%TAR_FILE%" 2>nul
        exit /b 1
    )
    
    del "%TAR_FILE%" 2>nul
    minikube ssh "rm -f /tmp/rag-api.tar" 2>nul
    
    echo [OK] Image loaded to minikube
    
    cd /d "%~dp0"
) else (
    echo.
    echo [SKIP] 2-4. Skipping image build (--skip-build)
)

REM ========================================
REM Step 5: Create namespace and config
REM ========================================

echo.
echo [CONFIG] 5. Creating namespace and config...

kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml

echo [OK] Config created

REM ========================================
REM Step 6: Create persistent storage
REM ========================================

echo.
echo [STORAGE] 6. Creating persistent storage...

kubectl apply -f pvc.yaml
timeout /t 10 /nobreak >nul

echo [OK] Storage created

REM ========================================
REM Step 7: Deploy base services
REM ========================================

echo.
echo [DEPLOY] 7. Deploying base services...

kubectl apply -f deployments\postgres.yaml
kubectl apply -f deployments\redis.yaml

echo Waiting for PostgreSQL...
kubectl rollout status deployment/postgres -n rag-system --timeout=180s 2>nul

echo Waiting for Redis...
kubectl rollout status deployment/redis -n rag-system --timeout=180s 2>nul

echo [OK] Base services deployed

REM ========================================
REM Step 8: Deploy vector store and storage
REM ========================================

echo.
echo [DEPLOY] 8. Deploying Milvus and MinIO...

kubectl apply -f deployments\milvus.yaml
kubectl apply -f deployments\minio.yaml

echo Waiting for Milvus (may take 2-3 minutes)...
kubectl rollout status deployment/milvus -n rag-system --timeout=300s 2>nul

echo Waiting for MinIO...
kubectl rollout status deployment/minio -n rag-system --timeout=180s 2>nul

echo [OK] Vector store and storage deployed

REM ========================================
REM Step 9: Deploy RAG API
REM ========================================

echo.
echo [DEPLOY] 9. Deploying RAG API...

kubectl apply -f deployments\rag-api-local.yaml

echo Waiting for RAG API...
kubectl rollout status deployment/rag-api -n rag-system --timeout=180s 2>nul

echo [OK] RAG API deployed

REM ========================================
REM Step 10: Configure Ingress
REM ========================================

echo.
echo [INGRESS] 10. Configuring Ingress...

minikube addons enable ingress 2>nul
kubectl apply -f ingress.yaml

echo [OK] Ingress configured

REM ========================================
REM Done
REM ========================================

echo.
echo ==========================================
echo   Deploy Complete!
echo ==========================================
echo.

echo [STATUS] Pod status:
kubectl get pods -n rag-system

for /f "tokens=*" %%i in ('minikube ip') do set MINIKUBE_IP=%%i

echo.
echo [ACCESS] How to access:
echo.
echo Method 1: Port forwarding (recommended)
echo   kubectl port-forward svc/rag-api-service -n rag-system 8000:8000
echo   Access: http://localhost:8000
echo   Web UI: http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo.
echo Method 2: Minikube Tunnel
echo   Run in new terminal: minikube tunnel
echo   Then access: http://rag-api.local
echo.

echo [COMMANDS] Common commands:
echo   Status:   kubectl get all -n rag-system
echo   Logs:     kubectl logs -f deployment/rag-api -n rag-system
echo   Uninstall: uninstall.bat
echo.

REM ========================================
REM Auto port-forward
REM ========================================

echo.
echo [AUTO] Starting port forwarding automatically...

REM Start port-forward in new windows
start "RAG API Port-Forward" cmd /k "kubectl port-forward svc/rag-api-service -n rag-system 8000:8000"
timeout /t 2 /nobreak >nul
start "MinIO Port-Forward" cmd /k "kubectl port-forward svc/minio-service -n rag-system 9001:9001"

echo.
echo [ACCESS] Access URLs:
echo   Web UI:   http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo   MinIO:    http://localhost:9001
echo.
echo [NOTE] Port forwarding windows have been opened!
echo.