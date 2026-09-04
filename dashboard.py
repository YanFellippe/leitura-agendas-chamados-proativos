from flask import Flask, render_template, jsonify, request
import os
import threading
import time as _time
from services.calendar import get_events, get_rooms
from rules.rules import is_valid_meeting
from utils.time_utils import to_local_time, format_time, is_happening_now
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__, template_folder="dashboard/templates", static_folder="dashboard/static")

# Salas monitoradas no dashboard
MONITORED_ROOMS = {email.lower() for email in [
    "salareuniaodti@agu.gov.br",
    "videopgf-gabinete1@AGU.GOV.BR",
    "videodpof-sede3@AGU.GOV.BR",
    "videosgct-sede1@AGU.GOV.BR",
    "videodti-Sede2@AGU.GOV.BR",
    "videoceagu-sede2@AGU.GOV.BR",
    "videosad-sede2@AGU.GOV.BR",
    "videodgdp-sede2@AGU.GOV.BR",
    "videosge-sede1@AGU.GOV.BR",
    "videocsagu-sede1@AGU.GOV.BR",
    "videosames-sede2@AGU.GOV.BR",
    "videocodip-sede2@AGU.GOV.BR",
    "videocgu1-sede1@AGU.GOV.BR",
    "videocgu2-sede1@AGU.GOV.BR",
    "videoouvidoria-sede1@AGU.GOV.BR",
    "videoaspar-sede1@AGU.GOV.BR",
    "videobackup-dti1@AGU.GOV.BR",
    "videoesagu-sede2@AGU.GOV.BR",
    "video-pu-pr@AGU.GOV.BR",
    "video-psfpel@AGU.GOV.BR",
    "videopgf-sede1@AGU.GOV.BR",
    "video-psf-cco@AGU.GOV.BR",
    "video-pf-ap@AGU.GOV.BR",
    "video-pfsc@AGU.GOV.BR",
    "video-cjusc@AGU.GOV.BR",
    "videoesagu-sede3@AGU.GOV.BR",
    "video-cju-ap@AGU.GOV.BR",
    "video-uea-ap@AGU.GOV.BR",
    "videoascom-sede1@AGU.GOV.BR",
    "video-gab-esagu@AGU.GOV.BR",
    "video-psfscz@AGU.GOV.BR",
    "video-psf-psu-srm@AGU.GOV.BR",
    "video-psf-lda@AGU.GOV.BR",
    "video-uea-am@AGU.GOV.BR",
    "video-pf-pu-cju-to@AGU.GOV.BR",
    "video-gab1@AGU.GOV.BR",
    "video-agu1@AGU.GOV.BR",
    "video.sad3-spo@AGU.GOV.BR",
    "video-agu-ro@AGU.GOV.BR",
    "video-pf-mt@AGU.GOV.BR",
    "videosga-sede2@AGU.GOV.BR",
    "gabagureuniao.sgcs@AGU.GOV.BR",
    "pru1.videoconf1@AGU.GOV.BR",
    "videosgcs-sede1@AGU.GOV.BR",
    "video-pu-ap@AGU.GOV.BR",
    "videocgu3-sede1@AGU.GOV.BR",
    "video-cxs@AGU.GOV.BR",
    "video-cjurs@AGU.GOV.BR",
    "video-nh@AGU.GOV.BR",
    "video-prf4@AGU.GOV.BR",
    "videocgau.gab-sede2@AGU.GOV.BR",
    "videodlog-sede2@AGU.GOV.BR",
    "prf1.videoconf3@AGU.GOV.BR",
    "prf1.videoconf2@AGU.GOV.BR",
    "video-psf-mga@AGU.GOV.BR",
    "videocgu-sede1@AGU.GOV.BR",
    "video-psf-bnu@AGU.GOV.BR",
    "videogabagu-sede1@AGU.GOV.BR",
    "video-pu-sc@AGU.GOV.BR",
    "videopgfgab-sede1@AGU.GOV.BR",
    "adjuntos.gab@AGU.GOV.BR",
    "video.prf-spo@AGU.GOV.BR",
    "video.eagu-spo@AGU.GOV.BR",
    "videopgu-sede1@AGU.GOV.BR",
    "videopnrjpgu-sede1@AGU.GOV.BR",
    "video-psf-jve@AGU.GOV.BR",
    "video-pf-pr@AGU.GOV.BR",
    "video-psf-cvl@AGU.GOV.BR",
    "video-psfsan@AGU.GOV.BR",
    "auditorio.saddf@AGU.GOV.BR",
    "videogab.sge-sede1@AGU.GOV.BR",
    "videogab.coord.sede1@AGU.GOV.BR",
    "videogab.sgeprojsed1@AGU.GOV.BR",
    "videogab.senor@AGU.GOV.BR",
    "video.psfsma@AGU.GOV.BR",
    "videopgu-gab-sede1@AGU.GOV.BR",
    "videosad2r-andar13@AGU.GOV.BR",
    "videocjurj-andar11@AGU.GOV.BR",
    "videopru2r-andar12@AGU.GOV.BR",
    "videoprf2r-andar15@AGU.GOV.BR",
    "videosgcs-gab-sede1@AGU.GOV.BR",
    "videopgf-gabinete2@AGU.GOV.BR",
    "videopgf-gabinete3@AGU.GOV.BR",
    "videopgf-gabinete4@AGU.GOV.BR",
    "dpro.sede3-video@AGU.GOV.BR",
    "videogabcgest-sede1@AGU.GOV.BR",
    "SalaDTI-Infraestrutura@agudf.onmicrosoft.com",
    "sadrj.auditorio@AGU.GOV.BR",
]}


