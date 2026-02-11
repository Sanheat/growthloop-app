import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(layout="wide", page_title="GrowthLoop Engine")

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
                
                # ДОБАВЛЯЕМ КОЛОНКУ ДЛЯ ВЫБОРА
                df.insert(0, "Выбрать", False) 
                
                df = df.rename(columns={"НаимСокр": "Название", "ИНН": "ИНН", "ЮрАдрес": "Адрес"})
                st.session_state['found_companies'] = df
            else:
                st.error("Ничего не найдено")
        except Exception as e:
            st.error(f"Ошибка: {e}")

# ИНТЕРФЕЙС ВЫБОРА
if 'found_companies' in st.session_state:
    st.subheader("📋 Шаг 1: Выберите компании для обогащения")
    
    # Используем data_editor, чтобы пользователь мог ставить галочки
    edited_df = st.data_editor(
        st.session_state['found_companies'],
        column_config={
            "Выбрать": st.column_config.CheckboxColumn(
                "Выбрать",
                help="Отметьте компании для сбора контактов",
                default=False,
            )
        },
        disabled=["Название", "ИНН", "Адрес", "Статус", "КПП", "ОГРН", "ДатаРег", "РегионКод", "ОКВЭД"],
        hide_index=True,
        use_container_width=True
    )

    # Фильтруем: только те, где стоит галочка
    selected_rows = edited_df[edited_df["Выбрать"] == True]
    
    st.write(f"✅ Выбрано компаний: **{len(selected_rows)}**")

    if st.button("🚀 Обогатить выбранные"):
        if len(selected_rows) == 0:
            st.warning("Сначала выберите хотя бы одну компанию (поставьте галочку)")
        else:
            enriched = []
            progress = st.progress(0)
            inns = selected_rows['ИНН'].tolist()
            
            for i, inn in enumerate(inns):
                try:
                    res = requests.get(f"{BASE_URL}/company", params={"key": API_KEY, "inn": inn}).json()
                    if "data" in res:
                        c = res["data"]
                        manager = c.get("Руковод", [{}])[0].get("ФИО", "Не указан")
                        enriched.append({
                            "Компания": c.get("НаимПолн"),
                            "ИНН": c.get("ИНН"),
                            "Директор": manager,
                            "Сотрудники": c.get("СЧР", "Н/Д"),
                            "Выручка": c.get("Налоги", {}).get("СумУпл", "Н/Д"),
                            "Телефон": c.get("Контакты", {}).get("Тел", ["-"])[0],
                            "Email": c.get("Контакты", {}).get("Емэйл", ["-"])[0]
                        })
                except:
                    continue
                progress.progress((i + 1) / len(inns))
                time.sleep(0.1)

            final_df = pd.DataFrame(enriched)
            st.subheader("💎 Результат обогащения")
            st.dataframe(final_df, use_container_width=True)
            st.download_button("📥 Скачать CSV", final_df.to_csv(index=False).encode('utf-8-sig'), "selected_leads.csv")
