import flet as ft
from utils import format_document, criar_linha_copia, copiar_texto
from views.charts import criar_graficos_view
from views.details import show_details_dialog

def tela_painel(page: ft.Page, user, dados, on_logout):
    page.clean()
    
    # Filtra dados do usuário
    df_user = dados["df"][dados["df"]['Dono'] == user].copy()

    # --- ABA 1: LISTA & FILTROS ---
    lv_lista = ft.ListView(expand=True, spacing=8, padding=10)
    
    # Filtros Inputs
    txt_busca = ft.TextField(
        label="Buscar (Nome ou CNPJ)", 
        prefix_icon=ft.Icons.SEARCH, 
        expand=True, height=45, 
        text_size=14, bgcolor=ft.Colors.GREY_900, border_radius=8, border_color=ft.Colors.GREY_700
    )
    
    dd_filtro_etapa = ft.Dropdown(
        label="Filtrar por Etapa", 
        options=[ft.dropdown.Option("Todas")] + [ft.dropdown.Option(x) for x in dados["etapas"]], 
        expand=True,
        text_size=13, bgcolor=ft.Colors.GREY_900, border_radius=8, border_color=ft.Colors.GREY_700
    )
    
    # NOVO: Filtro de Dias Flexível
    txt_dias_filtro = ft.TextField(
        label="Dias >", 
        value="0",
        width=80, height=45, 
        text_size=14, bgcolor=ft.Colors.GREY_900, border_radius=8, border_color=ft.Colors.GREY_700,
        keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.CENTER
    )
    
    # NOVO: Texto para mostrar o total
    txt_total = ft.Text("Total: 0", weight="bold", color=ft.Colors.AMBER)

    dd_tipo_data = ft.Dropdown(
        label="Regra de Data",
        options=[
            ft.dropdown.Option("ativ", "Sem Atividade"),
            ft.dropdown.Option("etapa", "Sem Mudar Etapa")
        ],
        value="ativ",
        width=160,
        text_size=13, bgcolor=ft.Colors.GREY_900, border_radius=8, border_color=ft.Colors.GREY_700
    )

    def atualizar_lista(e=None):
        lv_lista.controls.clear()
        res = df_user.copy()
        
        # 1. Filtro Texto
        if txt_busca.value:
            t = txt_busca.value.lower()
            t_clean = ''.join(filter(str.isdigit, t))
            mask = res['Nome'].str.lower().str.contains(t, na=False)
            if t_clean: mask = mask | res['Key'].str.contains(t_clean, na=False)
            res = res[mask]
        
        # 2. Filtro Etapa
        if dd_filtro_etapa.value and dd_filtro_etapa.value != "Todas":
            res = res[res['Negócio - Etapa'] == dd_filtro_etapa.value]
        
        # 3. Filtro Dias (Flexível)
        try:
            dias_corte = int(txt_dias_filtro.value)
        except:
            dias_corte = 0
        
        if dias_corte > 0:
            coluna_filtro = 'Dias_Sem_Ativ' if dd_tipo_data.value == "ativ" else 'Dias_Sem_Etapa'
            # Garante que a coluna existe (se não existir, assume 0)
            if coluna_filtro in res.columns:
                res = res[res[coluna_filtro] > dias_corte]

        # Atualiza o contador no topo
        txt_total.value = f"Total filtrado: {len(res)}"

        # Renderização
        if res.empty:
            lv_lista.controls.append(
                ft.Container(ft.Text("Nenhum resultado com esses filtros.", color=ft.Colors.GREY), alignment=ft.Alignment.CENTER, padding=20)
            )
        else:
            for _, row in res.head(40).iterrows(): # Top 40
                nm = str(row['Nome'])[:35]
                k = str(row['Key'])
                k_fmt = format_document(k) # Formata na lista também
                et = str(row.get('Negócio - Etapa', '-'))
                
                # Novos campos: Estado e Telefone
                uf = str(row.get('Organização - Estado de Endereço', '-'))
                if uf == 'nan': uf = '-'
                
                # Lógica robusta para encontrar telefone na lista
                raw_tel = '-'
                for col_tel in ['Pessoa - Telefone - Celular', 'Pessoa - Telefone', 'Organização - Telefone', 'Telefone']:
                    val = row.get(col_tel)
                    if val and str(val) != 'nan' and str(val).strip():
                        raw_tel = str(val)
                        break

                # Limpa telefone para cópia (apenas números)
                clean_tel = ''.join(filter(str.isdigit, raw_tel))
                
                # Pega os dias baseado na escolha atual para mostrar no card
                if dd_tipo_data.value == "ativ":
                    dias_mostra = int(row.get('Dias_Sem_Ativ', 0))
                    txt_dias = f"{dias_mostra}d s/ ativ."
                else:
                    dias_mostra = int(row.get('Dias_Sem_Etapa', 0))
                    txt_dias = f"{dias_mostra}d na etapa"

                # Cor de alerta se passar do filtro definido (ou 15 padrão)
                limite_visual = dias_corte if dias_corte > 0 else 15
                cor_bola = ft.Colors.RED if dias_mostra > limite_visual else ft.Colors.GREEN
                
                card = ft.Container(
                    content=ft.Row([
                        ft.Container(width=10, height=10, border_radius=5, bgcolor=cor_bola),
                        ft.Column([
                            ft.Text(nm, weight="bold", size=14, color=ft.Colors.WHITE), # Texto Branco
                            # Linha do meio: UF e Telefone com cópia
                            ft.Row([
                                ft.Container(
                                    content=ft.Text(uf, size=11, weight="bold", color=ft.Colors.BLACK),
                                    bgcolor=ft.Colors.AMBER, padding=ft.padding.symmetric(horizontal=6, vertical=2), border_radius=4
                                ),
                                ft.Text(raw_tel, size=12, color=ft.Colors.GREY_400),
                                ft.IconButton(
                                    ft.Icons.COPY, 
                                    icon_size=14, 
                                    icon_color=ft.Colors.AMBER, # Icone Amarelo
                                    tooltip="Copiar apenas números",
                                    data=clean_tel, # Passa o numero limpo
                                    on_click=lambda e: copiar_texto(e, page, "Telefone"),
                                    style=ft.ButtonStyle(padding=0)
                                )
                            ], spacing=5, vertical_alignment="center"),
                            ft.Text(f"{k_fmt} | {et}", size=11, color=ft.Colors.GREY_500)
                        ], expand=True, spacing=2),
                        ft.Container(
                            content=ft.Text(txt_dias, size=11, weight="bold", color=ft.Colors.WHITE),
                            padding=5, bgcolor=ft.Colors.GREY_800, border_radius=5
                        ),
                        ft.IconButton(ft.Icons.VISIBILITY, icon_size=20, icon_color=ft.Colors.AMBER, 
                                    data=k, on_click=lambda e: show_details_dialog(page, e.control.data, df_user))
                    ], alignment="spaceBetween"),
                    padding=ft.padding.symmetric(horizontal=15, vertical=12),
                    bgcolor=ft.Colors.GREY_900, border_radius=10, # Card Escuro
                    shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK))
                )
                lv_lista.controls.append(card)
        page.update()

    # Eventos dos filtros
    txt_busca.on_change = atualizar_lista
    # Flet 0.84+: Dropdown não usa `on_change`; use `on_select`.
    dd_filtro_etapa.on_select = atualizar_lista
    txt_dias_filtro.on_change = atualizar_lista
    dd_tipo_data.on_select = atualizar_lista

    # --- LAYOUT PRINCIPAL ---
    # Flet 0.84+: Tabs mudou. Agora `ft.Tabs` controla um `TabBar` + `TabBarView`.
    tab_lista = ft.Column(
        [
            # Barra de Filtros Fixa
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row([txt_busca, dd_filtro_etapa]),
                        ft.Row(
                            [
                                ft.Text("Filtro de Atraso:", weight="bold", color=ft.Colors.GREY_300),
                                txt_dias_filtro,
                                ft.Text("dias em", size=12, color=ft.Colors.GREY_400),
                                dd_tipo_data,
                                ft.VerticalDivider(width=20, color=ft.Colors.GREY_800),
                                txt_total,  # Adicionado aqui
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                        ),
                    ],
                    spacing=10,
                ),
                bgcolor=ft.Colors.GREY_900,
                padding=15,  # Fundo Filtros
                border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.GREY_800)),
            ),
            # Lista Rolável
            lv_lista,
        ],
        expand=True,
        spacing=0,
    )

    tab_graficos = criar_graficos_view(df_user)

    tab_bar = ft.TabBar(
        tabs=[
            ft.Tab(label="Lista & Ações", icon=ft.Icons.LIST_ALT_ROUNDED),
            ft.Tab(label="Dashboard Gráfico", icon=ft.Icons.INSERT_CHART_OUTLINED),
        ],
        scrollable=False,
        indicator_color=ft.Colors.AMBER,  # Indicador Amarelo
        label_color=ft.Colors.AMBER,  # Texto Ativo Amarelo
        unselected_label_color=ft.Colors.GREY_400,
        divider_color=ft.Colors.GREY_800,
    )

    tab_view = ft.TabBarView(controls=[tab_lista, tab_graficos], expand=True)

    tabs = ft.Tabs(
        content=ft.Column([tab_bar, tab_view], expand=True, spacing=0),
        length=2,
        selected_index=0,
        animation_duration=300,
        expand=True,
    )

    # Header Superior
    header = ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text(f"Olá, {user.split('|')[0].strip()}", size=20, weight="bold", color=ft.Colors.AMBER),
                ft.Text("Performance e Gestão", size=12, color=ft.Colors.GREY_400)
            ], spacing=2),
            ft.IconButton(ft.Icons.LOGOUT_ROUNDED, icon_color=ft.Colors.AMBER, tooltip="Sair", 
                        on_click=lambda e: on_logout())
        ], alignment="spaceBetween"),
        bgcolor=ft.Colors.GREY_900, padding=ft.padding.symmetric(horizontal=20, vertical=15),
        shadow=ft.BoxShadow(blur_radius=5, color=ft.Colors.with_opacity(0.5, ft.Colors.BLACK))
    )

    page.add(ft.Column([header, tabs], expand=True, spacing=0))
    atualizar_lista()
