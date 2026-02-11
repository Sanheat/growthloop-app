import streamlit as st
import pandas as pd
import requests
import time

# Настройка страницы
st.set_page_config(layout="wide", page_title="GrowthLoop Engine v2.2")

API_KEY = "4ag8CvRHFhXpwzOz"
BASE_URL = "https://api.ofdata.ru/v2"

# --- ЗАГРУЗКА СПРАВОЧНИКА ОКВЭД ---
@st.cache_data
def load_okved_directory():
    """Загружает полный справочник ОКВЭД-2 для выпадающего списка"""
    try:
        # Используем проверенный источник справочника в формате JSON
        url = "https://raw.githubusercontent.com/thefubv/okved/master/okved_2.json"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # Формируем список строк вида "Код - Описание"
            # Фильтруем только конечные коды (где есть точка или 4+ знака), 
            # либо оставляем все для гибкости
            options = [f"{item['code']} - {item['name']}" for item in data]
            return options
    except Exception as e:
        st.error(f"Не удалось загрузить справочник ОКВЭД: {e}")
    # Резервный вариант, если GitHub недоступен
    return ["63.11 - Деятельность по обработке данных", "62.01 - Разработка ПО"]

# Функция очистки данных от [object Object]
def clean_list_columns(val):
    if isinstance(val, list):
        if not val: return ""
        if isinstance(val[0], str): return ", ".join(val)
        if isinstance(val[0], dict):
            readable = []
            for item in val:
                pairs = [f"{k}: {v}" for k, v in item.items() if v is not None]
                readable.append(" | ".join(pairs))
            return "; ".join(readable)
    return val

# --- САЙДБАР ---
st.sidebar.title("🎯 Фильтры поиска")

# Загружаем список ОКВЭД
okved_options = load_okved_directory()

# Заменяем текстовое поле на выпадающий список с поиском
selected_okved_label = st.sidebar.selectbox(
    "Выберите вид деятельности (ОКВЭД)",
    options=okved_options,
    index=okved_options.index("63.11 - Деятельность по обработке данных") if "63.11 - Деятельность по обработке данных" in okved_options else 0,
    help="Начните печатать название деятельности, чтобы быстро найти код"
)

# Извлекаем только код (левая часть до тире) для отправки в API
okved_code = selected_okved_label.split(" - ")[0]

region = st.sidebar.text_input("Регион (код, например 77)", "77")

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Финансы (млн руб.)")
r_min = st.sidebar.number_input("Выручка от", 0) * 1_000_000
r_max = st.sidebar.number_input("Выручка до (0 = без огр.)", 0) * 1_000_000
p_min = st.sidebar.number_input("Прибыль от", 0) * 1_000_000

st.sidebar.subheader("👥 Штат")
s_min = st.sidebar.number_input("Сотрудников от", 0)

if st.sidebar.button("Найти компании"):
    params = {
        "key": API_KEY,
        "by": "advanced",
        "obj": "org",
        "okved": okved_code, # Передаем чистый код (например, 63.11)
        "region": region,
        "active": "true",
        "limit": 50
    }
    if r_min > 0: params["revenue_min"] = r_min
    if r_max > 0: params["revenue_max"] = r_max
    if p_min > 0: params["profit_min"] = p_min
    if s_min > 0: params["staff_min"] = s_min

    with st.spinner('Поиск по базе Ofdata...'):
        try:
            resp = requests.get(f"{BASE_URL}/search", params=params)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and "Записи" in data["data"]:
                    df = pd.DataFrame(data["data"]["Записи"])
                    df.insert(0, "Выбрать", False)
                    cols_map = {"НаимСокр": "Название", "ИНН": "ИНН", "ЮрАдрес": "Адрес"}
                    df = df.rename(columns={k: v for k, v in cols_map.items() if k in df.columns})
                    st.session_state['found_companies'] = df
                else:
                    st.warning("Компании не найдены. Попробуйте изменить фильтры.")
            else:
                st.error(f"Ошибка API ({resp.status_code}): {resp.text}")
        except Exception as e:
            st.error(f"Ошибка соединения: {str(e)}")

# --- ИНТЕРФЕЙС РЕЗУЛЬТАТОВ ---
if 'found_companies' in st.session_state:
    st.subheader(f"📋 Результаты по запросу: {selected_okved_label}")
    
    df_to_edit = st.session_state['found_companies']
    edited_df = st.data_editor(
        df_to_edit,
        column_config={"Выбрать": st.column_config.CheckboxColumn("Выбрать", default=False)},
        disabled=[c for c in df_to_edit.columns if c != "Выбрать"],
        hide_index=True,
        use_container_width=True
    )

    selected = edited_df[edited_df["Выбрать"] == True]
    st.write(f"Выбрано компаний: **{len(selected)}**")

    if st.button("🚀 Получить полные данные"):
        if selected.empty:
            st.info("Пожалуйста, выберите компании в таблице.")
        else:
            enriched = []
            progress = st.progress(0)
            inns = selected['ИНН'].tolist()
            
            for i, inn in enumerate(inns):
                try:
                    res = requests.get(f"{BASE_URL}/company", params={"key": API_KEY, "inn": inn})
                    if res.status_code == 200:
                        enriched.append(res.json().get("data", {}))
                    time.sleep(0.15)
                except: continue
                progress.progress((i + 1) / len(inns))
            
            if enriched:
                final_df = pd.json_normalize(enriched)
                for col in final_df.columns:
                    final_df[col] = final_df[col].apply(clean_list_columns)
                
                st.subheader("💎 Обогащенная база (готово к выгрузке)")
                st.dataframe(final_df, use_container_width=True)
                
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Скачать результаты (CSV)", csv, "target_leads.csv", "text/csv")
