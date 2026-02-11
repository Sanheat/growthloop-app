import streamlit as st
import pandas as pd
import requests
import time

# Настройки страницы
st.set_page_config(layout="wide", page_title="GrowthLoop Engine")

API_KEY = "4ag8CvRHFhXpwzOz"

st.sidebar.title("🔍 Фильтры поиска")

# Поля для ввода
region = st.sidebar.text_input("Регион (код)", "77")
okved = st.sidebar.text_input("ОКВЭД", "62.01")
status = st.sidebar.selectbox("Статус", ["Действующая", "Все"])

if st.sidebar.button("Найти компании"):
    # Исправляем формат: API ждет список в формате ["77"]
    search_url = "https://ofdata.ru/api/search"
    params = {
        "key": API_KEY,
        "region": [region],
        "okved": [okved],
        "status": [status],
        "count": 100
    }
    
    with st.spinner('Связываемся с базой данных Ofdata...'):
        try:
            # Делаем POST запрос (он надежнее для списков)
            response = requests.post(search_url, json=params)
            data_json = response.json()
            
            if data_json.get("data"):
                df = pd.DataFrame(data_json["data"])
                st.session_state['found_companies'] = df
                st.success(f"Успех! Найдено {len(df)} компаний")
            else:
                error_msg = data_json.get("error", {}).get("message", "Компании не найдены")
                st.warning(f"Ofdata говорит: {error_msg}")
        except Exception as e:
            st.error(f"Ошибка соединения: {e}")

# Отображение таблицы
if 'found_companies' in st.session_state:
    df = st.session_state['found_companies']
    st.subheader("📋 Предварительный список")
    st.dataframe(df, use_container_width=True)

    if st.button("🚀 Обогатить данные (Директор, Финансы)"):
        enriched_data = []
        progress_bar = st.progress(0)
        
        inns = df['inn'].tolist()
        for i, inn in enumerate(inns):
            try:
                comp_url = f"https://ofdata.ru/api/company?key={API_KEY}&inn={inn}"
                res = requests.get(comp_url).json()
                
                if "data" in res:
                    c = res["data"]
                    enriched_data.append({
                        "Название": c.get("full_name", "Нет данных"),
                        "ИНН": c.get("inn"),
                        "Директор": c.get("management", {}).get("name", "Не указан"),
                        "Выручка (тыс. руб)": c.get("finance", {}).get("revenue", 0),
                        "Сотрудники": c.get("staff_count", "Н/Д"),
                        "КПП": c.get("kpp")
                    })
            except:
                continue
            
            progress_bar.progress((i + 1) / len(inns))
            time.sleep(0.05) # Пауза, чтобы API не заблокировал

        final_df = pd.DataFrame(enriched_data)
        st.subheader("💎 Финальная база для CRM")
        st.dataframe(final_df, use_container_width=True)
        
        csv = final_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Скачать таблицу (CSV)", data=csv, file_name="growthloop_leads.csv")
