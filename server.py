import datetime
import os
import platform
import psutil
import time

from socket import gethostname, AF_INET, AF_INET6

from flask import Flask, jsonify, request

app = Flask(__name__)

LONGPOLL_TIMEOUT = 60
LONGPOLL_QUEUE = []

@app.route('/status/')
def status():
    status = {
        "os": os.name,
        "system": platform.system(),
        "release": platform.release(),
        "storage": [],
        "hostname": gethostname(),
        "net_addresses": [],
        "cpu_physicalcount": psutil.cpu_count(logical=False),
        "ts": int(datetime.datetime.now().timestamp()),
        "ts_lastboot": psutil.boot_time()
    }

    svmem = psutil.virtual_memory()
    for k in svmem._fields:
        v = getattr(svmem, k)
        if k.endswith("percent"):
            status["memory_" + k] = v
        else:
            status["memory_" + k + "_GB"] = round(v / (1<<30), 3)

    sdiskpart = psutil.disk_partitions(all=False)
    for part in sdiskpart:
        mountpoint = part.mountpoint
        usage = psutil.disk_usage(mountpoint)

        # https://github.com/giampaolo/psutil/blob/master/scripts/disk_usage.py
        if os.name == 'nt':
            if 'cdrom' in part.opts or part.fstype == '':
                continue

        info = {
            "mountpoint": mountpoint,
            "device": part.device,
            "usage_percent": usage.percent,
            "usage_GB": round(usage.used / (1<<30), 3),
            "total_GB": round(usage.total / (1<<30), 3)}

        status["storage"].append(info)

    for snicname, snicaddrs in psutil.net_if_addrs().items():
        for snicaddr in snicaddrs:
            if snicaddr.family in (AF_INET, AF_INET6):
                addr = snicaddr.address
                if not addr.startswith(
                    ("169.254.", "fe80::", "127.", "::1")):

                    status["net_addresses"].append(addr)

    if status["system"].lower() == "linux":
        # platform-specific targetting to alleviate bugginess
        status["hw_temps"] = psutil.sensors_temperatures()
        status["load_average"] = [
            x / psutil.cpu_count() * 100
            for x in psutil.getloadavg()]

    return jsonify(status)

@app.route('/longpoll/')
def longpoll():
    try:
        timeout = int(request.args.get("timeout") or LONGPOLL_TIMEOUT)
        if timeout < 1 or timeout > 600:
            raise ValueError("invalid")
    except:
        timeout = LONGPOLL_TIMEOUT

    started = time.time()
    while True:
        elapsed = time.time() - started
        if (LONGPOLL_QUEUE
              or elapsed > timeout):

            r = jsonify({
                "started": started,
                "ended": time.time(),
                "elapsed": elapsed,
                "timeout": timeout,
                "QUEUE": LONGPOLL_QUEUE
            })

            LONGPOLL_QUEUE.clear()
            return r

        time.sleep(0.5)

@app.route('/longpoll/debug/noop/')
def longpoll_noop():
    LONGPOLL_QUEUE.append("NOOP")
    return "debug"

@app.after_request
def add_header(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

if __name__ == "__main__":
    app.run(threaded=True, debug=True, host='0.0.0.0')
