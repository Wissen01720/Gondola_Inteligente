@echo off
IF NOT EXIST venv (
    echo Creando entorno virtual...
    python -m venv venv
)

call venv\Scripts\activate
echo Instalando dependencias...
pip install -q -r requirements.txt

echo Iniciando Scapder Vision...
python -m app.main
