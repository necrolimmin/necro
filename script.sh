pkill gunicorn


gunicorn --workers 3 --bind unix:/home/necro/gunicorn.sock bunker.wsgi:application --daemon

systemctl restart nginx.service
