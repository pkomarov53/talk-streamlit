import requests


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