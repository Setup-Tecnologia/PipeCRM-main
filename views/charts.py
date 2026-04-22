import flet as ft
import matplotlib

# Matplotlib em modo headless (Windows + Flet Desktop).
# Importante: definir backend ANTES de importar pyplot.
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from utils import MatplotlibChart

def criar_graficos_view(df_user):
    # Função helper para criar cards de gráficos
    def grafico_card(titulo, fig):
        return ft.Container(
            content=ft.Column([
                ft.Text(titulo, size=16, weight="bold", color=ft.Colors.AMBER),
                ft.Divider(height=10, color="transparent"),
                ft.Container(content=MatplotlibChart(fig, transparent=True, expand=True), height=300)
            ]),
            bgcolor=ft.Colors.GREY_900,
            border_radius=15,
            padding=20,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK)),
            margin=ft.margin.only(bottom=15)
        )

    # Gráfico 1: Barras (Etapas)
    fig1, ax1 = plt.subplots(figsize=(6, 4))
    fig1.patch.set_alpha(0)
    ax1.set_facecolor('#212121')
    
    if 'Negócio - Etapa' in df_user.columns:
        d_etapa = df_user['Negócio - Etapa'].value_counts().head(6)
        ax1.barh(d_etapa.index, d_etapa.values, color='#ffca28')
        ax1.set_xlabel('Qtd Clientes', color='white')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.spines['bottom'].set_color('#555555')
        ax1.spines['left'].set_color('#555555')
        ax1.tick_params(axis='x', colors='#cccccc')
        ax1.tick_params(axis='y', colors='#cccccc')
    else:
        ax1.text(0.5, 0.5, 'Sem dados', ha='center', color='white')

    # Gráfico 2: Pizza (Status Sittax)
    fig2, ax2 = plt.subplots(figsize=(6, 4))
    fig2.patch.set_alpha(0)
    
    if 'Status' in df_user.columns:
        d_status = df_user['Status'].value_counts()
        cores = ['#66bb6a', '#ef5350', '#bdbdbd', '#ffa726'] 
        wedges, texts, autotexts = ax2.pie(
            d_status.values, labels=d_status.index, autopct='%1.1f%%', 
            startangle=90, colors=cores, pctdistance=0.85
        )
        centre_circle = plt.Circle((0,0),0.70,fc='#212121')
        fig2.gca().add_artist(centre_circle)
        plt.setp(autotexts, size=9, weight="bold", color="black")
        plt.setp(texts, size=10, color="#cccccc")
    else:
        ax2.text(0.5, 0.5, 'Sem dados', ha='center', color='white')

    return ft.ListView([
        ft.Text("Visão Geral da Carteira", size=20, weight="bold", color=ft.Colors.WHITE),
        ft.Text("Indicadores de performance e saúde", size=12, color=ft.Colors.GREY_400, italic=True),
        ft.Divider(height=20, color="transparent"),
        grafico_card("Distribuição do Funil (Etapas)", fig1),
        grafico_card("Saúde Financeira (Status Sittax)", fig2)
    ], padding=20, expand=True)
