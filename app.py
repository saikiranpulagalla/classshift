from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from classshift.domain import PublicStatus
from classshift.input_validator import ValidationError, parse_outages
from classshift.loader import dataset_to_public_dict, load_dataset
from classshift.service import recover

BASE_DIR = Path(__file__).resolve().parent
DEMO_PATH = BASE_DIR / "data" / "demo_school.json"
LOGGER = logging.getLogger(__name__)


def _internal_error_response():
    return jsonify({
        "status": PublicStatus.INTERNAL_ERROR.value,
        "validated": False,
        "message": "The server could not process the request.",
    }), 500


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=128 * 1024, JSON_SORT_KEYS=False)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/demo")
    def api_demo():
        try:
            dataset = load_dataset(DEMO_PATH)
            return jsonify(dataset_to_public_dict(dataset))
        except Exception:
            LOGGER.exception("Failed to load validated synthetic demo dataset")
            return _internal_error_response()

    @app.post("/api/recover")
    def api_recover():
        if not request.is_json:
            return jsonify({
                "status": PublicStatus.INVALID_INPUT.value,
                "validated": False,
                "message": "Content-Type must be application/json.",
            }), 400
        body = request.get_json(silent=True)
        if type(body) is not dict:
            return jsonify({
                "status": PublicStatus.INVALID_INPUT.value,
                "validated": False,
                "message": "Request body must be a JSON object.",
            }), 400
        if set(body) != {"outages"}:
            return jsonify({
                "status": PublicStatus.INVALID_INPUT.value,
                "validated": False,
                "message": "Request must contain only the outages field.",
            }), 400
        try:
            dataset = load_dataset(DEMO_PATH)
            outages = parse_outages(body["outages"], dataset)
            result = recover(dataset, outages)
        except ValidationError as exc:
            result = {
                "status": PublicStatus.INVALID_INPUT.value,
                "validated": False,
                "message": str(exc),
            }
        except Exception:
            LOGGER.exception("Unhandled recovery API error")
            return _internal_error_response()

        if result["status"] in {PublicStatus.OPTIMAL.value, PublicStatus.INFEASIBLE.value}:
            code = 200
        elif result["status"] == PublicStatus.INVALID_INPUT.value:
            code = 400
        else:
            code = 500
        return jsonify(result), code

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify({
            "status": PublicStatus.INVALID_INPUT.value,
            "validated": False,
            "message": "Request body is too large.",
        }), 413

    @app.errorhandler(500)
    def internal(_error):
        return _internal_error_response()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
