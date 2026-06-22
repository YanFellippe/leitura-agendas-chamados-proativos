from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from services.calendar import get_events
from services.invgate import create_ticket
from rules.rules import is_valid_meeting
from utils.time_utils import to_local_time, calculate_visit_time, format_time, BRAZIL_TZ
from utils.daily_control import DailyControl
from config.rooms import load_rooms
import time

MAX_WORKERS = 5  # requisições paralelas à Graph API

# Reuniões do dia seguinte que começam até este horário geram chamado antecipado
EARLY_MEETING_HOUR = 9


def process_room(email: str, control: DailyControl, events=None) -> None:
    """Processa uma sala: busca eventos, valida e abre chamado se necessário."""
    print(f"📡 Verificando agenda: {email}")

    try:
        if events is None:
            events = get_events(email)

        if not events:
            print(f"   ➤ Nenhuma reunião encontrada. [{email}]")
            return

        for event in events:
            if not is_valid_meeting(event):
                continue

            location = event.get("location", {}).get("displayName")
            if not location:
                continue

            if control.already_opened(location):
                print(f"   ⏭️  Chamado já aberto hoje para: {location}")
                return

            start    = to_local_time(event["start"]["dateTime"], event["start"].get("timeZone", "UTC"))
            end      = to_local_time(event["end"]["dateTime"],   event["end"].get("timeZone", "UTC"))
            vistoria = calculate_visit_time(start)

            print("   📅 Reunião agendada encontrada!")
            print(f"   📌 Título: {event.get('subject')}")
            print(f"   📍 Sala:   {location}")
            organizer_email = event.get("organizer", {}).get("emailAddress", {}).get("address", "")
            print(f"   👤 Organizador: {organizer_email or 'N/A'}")
            print(f"   ⏰ Início: {format_time(start)}")
            print(f"   ⏳ Fim:    {format_time(end)}")
            print(f"   🛠️  Vistoria: {format_time(vistoria)}")

            try:
                organizer_email = event.get("organizer", {}).get("emailAddress", {}).get("address", "")
                organizer_name = event.get("organizer", {}).get("emailAddress", {}).get("name", "")
                result = create_ticket(location, event.get("subject"), start, email=email, organizer_email=organizer_email, organizer_name=organizer_name)
                req_id = int(result.get("request_id") or result.get("id") or 0)
                control.mark_as_opened(location, request_id=req_id)
            except Exception as e:
                print(f"   ⚠️  Erro ao criar chamado InvGate: {e}")
                control.mark_as_opened(location)

            print("   ✅ Pronto para ação\n")
            return  # um chamado por sala por dia

    except Exception as e:
        print(f"⚠  Erro ao processar sala {email}: {e}")


def check_next_day_early_meetings(rooms: list[str], control: DailyControl) -> None:
    """
    Verifica reuniões do dia seguinte que começam até EARLY_MEETING_HOUR (8h).
    Se houver, abre o chamado hoje para que a vistoria seja feita com antecedência.
    """
    now = datetime.now(BRAZIL_TZ)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    # +1 minuto de margem para incluir reuniões que começam exatamente no horário limite
    tomorrow_cutoff = tomorrow.replace(hour=EARLY_MEETING_HOUR, minute=1)

    print(f"\n🔮 Verificando reuniões de amanhã ({tomorrow.strftime('%d/%m/%Y')}) até às {EARLY_MEETING_HOUR}h...\n")

    def fetch_early(email: str):
        try:
            events = get_events(email, start=tomorrow, end=tomorrow_cutoff)
            if not events:
                return
            for event in events:
                if not is_valid_meeting(event):
                    continue
                location = event.get("location", {}).get("displayName")
                if not location:
                    continue

                start = to_local_time(event["start"]["dateTime"], event["start"].get("timeZone", "UTC"))
                # Chave única: inclui a data da reunião pra não conflitar com chamados do dia atual
                control_key = f"{location}|antecipado|{start.strftime('%Y-%m-%d')}"

                if control.already_opened(control_key):
                    print(f"   ⏭️  Chamado antecipado já aberto para: {location} ({start.strftime('%d/%m/%Y')})")
                    continue

                organizer_email = event.get("organizer", {}).get("emailAddress", {}).get("address", "")
                organizer_name = event.get("organizer", {}).get("emailAddress", {}).get("name", "")

                print(f"   🌅 Reunião cedo amanhã: {event.get('subject')} às {format_time(start)} em {location}")

                try:
                    result = create_ticket(
                        location,
                        event.get("subject"),
                        start,
                        email=email,
                        organizer_email=organizer_email,
                        organizer_name=organizer_name,
                    )
                    req_id = int(result.get("request_id") or result.get("id") or 0)
                    control.mark_as_opened(control_key, request_id=req_id, anticipated=True)
                    print(f"   ✅ Chamado antecipado criado para {location}")
                except Exception as e:
                    print(f"   ⚠️  Erro ao criar chamado antecipado: {e}")
                    control.mark_as_opened(control_key, anticipated=True)
        except Exception as e:
            print(f"   ⚠️  Erro ao verificar dia seguinte para {email}: {e}")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_early, email): email for email in rooms}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"⚠  Falha inesperada: {e}")


def run():
    t0 = time.time()
    print("\n🔎 Iniciando verificação de reuniões...\n")

    rooms   = load_rooms()
    control = DailyControl()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_room, email, control): email for email in rooms}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                email = futures[future]
                print(f"⚠  Falha inesperada em {email}: {e}")
            print("-" * 50)

    control.flush()

    # Verifica reuniões do dia seguinte que começam cedo (até 8h)
    check_next_day_early_meetings(rooms, control)

    elapsed = time.time() - t0
    print(f"\n⏱️  Ciclo concluído em {elapsed:.1f}s para {len(rooms)} sala(s)\n")


if __name__ == "__main__":
    while True:
        run()
        print("⏳ Aguardando próxima execução...\n")
        time.sleep(300)
