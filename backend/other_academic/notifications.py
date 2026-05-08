from other_academic.models import Notification


def create_notification(user, verb, description="", module="Other Academic Procedures", flag="notification"):
    if not user:
        return None
    payload = {"module": module, "flag": flag}
    return Notification.objects.create(
        user=user,
        verb=verb,
        description=description,
        data=str(payload),
    )
