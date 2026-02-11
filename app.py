import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(layout="wide", page_title="GrowthLoop Engine")

API_KEY = "4ag8CvRHFhXpwzOz"
BASE_URL = "https://api.ofdata.ru/v2"

st.sidebar.title("🎯 Фильтры поиска")

# Согласно документации /search:
# Для поиска по ОКВЭД параметр 'by' должен быть 'okved'
okved_query = st.sidebar.text_input("Введите код ОКВЭД", "63.11")
region_code = st.sidebar.text_input("Код региона (2 цифры)", "77")
only_active = st.sidebar.checkbox("Только активные", value=True)

if st.sidebar.button("Найти компании"):
    # Формируем запрос согласно документации v2/search
    search_url = f"{BASE_URL}/search"
    params = {
        "key": API_KEY,
        "by": "okved",
        "obj": "org",
        "query": okved_query,
        "region": region_code,
        "active": "true" if only_active else "false",
        "limit": 100
    }
    
    with st.spinner('Поиск в реестрах...'):
        try:
            response = requests.get(search_url, params=params)
            res_data = response.json()
            
            # В документации записи лежат в data -> Записи
            if "data" in res_data and "Записи" in res_data["data"]:
                found_list = res_data["data"]["Записи"]
                if found_list:
                    # Создаем таблицу с человеческими названиями колонок
                    df = pd.DataFrame(found_list)
                    # Переименуем для удобства
                    rename_map = {
                        "НаимСокр": "Название",
                        "ИНН": "ИНН",
                        "ЮрАдрес": "Адрес",
                        "Статус": "Статус"
                    }
                    df = df.rename(columns=rename_map)
                    st.session_state['found_companies'] = df
                    st.success(f"Найдено {len(df)} компаний")
                else:
                    st.warning("По вашему запросу ничего не найдено.")
            else:
                error_info = res_data.get("meta", {}).get("message", "Неизвестная ошибка")
                st.error(f"Ошибка API: {error_info}")
        except Exception as e:
            st.error(f"Ошибка соединения: {e}")

# Отображение результатов
if 'found_companies' in st.session_state:
    df = st.session_state['found_companies']
    st.subheader("📋 Предварительный список (из поиска)")
    st.dataframe(df[["Название", "ИНН", "Адрес", "Статус"]], use_container_width=True)

    if st.button("🚀 Обогатить данные (Clay Style)"):
        enriched = []
        progress = st.progress(0)
        status_text = st.empty()
        
        inns = df['ИНН'].tolist()
        for i, inn in enumerate(inns):
            status_text.text(f"Обогащаем {i+1} из {len(inns)}: ИНН {inn}")
            try:
                # Согласно документации v2/company
                comp_url = f"{BASE_URL}/company"
                res = requests.get(comp_url, params={"key": API_KEY, "inn": inn}).json()
                
                if "data" in res:
                    c = res["data"]
                    # Собираем данные по структуре из документации
                    # ФИО руководителя лежит в массиве Руковод
                    manager = c.get("Руковод", [{}])[0].get("ФИО", "Не указан")
                    
                    enriched.append({
                        "Компания": c.get("НаимПолн"),
                        "ИНН": c.get("ИНН"),
                        "Директор": manager,
                        "Сотрудников (СЧР)": c.get("СЧР", "Н/Д"),
                        "Выручка (Налоги)": c.get("Налоги", {}).get("СумУпл", "Н/Д"),
                        "Телефон": c.get("Контакты", {}).get("Тел", ["-"])[0],
                        "Email": c.get("Контакты", {}).get("Емэйл", ["-"])[0],
                        "Сайт": c.get("Контакты", {}).get("ВебСайт", "-")
                    })
            except:
                continue
            
            progress.progress((i + 1) / len(inns))
            time.sleep(0.1) # Чтобы не превысить лимиты API

        final_df = pd.DataFrame(enriched)
        st.subheader("💎 Обогащенная база данных")
        st.dataframe(final_df, use_container_width=True)
        
        csv = final_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Скачать результат в CSV", csv, "growthloop_data.csv", "text/csv")
