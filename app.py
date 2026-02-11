import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(layout="wide", page_title="GrowthLoop Engine - Full Data")

API_KEY = "4ag8CvRHFhXpwzOz"
BASE_URL = "https://api.ofdata.ru/v2"

st.sidebar.title("🎯 Поиск компаний")
okved_query = st.sidebar.text_input("Код ОКВЭД", "63.11")
region_code = st.sidebar.text_input("Код региона", "77")

if st.sidebar.button("Найти компании"):
    search_url = f"{BASE_URL}/search"
    params = {
        "key": API_KEY,
        "by": "okved",
        "obj": "org",
        "query": okved_query,
        "region": region_code,
        "active": "true",
        "limit": 100
    }
    
    with st.spinner('Поиск...'):
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
                st.error("Ничего не найдено")
        except Exception as e:
            st.error(f"Ошибка: {e}")

if 'found_companies' in st.session_state:
    st.subheader("📋 Шаг 1: Выберите компании")
    
    edited_df = st.data_editor(
        st.session_state['found_companies'],
        column_config={
            "Выбрать": st.column_config.CheckboxColumn("Выбрать", default=False)
        },
        disabled=["Название", "ИНН", "Адрес", "Статус", "КПП", "ОГРН", "ДатаРег", "РегионКод", "ОКВЭД"],
        hide_index=True,
        use_container_width=True
    )

    selected_rows = edited_df[edited_df["Выбрать"] == True]
    st.write(f"✅ Выбрано для полного обогащения: **{len(selected_rows)}**")

    if st.button("🚀 Собрать ВСЕ данные по выбранным"):
        if len(selected_rows) == 0:
            st.warning("Выберите хотя бы одну компанию")
        else:
            all_raw_data = []
            progress = st.progress(0)
            inns = selected_rows['ИНН'].tolist()
            
            for i, inn in enumerate(inns):
                try:
                    # Запрашиваем полные данные
                    res = requests.get(f"{BASE_URL}/company", params={"key": API_KEY, "inn": inn}).json()
                    if "data" in res:
                        # Сохраняем весь объект целиком
                        all_raw_data.append(res["data"])
                except:
                    continue
                
                progress.progress((i + 1) / len(inns))
                time.sleep(0.1)

            if all_raw_data:
                # МАГИЯ: превращаем вложенный JSON в плоскую таблицу
                # Каждое поле станет колонкой (например: Контакты.ВебСайт, Налоги.СумУпл и т.д.)
                final_df = pd.json_normalize(all_raw_data)
                
                st.subheader("💎 Полная база данных (Все поля API)")
                
                # Показываем таблицу (в ней будет ОЧЕНЬ много колонок)
                st.dataframe(final_df, use_container_width=True)
                
                # Экспорт
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 Скачать полный отчет (CSV)",
                    data=csv,
                    file_name="full_enriched_data.csv",
                    mime="text/csv"
                )
            else:
                st.error("Не удалось получить данные")