def get_monitored_rooms():
    """Retorna as salas da lista de monitoramento.
    
    Salas encontradas na Graph API vêm com displayName.
    Salas não encontradas são incluídas com o email como identificador.
    """
    all_rooms = get_rooms()
    
    # Monta mapa dos dados da Graph API (email -> objeto)
    graph_map = {r.get("emailAddress", "").lower(): r for r in all_rooms}
    
    result = []
    for email in MONITORED_ROOMS:
        if email in graph_map:
            # Sala encontrada na Graph API — usa dados completos
            result.append(graph_map[email])
        else:
            # Sala não está na Graph API — inclui com dados mínimos
            result.append({"emailAddress": email, "displayName": email.split("@")[0]})
    
    return result


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
    rooms = get_monitored_rooms()
    results = []
    # Limita concorrência para evitar MailboxConcurrency limit
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Processa em lotes para não sobrecarregar a API
        batch_size = 10
        for i in range(0, len(rooms), batch_size):
            batch = rooms[i:i + batch_size]
            futures = {executor.submit(fetch_room_events, room): room for room in batch}
            for f in as_completed(futures):
                results.append(f.result())
            # Pequena pausa entre lotes para evitar throttling
            if i + batch_size < len(rooms):
                _time.sleep(0.5)
    return results


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

    rooms = get_monitored_rooms()
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
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Processa em lotes para evitar MailboxConcurrency limit
        batch_size = 10
        indexed_rooms = list(enumerate(rooms))
        for i in range(0, len(indexed_rooms), batch_size):
            batch = indexed_rooms[i:i + batch_size]
            futures = [executor.submit(fetch_room_calendar, item) for item in batch]
            for f in as_completed(futures):
                events.extend(f.result())
            if i + batch_size < len(indexed_rooms):
                _time.sleep(0.5)

    return jsonify(events)


@app.route("/api/rooms/status")
def api_rooms_status():
    from core.graph import get as graph_get
    from core.auth import get_token
    import requests as req

    rooms_data = graph_get("/places/microsoft.graph.room")
    all_rooms = rooms_data.get("value", [])
    graph_map = {r.get("emailAddress", "").lower(): r for r in all_rooms}
    
    # Inclui todas as salas monitoradas (com ou sem dados da Graph API)
    rooms = []
    for email in MONITORED_ROOMS:
        if email in graph_map:
            rooms.append(graph_map[email])
        else:
            rooms.append({"emailAddress": email, "displayName": email.split("@")[0]})
    
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

    # Busca a próxima reunião de hoje da sala e usa o horário de início dela
    # como base da vistoria (em vez do horário do clique).
    meeting_start = None
    meeting_subject = None
    meeting_organizer_email = organizer_email
    if room_email:
        try:
            events = get_events(room_email)
        except Exception:
            events = []

        candidates = []
        for event in events:
            if not is_valid_meeting(event):
                continue
            ev_start = to_local_time(
                event["start"]["dateTime"], event["start"].get("timeZone", "UTC")
            )
            candidates.append((ev_start, event))

        # Prioriza reuniões que ainda não começaram; senão, pega a mais próxima do dia
        future = sorted((c for c in candidates if c[0] >= now), key=lambda c: c[0])
        chosen = future[0] if future else (
            min(candidates, key=lambda c: abs((c[0] - now).total_seconds())) if candidates else None
        )
        if chosen:
            meeting_start, ev = chosen
            meeting_subject = ev.get("subject")
            meeting_organizer_email = (
                organizer_email
                or ev.get("organizer", {}).get("emailAddress", {}).get("address", "")
            )

    if meeting_start is None:
        return jsonify({
            "error": "Nenhuma reunião encontrada hoje para esta sala. "
                     "A vistoria proativa é vinculada a uma reunião agendada."
        }), 404

    try:
        result = create_ticket(
            room=room_name,
            subject=meeting_subject or "Vistoria manual solicitada via dashboard",
            start_time=meeting_start,
            email=room_email,
            organizer_email=meeting_organizer_email,
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
