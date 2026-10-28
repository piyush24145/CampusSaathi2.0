@echo off
echo ========================================================
echo  Deploying CampusSathi AI to Google Cloud Run
echo ========================================================

:: Check if gcloud is installed
where gcloud >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Google Cloud SDK (gcloud) is not installed.
    echo Please install it from: https://cloud.google.com/sdk/docs/install
    pause
    exit /b 1
)

set SERVICE_NAME=campussathi-ai
set REGION=asia-south1
set MEMORY=2Gi
set CPU=1

echo Service: %SERVICE_NAME%
echo Region:  %REGION%
echo Memory:  %MEMORY%
echo CPU:     %CPU%
echo.

echo Starting deployment using Google Cloud Build and Cloud Run...
gcloud run deploy %SERVICE_NAME% ^
    --source . ^
    --region %REGION% ^
    --platform managed ^
    --allow-unauthenticated ^
    --memory %MEMORY% ^
    --cpu %CPU% ^
    --port 8080

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================================
    echo  Deployment Successful!
    echo  Copy the Service URL above and paste it into:
    echo  1. Frontend Vercel Environment Variables: VITE_API_URL
    echo  2. Or inside the CampusSathi UI: Server Settings (Cloud Run icon)
    echo ========================================================
) else (
    echo [ERROR] Deployment failed. Please check the logs above.
)
pause
