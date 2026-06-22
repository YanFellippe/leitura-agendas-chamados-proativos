def is_valid_meeting(event):

    if event.get("isCancelled"):
        return False

    if event.get("isAllDay"):
        return False

    if event.get("showAs") not in ["busy", "oof"]:
        return False

    if not event.get("location", {}).get("displayName"):
        return False

    subject = (event.get("subject") or "").lower()
    bloqueadas = ["chamando", "evento automático", "recorrência"]
    if any(b in subject for b in bloqueadas):
        return False

    return True