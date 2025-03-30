# run flask
# nohup flask --app geekapp run --port=5000 >/dev/null 2>&1 &

# check flask
# ps aux | grep geekapp

# run gunicorn
nohup gunicorn --config gunicorn.py geekapp:app >/dev/null 2>&1 &