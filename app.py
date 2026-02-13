import streamlit as st
import pandas as pd
import requests
import time

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(layout="wide", page_title="GrowthLoop Hybrid Pro v3.4")

# --- КЛЮЧИ API ---
FNS_API_KEY = "8f1364cd9916da3ba62170204442a80566bc5f29"
OFDATA_API_KEY = "4ag8CvRHFhXpwzOz"

# --- СПРАВОЧНИК РЕГИОНОВ ---
REGIONS = {
    "Все регионы": "", "01 - Адыгея": "01", "02 - Башкортостан": "02", "03 - Бурятия": "03", "04 - Алтай": "04",
    "05 - Дагестан": "05", "06 - Ингушетия": "06", "07 - Кабардино-Балкария": "07", "08 - Калмыкия": "08",
    "09 - Карачаево-Черкесия": "09", "10 - Карелия": "10", "11 - Коми": "11", "12 - Марий Эл": "12",
    "13 - Мордовия": "13", "14 - Якутия": "14", "15 - Северная Осетия": "15", "16 - Татарстан": "16",
    "17 - Тыва": "17", "18 - Удмуртия": "18", "19 - Хакасия": "19", "20 - Чечня": "20", "21 - Чувашия": "21",
    "22 - Алтайский край": "22", "23 - Краснодарский край": "23", "24 - Красноярский край": "24",
    "25 - Приморский край": "25", "26 - Ставропольский край": "26", "27 - Хабаровский край": "27",
    "28 - Амурская обл.": "28", "29 - Архангельская обл.": "29", "30 - Астраханская обл.": "30",
    "31 - Белгородская обл.": "31", "32 - Брянская обл.": "32", "33 - Владимирская обл.": "33",
    "34 - Волгоградская обл.": "34", "35 - Вологодская обл.": "35", "36 - Воронежская обл.": "36",
    "37 - Ивановская обл.": "37", "38 - Иркутская обл.": "38", "39 - Калининградская обл.": "39",
    "40 - Калужская обл.": "40", "41 - Камчатский край": "41", "42 - Кемеровская обл.": "42",
    "43 - Кировская обл.": "43", "44 - Костромская обл.": "44", "45 - Курганская обл.": "45",
    "46 - Курская обл.": "46", "47 - Ленинградская обл.": "47", "48 - Липецкая обл.": "48",
    "49 - Магаданская обл.": "49", "50 - Московская обл.": "50", "51 - Мурманская обл.": "51",
    "52 - Нижегородская обл.": "52", "53 - Новгородская обл.": "53", "54 - Новосибирская обл.": "54",
    "55 - Омская обл.": "55", "56 - Оренбургская обл.": "56", "57 - Орловская обл.": "57",
    "58 - Пензенская обл.": "58", "59 - Пермский край": "59", "60 - Псковская обл.": "60",
    "61 - Ростовская обл.": "61", "62 - Рязанская обл.": "62", "63 - Самарская обл.": "63",
    "64 - Саратовская обл.": "64", "65 - Сахалинская обл.": "65", "66 - Свердловская обл.": "66",
    "67 - Смоленская обл.": "67", "68 - Тамбовская обл.": "68", "69 - Тверская обл.": "69",
    "70 - Томская обл.": "70", "71 - Тульская обл.": "71", "72 - Тюменская обл.": "72",
    "73 - Ульяновская обл.": "73", "74 - Челябинская обл.": "74", "75 - Забайкальский край": "75",
    "76 - Ярославская обл.": "76", "77 - Москва": "77", "78 - Санкт-Петербург": "78",
    "79 - Еврейская АО": "79", "82 - Крым": "82", "83 - Ненецкий АО": "83", "86 - ХМАО": "86",
    "87 - Чукотский АО": "87", "89 - Ямало-Ненецкий АО": "89", "92 - Севастополь": "92"
}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def clean_val(val):
    if not val: return ""
    if isinstance(val, list):
        if not val: return ""
        if isinstance(val[0], dict):
            items = []
            for i in val:
                name = i.get('ФИО') or i.get('НаимСокрЮЛ') or i.get('НаимНалог') or i.get('Наименование')
                value = i.get('СумУплНал') or i.get('Сумма') or i.get('ДоляПроцент')
                if name and value: items.append(f"{name}: {value}")
                elif name: items.append(str(name))
                elif value: items.append(str(value))
            return " | ".join(items) if items else ""
        return ", ".join(map(str, val))
    if isinstance(val, dict):
        parts = [f"{v}" for k, v in val.items() if v]
        return " | ".join(parts)
    return str(val)

def process_contacts(df, col_name, prefix):
    if col_name not in df.columns: return df
    contacts_series = df[col_name].apply(lambda x: x if isinstance(x, list) else [])
    max_len = contacts_series.map(len).max()
    if pd.isna(max_len) or max_len == 0: return df.drop(columns=[col_name])
    new_cols = pd.DataFrame(contacts_series.tolist(), index=df.index)
    new_cols.columns = [f"{prefix} {i+1}" for i in range(new_cols.shape[1])]
    return pd.concat([df, new_cols], axis=1).drop(columns=[col_name])

def toggle_all_selection():
    if 'results' in st.session_state and st.session_state['results'] is not None:
        st.session_state['results']['Выбрать'] = st.session_state.select_all_cb

# --- ИНТЕРФЕЙС САЙДБАРА ---
st.sidebar.title("🎯 Фильтры поиска")

okved_input = st.sidebar.text_input("ОКВЭДы (через | )", placeholder="62 или 62.01|62.02")
sel_region_name = st.sidebar.selectbox("Регион", list(REGIONS.keys()))
region_code = REGIONS[sel_region_name]

st.sidebar.markdown("---")

