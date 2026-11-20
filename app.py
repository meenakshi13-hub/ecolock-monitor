from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)

vehicles_db = {
    "KL22A1024": {
        "owner_name": "Meenakshi Nair",
        "phone": "+91 98470 11223",
        "aadhaar_status": "Verified ([Aadhaar Redacted])",
        "vehicle_type": "Car",
        "fuel": "Petrol",
        "puc_expiry": "2027-02-18",
        "latest_reading": None
    },
    "KL01CD4589": {
        "owner_name": "Adhithya Menon",
        "phone": "+91 94460 99887",
        "aadhaar_status": "Verified ([Aadhaar Redacted])",
        "vehicle_type": "Heavy Vehicle",
        "fuel": "Diesel",
        "puc_expiry": "2027-01-10",
        "latest_reading": None
    },
    "KL22B7810": {
        "owner_name": "Aparna Krishnan",
        "phone": "+91 98951 33445",
        "aadhaar_status": "Verified ([Aadhaar Redacted])",
        "vehicle_type": "Two-Wheeler",
        "fuel": "Petrol",
        "puc_expiry": "2026-11-27",
        "latest_reading": None
    },
    "KL07EF3321": {
        "owner_name": "Chandrima Das",
        "phone": "+91 97442 66778",
        "aadhaar_status": "Verified ([Aadhaar Redacted])",
        "vehicle_type": "Car",
        "fuel": "Petrol",
        "puc_expiry": "2026-10-15",
        "latest_reading": None
    },
    "KL09G5120": {
        "owner_name": "Preeti Singh",
        "phone": "+91 94973 44510",
        "aadhaar_status": "Verified ([Aadhaar Redacted])",
        "vehicle_type": "Car",
        "fuel": "CNG",
        "puc_expiry": "2027-03-05",
        "latest_reading": None
    },
    "KL08H9042": {
        "owner_name": "Rahul Dev",
        "phone": "+91 96331 78290",
        "aadhaar_status": "Verified ([Aadhaar Redacted])",
        "vehicle_type": "Light Commercial Vehicle",
        "fuel": "Diesel",
        "puc_expiry": "2026-12-08",
        "latest_reading": None
    }
}

alert_logs = []

LIMITS = {
    "Petrol_2W": {"CO": 3.5, "HC": 4500},
    "Petrol_4W": {"CO": 0.3, "HC": 200},
    "CNG_4W": {"CO": 0.3, "HC": 200},
    "LPG_4W": {"CO": 0.3, "HC": 200},
    "Diesel": {"Smoke_K": 2.45}
}

def evaluate_emissions(v_type, fuel, puc_expiry, readings):
    days_left = (datetime.strptime(puc_expiry, "%Y-%m-%d").date() - datetime.now().date()).days
    expired = days_left < 0
    due_soon = 0 <= days_left <= 30

    if fuel == "Diesel":
        limit = LIMITS["Diesel"]["Smoke_K"]
        val = float(readings.get("smoke_k", 0))
        ratio = val / limit
        if ratio > 1.0 or expired:
            reason = f"Smoke opacity ({val:.2f} m⁻¹) exceeds limit ({limit} m⁻¹)." if ratio > 1.0 else f"PUC expired ({abs(days_left)} days overdue)."
            return "FAIL - Servicing / Renewal Required", f"{reason} Clean fuel injectors, replace air filter, and visit an authorised PUC centre."
        elif ratio >= 0.8 or due_soon:
            return "WARNING - Service / Renew Soon", f"Opacity at {int(ratio*100)}% of limit; PUC due in {days_left} days."
        return "PASS - Within Limits", f"Diesel exhaust opacity within CMVR norms. PUC valid ({days_left} days remaining)."
    else:
        key = "Petrol_2W" if v_type == "Two-Wheeler" else "Petrol_4W"
        co_lim = LIMITS[key]["CO"]
        hc_lim = LIMITS[key]["HC"]
        co = float(readings.get("co", 0))
        hc = float(readings.get("hc", 0))
        if co > co_lim or hc > hc_lim or expired:
            issues = []
            if co > co_lim:
                issues.append(f"CO ({co:.2f}% vs {co_lim}%)")
            if hc > hc_lim:
                issues.append(f"HC ({int(hc)} ppm vs {hc_lim} ppm)")
            if expired:
                issues.append(f"PUC expired ({abs(days_left)} days overdue)")
            return "FAIL - Servicing / Renewal Required", f"Alert: {', '.join(issues)}. Inspect air filter, spark plugs, O2 sensor, and catalytic converter."
        elif co >= 0.8 * co_lim or hc >= 0.8 * hc_lim or due_soon:
            return "WARNING - Service / Renew Soon", f"Readings nearing threshold or PUC due in {days_left} days. Schedule preventive tuning."
        return "PASS - Within Limits", f"Spark-ignition emissions within CMVR norms. PUC valid ({days_left} days remaining)."

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/register", methods=["POST"])
def register_vehicle():
    data = request.json
    vnum = data["vehicle_number"].upper().replace(" ", "").replace("-", "")
    vehicles_db[vnum] = {
        "owner_name": data["owner_name"],
        "phone": data["phone"],
        "aadhaar_status": "Verified ([Aadhaar Redacted])",
        "vehicle_type": data["vehicle_type"],
        "fuel": data["fuel"],
        "puc_expiry": data["puc_expiry"],
        "latest_reading": None
    }
    return jsonify({"status": "registered", "vehicle_number": vnum})

@app.route("/api/sensor-data", methods=["POST"])
def receive_sensor_data():
    data = request.json
    vnum = data["vehicle_number"].upper().replace(" ", "").replace("-", "")
    if vnum not in vehicles_db:
        return jsonify({"error": "Vehicle not registered"}), 404

    vehicle = vehicles_db[vnum]
    verdict, advice = evaluate_emissions(vehicle["vehicle_type"], vehicle["fuel"], vehicle["puc_expiry"], data)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    record = {
        "timestamp": timestamp,
        "co": data.get("co"),
        "hc": data.get("hc"),
        "co2": data.get("co2"),
        "o2": data.get("o2"),
        "lambda": data.get("lambda"),
        "smoke_k": data.get("smoke_k"),
        "hsu": data.get("hsu"),
        "verdict": verdict,
        "advice": advice
    }
    vehicle["latest_reading"] = record

    alert_logs.insert(0, {
        "time": timestamp,
        "vehicle": vnum,
        "owner": vehicle["owner_name"],
        "phone": vehicle["phone"],
        "danger": verdict.startswith("FAIL"),
        "message": f"EcoLock Notification ({vnum}): {verdict}. {advice}"
    })

    return jsonify({"status": "processed", "record": record})

@app.route("/api/state")
def get_state():
    return jsonify({"vehicles": vehicles_db, "alerts": alert_logs})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
