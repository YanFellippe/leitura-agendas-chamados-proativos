from flask import Flask, render_template, jsonify, request
import os
import threading
import time as _time
from services.calendar import get_events, get_rooms
from rules.rules import is_valid_meeting
from utils.time_utils import to_local_time, format_time, is_happening_now
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__, template_folder="dashboard/templates", static_folder="dashboard/static")


def fetch_room_events(room):
    email = room.get("emailAddress")
    name  = room.get("displayName", email)
    try:
        events = get_events(email)
    except Exception:
        events = []

    meetings = []
    for event in events:
        if not is_valid_meeting(event):
            continue
        start    = to_local_time(event["start"]["dateTime"], event["start"].get("timeZone", "UTC"))
        end      = to_local_time(event["end"]["dateTime"],   event["end"].get("timeZone", "UTC"))
        happening = is_happening_now(start, end)
        meetings.append({
            "subject":  event.get("subject", "Sem título"),
            "location": event.get("location", {}).get("displayName", name),
            "start":    format_time(start),
            "end":      format_time(end),
            "happening": happening,
            "organizer": event.get("organizer", {}).get("emailAddress", {}).get("address", ""),
        })

    return {"room": name, "email": email, "meetings": meetings}


def fetch_all_events():
    rooms = get_rooms()
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fetch_room_events, room): room for room in rooms}
        return [f.result() for f in as_completed(futures)]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/calendar")
def api_calendar():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    start_param = request.args.get("start")
    end_param   = request.args.get("end")

    try:
        start = datetime.fromisoformat(start_param[:19]).replace(tzinfo=BRAZIL_TZ) if start_param else None
        end   = datetime.fromisoformat(end_param[:19]).replace(tzinfo=BRAZIL_TZ)   if end_param   else None
    except Exception:
        start = end = None

    rooms = get_rooms()
    events = []
    colors = [
        "#6366f1", "#22c55e", "#f59e0b", "#3b82f6",
        "#ec4899", "#14b8a6", "#f97316", "#a855f7"
    ]

    def fetch_room_calendar(args):
        i, room = args
        email = room.get("emailAddress")
        name  = room.get("displayName", email)
        color = colors[i % len(colors)]
        try:
            room_events = get_events(email, start=start, end=end)
        except Exception:
            room_events = []

        result = []
        for event in room_events:
            if not is_valid_meeting(event):
                continue
            ev_start = to_local_time(event["start"]["dateTime"], event["start"].get("timeZone", "UTC"))
            ev_end   = to_local_time(event["end"]["dateTime"],   event["end"].get("timeZone", "UTC"))
            result.append({
                "title": event.get("subject", "Sem título"),
                "start": ev_start.isoformat(),
                "end":   ev_end.isoformat(),
                "color": color,
                "extendedProps": {
                    "room":     name,
                    "email":    email,
                    "location": event.get("location", {}).get("displayName", name),
                }
            })
        return result

    events = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(fetch_room_calendar, (i, room)) for i, room in enumerate(rooms)]
        for f in as_completed(futures):
            events.extend(f.result())

    return jsonify(events)


@app.route("/api/rooms/status")
def api_rooms_status():
    from core.graph import get as graph_get
    from core.auth import get_token
    import requests as req

    rooms_data = graph_get("/places/microsoft.graph.room")
    rooms = rooms_data.get("value", [])
    token = get_token()

    result = []
    for room in rooms:
        email = room.get("emailAddress")
        name  = room.get("displayName", email)

        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/Sao_Paulo"))
        start_str = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str   = now.replace(hour=23, minute=59, second=59, microsecond=0).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        url = f"https://graph.microsoft.com/v1.0/users/{email}/calendarView?startDateTime={start_str}&endDateTime={end_str}"
        resp = req.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)

        if resp.status_code == 200:
            count = len(resp.json().get("value", []))
            result.append({"name": name, "email": email, "status": "ok", "events": count, "error": None})
        else:
            try:
                error_msg = resp.json().get("error", {}).get("message", resp.text)
            except Exception:
                error_msg = resp.text
            result.append({"name": name, "email": email, "status": "error", "events": 0, "error": error_msg})

    return jsonify(result)


