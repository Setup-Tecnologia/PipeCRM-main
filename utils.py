import flet as ft
import pandas as pd
import io
from typing import Optional

def clean_cnpj(v): 
    if pd.isna(v) or str(v).strip() == "": return ""
    s = str(v).strip()
    if s.endswith('.0'): s = s[:-2]
    s = ''.join(filter(str.isdigit, s))
    
    if 12 <= len(s) <= 14:
        s = s.zfill(14)
    elif 1 <= len(s) <= 11:
        s = s.zfill(11)
    return s

def clean_curr(v):
    if pd.isna(v): return 0.0
    v = str(v).replace(' BRL','').replace(' R$','').strip().replace('.','').replace(',','.')
    try: return float(v)
    except: return 0.0

def format_document(v):
    v = str(v)
    if len(v) == 14: # CNPJ
        return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}"
    elif len(v) == 11: # CPF
        return f"{v[:3]}.{v[3:6]}.{v[6:9]}-{v[9:]}"
    return v

def copiar_texto(e, page: ft.Page, label="Texto"):
    val = e.control.data
    page.set_clipboard(val)
    # Flet 0.84+: SnackBar é um DialogControl e deve ser aberto via show_dialog().
    page.show_dialog(ft.SnackBar(ft.Text(f"{label} copiado!")))

def criar_linha_copia(label, valor, icon, page, valor_limpo=None):
    if(label == 'CNPJ'):
        valor_limpo = format_document(valor)
    texto_copia = valor_limpo if valor_limpo is not None else valor
    return ft.Row([
        ft.Icon(icon, size=18, color=ft.Colors.AMBER),
        ft.Text(f"{label}: ", weight="w600", size=13, color=ft.Colors.GREY_400),
        ft.Text(valor, size=14, weight="bold", color=ft.Colors.WHITE, selectable=True, expand=True),
        ft.IconButton(ft.Icons.COPY, icon_size=16, icon_color=ft.Colors.AMBER_200, 
                    tooltip="Copiar", data=texto_copia, 
                    on_click=lambda e: copiar_texto(e, page, label))
    ], alignment="start", vertical_alignment="center", spacing=5)


# -----------------------------------------------------------------------------
# Compatibilidade Flet 0.84+
# - O antigo `flet.matplotlib_chart.MatplotlibChart` não existe mais.
# - Para manter a lógica do app, renderizamos o `matplotlib.figure.Figure`
#   para PNG em memória e exibimos com `ft.Image(src=bytes)`.
# -----------------------------------------------------------------------------
def MatplotlibChart(fig, transparent: bool = True, expand: Optional[bool] = True) -> ft.Image:
    """
    Substituto drop-in do antigo MatplotlibChart do Flet.

    Args:
        fig: matplotlib Figure
        transparent: mantém fundo transparente quando possível
        expand: repassa para o controle Image
    """
    buf = io.BytesIO()
    # bbox_inches="tight" para evitar cortes e melhorar encaixe no layout
    fig.savefig(buf, format="png", dpi=150, transparent=transparent, bbox_inches="tight")
    buf.seek(0)

    # Fecha a figura para evitar vazamento de memória ao trocar telas/atualizar.
    try:
        import matplotlib.pyplot as plt

        plt.close(fig)
    except Exception:
        pass

    return ft.Image(src=buf.getvalue(), fit=ft.BoxFit.CONTAIN, expand=expand)
