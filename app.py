import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(layout="wide", page_title="GrowthLoop Engine: Hybrid Pro")

# Ключи
FNS_API_KEY = "8f1364cd9916da3ba62170204442a80566bc5f29"
OFDATA_API_KEY = "4ag8CvRHFhXpwzOz" # Твой предыдущий ключ Ofdata

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def clean_val(val):
    if isinstance(val, list):
        if not val: return ""
        if isinstance(val[0], str): return ", ".join(val)
        if isinstance(val[0], dict):
            return "; ".join([" | ".join([f"{k}: {v}" for k, v in i.items() if v]) for i in val])
    return val

# --- ИНТЕРФЕЙС САЙДБАРА ---
st.sidebar.title("🚀 Гибридный поиск")

okved = st.sidebar.text_input("ОКВЭД (группа или код)", "62.01")
region = st.sidebar.text_input("Регион (код)", "77")

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Финансовые фильтры")
rev_min = st.sidebar.number_input("Выручка от (млн руб.)", 0)
rev_max = st.sidebar.number_input("Выручка до (млн руб.)", 0)

st.sidebar.subheader("👥 Команда")
staff_min = st.sidebar.number_input("Сотрудников от", 0)
staff_max = st.sidebar.number_input("Сотрудников до", 0)

# --- ЛОГИКА ПОИСКА (FNS API) ---
if st.sidebar.button("Найти цели"):
    # Формируем строку фильтра для ФНС API
    filter_parts = ["active", "onlyul"] # Только действующие ЮЛ
    
    if okved: filter_parts.append(f"okvedgroup{okved}")
    if region: filter_parts.append(f"region{region}")
    
    # Конвертируем млн в тысячи для API (API ждет vyruchka>5000 для 5млн)
    if rev_min or rev_max:
        v_str = "vyruchka"
        if rev_min: v_str += f">{rev_min * 1000}"
        if rev_max: v_str += f"<{rev_max * 1000}"
        filter_parts.append(v_str)
        
    if staff_min or staff_max:
        s_str = "sotrudnikov"
        if staff_min: s_str += f">{staff_min}"
        if staff_max: s_str += f"<{staff_max}"
        filter_parts.append(s_str)

    filter_final = "+".join(filter_parts)
    
    params = {
        "q": "any",
        "filter": filter_final,
        "key": FNS_API_KEY
    }

    with st.spinner('ФНС API подбирает компании по фильтрам...'):
        try:
            r = requests.get("https://api-fns.ru/api/search", params=params)
            res_data = r.json()
            
            if "items" in res_data and res_data["items"]:
                df = pd.DataFrame(res_data["items"])
                df.insert(0, "Выбрать", False)
                # Маппинг колонок для удобства
                rename_map = {"НаимСокрЮЛ": "Название", "ИНН": "ИНН", "АдресПолн": "Адрес", "ОснВидДеят": "ОКВЭД"}
                df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
                st.session_state['search_results'] = df
            else:
                st.warning("По таким фильтрам ничего не найдено.")
        except Exception as e:
            st.error(f"Ошибка поиска: {e}")

# --- ОТОБРАЖЕНИЕ И ОБОГАЩЕНИЕ (OFDATA) ---
if 'search_results' in st.session_state:
    st.subheader("📋 Шаг 1: Выберите компании из фильтрованного списка")
    
    edited_df = st.data_editor(
        st.session_state['search_results'],
        column_config={"Выбрать": st.column_config.CheckboxColumn("Выбрать")},
        disabled=[c for c in st.session_state['search_results'].columns if c != "Выбрать"],
        hide_index=True, use_container_width=True
    )

    selected = edited_df[edited_df["Выбрать"] == True]
    
    if not selected.empty:
        st.write(f"✅ Выбрано для сбора контактов: **{len(selected)}**")
        
        if st.button("🚀 Собрать контакты и детали (через Ofdata)"):
            enriched = []
            bar = st.progress(0)
            inns = selected['ИНН'].tolist()
            
            for i, inn in enumerate(inns):
                try:
                    # Запрос к Ofdata за контактами
                    res = requests.get(f"https://api.ofdata.ru/v2/company", 
                                     params={"key": OFDATA_API_KEY, "inn": inn}).json()
                    if "data" in res:
                        enriched.append(res["data"])
                    time.sleep(0.15)
                except: pass
                bar.progress((i + 1) / len(inns))
            
            if enriched:
                final_df = pd.json_normalize(enriched)
                for col in final_df.columns:
                    final_df[col] = final_df[col].apply(clean_val)
                
                st.subheader("💎 Финальная база с контактами")
                st.dataframe(final_df, use_container_width=True)
                
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Скачать готовую базу (CSV)", csv, "enriched_leads.csv")
