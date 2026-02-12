import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(layout="wide", page_title="GrowthLoop Hybrid v2.7")

# Ключи (проверьте, что они верные)
FNS_API_KEY = "8f1364cd9916da3ba62170204442a80566bc5f29"
OFDATA_API_KEY = "4ag8CvRHFhXpwzOz"

def clean_val(val):
    """Очищает данные от технических символов и красиво склеивает списки."""
    if isinstance(val, (list, dict)):
        if not val: return ""
        if isinstance(val, list) and isinstance(val[0], dict):
            return " | ".join([f"{v}" for d in val for k, v in d.items() if v])
        return str(val)
    return val

st.sidebar.title("🚀 Гибридный поиск")
okved = st.sidebar.text_input("ОКВЭД (группа)", "62")
region = st.sidebar.text_input("Регион (код)", "77")

st.sidebar.subheader("📊 Финансы (млн руб.)")
rev_min = st.sidebar.number_input("Выручка от", 10)
staff_min = st.sidebar.number_input("Сотрудников от", 0)

# --- ШАГ 1: ПОИСК ---
if st.sidebar.button("Найти цели"):
    # Формируем фильтры для API-FNS
    f = f"active+onlyul+okvedgroup{okved}+region{region}+vyruchka>{rev_min*1000}"
    if staff_min > 0: f += f"+sotrudnikov>{staff_min}"
    
    url = f"https://api-fns.ru/api/search?q=any&filter={f}&key={FNS_API_KEY}"

    with st.spinner('Синхронизация с ФНС...'):
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                items = data.get("items", [])
                if items:
                    # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Разворачиваем вложенные объекты в плоскую таблицу
                    df = pd.json_normalize(items)
                    
                    # Чистим названия колонок (убираем префиксы типа 'ЮЛ.', 'ИП.')
                    df.columns = [c.split('.')[-1] for c in df.columns]
                    
                    # Добавляем колонку для выбора
                    df.insert(0, "Выбрать", False)
                    
                    # Сохраняем в сессию
                    st.session_state['results'] = df
                else:
                    st.warning("Компании не найдены. Попробуйте уменьшить фильтр выручки.")
            elif r.status_code == 403:
                st.error(f"🚫 Ошибка 403. Проверьте IP {r.text} в ЛК api-fns.ru")
        except Exception as e:
            st.error(f"Ошибка: {e}")

# --- ШАГ 2: ОТОБРАЖЕНИЕ И ВЫБОР ---
if 'results' in st.session_state:
    st.subheader("📋 Найденные компании (выберите нужные)")
    
    # Отображаем таблицу. Streamlit сам добавит прокрутку, если колонок много.
    edited_df = st.data_editor(
        st.session_state['results'],
        use_container_width=True,
        hide_index=True,
        column_config={"Выбрать": st.column_config.CheckboxColumn("Выбрать", default=False)}
    )

    selected = edited_df[edited_df["Выбрать"] == True]
    
    # --- ШАГ 3: ОБОГАЩЕНИЕ ЧЕРЕЗ OFDATA ---
    if st.button(f"🚀 Обогатить контактами ({len(selected)})"):
        if selected.empty:
            st.warning("Сначала отметьте галочками компании в таблице!")
        else:
            enriched = []
            bar = st.progress(0)
            # Теперь 'ИНН' точно найдется, так как мы развернули таблицу
            inns = selected['ИНН'].tolist()
            
            for i, inn in enumerate(inns):
                try:
                    res = requests.get(f"https://api.ofdata.ru/v2/company?key={OFDATA_API_KEY}&inn={inn}").json()
                    if "data" in res:
                        enriched.append(res["data"])
                    time.sleep(0.1)
                except: pass
                bar.progress((i + 1) / len(inns))
            
            if enriched:
                final_df = pd.json_normalize(enriched)
                # Чистим результат Ofdata от [object Object]
                for col in final_df.columns:
                    final_df[col] = final_df[col].apply(clean_val)
                
                st.subheader("💎 Финальный результат")
                st.dataframe(final_df, use_container_width=True)
                st.download_button("📥 Скачать базу", final_df.to_csv(index=False).encode('utf-8-sig'), "leads.csv")
