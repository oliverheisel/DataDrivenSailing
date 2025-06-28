from flask import Flask, request, jsonify
import logging
from pingcheck import ping_device
from rsync import rsync_data
from fileprep_boat import export_sqlite_to_csv  # Import function from fileprep_boat.py

# initialize logger
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/ping", methods=["GET"])
def pingfunc():
    """
    check if a device is reachable via ping.
    example: GET /ping?device=boat1
    """
    device = request.args.get("device")
    if not device:
        logger.error("ping_error: missing 'device' parameter")
        return jsonify({"error": "Missing 'device' parameter"}), 400

    if not device.endswith(".local"):
        device += ".local"

    result = ping_device(device)
    logger.debug("ping_result: %s", result)
    return jsonify(result)

@app.route("/rsync", methods=["GET"])
def trigger_rsync():
    """
    trigger rsync from a remote device to the local system.
    example: GET /rsync?device=boat1
    """
    device = request.args.get("device")
    if not device:
        logger.error("rsync_error: missing 'device' parameter")
        return jsonify({"error": "Missing 'device' parameter", "id": 'device'}), 400

    result = rsync_data(device)
    logger.debug("rsync_result: %s", result)
    return jsonify(result)

@app.route("/export", methods=["GET"])
def trigger_export():
    """
    trigger SQLite to CSV conversion for a specific database file.
    example: GET /export?filename=datalog_boat1.db
    """
    filename = request.args.get("filename")
    if not filename:
        logger.error("export_error: missing 'filename' parameter")
        return jsonify({"error": "Missing 'filename' parameter"}), 400

    if not filename.startswith("datalog_") or not filename.endswith(".db"):
        logger.error("export_error: invalid filename format: %s", filename)
        return jsonify({"error": "Invalid filename format. Expected: datalog_<boatname>.db"}), 400

    result = export_sqlite_to_csv(filename)
    logger.debug("export_result: %s", result)
    
    if result["status"] == "error":
        return jsonify(result), 500  # return error with status code 500
    
    return jsonify(result), 200

if __name__ == "__main__":
    app.run(host="172.17.0.1", port=5000)  # run Flask API on port 5000
