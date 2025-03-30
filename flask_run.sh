# run flask
# nohup flask --app geekapp run --port=5000 >/dev/null 2>&1 &

# check flask
# ps aux | grep geekapp

# run gunicorn
nohup gunicorn -w 1 --bind 127.0.0.1:5000 --reload geekapp:app --timeout 120 --access-logfile - --error-logfile - >/dev/null 2>&1 &
