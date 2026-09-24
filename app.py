import uuid
import calendar
import streamlit as st
from datetime import date, time, datetime, timedelta, timezone
from talk_api import TalkAPI, TalkAPIError

# Конфигурация страницы
st.set_page_config(
    page_title="Контур.Толк — Сервис планирования",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------------------------
# MATERIAL DESIGN STYLES (СВЕТЛАЯ ТЕМА)
# ------------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Принудительный сброс цветов под светлую тему */
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background-color: #F8FAFC !important;
        color: #0F172A !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    /* Заголовки, текст, метки полей */
    h1, h2, h3, h4, h5, h6, p, label, span, div, .stMarkdown {
        color: #0F172A !important;
    }

    /* Подписи и второстепенный текст */
    .stCaption, caption, small {
        color: #64748B !important;
    }

    /* Боковая панель */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0 !important;
    }

    /* Поля ввода (Text input, Textarea, Select, Number input, Date input) */
    div[data-baseweb="input"], 
    div[data-baseweb="base-input"],
    div[data-baseweb="textarea"],
    div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
        color: #0F172A !important;
    }

    input, textarea {
        color: #0F172A !important;
        background-color: #FFFFFF !important;
    }

    /* Код и ссылки */
    .stCodeBlock, code {
        background-color: #F1F5F9 !important;
        color: #0F172A !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
    }

    /* Вкладки в стиле Material */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #E2E8F0;
        padding: 6px;
        border-radius: 12px;
        border: 1px solid #CBD5E1;
    }

    .stTabs [data-baseweb="tab"] {
        height: 42px;
        border-radius: 8px;
        padding: 0 20px;
        font-weight: 500;
        font-size: 0.95rem;
        color: #475569 !important;
        border: none !important;
        background-color: transparent;
    }

    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #2563EB !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        font-weight: 600;
    }

    /* Кнопки Material */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        padding: 0.5rem 1.25rem !important;
        transition: all 0.15s ease-in-out !important;
    }

    /* Карточки метрик */
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0F172A;
        margin-top: 4px;
    }

    .metric-label {
        font-size: 0.85rem;
        font-weight: 500;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Бейджи участников */
    .badge-chip {
        display: inline-flex;
        align-items: center;
        background-color: #EFF6FF;
        color: #1D4ED8 !important;
        border: 1px solid #BFDBFE;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.85rem;
        font-weight: 500;
        margin: 3px 4px 3px 0;
    }

    .badge-org {
        display: inline-flex;
        align-items: center;
        background-color: #ECFDF5;
        color: #047857 !important;
        border: 1px solid #A7F3D0;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.85rem;
        font-weight: 500;
    }

    /* Скрытие дефолтных элементов */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Часовой пояс Москва/GMT+3
MSK_TZ = timezone(timedelta(hours=3))

# ---------- Вспомогательные функции ----------
def parse_datetime_to_msk(dt_input) -> datetime:
    """Преобразует ISO-строку или datetime из UTC в Московское время (GMT+3)."""
    if not dt_input:
        return dt_input
    
    if isinstance(dt_input, str):
        dt = datetime.fromisoformat(dt_input.replace("Z", "+00:00"))
    else:
        dt = dt_input

    if dt.tzinfo is not None:
        dt = dt.astimezone(MSK_TZ).replace(tzinfo=None)
        
    return dt


def extract_organizer(item: dict, default_org: str) -> str:
    """Извлекает организатора встречи с поддержкой всех полей API."""
    org_val = item.get("organizer") or item.get("organizerEmail") or item.get("author") or default_org
    if isinstance(org_val, dict):
        name = (org_val.get("name") or "").strip()
        email = org_val.get("mailbox") or org_val.get("email")
        
        user_obj = org_val.get("user")
        if isinstance(user_obj, dict) and not email:
            email = user_obj.get("email")

        if name and email:
            return f"{name} ({email})"
        return email or name or default_org
    return str(org_val)


def extract_attendees(item: dict) -> list:
    """Собирает всех участников из всех возможных полей ответа API."""
    attendees = []
    
    keys_to_check = [
        "requiredAttendees",
        "optionalAttendees",
        "requiredExternalAttendeesEmails",
        "optionalExternalAttendeesEmails",
        "requiredInternalAttendeesEmails",
        "optionalInternalAttendeesEmails",
        "attendees",
        "participants",
        "members",
        "listeners"
    ]

    for key in keys_to_check:
        val = item.get(key)
        if not val or not isinstance(val, list):
            continue

        for entry in val:
            label = None
            if isinstance(entry, str):
                label = entry
            elif isinstance(entry, dict):
                email = entry.get("mailbox") or entry.get("email") or entry.get("userEmail")
                name = entry.get("name")
                
                user_obj = entry.get("user")
                if isinstance(user_obj, dict):
                    if not email:
                        email = user_obj.get("email")
                    if not name:
                        fn = (user_obj.get("firstname") or "").strip()
                        sn = (user_obj.get("surname") or "").strip()
                        pn = (user_obj.get("patronymic") or "").strip()
                        full_n = " ".join(filter(None, [fn, sn, pn]))
                        if full_n:
                            name = full_n
                
                if name:
                    name = name.strip()

                if name and email:
                    label = f"{name} ({email})"
                elif name:
                    label = name
                elif email:
                    label = email

            if label and label not in attendees:
                attendees.append(label)

    return attendees


def generate_unique_room_name() -> str:
    """Генерация уникального идентификатора комнаты."""
    return f"room{uuid.uuid4().hex[:8]}"


def calculate_max_simultaneous(meetings: list) -> int:
    """Вычисление максимального количества одновременных встреч за день."""
    if not meetings:
        return 0

    events = []
    for m in meetings:
        start_dt = m["start"]
        end_dt = m["end"]

        if isinstance(start_dt, str):
            start_dt = parse_datetime_to_msk(start_dt)
        if isinstance(end_dt, str):
            end_dt = parse_datetime_to_msk(end_dt)

        events.append((start_dt, 1))
        events.append((end_dt, -1))

    events.sort(key=lambda x: (x[0], x[1]))

    max_simultaneous = 0
    current_simultaneous = 0
    for _, delta in events:
        current_simultaneous += delta
        if current_simultaneous > max_simultaneous:
            max_simultaneous = current_simultaneous

    return max_simultaneous


# ---------- Инициализация session_state ----------
if "room_name" not in st.session_state:
    st.session_state["room_name"] = generate_unique_room_name()

if "selected_dates" not in st.session_state:
    st.session_state["selected_dates"] = set()

if "created_meetings" not in st.session_state:
    st.session_state["created_meetings"] = []

# ---------- Боковая панель: Настройки подключения ----------
with st.sidebar:
    st.markdown("### ⚙️ Авторизация")
    st.caption("Параметры подключения к вашей организации в Контур.Толк")
    
    space = st.text_input(
        "Пространство",
        value=st.secrets.get("TALK_SPACE", ""),
        placeholder="myspace",
        help="Поддомен из адреса https://myspace.ktalk.ru",
    )
    api_key = st.text_input(
        "API Key",
        value=st.secrets.get("TALK_API_KEY", ""),
        type="password",
    )
    organizer_email = st.text_input(
        "Email организатора",
        value=st.secrets.get("TALK_ORGANIZER_EMAIL", ""),
        placeholder="organizer@example.ru",
    )

if not space or not api_key or not organizer_email:
    st.info("👈 Заполните параметры подключения в боковой панели для начала работы.")
    st.stop()

api = TalkAPI(space=space, api_key=api_key)

# Header приложения
st.markdown("## 🎥 Сервис планирования Контур.Толк")
st.caption("Единая панель управления онлайн-занятиями, вебинарами и расписанием")

# Основные вкладки
tab_plan, tab_calendar = st.tabs(["🗓 Планирование встреч", "📆 Календарь и Мониторинг"])

# ==============================================================================
# ВКЛАДКА 1: ЗАПЛАНИРОВАТЬ ВСТРЕЧИ
# ==============================================================================
with tab_plan:
    st.markdown("#### 1. Ссылка на единую комнату")
    col_gen1, col_gen2 = st.columns([3, 1])

    with col_gen1:
        room_name_input = st.text_input(
            "Идентификатор комнаты (roomName)",
            value=st.session_state["room_name"],
            help="Уникальное имя постоянной комнаты.",
        )
        st.session_state["room_name"] = room_name_input.strip().lower()

    with col_gen2:
        st.write("")
        st.write("")
        if st.button("🎲 Обновить ID", use_container_width=True):
            st.session_state["room_name"] = generate_unique_room_name()
            st.rerun()

    clean_space = space.strip().replace("https://", "").replace(".ktalk.ru", "").strip("/")
    room_url = f"https://{clean_space}.ktalk.ru/{st.session_state['room_name']}"

    st.code(room_url, language="text")

    st.markdown("---")

    st.markdown("#### 2. Выбор дат проведения")
    col_date_input, col_date_btn = st.columns([3, 1])

    with col_date_input:
        picked_date = st.date_input("Выберите дату проведения", value=date.today(), key="picked_date_input")

    with col_date_btn:
        st.write("")
        st.write("")
        if st.button("➕ Добавить в список", use_container_width=True):
            st.session_state["selected_dates"].add(picked_date)

    sorted_dates = sorted(list(st.session_state["selected_dates"]))

    # Значения времени и длительности по умолчанию из session_state
    default_start_time = st.session_state.get("global_start_time", time(18, 0))
    default_duration = st.session_state.get("global_duration", 60)

    if sorted_dates:
        col_d_title, col_d_clear = st.columns([3, 1])
        with col_d_title:
            st.markdown(f"**Выбранные даты ({len(sorted_dates)}):**")
        with col_d_clear:
            if st.button("🗑 Очистить все даты", type="secondary", use_container_width=True):
                st.session_state["selected_dates"].clear()
                st.rerun()

        weekdays_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

        for d in sorted_dates:
            d_str = d.strftime("%d.%m.%Y")
            is_custom = st.session_state.get(f"use_custom_{d}", False)

            if is_custom:
                c_time = st.session_state.get(f"time_{d}", default_start_time)
                c_dur = st.session_state.get(f"dur_{d}", default_duration)
                header_text = f"📅 {d_str} ({weekdays_ru[d.weekday()]}) — ⏰ {c_time.strftime('%H:%M')}, {c_dur} мин (индивидуально)"
            else:
                header_text = f"📅 {d_str} ({weekdays_ru[d.weekday()]}) — ⏰ {default_start_time.strftime('%H:%M')}, {default_duration} мин (по умолчанию)"

            with st.expander(header_text, expanded=is_custom):
                col_chk, col_del = st.columns([3, 1])
                with col_chk:
                    use_custom = st.checkbox(
                        "Задать индивидуальное время и длительность для этой даты",
                        value=is_custom,
                        key=f"use_custom_{d}"
                    )
                with col_del:
                    if st.button("🗑 Удалить дату", key=f"del_{d}", use_container_width=True):
                        st.session_state["selected_dates"].remove(d)
                        st.rerun()

                if use_custom:
                    col_t, col_dur_item = st.columns(2)
                    with col_t:
                        st.time_input(
                            "Время начала (по МСК)",
                            value=st.session_state.get(f"time_{d}", default_start_time),
                            key=f"time_{d}"
                        )
                    with col_dur_item:
                        st.number_input(
                            "Длительность (минут)",
                            min_value=15,
                            max_value=480,
                            value=st.session_state.get(f"dur_{d}", default_duration),
                            step=15,
                            key=f"dur_{d}"
                        )
                else:
                    st.caption(f"Используются общие параметры из разд. 3: начало в **{default_start_time.strftime('%H:%M')}**, длительность **{default_duration} мин.**")
    else:
        st.caption("Список выбранных дат пока пуст.")

    st.markdown("---")

    st.markdown("#### 3. Параметры и списки")
    col_t1, col_dur = st.columns(2)
    with col_t1:
        start_time = st.time_input(
            "Время начала по умолчанию (по МСК / GMT+3)",
            value=st.session_state.get("global_start_time", time(18, 0)),
            key="global_start_time"
        )
    with col_dur:
        duration = st.number_input(
            "Длительность по умолчанию (минут)",
            min_value=15,
            max_value=480,
            value=st.session_state.get("global_duration", 60),
            step=15,
            key="global_duration"
        )

    subject = st.text_input("Название мероприятия", value="Онлайн-занятие")
    description = st.text_area("Описание / ДЗ для участников", value="")
    
    enable_auto_rec = st.checkbox(
        "🔴 Включить автоматическую запись встречи при входе",
        value=True,
    )

    emails_raw = st.text_area(
        "Email участников (по одному в строке)",
        placeholder="student1@example.com\nstudent2@example.com",
    )

    st.write("")
    if st.button("🚀 Создать комнату и запланировать все встречи", type="primary", use_container_width=True):
        current_room_name = st.session_state["room_name"]
        
        if not current_room_name or not sorted_dates:
            st.error("Заполните имя комнаты и добавьте хотя бы одну дату!")
            st.stop()

        emails = [x.strip() for x in emails_raw.splitlines() if x.strip()]

        with st.spinner("Активация единой комнаты в Контур.Толк..."):
            try:
                api.upsert_room(
                    current_room_name,
                    {
                        "title": subject,
                        "description": f"Единая комната: {subject}",
                        "enableLobby": False,
                        "enableAutoRecording": enable_auto_rec,
                    },
                )
            except TalkAPIError as e:
                st.error(f"Ошибка активации комнаты: {e}")
                st.stop()

        success_count = 0
        errors = []

        with st.spinner("Создание событий в календаре..."):
            for d in sorted_dates:
                # Определение индивидуального или дефолтного времени/длительности
                use_custom = st.session_state.get(f"use_custom_{d}", False)
                if use_custom:
                    cur_start_time = st.session_state.get(f"time_{d}", start_time)
                    cur_duration = st.session_state.get(f"dur_{d}", duration)
                else:
                    cur_start_time = start_time
                    cur_duration = duration

                start_dt = datetime.combine(d, cur_start_time)
                end_dt = start_dt + timedelta(minutes=int(cur_duration))

                payload = {
                    "start": start_dt.strftime("%Y-%m-%dT%H:%M:%S+03:00"),
                    "end": end_dt.strftime("%Y-%m-%dT%H:%M:%S+03:00"),
                    "timezone": "GMT+3",
                    "subject": subject,
                    "description": description,
                    "roomName": current_room_name,
                    "allowAnonymous": True,
                    "isRecurring": False,
                    "enableAutoRecording": enable_auto_rec,
                    "requiredExternalAttendeesEmails": emails,
                }

                try:
                    res = api.create_meeting(organizer_email, payload)
                    meeting_id = (
                        res.get("id")
                        or res.get("meetingId")
                        or f"mtg_{uuid.uuid4().hex[:8]}"
                    ) if isinstance(res, dict) else f"mtg_{uuid.uuid4().hex[:8]}"

                    st.session_state["created_meetings"].append({
                        "id": meeting_id,
                        "subject": subject,
                        "description": description,
                        "start": start_dt,
                        "end": end_dt,
                        "room_name": current_room_name,
                        "room_url": room_url,
                        "attendees": emails.copy(),
                        "organizer": organizer_email,
                        "date": d,
                        "auto_recording": enable_auto_rec,
                        "raw_json": res if isinstance(res, dict) else {},
                    })
                    success_count += 1
                except TalkAPIError as e:
                    errors.append(f"{d.strftime('%d.%m.%Y')}: {e}")

        if success_count > 0:
            st.success(f"Успешно запланировано встреч: **{success_count} из {len(sorted_dates)}**")
            st.info(f"Ссылка для участников: [{room_url}]({room_url})")

        if errors:
            st.error("Ошибки при создании некоторых встреч:")
            for err in errors:
                st.caption(f"• {err}")

# ==============================================================================
# ВКЛАДКА 2: КАЛЕНДАРЬ НА МЕСЯЦ
# ==============================================================================
with tab_calendar:
    months_ru = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    now = datetime.now()

    # Панель навигации по месяцам
    col_m1, col_m2, col_sync, col_rec = st.columns([2, 2, 2.5, 2.5])

    with col_m1:
        selected_month = st.selectbox(
            "Месяц",
            options=list(range(1, 13)),
            format_func=lambda x: months_ru[x - 1],
            index=now.month - 1,
            key="cal_month_select"
        )

    with col_m2:
        selected_year = st.number_input(
            "Год",
            min_value=2020,
            max_value=2035,
            value=now.year,
            step=1,
            key="cal_year_select"
        )

    with col_sync:
        st.write("")
        st.write("")
        if st.button("🔄 Синхронизировать API", use_container_width=True, type="secondary"):
            try:
                _, last_day = calendar.monthrange(selected_year, selected_month)
                from_dt = datetime(selected_year, selected_month, 1, 0, 0, 0)
                to_dt = datetime(selected_year, selected_month, last_day, 23, 59, 59)
                
                from_str = from_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                to_str = to_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

                with st.spinner("Загрузка расписания из Контур.Толк..."):
                    fetched = api.get_meetings(
                        organizer_email,
                        start_date=from_str,
                        end_date=to_str
                    )

                if isinstance(fetched, list):
                    st.session_state["created_meetings"] = []
                    existing_ids = set()
                    added_count = 0
                    clean_space_name = space.strip().replace("https://", "").replace(".ktalk.ru", "").strip("/")
                    
                    for item in fetched:
                        m_id = item.get("id") or item.get("meetingId") or f"mtg_{uuid.uuid4().hex[:8]}"
                        if m_id not in existing_ids:
                            s_parsed = parse_datetime_to_msk(item.get("start"))
                            e_parsed = parse_datetime_to_msk(item.get("end"))
                            r_name = item.get("roomName", "")
                            
                            all_attendees = extract_attendees(item)
                            org = extract_organizer(item, organizer_email)

                            st.session_state["created_meetings"].append({
                                "id": m_id,
                                "subject": item.get("subject", "Встреча"),
                                "description": item.get("description", ""),
                                "start": s_parsed,
                                "end": e_parsed,
                                "room_name": r_name,
                                "room_url": f"https://{clean_space_name}.ktalk.ru/{r_name}",
                                "attendees": all_attendees,
                                "organizer": org,
                                "date": s_parsed.date(),
                                "auto_recording": item.get("enableAutoRecording", False),
                                "raw_json": item,
                            })
                            existing_ids.add(m_id)
                            added_count += 1

                    st.toast(f"Синхронизировано встреч: {added_count}", icon="✅")
                    st.rerun()
            except Exception as e:
                st.toast(f"Ошибка синхронизации: {e}", icon="⚠️")

    month_meetings = []
    for m in st.session_state["created_meetings"]:
        m_date = m["date"]
        if isinstance(m_date, str):
            m_date = date.fromisoformat(m_date)
        if m_date.year == selected_year and m_date.month == selected_month:
            month_meetings.append(m)

    # Массовое включение автозаписи
    with col_rec:
        st.write("")
        st.write("")
        if st.button("🔴 Включить запись для всех", use_container_width=True):
            if not month_meetings:
                st.warning("Нет встреч для обновления.")
            else:
                updated_cnt = 0
                processed_rooms = set()
                
                with st.spinner("Активация автозаписи..."):
                    for m in month_meetings:
                        m_id = m["id"]
                        r_name = m.get("room_name")
                        raw = m.get("raw_json", {})
                        is_recurring = raw.get("isRecurring", False)
                        
                        if r_name and r_name not in processed_rooms:
                            try:
                                api.upsert_room(
                                    r_name,
                                    {
                                        "title": m.get("subject", "Встреча"),
                                        "enableAutoRecording": True,
                                        "enableLobby": False,
                                    }
                                )
                                processed_rooms.add(r_name)
                            except Exception:
                                pass

                        s_dt = m["start"] if isinstance(m["start"], datetime) else parse_datetime_to_msk(m["start"])
                        e_dt = m["end"] if isinstance(m["end"], datetime) else parse_datetime_to_msk(m["end"])

                        update_payload = {
                            "start": s_dt.strftime("%Y-%m-%dT%H:%M:%S+03:00"),
                            "end": e_dt.strftime("%Y-%m-%dT%H:%M:%S+03:00"),
                            "timezone": "GMT+3",
                            "subject": m.get("subject", "Встреча"),
                            "description": m.get("description", ""),
                            "roomName": r_name,
                            "enableAutoRecording": True,
                            "isRecurring": is_recurring,
                        }

                        if is_recurring and raw.get("recurrence"):
                            update_payload["recurrence"] = raw["recurrence"]

                        try:
                            api.update_meeting(organizer_email, m_id, update_payload)
                            m["auto_recording"] = True
                            if "raw_json" in m and isinstance(m["raw_json"], dict):
                                m["raw_json"]["enableAutoRecording"] = True
                            updated_cnt += 1
                        except Exception:
                            pass

                st.toast(f"Запись включена для {updated_cnt} встреч", icon="🎉")
                st.rerun()

    st.write("")

    # Карточки метрик
    meetings_by_date_map = {}
    for m in month_meetings:
        d_val = m["date"] if isinstance(m["date"], date) else date.fromisoformat(m["date"])
        meetings_by_date_map.setdefault(d_val, []).append(m)

    days_with_overlap = sum(
        1 for d, d_list in meetings_by_date_map.items() if calculate_max_simultaneous(d_list) > 1
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Всего мероприятий</div>
            <div class="metric-value">{len(month_meetings)}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Активных дней</div>
            <div class="metric-value">{len(meetings_by_date_map)}</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        status_color = "#EF4444" if days_with_overlap > 0 else "#10B981"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Пересечения по времени</div>
            <div class="metric-value" style="color: {status_color};">{days_with_overlap}</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.markdown(f"#### 🗓 Расписание: {months_ru[selected_month - 1]} {selected_year}")

    # Сетка календаря
    month_cal = calendar.monthcalendar(selected_year, selected_month)
    days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    cols_header = st.columns(7)
    for idx, day_name in enumerate(days_of_week):
        cols_header[idx].markdown(f"<div style='text-align: center; font-weight: 600; color: #64748B; font-size: 0.85rem;'>{day_name}</div>", unsafe_allow_html=True)

    for week in month_cal:
        cols = st.columns(7)
        for idx, day_num in enumerate(week):
            with cols[idx]:
                if day_num == 0:
                    st.write("")
                else:
                    current_date = date(selected_year, selected_month, day_num)
                    day_m = meetings_by_date_map.get(current_date, [])
                    simultaneous_count = calculate_max_simultaneous(day_m)
                    is_today = (current_date == date.today())
                    
                    bg_col = "#FFFFFF"
                    border_col = "#E2E8F0"
                    text_badge = ""

                    if day_m:
                        if simultaneous_count > 1:
                            bg_col = "#FEF2F2"
                            border_col = "#FCA5A5"
                            text_badge = f"<span style='color: #DC2626; font-size: 0.75rem; font-weight: 600;'>🔴 Конфликт: {simultaneous_count}</span>"
                        else:
                            bg_col = "#F0FDF4"
                            border_col = "#86EFAC"
                            text_badge = f"<span style='color: #16A34A; font-size: 0.75rem; font-weight: 600;'>🟢 Встреч: {len(day_m)}</span>"

                    today_border = "border-width: 2px; border-color: #2563EB;" if is_today else f"border: 1px solid {border_col};"

                    st.markdown(f"""
                    <div style="background: {bg_col}; {today_border} border-radius: 8px; padding: 8px; margin-bottom: 8px; min-height: 64px; text-align: center;">
                        <div style="font-weight: 600; font-size: 0.95rem; color: #0F172A;">{day_num}</div>
                        <div style="margin-top: 4px;">{text_badge if text_badge else '<span style="color:#94A3B8; font-size:0.75rem;">—</span>'}</div>
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown("---")

# Список встреч с фильтрацией по датам и группам
    st.markdown("#### 📋 Детализация встреч")

    if not month_meetings:
        st.info("В выбранном месяце нет запланированных мероприятий.")
    else:
        available_days = sorted(list(meetings_by_date_map.keys()))
        day_options = ["Все дни месяца"] + [d.strftime("%d.%m.%Y") for d in available_days]
        
        col_f1, col_f2 = st.columns(2)

        with col_f1:
            selected_day_filter = st.selectbox(
                "Фильтр по дате:", 
                options=day_options,
                index=0
            )

        # Применяем фильтр по дате
        filtered_meetings = []
        if selected_day_filter != "Все дни месяца":
            target_d = datetime.strptime(selected_day_filter, "%d.%m.%Y").date()
            filtered_meetings = meetings_by_date_map.get(target_d, [])
        else:
            filtered_meetings = month_meetings

        if not filtered_meetings:
            st.info("На выбранную дату нет встреч.")
        else:
            # Группируем отфильтрованные встречи по названию (subject)
            meetings_by_subject = {}
            for m in filtered_meetings:
                subj = m.get("subject", "Без названия")
                meetings_by_subject.setdefault(subj, []).append(m)

            subject_names = sorted(list(meetings_by_subject.keys()))
            subject_options = ["Все мероприятия"] + [f"{subj} ({len(meetings_by_subject[subj])})" for subj in subject_names]

            with col_f2:
                selected_subj_filter = st.selectbox(
                    "Фильтр по мероприятию / группе:",
                    options=subject_options,
                    index=0
                )

            # Определяем, какие группы показывать
            if selected_subj_filter == "Все мероприятия":
                display_subjects = subject_names
            else:
                idx_selected = subject_options.index(selected_subj_filter) - 1
                display_subjects = [subject_names[idx_selected]]

            for subj in display_subjects:
                m_list = meetings_by_subject[subj]
                
                st.markdown(f"##### 📌 {subj} ({len(m_list)})")
                
                # Сортируем встречи внутри группы по дате и времени
                def get_start_dt(m_item):
                    return parse_datetime_to_msk(m_item["start"])
                
                m_list.sort(key=get_start_dt)

                for m_idx, m in enumerate(m_list):
                    s_dt = parse_datetime_to_msk(m["start"])
                    e_dt = parse_datetime_to_msk(m["end"])
                    d_val = s_dt.date()
                    
                    m_date_str = s_dt.strftime("%d.%m.%Y")
                    s_time = s_dt.strftime("%H:%M")
                    e_time = e_dt.strftime("%H:%M")
                    dur_minutes = int((e_dt - s_dt).total_seconds() // 60)

                    rec_status = "🔴 Автозапись ВКЛ" if m.get("auto_recording") else "⚪ Запись ВЫКЛ"

                    # Раскрывающийся список с датой, временем и продолжительностью
                    with st.expander(f"📅 {m_date_str} | ⏰ {s_time} – {e_time} МСК ({dur_minutes} мин)", expanded=False):
                        col_info, col_link = st.columns([3, 1])
                        
                        with col_info:
                            if m.get("description"):
                                st.markdown(f"**Описание:** {m['description']}")
                            st.markdown(f"**Комната:** `{m.get('room_name', '—')}` | **Запись:** `{rec_status}`")

                        with col_link:
                            st.markdown(f"[👉 **Открыть Толк**]({m['room_url']})")

                        st.markdown("---")

                        # Участники
                        st.markdown("**Состав участников:**")
                        org_mail = m.get("organizer") or organizer_email
                        st.markdown(f"<span class='badge-org'>👑 {org_mail}</span>", unsafe_allow_html=True)

                        attendees_list = m.get("attendees") or []
                        if attendees_list:
                            badges_html = " ".join([
                                f"<span class='badge-chip'>👤 {att}</span>"
                                for att in attendees_list
                            ])
                            st.markdown(f"<div style='margin-top: 6px;'>{badges_html}</div>", unsafe_allow_html=True)
                        else:
                            st.caption("Дополнительные участники не добавлены.")

                        # Форма добавления участника
                        st.write("")
                        form_key = f"add_att_{m['id']}_{d_val.isoformat()}_{m_idx}"
                        
                        with st.form(key=form_key, clear_on_submit=True):
                            c_in, c_btn = st.columns([3, 1])
                            with c_in:
                                new_email_input = st.text_input(
                                    "Email нового участника",
                                    placeholder="user@example.com",
                                    key=f"inp_{form_key}",
                                    label_visibility="collapsed"
                                )
                            with c_btn:
                                submit_btn = st.form_submit_button("Добавить", use_container_width=True)

                            if submit_btn:
                                email_clean = new_email_input.strip().lower()
                                if email_clean and "@" in email_clean and "." in email_clean:
                                    start_iso = s_dt.strftime("%Y-%m-%dT%H:%M:%S+03:00")
                                    end_iso = e_dt.strftime("%Y-%m-%dT%H:%M:%S+03:00")

                                    current_emails = []
                                    for att in m.get("attendees", []):
                                        if "(" in att and ")" in att:
                                            mail_extracted = att.split("(")[-1].replace(")", "").strip()
                                            if "@" in mail_extracted:
                                                current_emails.append(mail_extracted)
                                        elif "@" in att:
                                            current_emails.append(att)

                                    if email_clean not in current_emails:
                                        current_emails.append(email_clean)

                                    raw = m.get("raw_json", {})
                                    is_recurring = raw.get("isRecurring", False)

                                    update_payload = {
                                        "start": start_iso,
                                        "end": end_iso,
                                        "timezone": "GMT+3",
                                        "subject": m.get("subject", "Встреча"),
                                        "description": m.get("description", ""),
                                        "roomName": m.get("room_name", ""),
                                        "enableAutoRecording": m.get("auto_recording", True),
                                        "isRecurring": is_recurring,
                                        "requiredExternalAttendeesEmails": current_emails,
                                        "requiredInternalAttendeesEmails": current_emails,
                                        "requiredAttendees": [{"mailbox": e} for e in current_emails],
                                    }

                                    if is_recurring and raw.get("recurrence"):
                                        update_payload["recurrence"] = raw["recurrence"]

                                    try:
                                        api.add_attendee(
                                            organizer_email,
                                            m["id"],
                                            email_clean,
                                            meeting_payload=update_payload
                                        )
                                        st.toast(f"Участник {email_clean} добавлен!", icon="✅")
                                    except Exception as err:
                                        st.toast(f"Ошибка API при добавлении: {err}", icon="⚠️")

                                    if "attendees" not in m or m["attendees"] is None:
                                        m["attendees"] = []

                                    if email_clean not in m["attendees"]:
                                        m["attendees"].append(email_clean)

                                    st.rerun()
                                else:
                                    st.error("Введите корректный Email адрес.")
            st.write("")