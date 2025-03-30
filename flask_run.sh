# run flask
nohup flask --app geekapp run --host=0.0.0.0 --port=5000 >/dev/null 2>&1 &

# check flask
# ps aux | grep geekapp