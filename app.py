import uuid
import streamlit as st
from datetime import date, time, datetime, timedelta
from talk_api import TalkAPI, TalkAPIError

st.set_page_config(
    page_title="Контур.Толк — Планирование по единой ссылке",
    page_icon="🎥",
    layout="wide"
)

st.title("🎥 Генератор единой ссылки и планирование встреч")
st.caption("Автоматическая генерация уникальной постоянной ссылки, интерактивный выбор любых дат и создание встреч.")

# ---------- Функция генерации уникального идентификатора комнаты ----------
def generate_unique_room_name() -> str:
    # Идентификатор комнаты содержит только латинские буквы и цифры в нижнем регистре
    return f"room{uuid.uuid4().hex[:8]}"

# Инициализация комнаты в session_state, если она еще не создана
if "room_name" not in st.session_state:
    st.session_state["room_name"] = generate_unique_room_name()

if "selected_dates" not in st.session_state:
    st.session_state["selected_dates"] = set()

# ---------- Боковая панель: Параметры подключения ----------
with st.sidebar:
    st.header("⚙️ Авторизация API")
    space = st.text_input(
        "Имя пространства",
        value=st.secrets.get("TALK_SPACE", ""),
        placeholder="myspace",
        help="Поддомен из адреса https://myspace.ktalk.ru",
    )
    api_key = st.text_input(
        "API-ключ",
        value=st.secrets.get("TALK_API_KEY", ""),
        type="password",
    )
    organizer_email = st.text_input(
        "Email организатора",
        value=st.secrets.get("TALK_ORGANIZER_EMAIL", ""),
        placeholder="organizer@example.ru",
    )

if not space or not api_key or not organizer_email:
    st.info("👈 Заполните имя пространства, API-ключ и Email организатора в боковой панели.")
    st.stop()

api = TalkAPI(space=space, api_key=api_key)

# ---------- 1. Генерация и настройка единой ссылки ----------
st.subheader("1. Единая ссылка на встречу")

col_gen1, col_gen2, col_gen3 = st.columns([2, 1, 3])

with col_gen1:
    room_name_input = st.text_input(
        "Идентификатор комнаты (roomName)",
        value=st.session_state["room_name"],
        help="Сгенерирован автоматически. Можно отредактировать вручную или перегенерировать кнопкой.",
    )
    # Обновляем состояние при ручном редактировании
    st.session_state["room_name"] = room_name_input.strip().lower()

with col_gen2:
    st.write("") # Вертикальный отступ для выравнивания кнопки
    st.write("")
    if st.button("🎲 Перегенерировать", use_container_width=True):
        st.session_state["room_name"] = generate_unique_room_name()
        st.rerun()

clean_space = space.strip().replace("https://", "").replace(".ktalk.ru", "").strip("/")
room_url = f"https://{clean_space}.ktalk.ru/{st.session_state['room_name']}"

with col_gen3:
    st.write("**Сгенерированная единая ссылка:**")
    st.code(room_url, language="text")

st.divider()

# ---------- 2. Интерактивный выбор произвольных дат ----------
st.subheader("2. Выберите даты проведения в календаре")

col_date_input, col_date_btn = st.columns([2, 1])

with col_date_input:
    picked_date = st.date_input("Выберите дату", value=date.today())

with col_date_btn:
    st.write("")
    st.write("")
    if st.button("➕ Добавить дату", use_container_width=True):
        st.session_state["selected_dates"].add(picked_date)

# Отображение добавленных дат
sorted_dates = sorted(list(st.session_state["selected_dates"]))

if sorted_dates:
    st.write(f"**Выбранные даты ({len(sorted_dates)} шт.):**")
    
    # Выводим даты в сетке с кнопками для быстрого удаления
    cols = st.columns(min(len(sorted_dates), 5))
    for idx, d in enumerate(sorted_dates):
        col_idx = idx % 5
        with cols[col_idx]:
            if st.button(f"❌ {d.strftime('%d.%m.%Y')}", key=f"del_{d}"):
                st.session_state["selected_dates"].remove(d)
                st.rerun()

    if st.button("🗑️ Очистить список дат"):
        st.session_state["selected_dates"].clear()
        st.rerun()
else:
    st.warning("Список дат пуст. Выберите дату в календаре выше и нажмите «➕ Добавить дату».")

st.divider()

# ---------- 3. Параметры встреч ----------
st.subheader("3. Настройки и участники")

col_time, col_dur = st.columns(2)
with col_time:
    start_time = st.time_input("Время начала", value=time(18, 0))
with col_dur:
    duration = st.number_input("Длительность (минут)", min_value=15, max_value=480, value=60, step=15)

subject = st.text_input("Название встречи", value="Онлайн-занятие")
description = st.text_area("Описание встречи", value="")
emails_raw = st.text_area(
    "Email приглашаемых внешних участников (по одному в строке)",
    placeholder="student1@example.com\nstudent2@example.com",
)

st.divider()

# ---------- 4. Создание единой комнаты и списка встреч ----------
if st.button("🚀 Создать комнату и запланировать встречи по единой ссылке", type="primary", use_container_width=True):
    current_room_name = st.session_state["room_name"]
    
    if not current_room_name:
        st.error("Идентификатор комнаты не может быть пустым!")
        st.stop()
        
    if not sorted_dates:
        st.error("Добавьте хотя бы одну дату в список!")
        st.stop()

    emails = [x.strip() for x in emails_raw.splitlines() if x.strip()]

    # 1. Создание / инициализация единой комнаты в Контур.Толк
    with st.spinner("Создание и активация единой комнаты..."):
        try:
            api.upsert_room(
                current_room_name,
                {
                    "title": subject,
                    "description": f"Единая комната для встреч: {subject}",
                    "enableLobby": False,
                },
            )
            st.toast("Единая комната успешно активирована!", icon="✅")
        except TalkAPIError as e:
            st.error(f"Ошибка при создании комнаты: {e}")
            st.stop()

    # 2. Создание встреч на каждую выбранную дату
    success_count = 0
    errors = []

    with st.spinner(f"Создание встреч по выбранным датам ({len(sorted_dates)})..."):
        for d in sorted_dates:
            start_dt = datetime.combine(d, start_time)
            end_dt = start_dt + timedelta(minutes=int(duration))

            payload = {
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "timezone": "GMT+3",
                "subject": subject,
                "description": description,
                "roomName": current_room_name,
                "allowAnonymous": True,
                "isRecurring": False,
                "requiredExternalAttendeesEmails": emails,
            }

            try:
                api.create_meeting(organizer_email, payload)
                success_count += 1
            except TalkAPIError as e:
                errors.append(f"{d.strftime('%d.%m.%Y')}: {e}")

    if success_count > 0:
        st.success(f"🎉 Запланировано встреч: **{success_count} из {len(sorted_dates)}**!")
        st.info(f"📍 **Единая постоянная ссылка на все встречи:** [{room_url}]({room_url})")

    if errors:
        st.error("Ошибки при добавлении встреч на некоторые даты:")
        for err in errors:
            st.write(f"- {err}")