with st.sidebar.expander("💰 Выручка (млн руб.)", expanded=True):
    r_col1, r_col2 = st.columns(2)
    with r_col1:
        rev_min = st.number_input("От", value=0, key="rev_min", label_visibility="collapsed")
    with r_col2:
        rev_max = st.number_input("До", value=0, key="rev_max", label_visibility="collapsed")

with st.sidebar.expander("👥 Параметры"):
    staff_min = st.number_input("Сотрудников от", value=0)
    with_phone = st.checkbox("Только с телефоном")
    with_email = st.checkbox("Только с Email")
    active_only = st.checkbox("Только действующие", value=True)

# --- ФУНКЦИЯ ЗАПРОСА К API ФНС ---
def fetch_fns_data(page=1):
    f_parts = ["onlyul"]
    if active_only: f_parts.append("active")
    if okved_input:
        if "|" in okved_input or "." in okved_input: f_parts.append(f"okved{okved_input}")
        else: f_parts.append(f"okvedgroup{okved_input}")
    if region_code: f_parts.append(f"region{region_code}")
    if rev_min > 0 or rev_max > 0:
        v_str = "vyruchka"
        if rev_min > 0: v_str += f">{rev_min * 1000}"
        if rev_max > 0: v_str += f"<{rev_max * 1000}"
        f_parts.append(v_str)
    if staff_min > 0: f_parts.append(f"sotrudnikov>{staff_min}")
    if with_phone: f_parts.append("withphone")
    if with_email: f_parts.append("withemail")

    filter_final = "+".join(f_parts)
    search_url = f"https://api-fns.ru/api/search?q=any&filter={filter_final}&page={page}&key={FNS_API_KEY}"
    
    try:
        r = requests.get(search_url, timeout=20)
        if r.status_code == 200:
            return r.json().get("items", [])
        elif r.status_code == 403:
            st.error(f"Ошибка 403: Добавьте IP {r.text} в ЛК API.")
            return None
    except Exception as e:
        st.error(f"Сбой: {e}")
        return None

# --- ЛОГИКА КНОПОК ПОИСКА ---
if st.sidebar.button("Найти компании (первые 100)", use_container_width=True):
    # Сброс данных при новом поиске
    st.session_state['current_page'] = 1
    items = fetch_fns_data(page=1)
    if items:
        df = pd.json_normalize(items)
        df.columns = [c.split('.')[-1] for c in df.columns]
        df.insert(0, "Выбрать", False)
        st.session_state['results'] = df
        st.session_state['search_count'] = len(df)
    else:
        st.session_state['results'] = None
        st.warning("Ничего не найдено.")

# --- ОТОБРАЖЕНИЕ ТАБЛИЦЫ ---
if 'results' in st.session_state and st.session_state['results'] is not None:
    
    st.metric("Найдено компаний в списке", st.session_state['search_count'])
    
    st.checkbox("Выбрать все", key="select_all_cb", on_change=toggle_all_selection)
    
    # Редактор таблицы
    edited_df = st.data_editor(
        st.session_state['results'], 
        use_container_width=True, 
        hide_index=True,
        column_config={"Выбрать": st.column_config.CheckboxColumn("Выбрать")},
        key="table_editor"
    )

    # Синхронизация ручного выбора
    if st.session_state.get("table_editor"):
        for row_idx, edit in st.session_state.table_editor["edited_rows"].items():
            if "Выбрать" in edit:
                st.session_state['results'].iat[int(row_idx), 0] = edit["Выбрать"]

    # КНОПКА ДОЗАГРУЗКИ СЛЕДУЮЩИХ 100
    if st.button("🔽 Загрузить еще 100 компаний", use_container_width=True):
        st.session_state['current_page'] += 1
        new_items = fetch_fns_data(page=st.session_state['current_page'])
        
        if new_items:
            new_df = pd.json_normalize(new_items)
            new_df.columns = [c.split('.')[-1] for c in new_df.columns]
            new_df.insert(0, "Выбрать", st.session_state.select_all_cb) # Подстраиваем под чекбокс "Выбрать все"
            
            # Склеиваем и удаляем дубликаты по ИНН
            combined_df = pd.concat([st.session_state['results'], new_df], ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=['ИНН'], keep='first')
            
            st.session_state['results'] = combined_df
            st.session_state['search_count'] = len(combined_df)
            st.rerun() # Перезапускаем для обновления таблицы
        else:
            st.info("Больше данных по этому запросу нет.")

    selected = st.session_state['results'][st.session_state['results']["Выбрать"] == True]
    
    # --- ОБОГАЩЕНИЕ ---
    st.markdown("---")
    if st.button(f"🚀 Обогатить данными ({len(selected)})", use_container_width=True):
        if selected.empty:
            st.warning("Выберите компании!")
        else:
            enriched = []
            bar = st.progress(0)
            inns = selected['ИНН'].tolist()
            
            for i, inn in enumerate(inns):
                try:
                    res = requests.get(f"https://api.ofdata.ru/v2/company?key={OFDATA_API_KEY}&inn={inn}").json()
                    if "data" in res: enriched.append(res["data"])
                    time.sleep(0.15)
                except: pass
                bar.progress((i + 1) / len(inns))
            
            if enriched:
                final_df = pd.json_normalize(enriched)
                final_df = process_contacts(final_df, 'Контакты.Тел', 'Телефон')
                final_df = process_contacts(final_df, 'Контакты.Емэйл', 'Email')
                for col in final_df.columns:
                    final_df[col] = final_df[col].apply(clean_val)
                final_df.columns = [c.replace('.', ' ') for c in final_df.columns]
                
                st.subheader("💎 Финальная база")
                st.dataframe(final_df, use_container_width=True)
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Скачать CSV", csv, "leads.csv", "text/csv")
