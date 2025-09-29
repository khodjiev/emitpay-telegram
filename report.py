import pandas as pd
from pathlib import Path
from typing import List, Tuple
import datetime as dt

def make_report_xlsx(rows: List[Tuple], out_dir: Path, user_id: int, start: dt.date, end: dt.date) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=['kind','category','amount','created_at'])
    if df.empty:
        file_path = out_dir / f'report_{user_id}_{start}_{end}.xlsx'
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            empty = pd.DataFrame(columns=['kind','category','amount','created_at'])
            empty.to_excel(writer, index=False, sheet_name='records')
        return file_path

    df['created_at'] = pd.to_datetime(df['created_at'])
    pivot = df.pivot_table(index=['kind','category'], values='amount', aggfunc='sum').reset_index()
    total_income = float(df.loc[df['kind']=='income','amount'].sum())
    total_expense = float(df.loc[df['kind']=='expense','amount'].sum())
    balance = total_income - total_expense

    file_path = out_dir / f'report_{user_id}_{start}_{end}.xlsx'
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        df.sort_values('created_at').to_excel(writer, index=False, sheet_name='records')
        pivot.sort_values(['kind','category']).to_excel(writer, index=False, sheet_name='by_category')
        summary = pd.DataFrame([
            {'metric':'Доход', 'value': total_income},
            {'metric':'Расход', 'value': total_expense},
            {'metric':'Баланс', 'value': balance},
        ])
        summary.to_excel(writer, index=False, sheet_name='summary')
    return file_path

def make_text_summary(rows: List[Tuple]) -> str:
    if not rows:
        return "За выбранный период записей не найдено."
    import pandas as pd
    df = pd.DataFrame(rows, columns=['kind','category','amount','created_at'])
    total_income = float(df.loc[df['kind']=='income','amount'].sum())
    total_expense = float(df.loc[df['kind']=='expense','amount'].sum())
    balance = total_income - total_expense

    by_cat = df.groupby(['kind','category'])['amount'].sum().reset_index()
    lines = ["📊 *Отчёт по категории:*"]
    for _, r in by_cat.sort_values(['kind','category']).iterrows():
        emoji = "➕" if r['kind']=='income' else "➖"
        lines.append(f"{emoji} {r['kind']}: {r['category']} — {r['amount']:.2f}")
    lines.append("")
    lines.append(f"💰 Доход: *{total_income:.2f}*")
    lines.append(f"💸 Расход: *{total_expense:.2f}*")
    b_emoji = "✅" if balance >= 0 else "⚠️"
    lines.append(f"{b_emoji} Баланс: *{balance:.2f}*")
    return "\n".join(lines)