@app.route("/api/history")
def api_history():
    import json as _json
    from utils.daily_control import CONTROL_FILE

    days  = int(request.args.get("days", 7))
    from datetime import date, timedelta
    cutoff = str(date.today() - timedelta(days=days - 1))

    try:
        if not os.path.exists(CONTROL_FILE):
            return jsonify([])
        with open(CONTROL_FILE, "r") as f:
            data = _json.load(f)
    except Exception:
        return jsonify([])

    rows = []
    for day, rooms in sorted(data.items(), reverse=True):
        if day < cutoff:
            continue
        for room, value in rooms.items():
            # Extrai nome limpo da sala (remove sufixo de antecipado)
            display_room = room.split("|antecipado|")[0] if "|antecipado|" in room else room
            anticipated = "|antecipado|" in room

            # Novo formato: lista de chamados
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict):
                        rows.append({
                            "date": day,
                            "room": display_room,
                            "request_id": entry.get("request_id") or None,
                            "forced": entry.get("forced", False),
                            "anticipated": entry.get("anticipated", anticipated),
                        })
                    elif isinstance(entry, (int, str)) and entry not in (True, False, 0, ""):
                        rows.append({"date": day, "room": display_room, "request_id": entry, "forced": False, "anticipated": anticipated})
                    else:
                        rows.append({"date": day, "room": display_room, "request_id": None, "forced": False, "anticipated": anticipated})
            # Formato antigo: valor único (compatibilidade)
            elif isinstance(value, dict):
                rows.append({
                    "date": day,
                    "room": display_room,
                    "request_id": value.get("request_id") or None,
                    "forced": value.get("forced", False),
                    "anticipated": value.get("anticipated", anticipated),
                })
            elif isinstance(value, (int, str)) and value not in (True, False, 0, ""):
                rows.append({"date": day, "room": display_room, "request_id": value, "forced": False, "anticipated": anticipated})
            else:
                rows.append({"date": day, "room": display_room, "request_id": None, "forced": False, "anticipated": anticipated})

    return jsonify(rows)


@app.route("/api/rooms")
def api_rooms():
    return jsonify(fetch_all_events())


@app.route("/api/force-ticket", methods=["POST"])
def api_force_ticket():
    """Força a abertura de um chamado de vistoria para uma sala."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from services.invgate import create_ticket
    from utils.daily_control import DailyControl

    data = request.get_json() or {}
    room_name = data.get("room", "").strip()
    room_email = data.get("email", "").strip()
    organizer_email = data.get("organizer_email", "").strip()

    if not room_name:
        return jsonify({"error": "Nome da sala é obrigatório"}), 400

    now = datetime.now(ZoneInfo("America/Sao_Paulo"))

    try:
        result = create_ticket(
            room=room_name,
            subject="Vistoria manual solicitada via dashboard",
            start_time=now,
            email=room_email,
            organizer_email=organizer_email,
        )
        # Registra no controle diário
        control = DailyControl()
        control.mark_as_opened(room_name, request_id=int(result.get("request_id") or 0), forced=True)
        control.flush()

        return jsonify({
            "success": True,
            "request_id": result.get("request_id"),
            "message": f"Chamado #{result.get('request_id')} criado com sucesso",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Inicia o loop de abertura de chamados em background
    def monitor_loop():
        from app import run
        while True:
            run()
            print("⏳ Aguardando próxima execução...\n")
            _time.sleep(300)

    t = threading.Thread(target=monitor_loop, daemon=True, name="monitor")
    t.start()
    print("🤖 Monitor de chamados iniciado em background")

    app.run(host="0.0.0.0", port=5000, debug=False)
