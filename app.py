import streamlit as st
import pandas as pd
import requests
import time

# Настройка страницы
st.set_page_config(layout="wide", page_title="GrowthLoop Engine - Full Data")

API_KEY = "4ag8CvRHFhXpwzOz"
BASE_URL = "https://api.ofdata.ru/v2"

# Функция для превращения сложных списков/словарей в читаемый текст
def clean_list_columns(val):
    if isinstance(val, list):
        if not val:
            return ""
        # Если это простой список строк (например, Телефоны или Email)
        if isinstance(val[0], str):
            return ", ".join(val)
        # Если это список словарей (Налоги, Руководители, Учредители)
        if isinstance(val[0], dict):
            readable_items = []
            for item in val:
                # Собираем все ключи и значения в строку: "Наим: НДС | Сумма: 100"
                pairs = [f"{k}: {v}" for k, v in item.items() if v is not None]
                readable_items.append(" | ".join(pairs))
            return "; ".join(readable_items)
    return val

st.sidebar.title("🎯 Поиск компаний")
okved_query = st.sidebar.text_input("Код ОКВЭД (основной)", "63.11")
region_code = st.sidebar.text_input("Код региона (например, 77)", "77")

# Шаг 1: Поиск
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
    
    with st.spinner('Поиск в реестре...'):
        try:
            response = requests.get(search_url, params=params)
            res_data = response.json()
            if "data" in res_data and "Записи" in res_data["data"]:
                found_list = res_data["data"]["Записи"]
                df = pd.DataFrame(found_list)
                # Добавляем колонку выбора в начало
                df.insert(0, "Выбрать", False) 
                df = df.rename(columns={"НаимСокр": "Название", "ИНН": "ИНН", "ЮрАдрес": "Адрес"})
                st.session_state['found_companies'] = df
            else:
                error_msg = res_data.get("meta", {}).get("message", "Ничего не найдено")
                st.error(f"Ошибка: {error_msg}")
        except Exception as e:
            st.error(f"Ошибка соединения: {e}")

# Шаг 2: Выбор и Обогащение
if 'found_companies' in st.session_state:
    st.subheader("📋 Шаг 1: Выберите компании для полного сбора данных")
    
    # Интерактивная таблица с чекбоксами
    edited_df = st.data_editor(
        st.session_state['found_companies'],
        column_config={
            "Выбрать": st.column_config.CheckboxColumn("Выбрать", default=False)
        },
        disabled=st.session_state['found_companies'].columns.drop("Выбрать"),
        hide_index=True,
        use_container_width=True
    )

    selected_rows = edited_df[edited_df["Выбрать"] == True]
    st.write(f"✅ Выбрано компаний: **{len(selected_rows)}**")

    if st.button("🚀 Собрать ВСЕ данные по выбранным"):
        if len(selected_rows) == 0:
            st.warning("Пожалуйста, отметьте хотя бы одну компанию галочкой.")
        else:
            all_raw_data = []
            progress = st.progress(0)
            status_text = st.empty()
            inns = selected_rows['ИНН'].tolist()
            
            for i, inn in enumerate(inns):
                status_text.text(f"Загрузка данных по ИНН {inn}...")
                try:
                    # Запрос полной карточки компании
                    res = requests.get(f"{BASE_URL}/company", params={"key": API_KEY, "inn": inn}).json()
                    if "data" in res:
                        all_raw_data.append(res["data"])
                except Exception:
                    continue
                
                progress.progress((i + 1) / len(inns))
                time.sleep(0.1) # Небольшая пауза для стабильности

            if all_raw_data:
                # Превращаем в плоскую таблицу (Налоги.СумУпл и т.д.)
                final_df = pd.json_normalize(all_raw_data)
                
                # Применяем «умную» очистку ко всем колонкам, чтобы убрать [object Object]
                for col in final_df.columns:
                    final_df[col] = final_df[col].apply(clean_list_columns)
                
                st.subheader("💎 Полная обогащенная база")
                st.dataframe(final_df, use_container_width=True)
                
                # Кнопка скачивания
                csv_data = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 Скачать полный результат (CSV)",
                    data=csv_data,
                    file_name="growthloop_full_export.csv",
                    mime="text/csv"
                )
            else:
                st.error("Не удалось получить детальную информацию.")
