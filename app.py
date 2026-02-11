import streamlit as st
import pandas as pd
import requests
import time

# Настройки страницы
st.set_page_config(layout="wide", page_title="Data Outreach Engine")

API_KEY = "4ag8CvRHFhXpwzOz"

st.sidebar.title("🔍 Фильтры поиска")

# Поля для ввода (Фильтры)
region = st.sidebar.text_input("Регион (код, например 77)", "")
okved = st.sidebar.text_input("ОКВЭД (например 62.01)", "")
status = st.sidebar.selectbox("Статус", ["Действующая", "Все"])

# Кнопка поиска
if st.sidebar.button("Найти компании"):
    # Запрос к API Search
    search_url = f"https://ofdata.ru/api/search?key={API_KEY}&region={region}&okved={okved}&count=100"
    
    with st.spinner('Ищем компании...'):
        response = requests.get(search_url).json()
        
        if "data" in response:
            df = pd.DataFrame(response["data"])
            st.session_state['found_companies'] = df
            st.success(f"Найдено {len(df)} компаний (превью)")
        else:
            st.error("Ничего не найдено или ошибка API")

# Если компании найдены, показываем таблицу
if 'found_companies' in st.session_state:
    df = st.session_state['found_companies']
    st.subheader("📋 Результаты поиска (Превью)")
    st.dataframe(df)

    # Кнопка глубокого обогащения
    if st.button("🚀 Обогатить данные (Директор, Финансы, Контакты)"):
        enriched_data = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        inns = df['inn'].tolist()
        total = len(inns)

        for i, inn in enumerate(inns):
            # Запрос к API Company
            comp_url = f"https://ofdata.ru/api/company?key={API_KEY}&inn={inn}"
            res = requests.get(comp_url).json()
            
            if "data" in res:
                # Вытаскиваем только самое сочное
                data = res["data"]
                enriched_data.append({
                    "Название": data.get("full_name"),
                    "ИНН": data.get("inn"),
                    "Директор": data.get("management", {}).get("name"),
                    "Выручка": data.get("finance", {}).get("revenue"),
                    "Сотрудники": data.get("staff_count"),
                })
            
            # Обновляем прогресс
            progress = (i + 1) / total
            progress_bar.progress(progress)
            status_text.text(f"Обработано {i+1} из {total}")
            time.sleep(0.1) # Небольшая пауза для API

        final_df = pd.DataFrame(enriched_data)
        st.subheader("💎 Обогащенные данные (Clay Style)")
        st.dataframe(final_df)
        
        # Кнопка скачивания
        csv = final_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("Скачать таблицу в Excel/CSV", data=csv, file_name="leads.csv")
