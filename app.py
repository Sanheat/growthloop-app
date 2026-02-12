import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(layout="wide", page_title="GrowthLoop Hybrid Pro v2.5")

# Ключи
FNS_API_KEY = "8f1364cd9916da3ba62170204442a80566bc5f29"
OFDATA_API_KEY = "4ag8CvRHFhXpwzOz"

def clean_val(val):
    if isinstance(val, list):
        if not val: return ""
        if isinstance(val[0], str): return ", ".join(val)
        if isinstance(val[0], dict):
            return "; ".join([" | ".join([f"{k}: {v}" for k, v in i.items() if v]) for i in val])
    return val

# --- САЙДБАР ---
st.sidebar.title("🚀 Гибридный поиск")
okved = st.sidebar.text_input("ОКВЭД (группа или код)", "62.01")
region = st.sidebar.text_input("Регион (код)", "77")

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Финансовые фильтры")
rev_min = st.sidebar.number_input("Выручка от (млн руб.)", 0)
rev_max = st.sidebar.number_input("Выручка до (млн руб.)", 0)
staff_min = st.sidebar.number_input("Сотрудников от", 0)

if st.sidebar.button("Найти цели"):
    # 1. Формируем фильтр строго по документации
    filter_parts = ["active", "onlyul"]
    if okved: filter_parts.append(f"okvedgroup{okved}")
    if region: filter_parts.append(f"region{region}")
    
    if rev_min > 0 or rev_max > 0:
        v_str = "vyruchka"
        if rev_min > 0: v_str += f">{rev_min * 1000}" # в тыс. руб.
        if rev_max > 0: v_str += f"<{rev_max * 1000}"
        filter_parts.append(v_str)
        
    if staff_min > 0:
        filter_parts.append(f"sotrudnikov>{staff_min}")

    filter_final = "+".join(filter_parts)
    
    # 2. Ручное формирование URL (защита от перекодирования символов requests-ом)
    # Это критически важно для API-FNS
    search_url = f"https://api-fns.ru/api/search?q=any&filter={filter_final}&key={FNS_API_KEY}"

    with st.spinner('Запрос к ФНС API...'):
        try:
            r = requests.get(search_url)
            
            # Если сервер вернул не 200 OK
            if r.status_code != 200:
                st.error(f"Сервер вернул ошибку {r.status_code}. Текст: {r.text}")
            else:
                try:
                    res_data = r.json()
                    if "items" in res_data and res_data["items"]:
                        df = pd.DataFrame(res_data["items"])
                        df.insert(0, "Выбрать", False)
                        rename_map = {"НаимСокрЮЛ": "Название", "ИНН": "ИНН", "АдресПолн": "Адрес"}
                        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
                        st.session_state['search_results'] = df
                    else:
                        st.warning("Компании не найдены. Попробуйте уменьшить фильтры (например, выручку).")
                        # Показываем сырой ответ для диагностики, если пусто
                        with st.expander("Технический ответ сервера"):
                            st.write(res_data)
                except Exception as json_err:
                    st.error("Ошибка чтения данных. Похоже, API прислал не таблицу, а текст.")
                    with st.expander("Посмотреть, что прислал сервер"):
                        st.code(r.text)
        except Exception as e:
            st.error(f"Ошибка соединения: {e}")

# --- ВТОРОЙ ШАГ: OFDATA ---
if 'search_results' in st.session_state:
    st.subheader("📋 Найденные компании")
    res_df = st.session_state['search_results']
    
    edited_df = st.data_editor(
        res_df,
        column_config={"Выбрать": st.column_config.CheckboxColumn("Выбрать")},
        disabled=[c for c in res_df.columns if c != "Выбрать"],
        hide_index=True, use_container_width=True
    )

    selected = edited_df[edited_df["Выбрать"] == True]
    
    if st.button(f"🚀 Обогатить контактами ({len(selected)})"):
        if selected.empty:
            st.info("Отметьте нужные компании в таблице выше.")
        else:
            enriched = []
            bar = st.progress(0)
            inns = selected['ИНН'].tolist()
            
            for i, inn in enumerate(inns):
                try:
                    res = requests.get(f"https://api.ofdata.ru/v2/company", 
                                     params={"key": OFDATA_API_KEY, "inn": inn}).json()
                    if "data" in res:
                        enriched.append(res["data"])
                    time.sleep(0.1)
                except: pass
                bar.progress((i + 1) / len(inns))
            
            if enriched:
                final_df = pd.json_normalize(enriched)
                for col in final_df.columns:
                    final_df[col] = final_df[col].apply(clean_val)
                st.subheader("💎 Результат с контактами")
                st.dataframe(final_df, use_container_width=True)
                st.download_button("📥 Скачать CSV", final_df.to_csv(index=False).encode('utf-8-sig'), "leads.csv")
