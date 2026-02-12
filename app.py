import streamlit as st
import pandas as pd
import requests
import time

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(layout="wide", page_title="GrowthLoop Hybrid Pro v3.0")

# --- КЛЮЧИ API ---
FNS_API_KEY = "8f1364cd9916da3ba62170204442a80566bc5f29"
OFDATA_API_KEY = "4ag8CvRHFhXpwzOz"

# --- СПРАВОЧНИКИ (Для примера, можно расширять) ---
REGIONS = {
    "Все регионы": "", "77 - Москва": "77", "78 - Санкт-Петербург": "78", 
    "50 - Московская область": "50", "23 - Краснодарский край": "23", 
    "66 - Свердловская область": "66", "54 - Новосибирская область": "54",
    "16 - Татарстан": "16", "02 - Башкортостан": "02"
}

OKVED_GROUPS = {
    "Все отрасли": "",
    "62 - Разработка ПО": "62",
    "63 - ИТ-услуги": "63",
    "46 - Оптовая торговля": "46",
    "41 - Строительство": "41",
    "70 - Консалтинг": "70",
    "43 - Спец. строительные работы": "43"
}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def clean_val(val):
    """Очищает данные от технических символов и красиво склеивает списки (например, налоги)."""
    if isinstance(val, list):
        if not val: return ""
        if isinstance(val[0], dict):
            # Разбираем налоги/сборы: Название: Сумма
            return " | ".join([f"{i.get('НаимНалог', i.get('Наименование', ''))}: {i.get('СумУплНал', i.get('Сумма', ''))}" for i in val if i])
        return ", ".join(map(str, val))
    return val

def process_contacts(df, col_name, prefix):
    """Разносит список контактов (почты/телефоны) по отдельным нумерованным столбцам без кавычек."""
    if col_name not in df.columns:
        return df
    
    # Превращаем данные в чистые списки
    contacts_series = df[col_name].apply(lambda x: x if isinstance(x, list) else [])
    
    max_len = contacts_series.map(len).max()
    if pd.isna(max_len) or max_len == 0:
        return df.drop(columns=[col_name])

    # Создаем новые чистые столбцы
    new_cols = pd.DataFrame(contacts_series.tolist(), index=df.index)
    new_cols.columns = [f"{prefix} {i+1}" for i in range(new_cols.shape[1])]
    
    return pd.concat([df, new_cols], axis=1).drop(columns=[col_name])

# --- БОКОВАЯ ПАНЕЛЬ (SIDEBAR) ---
st.sidebar.title("🎯 Фильтры поиска")

# Группа 1: Отрасль и Регион
sel_okved_name = st.sidebar.selectbox("Выберите вид деятельности (ОКВЭД)", list(OKVED_GROUPS.keys()))
okved_code = OKVED_GROUPS[sel_okved_name]

sel_region_name = st.sidebar.selectbox("Регион (код)", list(REGIONS.keys()))
region_code = REGIONS[sel_region_name]

st.sidebar.markdown("---")

# Группа 2: Финансы (в две колонки как на скрине)
with st.sidebar.expander("💰 Выручка (млн руб.)", expanded=True):
    r_col1, r_col2 = st.columns(2)
    with r_col1:
        rev_min = st.number_input("От", value=0, key="rev_min", label_visibility="collapsed", placeholder="От")
    with r_col2:
        rev_max = st.number_input("До", value=0, key="rev_max", label_visibility="collapsed", placeholder="До")
    st.caption("Укажите интервал выручки в млн ₽")

# Группа 3: Дополнительно
with st.sidebar.expander("👥 Штат и контакты"):
    staff_min = st.number_input("Сотрудников от", value=0)
    with_phone = st.checkbox("Только с телефоном")
    with_email = st.checkbox("Только с Email")
    active_only = st.checkbox("Только действующие", value=True)

# --- ЛОГИКА ПОИСКА (ФНС API) ---
if st.sidebar.button("Найти компании", use_container_width=True):
    # Собираем фильтр
    f_parts = ["onlyul"]
    if active_only: f_parts.append("active")
    if okved_code: f_parts.append(f"okvedgroup{okved_code}")
    if region_code: f_parts.append(f"region{region_code}")
    
    if rev_min > 0 or rev_max > 0:
        v_str = "vyruchka"
        if rev_min > 0: v_str += f">{rev_min * 1000}" # перевод в тыс. руб для API
        if rev_max > 0: v_str += f"<{rev_max * 1000}"
        f_parts.append(v_str)
    
    if staff_min > 0: f_parts.append(f"sotrudnikov>{staff_min}")
    if with_phone: f_parts.append("withphone")
    if with_email: f_parts.append("withemail")

    filter_final = "+".join(f_parts)
    search_url = f"https://api-fns.ru/api/search?q=any&filter={filter_final}&key={FNS_API_KEY}"

    with st.spinner('Поиск в базе ФНС...'):
        try:
            r = requests.get(search_url, timeout=20)
            if r.status_code == 200:
                res_data = r.json()
                items = res_data.get("items", [])
                if items:
                    # Нормализуем данные (разворачиваем ЮЛ.ИНН и т.д.)
                    df = pd.json_normalize(items)
                    # Очищаем заголовки от точек
                    df.columns = [c.split('.')[-1] for c in df.columns]
                    df.insert(0, "Выбрать", False)
                    st.session_state['results'] = df
                else:
                    st.warning("Компании не найдены. Попробуйте смягчить фильтры.")
            elif r.status_code == 403:
                st.error(f"🚫 Доступ запрещен. Добавьте IP {r.text} в ЛК api-fns.ru")
        except Exception as e:
            st.error(f"Ошибка связи: {e}")

# --- ОТОБРАЖЕНИЕ ТАБЛИЦЫ И ОБОГАЩЕНИЕ ---
if 'results' in st.session_state:
    st.subheader("📋 Найденные цели")
    
    edited_df = st.data_editor(
        st.session_state['results'],
        use_container_width=True,
        hide_index=True,
        column_config={"Выбрать": st.column_config.CheckboxColumn("Выбрать")}
    )

    selected = edited_df[edited_df["Выбрать"] == True]
    
    if st.button(f"🚀 Собрать контакты для ({len(selected)})"):
        if selected.empty:
            st.warning("Отметьте хотя бы одну компанию галочкой.")
        else:
            enriched = []
            bar = st.progress(0)
            inns = selected['ИНН'].tolist()
            
            for i, inn in enumerate(inns):
                try:
                    res = requests.get(f"https://api.ofdata.ru/v2/company?key={OFDATA_API_KEY}&inn={inn}").json()
                    if "data" in res:
                        enriched.append(res["data"])
                    time.sleep(0.12) # защита от лимитов
                except: pass
                bar.progress((i + 1) / len(inns))
            
            if enriched:
                final_df = pd.json_normalize(enriched)
                
                # РАЗНОСИМ КОНТАКТЫ ПО СТОЛБЦАМ
                final_df = process_contacts(final_df, 'Контакты.Тел', 'Телефон')
                final_df = process_contacts(final_df, 'Контакты.Емэйл', 'Email')
                
                # Очищаем остальные сложные данные
                for col in final_df.columns:
                    final_df[col] = final_df[col].apply(clean_val)
                
                # Красивые заголовки
                final_df.columns = [c.replace('.', ' ') for c in final_df.columns]
                
                st.subheader("💎 Готовая база с контактами")
                st.dataframe(final_df, use_container_width=True)
                
                # Кнопка скачивания
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Скачать Excel (CSV)", csv, "leads_ready.csv", "text/csv")
