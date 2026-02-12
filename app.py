def process_contacts(df, col_name, prefix):
    """Разносит список контактов по отдельным нумерованным столбцам."""
    if col_name not in df.columns:
        return df
    
    # Превращаем все в списки, если это строки
    contacts_series = df[col_name].apply(lambda x: x if isinstance(x, list) else [])
    
    # Находим максимальное количество контактов в одной ячейке
    max_len = contacts_series.map(len).max()
    if pd.isna(max_len) or max_len == 0:
        return df.drop(columns=[col_name])

    # Создаем новые столбцы
    new_cols = pd.DataFrame(contacts_series.tolist(), index=df.index)
    new_cols.columns = [f"{prefix} {i+1}" for i in range(new_cols.shape[1])]
    
    # Склеиваем с основным DF и удаляем старую колонку
    return pd.concat([df, new_cols], axis=1).drop(columns=[col_name])

# ... внутри блока 'if enriched:' после pd.json_normalize(enriched) ...

if enriched:
    final_df = pd.json_normalize(enriched)
    
    # 1. Сначала обрабатываем контакты (разносим по столбцам)
    final_df = process_contacts(final_df, 'Контакты.Тел', 'Телефон')
    final_df = process_contacts(final_df, 'Контакты.Емэйл', 'Email')
    
    # 2. Очищаем остальные столбцы (налоги и т.д.) от [object Object]
    for col in final_df.columns:
        final_df[col] = final_df[col].apply(clean_val)
    
    # 3. Убираем лишние точки в заголовках для красоты
    final_df.columns = [c.replace('.', ' ') for c in final_df.columns]
    
    st.subheader("💎 Финальный результат")
    st.dataframe(final_df, use_container_width=True)
    
    csv = final_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 Скачать базу", csv, "leads_pro.csv")
