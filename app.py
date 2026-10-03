from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template, request

from classshift.domain import PublicStatus
from classshift.input_validator import ValidationError, parse_outages
from classshift.loader import load_json, load_dataset
from classshift.service import recover

BASE_DIR = Path(__file__).resolve().parent
DEMO_PATH = BASE_DIR / "data" / "demo_school.json"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=128 * 1024, JSON_SORT_KEYS=False)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/demo")
    def api_demo():
        raw = load_json(DEMO_PATH)
        raw.pop("outages", None)
        return jsonify(raw)

    @app.post("/api/recover")
    def api_recover():
        if not request.is_json:
            return jsonify({"status": PublicStatus.INVALID_INPUT.value, "validated": False, "message": "Content-Type must be application/json."}), 400
        body = request.get_json(silent=True)
        if type(body) is not dict:
            return jsonify({"status": PublicStatus.INVALID_INPUT.value, "validated": False, "message": "Request body must be a JSON object."}), 400
        if set(body) != {"outages"}:
            return jsonify({"status": PublicStatus.INVALID_INPUT.value, "validated": False, "message": "Request must contain only the outages field."}), 400
        try:
            dataset = load_dataset(DEMO_PATH)
            outages = parse_outages(body["outages"], dataset)
            result = recover(dataset, outages)
        except ValidationError as exc:
            result = {"status": PublicStatus.INVALID_INPUT.value, "validated": False, "message": str(exc)}
        except Exception:
            return jsonify({"status": PublicStatus.INTERNAL_ERROR.value, "validated": False, "message": "The server could not process the request."}), 500
        code = 200 if result["status"] in {PublicStatus.OPTIMAL.value, PublicStatus.INFEASIBLE.value} else 400 if result["status"] == PublicStatus.INVALID_INPUT.value else 500
        return jsonify(result), code

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify({"status": PublicStatus.INVALID_INPUT.value, "validated": False, "message": "Request body is too large."}), 413

    @app.errorhandler(500)
    def internal(_error):
        return jsonify({"status": PublicStatus.INTERNAL_ERROR.value, "validated": False, "message": "The server could not process the request."}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
