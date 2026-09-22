import requests
from datetime import datetime, timedelta


class TalkAPIError(Exception):
    """Исключение при ошибках работы с API Контур.Толк."""
    pass


class TalkAPI:
    def __init__(self, space: str, api_key: str, timeout: int = 30):
        self.space = space.strip().replace("https://", "").replace(".ktalk.ru", "").strip("/")
        self.base_url = f"https://{self.space}.ktalk.ru/api"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "X-Auth-Token": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as e:
            raise TalkAPIError(f"Ошибка соединения с Толк: {e}") from e

        if not response.ok:
            try:
                details = response.json()
            except ValueError:
                details = response.text
            raise TalkAPIError(
                f"Толк вернул HTTP {response.status_code}: {details}"
            )

        if not response.content:
            return {}

        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    def upsert_room(self, room_name: str, payload: dict):
        """Создать или обновить постоянную комнату (PUT /api/Rooms/{roomName})."""
        return self._request("PUT", f"/Rooms/{room_name}", json=payload)

    def create_meeting(self, organizer_email: str, payload: dict):
        """Создать новую встречу в календаре (POST /api/EmailCalendar/{email})."""
        return self._request("POST", f"/EmailCalendar/{organizer_email}", json=payload)

    def update_meeting(self, organizer_email: str, meeting_id: str, payload: dict):
        """Обновить существующую встречу (PUT /api/EmailCalendar/{email}/{meetingId})."""
        return self._request("PUT", f"/EmailCalendar/{organizer_email}/{meeting_id}", json=payload)

    def get_meetings(
        self,
        organizer_email: str,
        start_date: str = None,
        end_date: str = None,
        take: int = None
    ):
        """
        Получить список встреч.
        Автоматически разбивает интервалы более 7 дней на части по 7 дней.
        """
        if start_date and end_date:
            try:
                s_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                e_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

                if (e_dt - s_dt) > timedelta(days=7):
                    all_meetings = []
                    curr_start = s_dt

                    while curr_start < e_dt:
                        curr_end = min(curr_start + timedelta(days=7), e_dt)

                        params = {
                            "start": curr_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "end": curr_end.strftime("%Y-%m-%dT%H:%M:%SZ")
                        }
                        if take is not None:
                            params["take"] = take

                        res = self._request("GET", f"/EmailCalendar/{organizer_email}", params=params)
                        
                        if isinstance(res, list):
                            all_meetings.extend(res)
                        elif isinstance(res, dict) and "items" in res:
                            all_meetings.extend(res.get("items", []))

                        curr_start = curr_end

                    return all_meetings
            except ValueError:
                pass

        params = {}
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date
        if take is not None:
            params["take"] = take

        return self._request("GET", f"/EmailCalendar/{organizer_email}", params=params)

    def add_attendee(
        self,
        organizer_email: str,
        meeting_id: str,
        attendee_email: str,
        meeting_payload: dict = None
    ):
        """Добавить участника в существующую встречу."""
        if meeting_payload:
            return self.update_meeting(organizer_email, meeting_id, meeting_payload)

        return self._request(
            "POST",
            f"/EmailCalendar/{organizer_email}/{meeting_id}/attendees",
            json={"mailbox": attendee_email, "email": attendee_email}
        )