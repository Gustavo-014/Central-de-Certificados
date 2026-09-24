@echo off
chcp 65001 >nul
title Central de Certificados - Brobot

rem Garante que o diretorio atual seja a pasta onde o .bat esta localizado
cd /d "%~dp0"

echo ======================================================
echo       CENTRAL DE CERTIFICADOS - BROBOT
echo ======================================================
echo.

rem 1. Localiza o executavel do Python no sistema
set "PY_CMD="
python --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=python"
) else (
    py --version >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=py"
    )
)

if "%PY_CMD%"=="" (
    echo [ERRO] Python nao foi encontrado no seu computador!
    echo.
    echo Para usar este aplicativo:
    echo 1. Baixe e instale o Python em: https://www.python.org/downloads/
    echo 2. IMPORTANTE: Na instalacao, marque a opcao "Add Python to PATH".
    echo 3. Apos instalar, execute este arquivo novamente.
    echo ======================================================
    echo.
    pause
    exit /b 1
)

rem 2. Verifica se o ambiente virtual .venv ja existe
if not exist ".venv\Scripts\activate.bat" (
    echo [1/3] Primeira execucao detectada neste computador!
    echo [*] Criando ambiente virtual (.venv)...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
    
    echo [*] Ativando ambiente virtual...
    call ".venv\Scripts\activate.bat"
    
    echo [2/3] Instalando bibliotecas necessarias...
    echo [*] Isso acontece apenas uma vez na primeira execucao!
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar as dependencias. Verifique sua conexao com a internet.
        pause
        exit /b 1
    )
    echo.
    echo [*] Instalacao concluida com sucesso!
) else (
    echo [*] Ambiente virtual encontrado. Ativando...
    call ".venv\Scripts\activate.bat"
)

echo [3/3] Iniciando aplicacao Streamlit na porta 8502...
echo.
echo * O seu navegador padrao sera aberto em: http://localhost:8502
echo * Para encerrar a aplicacao, feche esta janela ou pressione Ctrl+C.
echo.
echo ======================================================
echo.

python -m streamlit run app.py --server.port 8502 --server.headless false

if errorlevel 1 (
    echo.
    echo ======================================================
    echo [ERRO] A aplicacao foi encerrada com erro.
    echo ======================================================
    echo.
    pause
)
