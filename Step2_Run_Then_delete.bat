@echo off
:: Create a virtual environment in a folder named "venv"
echo Creating virtual environment...
python -m venv venv

:: Activate the virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

:: Upgrade pip to the latest version
echo Upgrading pip...
pip install --upgrade pip

:: Install the wheel package
echo Installing wheel...
pip install wheel

:: Install requirements from requirements.txt
echo Installing requirements from requirements.txt...
pip install -r requirements.txt

:: Deactivate the virtual environment after installation
echo Deactivating virtual environment...
call venv\Scripts\deactivate

echo Setup complete! All packages have been installed successfully.
pause
