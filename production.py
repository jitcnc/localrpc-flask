from server import app

if __name__ == "__main__":
    app.run(threaded=True, host='127.0.0.1', port=5000)
