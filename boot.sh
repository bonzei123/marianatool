#!/bin/sh
# boot.sh

# 1. Datenbank migrieren
echo "Starte DB Migration..."
flask db upgrade

# 2. Prüfen, ob Migration erfolgreich war
if [ $? -eq 0 ]; then
    echo "Migration erfolgreich."
else
    echo "Migration FEHLGESCHLAGEN!"
    exit 1
fi

# 3. Die eigentliche App starten (Gunicorn)
# exec ist wichtig, damit gunicorn die Prozess-ID 1 übernimmt
exec gunicorn --bind 0.0.0.0:5000 run:app -timeout 120