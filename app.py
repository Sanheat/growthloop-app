import streamlit as st
import pandas as pd
import requests
import time

# Настройка страницы
st.set_page_config(layout="wide", page_title="GrowthLoop Engine - Advanced Search")

API_KEY = "4ag8CvRHFhXpwzOz"
BASE_URL = "https://api.ofdata.ru/v2"

# Функция для очистки данных (убираем [object Object])
def clean_list_columns(val):
    if isinstance(val, list):
        if not val: return ""
        if isinstance(val[0], str): return ", ".join(val)
        if isinstance(val[0], dict):
            readable_items = []
            for item in val:
                pairs = [f"{k}: {v}" for k, v in item.items() if v is not None]
                readable_items.append(" | ".join(pairs))
            return "; ".join(readable_items)
    return val

# --- БОКОВАЯ ПАНЕЛЬ (ФИЛЬТРЫ) ---
st.sidebar.title("🎯 Расширенный поиск")

okved_query = st.sidebar.text_input("Код ОКВЭД", "63.11")
region_code = st.sidebar.text_input("Код региона", "77")

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Финансы (млн руб.)")
# Вводим в миллионах для удобства, в API отправляем чистые числа
rev_min = st.sidebar.number_input("Выручка от (млн)", value=0) * 1_000_000
rev_max = st.sidebar.number_input("Выручка до (млн)", value=0) * 1_000_000

prof_min = st.sidebar.number_input("Прибыль от (млн)", value=0) * 1_000_000
prof_max = st.sidebar.number_input("Прибыль до (млн)", value=0) * 1_000_000

st.sidebar.subheader("👥 Команда")
staff_min = st.sidebar.number_input("Сотрудников от", value=0)
staff_max = st.sidebar.number_input("Сотрудников до", value=0)

# --- ЛОГИКА ПОИСКА ---
if st.sidebar.button("Найти компании"):
    search_url = f"{BASE_URL}/search"
    
    # Формируем параметры для Advanced Search
    params = {
        "key": API_KEY,
        "by": "advanced", # Переключаем на расширенный поиск
        "obj": "org",
        "okved": okved_query,
        "region": region_code,
        "active": "true",
        "limit": 100
    }
    
    # Добавляем фильтры только если они указаны пользователем
    if rev_min > 0: params["revenue_min"] = rev_min
    if rev_max > 0: params["revenue_max"] = rev_max
    if prof_min > 0: params["profit_min"] = prof_min
    if prof_max > 0: params["profit_max"] = prof_max
    if staff_min > 0: params["staff_min"] = staff_min
    if staff_max > 0: params["staff_max"] = staff_max
    
    with st.spinner('Сканируем реестры по вашим фильтрам...'):
        try:
            response = requests.get(search_url, params=params)
            res_data = response.json()
            if "data" in res_data and "Записи" in res_data["data"]:
                found_list = res_data["data"]["Записи"]
                df = pd.DataFrame(found_list)
                df.insert(0, "Выбрать", False) 
                df = df.rename(columns={"НаимСокр": "Название", "ИНН": "ИНН", "ЮрАдрес": "Адрес"})
                st.session_state['found_companies'] = df
            else:
                st.error("По таким критериям компаний не найдено.")
        except Exception as e:
            st.error(f"Ошибка запроса: {e}")

# --- ИНТЕРФЕЙС ВЫБОРА И ОБОГАЩЕНИЯ ---
if 'found_companies' in st.session_state:
    st.subheader("📋 Результаты поиска")
    
    edited_df = st.data_editor(
        st.session_state['found_companies'],
        column_config={"Выбрать": st.column_config.CheckboxColumn("Выбрать", default=False)},
        disabled=st.session_state['found_companies'].columns.drop("Выбрать"),
        hide_index=True,
        use_container_width=True
    )

    selected_rows = edited_df[edited_df["Выбрать"] == True]
    st.write(f"✅ Выбрано для обогащения: **{len(selected_rows)}**")

    if st.button("🚀 Обогатить (Собрать все данные)"):
        if len(selected_rows) == 0:
            st.warning("Отметьте компании галочками.")
        else:
            all_raw_data = []
            progress = st.progress(0)
            inns = selected_rows['ИНН'].tolist()
            
            for i, inn in enumerate(inns):
                try:
                    res = requests.get(f"{BASE_URL}/company", params={"key": API_KEY, "inn": inn}).json()
                    if "data" in res:
                        all_raw_data.append(res["data"])
                except: continue
                progress.progress((i + 1) / len(inns))
                time.sleep(0.1)

            if all_raw_data:
                final_df = pd.json_normalize(all_raw_data)
                for col in final_df.columns:
                    final_df[col] = final_df[col].apply(clean_list_columns)
                
                st.subheader("💎 Полные данные по выбранным целям")
                st.dataframe(final_df, use_container_width=True)
                
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Скачать CSV", csv, "leads_enriched.csv", "text/csv")
